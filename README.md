# Smart Expense Tracker

A Flask web application that helps students track daily spending, stay within a monthly budget and see where their money goes.

## Features
- User registration and login (passwords stored as hashes)
- Add, edit and delete expenses, with input validation
- Automatic category suggestion from the expense title
- Monthly view, category chart and budget-exceeded alert
- Export all expenses to CSV
- Automated tests for the main features

## Tech Stack
Python, Flask, SQLite, HTML, CSS, Bootstrap, JavaScript (Chart.js), Git

## Run Locally
```bash
git clone https://github.com/-------
cd expense-tracker
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000, create an account and add your first expense.

## Run Tests
```bash
pip install pytest
python -m pytest -q
```

## Project Structure
```
app.py            routes, database logic, validation
templates/        HTML pages (Bootstrap)
test_app.py       automated tests
requirements.txt  dependencies
```

## Requirements Analysis (how I planned it)
| Requirement | Solution |
|---|---|
| Students forget where money goes | Category totals and doughnut chart |
| Overspending | Monthly budget with alert |
| Typing categories is slow | Keyword-based auto-suggestion |
| Data should be portable | CSV export |

## Future Improvements
- Replace keyword rules with an ML text classifier (scikit-learn)
- Deploy on Render or PythonAnywhere
- Add monthly email summary
