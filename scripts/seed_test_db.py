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
            ("tnt_demo", "Priya Kapoor", "priya@test.local", "user", "active"),
            ("tnt_demo", "Arjun Mehta", "arjun@test.local", "user", "active"),
            ("tnt_other", "Other Tenant User", "other@test.local", "user", "active"),
        ],
    )

    cur.executemany(
        "INSERT INTO chatbot_tenant_users (tenant_id, user_id) VALUES (?, ?)",
        [("tnt_demo", 1), ("tnt_demo", 2), ("tnt_demo", 3), ("tnt_demo", 4), ("tnt_demo", 5), ("tnt_other", 6)],
    )

    credentials = [
        (1, "Admin@123", "salt-admin-01"),
        (2, "User@123", "salt-user-02"),
        (3, "User@123", "salt-user-03"),
        (4, "User@123", "salt-user-04"),
        (5, "User@123", "salt-user-05"),
        (6, "User@123", "salt-user-06"),
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
            ("Utilities", "expense"),
            ("Health", "expense"),
            ("Entertainment", "expense"),
            ("Investments", "income"),
        ],
    )

    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev2_month_start = (prev_month_start - timedelta(days=1)).replace(day=1)

    txns = [
        # John Doe (user_id=2) - healthy with increasing spending pressure
        (2, 1, 60000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (2, 2, -8500.0, "Dining and takeout", month_start + timedelta(days=3), 0),
        (2, 3, -4200.0, "Shopping", month_start + timedelta(days=6), 0),
        (2, 4, -15000.0, "House rent", month_start + timedelta(days=2), 0),
        (2, 6, -1800.0, "Metro and fuel", month_start + timedelta(days=5), 0),
        (2, 7, -3200.0, "Electricity and internet", month_start + timedelta(days=9), 0),
        (2, 9, -2200.0, "Weekend movies and outings", month_start + timedelta(days=10), 0),
        (2, 10, 5500.0, "Quarterly investment dividend", month_start + timedelta(days=11), 0),

        # Jane Smith (user_id=3) - strong earnings with moderate discretionary spend
        (3, 1, 45000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (3, 5, 12000.0, "Freelance project", month_start + timedelta(days=4), 0),
        (3, 2, -6200.0, "Food expenses", month_start + timedelta(days=3), 0),
        (3, 3, -2500.0, "Shopping essentials", month_start + timedelta(days=7), 0),
        (3, 6, -1300.0, "Transport", month_start + timedelta(days=8), 0),
        (3, 8, -1800.0, "Routine health checkup", month_start + timedelta(days=10), 0),
        (3, 7, -2400.0, "Utility bills", month_start + timedelta(days=11), 0),

        # Priya Kapoor (user_id=4) - high utilization and expense spikes
        (4, 1, 38000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (4, 2, -9100.0, "Dining and groceries", month_start + timedelta(days=2), 0),
        (4, 4, -13500.0, "Rent", month_start + timedelta(days=2), 0),
        (4, 3, -4700.0, "Unplanned shopping", month_start + timedelta(days=6), 0),
        (4, 9, -3600.0, "Concert and subscriptions", month_start + timedelta(days=8), 0),
        (4, 6, -1700.0, "Cab and commute", month_start + timedelta(days=9), 0),

        # Arjun Mehta (user_id=5) - negative balance scenario
        (5, 1, 30000.0, "Monthly salary", month_start + timedelta(days=1), 0),
        (5, 4, -14000.0, "Rent", month_start + timedelta(days=2), 0),
        (5, 2, -7600.0, "Food and dining", month_start + timedelta(days=4), 0),
        (5, 3, -6200.0, "Online shopping", month_start + timedelta(days=7), 0),
        (5, 7, -3900.0, "Utilities", month_start + timedelta(days=9), 0),
        (5, 8, -2400.0, "Medicines", month_start + timedelta(days=10), 0),
        (5, 6, -1800.0, "Travel", month_start + timedelta(days=12), 0),

        # Admin baseline (user_id=1)
        (1, 1, 90000.0, "Admin salary", month_start + timedelta(days=1), 0),
        (1, 2, -3000.0, "Team lunch", month_start + timedelta(days=5), 0),

        # Prior month variance for trend-sensitive prompts
        (2, 1, 60000.0, "Monthly salary", prev_month_start + timedelta(days=1), 0),
        (2, 4, -15000.0, "House rent", prev_month_start + timedelta(days=2), 0),
        (2, 2, -7300.0, "Dining and takeout", prev_month_start + timedelta(days=4), 0),
        (2, 7, -2800.0, "Utilities", prev_month_start + timedelta(days=7), 0),
        (3, 1, 45000.0, "Monthly salary", prev_month_start + timedelta(days=1), 0),
        (3, 5, 8000.0, "Freelance project", prev_month_start + timedelta(days=5), 0),
        (3, 2, -5400.0, "Food expenses", prev_month_start + timedelta(days=4), 0),
        (4, 1, 38000.0, "Monthly salary", prev_month_start + timedelta(days=1), 0),
        (4, 3, -5100.0, "Shopping", prev_month_start + timedelta(days=6), 0),
        (5, 1, 30000.0, "Monthly salary", prev_month_start + timedelta(days=1), 0),
        (5, 4, -14000.0, "Rent", prev_month_start + timedelta(days=2), 0),
        (5, 2, -6800.0, "Food and dining", prev_month_start + timedelta(days=4), 0),

        # Two months back baseline
        (2, 1, 58000.0, "Monthly salary", prev2_month_start + timedelta(days=1), 0),
        (2, 4, -15000.0, "House rent", prev2_month_start + timedelta(days=2), 0),
        (3, 1, 44000.0, "Monthly salary", prev2_month_start + timedelta(days=1), 0),
        (4, 1, 36000.0, "Monthly salary", prev2_month_start + timedelta(days=1), 0),
        (5, 1, 29000.0, "Monthly salary", prev2_month_start + timedelta(days=1), 0),
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
            (4, None, 28000.0, "monthly", month_start.date(), (month_start + timedelta(days=30)).date()),
            (5, None, 27000.0, "monthly", month_start.date(), (month_start + timedelta(days=30)).date()),
        ],
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {db_name} with tenant-isolated admin/user test data")


if __name__ == "__main__":
    main()
