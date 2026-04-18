# SpendSmart

A database-driven, Flask + MySQL personal finance tracker built for CS 4710
Database Systems (Spring 2026). Users can track multiple bank accounts,
categorize transactions, set monthly budgets, and forecast end-of-month
spending with a CTE-based query that joins across four tables.

## Features

**Basic functions (required by the rubric):**

- **INSERT** — tabbed form for adding Users, Accounts, Transactions, and Budgets
- **SEARCH / LIST** — 7-filter transaction search (user, category, type, date range, amount range)
- **JOIN** — 4-table join view (Transaction × Account × User × Category) with SQL displayed
- **AGGREGATE** — spending summary with `SUM + COUNT + GROUP BY` per category and % bars
- **UPDATE** — edit any transaction with a pre-filled form
- **DELETE** — delete with confirmation dialog

**Advanced function — Budget Forecasting:**

A single query pipeline uses a CTE, a multi-table JOIN, `SUM` aggregation, and
date arithmetic to project end-of-month spending based on the user's current
daily spending rate, then flags categories as over-budget / at-risk / on-track.

## Tech stack

| Layer    | Technology                |
| -------- | ------------------------- |
| Database | MySQL 8.0+                |
| Backend  | Python 3.9+ / Flask 3.0.3 |
| Driver   | pymysql 1.1.1             |
| Frontend | Jinja2, plain CSS, HTML5  |
| Testing  | unittest + requests       |

## Schema (5 tables, BCNF)

```
User        (user_id PK, name, email UNIQUE, password)
Account     (account_id PK, user_id FK, type, balance)
Category    (category_id PK, name UNIQUE)
Transaction (transaction_id PK, account_id FK, category_id FK, amount, date, type)
Budget      (budget_id PK, user_id FK, category_id FK, monthly_limit, month,
             UNIQUE (user_id, category_id, month))
```

## Recreate from scratch

### 1. Prerequisites

- Python 3.9 or newer
- MySQL 8.0+ (`brew install mysql` on macOS)
- Git

### 2. Clone

```bash
git clone https://github.com/neharaneru13/spendsmart.git
cd spendsmart
```

### 3. Start MySQL and load the database

```bash
# macOS / Linux (Homebrew)
brew services start mysql

# Set root to have an empty password (what the app expects by default).
# If you set a password during install, either clear it or update DB_CONFIG below.
mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '';"

# Create the database and load schema + sample data
mysql -u root -e "CREATE DATABASE IF NOT EXISTS spendsmart;"
mysql -u root spendsmart < schema.sql
mysql -u root spendsmart < seed.sql

# Verify the seed loaded
mysql -u root spendsmart -e "
  SELECT 'users'        AS t, COUNT(*) FROM User UNION ALL
  SELECT 'accounts'     AS t, COUNT(*) FROM Account UNION ALL
  SELECT 'categories'   AS t, COUNT(*) FROM Category UNION ALL
  SELECT 'transactions' AS t, COUNT(*) FROM Transaction UNION ALL
  SELECT 'budgets'      AS t, COUNT(*) FROM Budget;"
```

Expected output:

| table        | count |
| ------------ | ----- |
| users        | 3     |
| accounts     | 5     |
| categories   | 6     |
| transactions | 54    |
| budgets      | 22    |

### 4. Python virtual environment and dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate       # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Run the app

```bash
python app.py
```

Open http://localhost:5050

To override defaults:

```bash
PORT=8000 DB_PASSWORD=secret python app.py
```

The app reads these environment variables (see `DB_CONFIG` in `app.py`):
`DB_HOST` (127.0.0.1), `DB_PORT` (3306), `DB_USER` (root), `DB_PASSWORD` (empty),
`DB_NAME` (spendsmart), `PORT` (5050), `SECRET_KEY`.

## Running the tests

The end-to-end test suite has 25 tests covering every CRUD operation, edge
cases (NULL handling, empty result sets, month boundaries for the forecaster,
duplicate budget constraint, leap years), and validation.

Requires the app to be running and the database to be seeded.

```bash
source .venv/bin/activate
python -m unittest tests.test_e2e -v
```

Expected: `Ran 25 tests in ~0.3s  OK`

## Project layout

```
spendsmart/
├── app.py                 # Flask app — all 7 routes + validation
├── schema.sql             # CREATE TABLE statements
├── seed.sql               # 54 transactions + 22 budgets of sample data
├── requirements.txt
├── templates/
│   ├── base.html          # Shared layout, topbar, nav
│   ├── dashboard.html     # Stat cards + recent transactions
│   ├── transactions.html  # Search & List with filters
│   ├── add.html           # Tabbed INSERT form (Tx / User / Account / Budget)
│   ├── edit.html          # UPDATE form with inline errors
│   ├── summary.html       # Aggregate query + bar chart
│   ├── forecast.html      # CTE + date arithmetic + status badges
│   └── join.html          # 4-table JOIN view with SQL shown
├── static/
│   └── style.css          # Responsive styling (desktop / tablet / mobile)
└── tests/
    └── test_e2e.py        # End-to-end test suite
```

## Routes

| Method   | Path                        | Purpose                              |
| -------- | --------------------------- | ------------------------------------ |
| GET      | `/`                         | Dashboard: income/expense/net totals |
| GET      | `/transactions`             | Search & list with filters           |
| GET/POST | `/add`                      | Tabbed insert form                   |
| GET/POST | `/edit/<id>`                | Update a transaction                 |
| POST     | `/delete/<id>`              | Delete a transaction                 |
| GET      | `/join`                     | 4-table JOIN view                    |
| GET      | `/summary?month=YYYY-MM`    | SUM + COUNT + GROUP BY               |
| GET      | `/forecast?user_id=&month=` | Budget forecast (CTE)                |

## Troubleshooting

| Symptom                                     | Fix                                                                                    |
| ------------------------------------------- | -------------------------------------------------------------------------------------- |
| `Access denied for user 'root'@'localhost'` | Root has a password — either `ALTER USER` to clear it, or set `DB_PASSWORD` env var    |
| `Unknown database 'spendsmart'`             | Re-run the `CREATE DATABASE` + schema + seed commands from step 3                      |
| `ModuleNotFoundError: No module named 'pymysql'` | Virtual env not activated — run `source .venv/bin/activate` then `pip install -r requirements.txt` |
| Port 5050 already in use                    | `PORT=8000 python app.py`                                                              |
| `Address already in use` starting MySQL     | Another MySQL is running (e.g. Oracle installer). Stop it with `sudo launchctl unload -w /Library/LaunchDaemons/com.oracle.oss.mysql.mysqld.plist` |

## License

Built for CS 4710 coursework. No license granted beyond academic review.
