from __future__ import annotations

import os
import hashlib
from datetime import datetime, timedelta

import pyodbc


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return digest.hex()


def connect(database: str):
    driver = env("CHATBOT_SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    host = env("CHATBOT_SQLSERVER_HOST", "127.0.0.1")
    port = env("CHATBOT_SQLSERVER_PORT", "1433")
    user = env("CHATBOT_SQLSERVER_USER", "sa")
    password = env("CHATBOT_SQLSERVER_PASSWORD", "StrongPass123!")
    encrypt = env("CHATBOT_SQLSERVER_ENCRYPT", "no")
    trust = env("CHATBOT_SQLSERVER_TRUST_CERT", "yes")
    server = f"{host},{port}"
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={server};UID={user};PWD={password};DATABASE={database};"
        f"Encrypt={encrypt};TrustServerCertificate={trust};"
    )


def main() -> None:
    db_name = env("CHATBOT_SQLSERVER_DB", "chatbot_test_db")

    master = connect("master")
    master.autocommit = True
    cur = master.cursor()
    cur.execute(f"IF DB_ID('{db_name}') IS NULL CREATE DATABASE {db_name}")
    cur.close()
    master.close()

    conn = connect(db_name)
    cur = conn.cursor()

    cur.execute(
        """
        IF OBJECT_ID('transactions', 'U') IS NOT NULL DROP TABLE transactions;
        IF OBJECT_ID('budgets', 'U') IS NOT NULL DROP TABLE budgets;
        IF OBJECT_ID('categories', 'U') IS NOT NULL DROP TABLE categories;
        IF OBJECT_ID('chatbot_tenant_profiles', 'U') IS NOT NULL DROP TABLE chatbot_tenant_profiles;
        IF OBJECT_ID('chatbot_user_credentials', 'U') IS NOT NULL DROP TABLE chatbot_user_credentials;
        IF OBJECT_ID('chatbot_tenant_users', 'U') IS NOT NULL DROP TABLE chatbot_tenant_users;
        IF OBJECT_ID('users', 'U') IS NOT NULL DROP TABLE users;
        """
    )

    cur.execute(
        """
        CREATE TABLE users (
          id INT IDENTITY(1,1) PRIMARY KEY,
          tenant_id NVARCHAR(100) NOT NULL,
          name NVARCHAR(100) NOT NULL,
          email NVARCHAR(255) NOT NULL,
          role NVARCHAR(20) NOT NULL,
          status NVARCHAR(20) NOT NULL DEFAULT 'active'
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE chatbot_tenant_profiles (
          tenant_id NVARCHAR(100) NOT NULL PRIMARY KEY,
          domain NVARCHAR(50) NOT NULL,
          display_name NVARCHAR(200) NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE chatbot_user_credentials (
          user_id INT NOT NULL PRIMARY KEY,
          password_hash NVARCHAR(256) NOT NULL,
          salt NVARCHAR(128) NOT NULL,
          is_active BIT NOT NULL DEFAULT 1,
          CONSTRAINT FK_chatbot_credentials_user FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE chatbot_tenant_users (
          tenant_id NVARCHAR(100) NOT NULL,
          user_id INT NOT NULL,
          PRIMARY KEY (tenant_id, user_id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE categories (
          id INT IDENTITY(1,1) PRIMARY KEY,
          name NVARCHAR(100) NOT NULL,
          type NVARCHAR(20) NOT NULL
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE transactions (
          id INT IDENTITY(1,1) PRIMARY KEY,
          user_id INT NOT NULL,
          category_id INT NOT NULL,
          amount FLOAT NOT NULL,
          description NVARCHAR(500) NULL,
          date DATETIME2 NOT NULL,
          is_deleted BIT NOT NULL DEFAULT 0,
          CONSTRAINT FK_transactions_user FOREIGN KEY (user_id) REFERENCES users(id),
          CONSTRAINT FK_transactions_category FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE budgets (
          id INT IDENTITY(1,1) PRIMARY KEY,
          user_id INT NOT NULL,
          category_id INT NULL,
          amount FLOAT NOT NULL,
          period NVARCHAR(20) NOT NULL,
          start_date DATE NOT NULL,
          end_date DATE NOT NULL,
          CONSTRAINT FK_budgets_user FOREIGN KEY (user_id) REFERENCES users(id),
          CONSTRAINT FK_budgets_category FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        """
    )

    cur.executemany(
        "INSERT INTO chatbot_tenant_profiles (tenant_id, domain, display_name) VALUES (?, ?, ?)",
        [
            ("tnt_demo", "finance", "Finance Demo"),
            ("tnt_other", "event", "Event Demo"),
        ],
    )

    cur.executemany(
        "INSERT INTO users (tenant_id, name, email, role, status) VALUES (?, ?, ?, ?, ?)",
        [
            ("tnt_demo", "System Admin", "admin@test.local", "admin", "active"),
            ("tnt_demo", "John Doe", "john@test.local", "user", "active"),
            ("tnt_demo", "Jane Smith", "jane@test.local", "user", "active"),
            ("tnt_other", "Other Tenant User", "other@test.local", "user", "active"),
        ],
    )

    cur.executemany(
        "INSERT INTO chatbot_tenant_users (tenant_id, user_id) VALUES (?, ?)",
        [("tnt_demo", 1), ("tnt_demo", 2), ("tnt_demo", 3), ("tnt_other", 4)],
    )

    credentials = [
        (1, "Admin@123", "salt-admin-01"),
        (2, "User@123", "salt-user-02"),
        (3, "User@123", "salt-user-03"),
        (4, "User@123", "salt-user-04"),
    ]
    cur.executemany(
        "INSERT INTO chatbot_user_credentials (user_id, password_hash, salt, is_active) VALUES (?, ?, ?, 1)",
        [(uid, hash_password(password, salt), salt) for uid, password, salt in credentials],
    )

    cur.executemany(
        "INSERT INTO categories (name, type) VALUES (?, ?)",
        [
            ("Salary", "income"),
            ("Food & Dining", "expense"),
            ("Shopping", "expense"),
            ("Rent", "expense"),
            ("Freelance", "income"),
            ("Transport", "expense"),
        ],
    )

    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    txns = [
        (2, 1, 60000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (2, 2, -8500.0, "Dining and takeout", month_start + timedelta(days=3), 0),
        (2, 3, -4200.0, "Shopping", month_start + timedelta(days=6), 0),
        (2, 4, -15000.0, "House rent", month_start + timedelta(days=2), 0),
        (2, 6, -1800.0, "Metro and fuel", month_start + timedelta(days=5), 0),
        (3, 1, 45000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (3, 5, 12000.0, "Freelance project", month_start + timedelta(days=4), 0),
        (3, 2, -6200.0, "Food expenses", month_start + timedelta(days=3), 0),
        (3, 3, -2500.0, "Shopping essentials", month_start + timedelta(days=7), 0),
        (3, 6, -1300.0, "Transport", month_start + timedelta(days=8), 0),
        (1, 1, 90000.0, "Admin salary", month_start + timedelta(days=1), 0),
        (1, 2, -3000.0, "Team lunch", month_start + timedelta(days=5), 0),
    ]
    cur.executemany(
        "INSERT INTO transactions (user_id, category_id, amount, description, date, is_deleted) VALUES (?, ?, ?, ?, ?, ?)",
        txns,
    )

    cur.executemany(
        "INSERT INTO budgets (user_id, category_id, amount, period, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (2, None, 32000.0, "monthly", month_start.date(), (month_start + timedelta(days=30)).date()),
            (3, None, 24000.0, "monthly", month_start.date(), (month_start + timedelta(days=30)).date()),
        ],
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {db_name} with tenant-isolated admin/user test data")


if __name__ == "__main__":
    main()
