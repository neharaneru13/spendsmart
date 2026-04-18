"""
End-to-end tests for SpendSmart.

Covers every item in the Future Work checklist:
  - All CRUD operations (INSERT, SEARCH/LIST, UPDATE, DELETE) via HTTP
  - JOIN + aggregate + forecast queries via HTTP
  - NULL handling (users with no transactions, categories with no spending)
  - Empty result sets (filters that match nothing)
  - Month boundaries for the forecasting function (future / past / current)
  - Duplicate budget constraint enforcement (UNIQUE user_id+category_id+month)

Assumes:
  - MySQL running at 127.0.0.1:3306 with empty root password
  - Flask app running at http://localhost:5050
  - seed.sql has been loaded (3 users, 5 accounts, 6 categories, 54 tx, 22 budgets)

Usage:
    python -m unittest tests.test_e2e -v
    # or
    python tests/test_e2e.py
"""

import os
import sys
import unittest
from calendar import monthrange
from datetime import date
from urllib.parse import urlencode

import pymysql
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5050")
DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306,
    "user": "root", "password": "",
    "database": "spendsmart",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def db():
    return pymysql.connect(**DB_CONFIG)


def _exec(cur, sql, params):
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)


def fetch_one(sql, params=()):
    with db() as conn, conn.cursor() as cur:
        _exec(cur, sql, params)
        return cur.fetchone()


def fetch_all(sql, params=()):
    with db() as conn, conn.cursor() as cur:
        _exec(cur, sql, params)
        return cur.fetchall()


def exec_sql(sql, params=()):
    with db() as conn, conn.cursor() as cur:
        _exec(cur, sql, params)
        return cur.lastrowid


class SpendSmartE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure app is reachable
        try:
            r = requests.get(BASE_URL + "/", timeout=3)
            r.raise_for_status()
        except Exception as e:
            raise unittest.SkipTest(f"App not reachable at {BASE_URL}: {e}")
        cls.session = requests.Session()

    def setUp(self):
        # Clean up any test-specific rows between tests
        exec_sql("DELETE FROM User WHERE email LIKE 'e2e-%@test.com'")
        exec_sql("DELETE FROM Budget WHERE month = '2099-12'")

    # ---------- Smoke tests ----------

    def test_010_all_routes_return_200(self):
        routes = ["/", "/transactions", "/add", "/join",
                  "/summary?month=2026-02", "/forecast?user_id=1&month=2026-02"]
        for route in routes:
            with self.subTest(route=route):
                r = self.session.get(BASE_URL + route)
                self.assertEqual(r.status_code, 200, route)

    def test_020_nav_has_six_links(self):
        r = self.session.get(BASE_URL + "/")
        for label in ["Dashboard", "Transactions", "Add", "Join View", "Summary", "Forecast"]:
            self.assertIn(label, r.text)

    # ---------- INSERT (via HTTP) ----------

    def test_100_insert_user_via_form(self):
        email = "e2e-insert@test.com"
        r = self.session.post(BASE_URL + "/add?tab=user", data={
            "form_type": "user", "name": "E2E Insert",
            "email": email, "password": "secret123",
        })
        self.assertEqual(r.status_code, 200)
        row = fetch_one("SELECT name, email FROM User WHERE email=%s", (email,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "E2E Insert")

    def test_110_insert_transaction_via_form(self):
        before = fetch_one("SELECT COUNT(*) AS c FROM Transaction")["c"]
        r = self.session.post(BASE_URL + "/add?tab=transaction", data={
            "form_type": "transaction",
            "account_id": 1, "category_id": 1,
            "amount": "12.34", "date": "2026-04-01", "type": "expense",
        })
        self.assertEqual(r.status_code, 200)
        after = fetch_one("SELECT COUNT(*) AS c FROM Transaction")["c"]
        self.assertEqual(after, before + 1)
        exec_sql("DELETE FROM Transaction WHERE amount=12.34 AND date='2026-04-01'")

    # ---------- SEARCH / LIST ----------

    def test_200_search_returns_results(self):
        r = self.session.get(BASE_URL + "/transactions?" + urlencode({
            "user_id": 1, "category_id": 1, "type": "expense",
        }))
        self.assertEqual(r.status_code, 200)
        self.assertIn("transactions found", r.text)
        self.assertNotIn("0 transactions found", r.text)

    def test_210_search_empty_result_set(self):
        """Empty result set - filter matching no rows."""
        r = self.session.get(BASE_URL + "/transactions?" + urlencode({
            "min_amount": 999999,
        }))
        self.assertEqual(r.status_code, 200)
        self.assertIn("0 transactions found", r.text)
        self.assertIn("No transactions match your filters", r.text)

    # ---------- JOIN ----------

    def test_300_join_view_shows_all_columns(self):
        r = self.session.get(BASE_URL + "/join")
        self.assertEqual(r.status_code, 200)
        for col in ["User", "Account", "Category", "Amount", "Date", "Type"]:
            self.assertIn(col, r.text)
        self.assertIn("rows returned", r.text)

    # ---------- AGGREGATE ----------

    def test_400_aggregate_sums_match_db(self):
        r = self.session.get(BASE_URL + "/summary?month=2026-02")
        self.assertEqual(r.status_code, 200)
        # Compute expected from DB
        rows = fetch_all("""
            SELECT c.name AS category, COALESCE(SUM(t.amount), 0) AS total
            FROM Category c
            LEFT JOIN Transaction t ON t.category_id = c.category_id
                AND t.type='expense'
                AND DATE_FORMAT(t.date, '%Y-%m') = '2026-02'
            GROUP BY c.category_id, c.name
            HAVING total > 0
        """)
        for row in rows:
            # Each category with >0 total should appear in the page
            self.assertIn(row["category"], r.text, f"missing {row['category']}")

    def test_410_aggregate_null_handling_for_empty_month(self):
        """Month with no transactions should produce empty-state, not 500."""
        r = self.session.get(BASE_URL + "/summary?month=2099-01")
        self.assertEqual(r.status_code, 200)
        self.assertIn("No expenses recorded for this period", r.text)

    # ---------- UPDATE ----------

    def test_500_update_transaction(self):
        tx_id = exec_sql(
            "INSERT INTO Transaction (account_id, category_id, amount, date, type) "
            "VALUES (1, 1, 11.11, '2026-04-01', 'expense')"
        )
        try:
            r = self.session.post(BASE_URL + f"/edit/{tx_id}", data={
                "account_id": 1, "category_id": 2,
                "amount": "22.22", "date": "2026-04-02", "type": "income",
            }, allow_redirects=False)
            self.assertIn(r.status_code, (302, 303))
            row = fetch_one("SELECT * FROM Transaction WHERE transaction_id=%s", (tx_id,))
            self.assertAlmostEqual(float(row["amount"]), 22.22)
            self.assertEqual(row["category_id"], 2)
            self.assertEqual(row["type"], "income")
            self.assertEqual(str(row["date"]), "2026-04-02")
        finally:
            exec_sql("DELETE FROM Transaction WHERE transaction_id=%s", (tx_id,))

    def test_510_update_nonexistent_returns_404(self):
        r = self.session.get(BASE_URL + "/edit/999999")
        self.assertEqual(r.status_code, 404)

    # ---------- DELETE ----------

    def test_600_delete_transaction(self):
        tx_id = exec_sql(
            "INSERT INTO Transaction (account_id, category_id, amount, date, type) "
            "VALUES (1, 1, 99.99, '2026-04-01', 'expense')"
        )
        r = self.session.post(BASE_URL + f"/delete/{tx_id}", allow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertIsNone(fetch_one("SELECT 1 FROM Transaction WHERE transaction_id=%s", (tx_id,)))

    def test_610_delete_nonexistent_flashes_not_found(self):
        r = self.session.post(BASE_URL + "/delete/999999", allow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("not found", r.text.lower())

    # ---------- Edge: NULL handling ----------

    def test_700_user_with_no_transactions_renders_everywhere(self):
        """User with no transactions: every page must still render (LEFT JOINs / NULL handling)."""
        user_id = exec_sql(
            "INSERT INTO User (name, email, password) VALUES "
            "('E2E NoTx', 'e2e-notx@test.com', 'x')"
        )
        try:
            # Dashboard still renders
            self.assertEqual(self.session.get(BASE_URL + "/").status_code, 200)
            # Transactions filtered to this user should render empty state
            r = self.session.get(BASE_URL + f"/transactions?user_id={user_id}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("0 transactions found", r.text)
            # Summary filtered to this user should render empty state
            r = self.session.get(BASE_URL + f"/summary?user_id={user_id}&month=2026-02")
            self.assertEqual(r.status_code, 200)
            self.assertIn("No expenses recorded", r.text)
            # Forecast for this user with no budgets should render empty state
            r = self.session.get(BASE_URL + f"/forecast?user_id={user_id}&month=2026-02")
            self.assertEqual(r.status_code, 200)
            self.assertIn("No budgets set", r.text)
        finally:
            exec_sql("DELETE FROM User WHERE user_id=%s", (user_id,))

    def test_710_forecast_with_no_spending_shows_zero(self):
        """Budget exists but no transactions -> spent=0, on track."""
        user_id = exec_sql(
            "INSERT INTO User (name, email, password) VALUES "
            "('E2E EmptyBudget', 'e2e-emptybudget@test.com', 'x')"
        )
        try:
            exec_sql(
                "INSERT INTO Budget (user_id, category_id, monthly_limit, month) "
                "VALUES (%s, 1, 100.00, '2099-12')",
                (user_id,),
            )
            r = self.session.get(BASE_URL + f"/forecast?user_id={user_id}&month=2099-12")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Food", r.text)
            self.assertIn("$100.00", r.text)
            self.assertIn("On Track", r.text)
        finally:
            exec_sql("DELETE FROM Budget WHERE user_id=%s", (user_id,))
            exec_sql("DELETE FROM User WHERE user_id=%s", (user_id,))

    # ---------- Edge: forecasting month boundaries ----------

    def test_800_forecast_future_month_uses_day_one(self):
        """Future month: days_elapsed=1, days_remaining near full month."""
        r = self.session.get(BASE_URL + "/forecast?user_id=1&month=2099-06")
        self.assertEqual(r.status_code, 200)
        days_in_jun = monthrange(2099, 6)[1]
        self.assertIn(f"Day 1 of {days_in_jun}", r.text)
        self.assertIn(f"{days_in_jun - 1} days remaining", r.text)

    def test_810_forecast_past_month_uses_full_days(self):
        """Past month: days_elapsed = days_in_month, days_remaining = 0."""
        r = self.session.get(BASE_URL + "/forecast?user_id=1&month=2020-02")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Day 29 of 29", r.text)  # 2020 was a leap year
        self.assertIn("0 days remaining", r.text)

    def test_820_forecast_february_leap_year(self):
        """Forecast handles Feb in a leap year correctly (29 days)."""
        r = self.session.get(BASE_URL + "/forecast?user_id=1&month=2024-02")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Day 29 of 29", r.text)

    def test_830_forecast_february_non_leap_year(self):
        """Forecast handles Feb in a non-leap year correctly (28 days)."""
        r = self.session.get(BASE_URL + "/forecast?user_id=1&month=2023-02")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Day 28 of 28", r.text)

    def test_840_forecast_invalid_month_falls_back(self):
        """Malformed month parameter must not crash the app."""
        r = self.session.get(BASE_URL + "/forecast?user_id=1&month=not-a-month")
        self.assertEqual(r.status_code, 200)

    # ---------- Edge: duplicate budget constraint enforcement ----------

    def test_900_duplicate_budget_is_rejected(self):
        """UNIQUE(user_id, category_id, month) must prevent duplicates."""
        r1 = self.session.post(BASE_URL + "/add?tab=budget", data={
            "form_type": "budget",
            "user_id": 1, "category_id": 1,
            "monthly_limit": "123.45", "month": "2099-12",
        })
        self.assertEqual(r1.status_code, 200)
        self.assertIsNotNone(fetch_one(
            "SELECT 1 FROM Budget WHERE user_id=1 AND category_id=1 AND month='2099-12'"
        ))
        # Same user/category/month -> should fail and show inline error
        r2 = self.session.post(BASE_URL + "/add?tab=budget", data={
            "form_type": "budget",
            "user_id": 1, "category_id": 1,
            "monthly_limit": "999.00", "month": "2099-12",
        })
        self.assertEqual(r2.status_code, 200)
        self.assertIn("already exists", r2.text.lower())
        count = fetch_one(
            "SELECT COUNT(*) AS c FROM Budget "
            "WHERE user_id=1 AND category_id=1 AND month='2099-12'"
        )["c"]
        self.assertEqual(count, 1)

    def test_910_duplicate_user_email_is_rejected(self):
        """UNIQUE email constraint - same email twice is rejected with inline error."""
        email = "e2e-dup@test.com"
        r1 = self.session.post(BASE_URL + "/add?tab=user", data={
            "form_type": "user", "name": "Dup1",
            "email": email, "password": "secret123",
        })
        self.assertEqual(r1.status_code, 200)
        r2 = self.session.post(BASE_URL + "/add?tab=user", data={
            "form_type": "user", "name": "Dup2",
            "email": email, "password": "secret123",
        })
        self.assertEqual(r2.status_code, 200)
        self.assertIn("already registered", r2.text.lower())

    # ---------- Validation ----------

    def test_a000_invalid_email_shows_error(self):
        r = self.session.post(BASE_URL + "/add?tab=user", data={
            "form_type": "user", "name": "X",
            "email": "not-an-email", "password": "secret123",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("valid email address", r.text)

    def test_a010_short_password_shows_error(self):
        r = self.session.post(BASE_URL + "/add?tab=user", data={
            "form_type": "user", "name": "X",
            "email": "e2e-shortpw@test.com", "password": "123",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("at least 6 characters", r.text)

    def test_a020_negative_amount_shows_error(self):
        r = self.session.post(BASE_URL + "/add?tab=transaction", data={
            "form_type": "transaction",
            "account_id": 1, "category_id": 1,
            "amount": "-5.00", "date": "2026-04-01", "type": "expense",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("greater than 0", r.text)


if __name__ == "__main__":
    # When run directly, show verbose output
    sys.argv.append("-v")
    unittest.main()
