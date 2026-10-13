import csv
import io
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")
app.config["DATABASE"] = os.environ.get("DATABASE", "expenses.db")

CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Education", "Health", "Entertainment", "Other"]

# Simple keyword rules that suggest a category from the expense title.
KEYWORDS = {
    "Food": ["lunch", "dinner", "breakfast", "pizza", "coffee", "tea", "snack", "canteen", "grocery", "restaurant"],
    "Travel": ["bus", "train", "metro", "uber", "ola", "auto", "petrol", "fuel", "ticket", "cab"],
    "Shopping": ["shirt", "shoes", "amazon", "flipkart", "clothes", "bag", "mall"],
    "Bills": ["recharge", "electricity", "wifi", "internet", "rent", "phone", "water bill"],
    "Education": ["book", "course", "udemy", "fees", "exam", "notes", "stationery", "pen"],
    "Health": ["medicine", "doctor", "hospital", "pharmacy", "gym"],
    "Entertainment": ["movie", "netflix", "game", "spotify", "concert"],
}


def suggest_category(title: str) -> str:
    """Return the best-matching category for a title, or 'Other'."""
    text = title.lower()
    for category, words in KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return "Other"


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            monthly_budget REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            category TEXT NOT NULL,
            spent_on TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_expense_form(form):
    """Validate form input. Returns (data, error)."""
    title = form.get("title", "").strip()
    category = form.get("category", "")
    spent_on = form.get("spent_on", "")
    try:
        amount = float(form.get("amount", ""))
    except ValueError:
        return None, "Amount must be a number."
    if not title:
        return None, "Title is required."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    try:
        date.fromisoformat(spent_on)
    except ValueError:
        return None, "Please enter a valid date."
    if category not in CATEGORIES:
        category = suggest_category(title)  # auto-suggest when not chosen
    return {"title": title, "amount": amount, "category": category, "spent_on": spent_on}, None


# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            flash("Username needs 3+ characters and password 6+ characters.", "danger")
        else:
            try:
                get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (request.form.get("username", "").strip(),)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- expenses ----------
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    rows = db.execute(
        "SELECT * FROM expenses WHERE user_id = ? AND substr(spent_on, 1, 7) = ? ORDER BY spent_on DESC, id DESC",
        (session["user_id"], month),
    ).fetchall()
    totals = db.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? AND substr(spent_on, 1, 7) = ? GROUP BY category",
        (session["user_id"], month),
    ).fetchall()
    budget = db.execute("SELECT monthly_budget FROM users WHERE id = ?", (session["user_id"],)).fetchone()[0]
    spent = sum(r["amount"] for r in rows)
    return render_template(
        "dashboard.html", expenses=rows, month=month, spent=spent, budget=budget,
        over_budget=budget > 0 and spent > budget,
        labels=[t["category"] for t in totals], values=[round(t["total"], 2) for t in totals],
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        data, error = parse_expense_form(request.form)
        if error:
            flash(error, "danger")
        else:
            get_db().execute(
                "INSERT INTO expenses (user_id, title, amount, category, spent_on) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], data["title"], data["amount"], data["category"], data["spent_on"]),
            )
            get_db().commit()
            flash(f"Added to {data['category']}.", "success")
            return redirect(url_for("dashboard"))
    return render_template("form.html", categories=CATEGORIES, expense=None, today=date.today().isoformat())


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session["user_id"])
    ).fetchone()
    if expense is None:
        flash("Expense not found.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data, error = parse_expense_form(request.form)
        if error:
            flash(error, "danger")
        else:
            db.execute(
                "UPDATE expenses SET title=?, amount=?, category=?, spent_on=? WHERE id=? AND user_id=?",
                (data["title"], data["amount"], data["category"], data["spent_on"], expense_id, session["user_id"]),
            )
            db.commit()
            flash("Expense updated.", "success")
            return redirect(url_for("dashboard"))
    return render_template("form.html", categories=CATEGORIES, expense=expense, today=date.today().isoformat())


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    get_db().execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session["user_id"]))
    get_db().commit()
    flash("Expense deleted.", "info")
    return redirect(url_for("dashboard"))


@app.route("/budget", methods=["POST"])
@login_required
def set_budget():
    try:
        value = max(0.0, float(request.form.get("budget", "0")))
    except ValueError:
        value = 0.0
    get_db().execute("UPDATE users SET monthly_budget = ? WHERE id = ?", (value, session["user_id"]))
    get_db().commit()
    flash("Monthly budget saved.", "success")
    return redirect(url_for("dashboard"))


@app.route("/export")
@login_required
def export_csv():
    rows = get_db().execute(
        "SELECT spent_on, title, category, amount FROM expenses WHERE user_id = ? ORDER BY spent_on",
        (session["user_id"],),
    ).fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Title", "Category", "Amount"])
    writer.writerows([tuple(r) for r in rows])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})


@app.route("/api/suggest")
@login_required
def api_suggest():
    return {"category": suggest_category(request.args.get("title", ""))}


init_db()

if __name__ == "__main__":
    app.run(debug=True)
