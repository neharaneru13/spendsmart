-- SpendSmart sample data
-- 3 users, 5 accounts, 6 categories, ~54 transactions, 22 budgets

INSERT INTO User (user_id, name, email, password) VALUES
    (1, 'Neha Raneru', 'neha@email.com',  'hashed_pw_1'),
    (2, 'Sara Patel',  'sara@email.com',  'hashed_pw_2'),
    (3, 'James Lee',   'james@email.com', 'hashed_pw_3');

INSERT INTO Account (account_id, user_id, type, balance) VALUES
    (1, 1, 'Checking',    2500.00),
    (2, 1, 'Credit Card',  850.00),
    (3, 2, 'Savings',     5000.00),
    (4, 2, 'Checking',    1800.00),
    (5, 3, 'Checking',    1200.00);

INSERT INTO Category (category_id, name) VALUES
    (1, 'Food'),
    (2, 'Rent'),
    (3, 'Transportation'),
    (4, 'Entertainment'),
    (5, 'Shopping'),
    (6, 'Income');

-- Transactions spanning February and March 2026 for realistic student spending
INSERT INTO Transaction (transaction_id, account_id, category_id, amount, date, type) VALUES
    -- Neha (user 1) - February 2026
    (1,  1, 1,   45.00, '2026-02-01', 'expense'),
    (2,  1, 3,   32.50, '2026-02-03', 'expense'),
    (3,  1, 6, 1500.00, '2026-02-05', 'income'),
    (4,  2, 4,   60.00, '2026-02-07', 'expense'),
    (5,  1, 1,   78.00, '2026-02-10', 'expense'),
    (6,  1, 5,  120.00, '2026-02-12', 'expense'),
    (7,  2, 1,   22.00, '2026-02-14', 'expense'),
    (8,  1, 3,   45.00, '2026-02-15', 'expense'),
    (9,  1, 6,  500.00, '2026-02-15', 'income'),
    (10, 2, 4,   35.00, '2026-02-17', 'expense'),
    (11, 1, 2,  950.00, '2026-02-01', 'expense'),
    (12, 1, 1,   52.30, '2026-02-20', 'expense'),
    (13, 2, 5,   89.99, '2026-02-22', 'expense'),
    (14, 1, 3,   28.00, '2026-02-24', 'expense'),
    (15, 2, 4,   42.50, '2026-02-26', 'expense'),
    (16, 1, 1,   63.75, '2026-02-27', 'expense'),
    -- Neha (user 1) - March 2026
    (17, 1, 2,  950.00, '2026-03-01', 'expense'),
    (18, 1, 1,   48.20, '2026-03-02', 'expense'),
    (19, 1, 6, 1500.00, '2026-03-05', 'income'),
    (20, 1, 3,   35.00, '2026-03-06', 'expense'),
    (21, 2, 4,   75.00, '2026-03-08', 'expense'),
    (22, 1, 1,   82.40, '2026-03-10', 'expense'),
    (23, 2, 5,  149.99, '2026-03-12', 'expense'),
    (24, 1, 1,   31.50, '2026-03-14', 'expense'),
    (25, 1, 6,  500.00, '2026-03-15', 'income'),
    (26, 1, 3,   40.00, '2026-03-16', 'expense'),
    (27, 2, 4,   55.00, '2026-03-18', 'expense'),
    (28, 1, 1,   71.25, '2026-03-20', 'expense'),
    (29, 1, 5,   95.00, '2026-03-22', 'expense'),
    (30, 1, 3,   38.75, '2026-03-24', 'expense'),
    -- Sara (user 2) - February 2026
    (31, 4, 1,   35.50, '2026-02-02', 'expense'),
    (32, 4, 6, 2000.00, '2026-02-05', 'income'),
    (33, 4, 2,  800.00, '2026-02-01', 'expense'),
    (34, 4, 3,   50.00, '2026-02-08', 'expense'),
    (35, 4, 1,   42.75, '2026-02-11', 'expense'),
    (36, 3, 5,  210.00, '2026-02-14', 'expense'),
    (37, 4, 4,   85.00, '2026-02-18', 'expense'),
    (38, 4, 1,   55.20, '2026-02-22', 'expense'),
    (39, 4, 3,   60.00, '2026-02-25', 'expense'),
    -- Sara (user 2) - March 2026
    (40, 4, 2,  800.00, '2026-03-01', 'expense'),
    (41, 4, 6, 2000.00, '2026-03-05', 'income'),
    (42, 4, 1,   47.30, '2026-03-07', 'expense'),
    (43, 4, 4,   65.00, '2026-03-10', 'expense'),
    (44, 4, 1,   39.99, '2026-03-13', 'expense'),
    (45, 3, 5,   125.00,'2026-03-16', 'expense'),
    (46, 4, 3,   45.00, '2026-03-19', 'expense'),
    -- James (user 3) - February 2026
    (47, 5, 6, 1200.00, '2026-02-05', 'income'),
    (48, 5, 2,  650.00, '2026-02-01', 'expense'),
    (49, 5, 1,   29.50, '2026-02-09', 'expense'),
    (50, 5, 3,   25.00, '2026-02-12', 'expense'),
    (51, 5, 4,   48.00, '2026-02-20', 'expense'),
    -- James (user 3) - March 2026
    (52, 5, 6, 1200.00, '2026-03-05', 'income'),
    (53, 5, 2,  650.00, '2026-03-01', 'expense'),
    (54, 5, 1,   34.20, '2026-03-10', 'expense');

-- Monthly budgets: Neha + Sara both months, James February only
INSERT INTO Budget (budget_id, user_id, category_id, monthly_limit, month) VALUES
    -- Neha Feb 2026
    (1,  1, 1, 300.00, '2026-02'),
    (2,  1, 2, 1000.00,'2026-02'),
    (3,  1, 3, 150.00, '2026-02'),
    (4,  1, 4, 100.00, '2026-02'),
    (5,  1, 5, 200.00, '2026-02'),
    -- Neha Mar 2026
    (6,  1, 1, 300.00, '2026-03'),
    (7,  1, 2, 1000.00,'2026-03'),
    (8,  1, 3, 150.00, '2026-03'),
    (9,  1, 4, 100.00, '2026-03'),
    (10, 1, 5, 200.00, '2026-03'),
    -- Sara Feb 2026
    (11, 2, 1, 250.00, '2026-02'),
    (12, 2, 2, 900.00, '2026-02'),
    (13, 2, 3, 120.00, '2026-02'),
    (14, 2, 4, 150.00, '2026-02'),
    (15, 2, 5, 300.00, '2026-02'),
    -- Sara Mar 2026
    (16, 2, 1, 250.00, '2026-03'),
    (17, 2, 2, 900.00, '2026-03'),
    (18, 2, 3, 120.00, '2026-03'),
    (19, 2, 4, 150.00, '2026-03'),
    (20, 2, 5, 300.00, '2026-03'),
    -- James Feb 2026
    (21, 3, 1, 200.00, '2026-02'),
    (22, 3, 2, 700.00, '2026-02');
