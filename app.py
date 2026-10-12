import os
import sqlite3
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-for-local-development")
DB_PATH = os.environ.get("EXPENSE_DB", "expenses.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER,
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT NOT NULL DEFAULT '',
            expense_date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        """)
        for category in ["Food", "Travel", "Education", "Bills", "Shopping", "Other"]:
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (category,))

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must have 3+ characters and password must have 8+ characters.")
            return render_template("register.html")
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users(username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
            flash("Account created. Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    with get_db() as conn:
        expenses = conn.execute("""
            SELECT e.id, e.amount, e.note, e.expense_date, c.name AS category
            FROM expenses e LEFT JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = ? AND substr(e.expense_date, 1, 7) = ?
            ORDER BY e.expense_date DESC, e.id DESC
        """, (session["user_id"], month)).fetchall()
        categories = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        total = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE user_id = ? AND substr(expense_date, 1, 7) = ?
        """, (session["user_id"], month)).fetchone()[0]
        category_totals = conn.execute("""
            SELECT c.name, SUM(e.amount) AS total
            FROM expenses e JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = ? AND substr(e.expense_date, 1, 7) = ?
            GROUP BY c.name ORDER BY total DESC
        """, (session["user_id"], month)).fetchall()
    return render_template("dashboard.html", expenses=expenses, categories=categories,
                           total=total, month=month, category_totals=category_totals,
                           today=date.today().isoformat())

@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    try:
        amount = float(request.form.get("amount", "0"))
        category_id = int(request.form.get("category_id", "0"))
        expense_date = request.form.get("expense_date", "")
        note = request.form.get("note", "").strip()[:200]
        if amount <= 0:
            raise ValueError
        date.fromisoformat(expense_date)
        with get_db() as conn:
            category = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
            if not category:
                raise ValueError
            conn.execute("""INSERT INTO expenses(user_id, category_id, amount, note, expense_date)
                            VALUES (?, ?, ?, ?, ?)""",
                         (session["user_id"], category_id, amount, note, expense_date))
        flash("Expense added.")
    except (ValueError, TypeError):
        flash("Please enter a valid positive amount, category and date.")
    return redirect(url_for("dashboard"))

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    with get_db() as conn:
        expense = conn.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                               (expense_id, session["user_id"])).fetchone()
        categories = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        if not expense:
            flash("Expense not found.")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            try:
                amount = float(request.form.get("amount", "0"))
                category_id = int(request.form.get("category_id", "0"))
                expense_date = request.form.get("expense_date", "")
                note = request.form.get("note", "").strip()[:200]
                if amount <= 0 or not conn.execute("SELECT id FROM categories WHERE id=?", (category_id,)).fetchone():
                    raise ValueError
                date.fromisoformat(expense_date)
                conn.execute("""UPDATE expenses SET amount=?, category_id=?, note=?, expense_date=?
                                WHERE id=? AND user_id=?""",
                             (amount, category_id, note, expense_date, expense_id, session["user_id"]))
                flash("Expense updated.")
                return redirect(url_for("dashboard"))
            except (ValueError, TypeError):
                flash("Please enter valid values.")
    return render_template("edit.html", expense=expense, categories=categories)

@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?",
                     (expense_id, session["user_id"]))
    flash("Expense deleted.")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
