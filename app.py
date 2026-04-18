import os
import re
from datetime import date, datetime
from calendar import monthrange
from flask import Flask, render_template, request, redirect, url_for, flash, abort
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendsmart-dev-secret")

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "127.0.0.1"),
    "port":     int(os.environ.get("DB_PORT", 3306)),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "spendsmart"),
    "cursorclass": DictCursor,
    "autocommit": True,
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def query(sql, params=None, one=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return (rows[0] if rows else None) if one else rows


def execute(sql, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid


@app.template_filter("money")
def money_filter(value):
    if value is None:
        return "$0.00"
    return f"${float(value):,.2f}"


@app.template_filter("pct")
def pct_filter(value):
    if value is None:
        return "0%"
    return f"{float(value):.1f}%"


# ===== Validation helpers =====

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")

VALID_ACCOUNT_TYPES = {"Checking", "Savings", "Credit Card"}
VALID_TX_TYPES      = {"expense", "income"}


def _pos_float(val, field, errors, allow_zero=False):
    try:
        f = float(val)
    except (TypeError, ValueError):
        errors[field] = "Must be a number."
        return None
    if f < 0 or (not allow_zero and f == 0):
        errors[field] = "Must be greater than 0." if not allow_zero else "Cannot be negative."
        return None
    return f


def _int_fk(val, field, errors, label):
    try:
        return int(val)
    except (TypeError, ValueError):
        errors[field] = f"{label} is required."
        return None


def validate_transaction(form):
    errors = {}
    account_id  = _int_fk(form.get("account_id"), "account_id", errors, "Account")
    category_id = _int_fk(form.get("category_id"), "category_id", errors, "Category")
    amount = _pos_float(form.get("amount"), "amount", errors)
    d = (form.get("date") or "").strip()
    if not DATE_RE.match(d):
        errors["date"] = "Use YYYY-MM-DD."
    else:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            errors["date"] = "Not a valid date."
    tx_type = (form.get("type") or "").strip()
    if tx_type not in VALID_TX_TYPES:
        errors["type"] = "Must be expense or income."
    return {
        "account_id": account_id, "category_id": category_id,
        "amount": amount, "date": d, "type": tx_type,
    }, errors


def validate_user(form):
    errors = {}
    name = (form.get("name") or "").strip()
    if not name:
        errors["name"] = "Name is required."
    elif len(name) > 100:
        errors["name"] = "Name is too long (max 100 characters)."
    email = (form.get("email") or "").strip()
    if not email:
        errors["email"] = "Email is required."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    password = form.get("password") or ""
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    return {"name": name, "email": email, "password": password}, errors


def validate_account(form):
    errors = {}
    user_id = _int_fk(form.get("user_id"), "user_id", errors, "User")
    acct_type = (form.get("type") or "").strip()
    if acct_type not in VALID_ACCOUNT_TYPES:
        errors["type"] = "Must be Checking, Savings, or Credit Card."
    bal_raw = form.get("balance", "0") or "0"
    try:
        balance = float(bal_raw)
    except ValueError:
        errors["balance"] = "Must be a number."
        balance = 0.0
    return {"user_id": user_id, "type": acct_type, "balance": balance}, errors


def validate_budget(form):
    errors = {}
    user_id = _int_fk(form.get("user_id"), "user_id", errors, "User")
    category_id = _int_fk(form.get("category_id"), "category_id", errors, "Category")
    monthly_limit = _pos_float(form.get("monthly_limit"), "monthly_limit", errors, allow_zero=True)
    if monthly_limit is not None and monthly_limit == 0:
        errors["monthly_limit"] = "Must be greater than 0."
    month = (form.get("month") or "").strip()
    if not MONTH_RE.match(month):
        errors["month"] = "Use YYYY-MM (e.g. 2026-04)."
    return {
        "user_id": user_id, "category_id": category_id,
        "monthly_limit": monthly_limit, "month": month,
    }, errors


def _friendly_db_error(e, form_type):
    msg = e.args[1] if len(e.args) > 1 else str(e)
    code = e.args[0] if e.args else 0
    if code == 1062:
        if form_type == "user" and "email" in msg.lower():
            return {"email": "This email is already registered."}, None
        if form_type == "budget":
            return {
                "month": "A budget for this user, category, and month already exists.",
            }, None
        return {}, msg
    if code == 1452:
        return {}, "Foreign key error — the selected user/account/category does not exist."
    return {}, msg


# ===== Routes =====

@app.route("/")
def dashboard():
    totals = query("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income'  THEN amount END), 0) AS total_income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount END), 0) AS total_expense,
            COUNT(*) AS tx_count
        FROM Transaction
    """, one=True)
    totals["net"] = float(totals["total_income"]) - float(totals["total_expense"])

    recent = query("""
        SELECT t.transaction_id, t.amount, t.date, t.type,
               c.name AS category, a.type AS account_type, u.name AS user_name
        FROM Transaction t
        JOIN Account  a ON t.account_id  = a.account_id
        JOIN User     u ON a.user_id     = u.user_id
        JOIN Category c ON t.category_id = c.category_id
        ORDER BY t.date DESC, t.transaction_id DESC
        LIMIT 10
    """)

    user_totals = query("""
        SELECT u.user_id, u.name,
               COALESCE(SUM(CASE WHEN t.type='expense' THEN t.amount END), 0) AS spent
        FROM User u
        LEFT JOIN Account a ON u.user_id = a.user_id
        LEFT JOIN Transaction t ON a.account_id = t.account_id
        GROUP BY u.user_id, u.name
        ORDER BY u.user_id
    """)

    return render_template(
        "dashboard.html",
        totals=totals,
        recent=recent,
        user_totals=user_totals,
    )


@app.route("/transactions")
def transactions():
    user_id     = request.args.get("user_id", type=int)
    category_id = request.args.get("category_id", type=int)
    tx_type     = request.args.get("type") or None
    start_date  = request.args.get("start_date") or None
    end_date    = request.args.get("end_date") or None
    min_amount  = request.args.get("min_amount", type=float)
    max_amount  = request.args.get("max_amount", type=float)

    sql = """
        SELECT t.transaction_id, t.amount, t.date, t.type,
               c.name AS category, a.type AS account_type,
               u.name AS user_name, u.user_id
        FROM Transaction t
        JOIN Account  a ON t.account_id  = a.account_id
        JOIN User     u ON a.user_id     = u.user_id
        JOIN Category c ON t.category_id = c.category_id
        WHERE 1=1
    """
    params = []
    if user_id:
        sql += " AND u.user_id = %s";     params.append(user_id)
    if category_id:
        sql += " AND c.category_id = %s"; params.append(category_id)
    if tx_type in ("expense", "income"):
        sql += " AND t.type = %s";        params.append(tx_type)
    if start_date:
        sql += " AND t.date >= %s";       params.append(start_date)
    if end_date:
        sql += " AND t.date <= %s";       params.append(end_date)
    if min_amount is not None:
        sql += " AND t.amount >= %s";     params.append(min_amount)
    if max_amount is not None:
        sql += " AND t.amount <= %s";     params.append(max_amount)

    sql += " ORDER BY t.date DESC, t.transaction_id DESC"

    rows = query(sql, params)
    users = query("SELECT user_id, name FROM User ORDER BY name")
    categories = query("SELECT category_id, name FROM Category ORDER BY name")

    return render_template(
        "transactions.html",
        rows=rows,
        users=users,
        categories=categories,
        filters={
            "user_id": user_id, "category_id": category_id, "type": tx_type,
            "start_date": start_date, "end_date": end_date,
            "min_amount": min_amount, "max_amount": max_amount,
        },
    )


def _add_context(active_tab, form=None, errors=None):
    return dict(
        active_tab=active_tab,
        form=form or {},
        errors=errors or {},
        users=query("SELECT user_id, name FROM User ORDER BY name"),
        accounts=query(
            "SELECT a.account_id, a.type, a.balance, u.name AS user_name "
            "FROM Account a JOIN User u ON a.user_id = u.user_id ORDER BY u.name, a.type"
        ),
        categories=query("SELECT category_id, name FROM Category ORDER BY name"),
        today=date.today().isoformat(),
        this_month=date.today().strftime("%Y-%m"),
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    active_tab = request.args.get("tab", "transaction")

    if request.method == "POST":
        form_type = request.form.get("form_type") or active_tab
        validators = {
            "transaction": validate_transaction,
            "user":        validate_user,
            "account":     validate_account,
            "budget":      validate_budget,
        }
        if form_type not in validators:
            flash("Unknown form.", "error")
            return redirect(url_for("add"))

        data, errors = validators[form_type](request.form)

        if not errors:
            try:
                if form_type == "transaction":
                    execute(
                        "INSERT INTO Transaction (account_id, category_id, amount, date, type) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (data["account_id"], data["category_id"], data["amount"], data["date"], data["type"]),
                    )
                elif form_type == "user":
                    execute(
                        "INSERT INTO User (name, email, password) VALUES (%s, %s, %s)",
                        (data["name"], data["email"], data["password"]),
                    )
                elif form_type == "account":
                    execute(
                        "INSERT INTO Account (user_id, type, balance) VALUES (%s, %s, %s)",
                        (data["user_id"], data["type"], data["balance"]),
                    )
                elif form_type == "budget":
                    execute(
                        "INSERT INTO Budget (user_id, category_id, monthly_limit, month) "
                        "VALUES (%s, %s, %s, %s)",
                        (data["user_id"], data["category_id"], data["monthly_limit"], data["month"]),
                    )
                flash(f"{form_type.capitalize()} added.", "success")
                return redirect(url_for("add", tab=form_type))
            except pymysql.MySQLError as e:
                field_errors, flash_msg = _friendly_db_error(e, form_type)
                errors.update(field_errors)
                if flash_msg:
                    flash(f"Database error: {flash_msg}", "error")

        return render_template("add.html", **_add_context(form_type, request.form, errors))

    return render_template("add.html", **_add_context(active_tab))


@app.route("/edit/<int:transaction_id>", methods=["GET", "POST"])
def edit(transaction_id):
    tx = query(
        "SELECT * FROM Transaction WHERE transaction_id = %s",
        (transaction_id,), one=True,
    )
    if not tx:
        abort(404)

    accounts = query(
        "SELECT a.account_id, a.type, u.name AS user_name "
        "FROM Account a JOIN User u ON a.user_id = u.user_id ORDER BY u.name, a.type"
    )
    categories = query("SELECT category_id, name FROM Category ORDER BY name")

    if request.method == "POST":
        data, errors = validate_transaction(request.form)
        if not errors:
            try:
                execute(
                    "UPDATE Transaction SET account_id=%s, category_id=%s, amount=%s, date=%s, type=%s "
                    "WHERE transaction_id=%s",
                    (data["account_id"], data["category_id"], data["amount"],
                     data["date"], data["type"], transaction_id),
                )
                flash("Transaction updated.", "success")
                return redirect(url_for("transactions"))
            except pymysql.MySQLError as e:
                _, flash_msg = _friendly_db_error(e, "transaction")
                if flash_msg:
                    flash(f"Database error: {flash_msg}", "error")
        return render_template(
            "edit.html", tx=tx, accounts=accounts, categories=categories,
            form=request.form, errors=errors,
        )

    return render_template(
        "edit.html", tx=tx, accounts=accounts, categories=categories,
        form={}, errors={},
    )


@app.route("/delete/<int:transaction_id>", methods=["POST"])
def delete(transaction_id):
    result = query("SELECT transaction_id FROM Transaction WHERE transaction_id = %s",
                   (transaction_id,), one=True)
    if not result:
        flash(f"Transaction #{transaction_id} not found.", "error")
    else:
        execute("DELETE FROM Transaction WHERE transaction_id = %s", (transaction_id,))
        flash("Transaction deleted.", "success")
    return redirect(url_for("transactions"))


@app.route("/join")
def join_view():
    rows = query("""
        SELECT t.transaction_id, t.amount, t.date, t.type,
               c.name AS category, a.type AS account_type,
               u.name AS user_name
        FROM Transaction t
        JOIN Account  a ON t.account_id  = a.account_id
        JOIN User     u ON a.user_id     = u.user_id
        JOIN Category c ON t.category_id = c.category_id
        ORDER BY t.date DESC, t.transaction_id DESC
    """)
    return render_template("join.html", rows=rows)


@app.route("/summary")
def summary():
    user_id = request.args.get("user_id", type=int)
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    if not MONTH_RE.match(month):
        month = date.today().strftime("%Y-%m")

    base_sql = """
        SELECT c.category_id, c.name AS category,
               COUNT(t.transaction_id) AS tx_count,
               COALESCE(SUM(t.amount), 0) AS total
        FROM Category c
        LEFT JOIN Transaction t ON t.category_id = c.category_id
            AND t.type = 'expense'
            AND DATE_FORMAT(t.date, '%%Y-%%m') = %s
            {user_filter}
        GROUP BY c.category_id, c.name
        HAVING total > 0
        ORDER BY total DESC
    """
    if user_id:
        sql = base_sql.format(
            user_filter="AND t.account_id IN (SELECT account_id FROM Account WHERE user_id = %s)"
        )
        rows = query(sql, (month, user_id))
    else:
        sql = base_sql.format(user_filter="")
        rows = query(sql, (month,))

    grand_total = sum(float(r["total"]) for r in rows) or 1.0
    for r in rows:
        r["pct"] = float(r["total"]) / grand_total * 100

    users = query("SELECT user_id, name FROM User ORDER BY name")
    return render_template(
        "summary.html",
        rows=rows,
        users=users,
        selected_user=user_id,
        month=month,
        grand_total=grand_total if rows else 0,
    )


@app.route("/forecast")
def forecast():
    user_id = request.args.get("user_id", type=int, default=1)
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    if not MONTH_RE.match(month):
        month = date.today().strftime("%Y-%m")

    year_str, month_str = month.split("-")
    year, mon = int(year_str), int(month_str)
    days_in_month = monthrange(year, mon)[1]
    today = date.today()
    if today.year == year and today.month == mon:
        days_elapsed = today.day
    elif (today.year, today.month) > (year, mon):
        days_elapsed = days_in_month
    else:
        days_elapsed = 1
    days_remaining = max(days_in_month - days_elapsed, 0)

    sql = """
        WITH spent AS (
            SELECT t.category_id,
                   COALESCE(SUM(t.amount), 0) AS spent_amount
            FROM Transaction t
            JOIN Account a ON t.account_id = a.account_id
            WHERE a.user_id = %s
              AND t.type = 'expense'
              AND DATE_FORMAT(t.date, '%%Y-%%m') = %s
            GROUP BY t.category_id
        )
        SELECT b.budget_id, c.name AS category, b.monthly_limit,
               COALESCE(s.spent_amount, 0) AS spent
        FROM Budget b
        JOIN Category c ON b.category_id = c.category_id
        LEFT JOIN spent s ON s.category_id = b.category_id
        WHERE b.user_id = %s AND b.month = %s
        ORDER BY c.name
    """
    rows = query(sql, (user_id, month, user_id, month))

    forecasts = []
    for r in rows:
        spent = float(r["spent"])
        limit = float(r["monthly_limit"])
        daily_rate = spent / days_elapsed if days_elapsed > 0 else 0
        projected = spent + daily_rate * days_remaining
        status = "on_track"
        if projected > limit:
            status = "over_budget"
        elif projected > limit * 0.9:
            status = "at_risk"
        forecasts.append({
            "budget_id": r["budget_id"],
            "category": r["category"],
            "monthly_limit": limit,
            "spent": spent,
            "daily_rate": daily_rate,
            "projected": projected,
            "over_by": projected - limit,
            "pct_used": (spent / limit * 100) if limit else 0,
            "status": status,
        })

    users = query("SELECT user_id, name FROM User ORDER BY name")
    return render_template(
        "forecast.html",
        forecasts=forecasts,
        users=users,
        selected_user=user_id,
        month=month,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        days_in_month=days_in_month,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", body_error="404 - Page not found"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
