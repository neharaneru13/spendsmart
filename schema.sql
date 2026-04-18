-- SpendSmart Database Schema
-- CS 4710 Database Systems

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS Budget;
DROP TABLE IF EXISTS Transaction;
DROP TABLE IF EXISTS Category;
DROP TABLE IF EXISTS Account;
DROP TABLE IF EXISTS User;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE User (
    user_id     INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL
);

CREATE TABLE Account (
    account_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    type        VARCHAR(50) NOT NULL,
    balance     DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_account_user FOREIGN KEY (user_id)
        REFERENCES User(user_id) ON DELETE CASCADE
);

CREATE TABLE Category (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Transaction (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id     INT NOT NULL,
    category_id    INT NOT NULL,
    amount         DECIMAL(10, 2) NOT NULL,
    date           DATE NOT NULL,
    type           ENUM('expense', 'income') NOT NULL,
    CONSTRAINT fk_tx_account  FOREIGN KEY (account_id)
        REFERENCES Account(account_id) ON DELETE CASCADE,
    CONSTRAINT fk_tx_category FOREIGN KEY (category_id)
        REFERENCES Category(category_id) ON DELETE RESTRICT,
    INDEX idx_tx_date (date),
    INDEX idx_tx_category (category_id)
);

CREATE TABLE Budget (
    budget_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    category_id   INT NOT NULL,
    monthly_limit DECIMAL(10, 2) NOT NULL,
    month         CHAR(7) NOT NULL,
    CONSTRAINT fk_budget_user     FOREIGN KEY (user_id)
        REFERENCES User(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_budget_category FOREIGN KEY (category_id)
        REFERENCES Category(category_id) ON DELETE RESTRICT,
    CONSTRAINT uq_budget UNIQUE (user_id, category_id, month)
);
