# Smart Expense Tracker

A beginner-friendly Flask + SQLite web app with registration/login, hashed passwords, monthly expense filtering, category totals, and add/edit/delete operations. User-specific queries prevent one signed-in user from accessing another user's expenses.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 and register an account. The SQLite database is created automatically.

## Before deployment
Set a strong `FLASK_SECRET_KEY` environment variable, turn off debug mode, add CSRF protection, HTTPS, rate limiting and automated tests. This starter app is for learning/local use, not a production security audit.
