import os
import sqlite3
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "ai_expense_visualizer")
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")


class DBWrapper:
    """Wrapper that provides a consistent dict-cursor interface across MySQL and SQLite."""
    def __init__(self, raw_conn, is_sqlite=False):
        self.conn = raw_conn
        self.is_sqlite = is_sqlite

    def cursor(self, dictionary=True):
        if self.is_sqlite:
            self.conn.row_factory = sqlite3.Row
            return SQLiteDictCursor(self.conn.cursor())
        else:
            return self.conn.cursor(dictionary=dictionary)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


class SQLiteDictCursor:
    """Adapts sqlite3.Cursor to match mysql-connector dictionary cursor behaviors."""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        sqlite_query = query.replace("%s", "?")
        sqlite_query = sqlite_query.replace("CURDATE()", "date('now')")
        sqlite_query = sqlite_query.replace("MONTH(CURDATE())", "CAST(strftime('%m', 'now') AS INTEGER)")
        sqlite_query = sqlite_query.replace("YEAR(CURDATE())", "CAST(strftime('%Y', 'now') AS INTEGER)")
        sqlite_query = sqlite_query.replace("MONTH(expense_date)", "CAST(strftime('%m', expense_date) AS INTEGER)")
        sqlite_query = sqlite_query.replace("YEAR(expense_date)", "CAST(strftime('%Y', expense_date) AS INTEGER)")
        sqlite_query = sqlite_query.replace("MONTH(transaction_date)", "CAST(strftime('%m', transaction_date) AS INTEGER)")
        sqlite_query = sqlite_query.replace("YEAR(transaction_date)", "CAST(strftime('%Y', transaction_date) AS INTEGER)")
        sqlite_query = sqlite_query.replace("DATE_FORMAT(expense_date, '%Y-%m')", "strftime('%Y-%m', expense_date)")
        sqlite_query = sqlite_query.replace("DATE_FORMAT(expense_date, '%Y-%m-%d')", "strftime('%Y-%m-%d', expense_date)")
        sqlite_query = sqlite_query.replace("DATE_FORMAT(transaction_date, '%Y-%m')", "strftime('%Y-%m', transaction_date)")
        sqlite_query = sqlite_query.replace("DATE_FORMAT(transaction_date, '%Y-%m-%d')", "strftime('%Y-%m-%d', transaction_date)")

        if params is None:
            return self.cursor.execute(sqlite_query)
        return self.cursor.execute(sqlite_query, params)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.cursor.close()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount


def get_db_connection():
    """
    Connect to MySQL / PostgreSQL with automatic SQLite fallback if unavailable.
    Supports standard DB_HOST, DB_USER envs and cloud DATABASE_URL.
    Returns a unified DB connection wrapper.
    """
    db_url = os.getenv("DATABASE_URL", "").strip()

    if db_url.startswith("mysql://") or db_url.startswith("mysql+mysqlconnector://") or DB_TYPE == "mysql":
        try:
            import mysql.connector
            if db_url:
                conn = mysql.connector.connect(db_url)
            else:
                conn = mysql.connector.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    connect_timeout=3
                )
            return DBWrapper(conn, is_sqlite=False)
        except Exception:
            pass

    # Persistent SQLite database file fallback
    conn = sqlite3.connect(SQLITE_DB_PATH)
    return DBWrapper(conn, is_sqlite=True)


def init_db():
    """Initialize ultra-deep financial tables and schemas."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if not conn.is_sqlite:
        # MySQL Schemas
        # 0. Users & Authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL UNIQUE,
                phone VARCHAR(20) NULL,
                password_hash VARCHAR(255) NOT NULL,
                avatar VARCHAR(255) NULL DEFAULT '',
                is_verified BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_verifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phone VARCHAR(20) NOT NULL,
                email VARCHAR(150) NOT NULL,
                otp_code VARCHAR(10) NOT NULL,
                payload TEXT NOT NULL,
                attempts INT DEFAULT 0,
                last_sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 1. Accounts & Banking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL, -- 'Bank', 'Credit Card', 'Wallet', 'Cash', 'Investment'
                balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                currency VARCHAR(10) NOT NULL DEFAULT 'INR',
                card_limit DECIMAL(12,2) NULL DEFAULT 0.00,
                billing_day INT NULL DEFAULT 1,
                color VARCHAR(20) NULL DEFAULT '#4f46e5',
                icon VARCHAR(20) NULL DEFAULT '🏦',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Unified Transactions (Expense, Income, Transfer)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'expense', -- 'expense', 'income', 'transfer'
                account_id INT NULL,
                to_account_id INT NULL, -- for transfers
                amount DECIMAL(12,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                sub_category VARCHAR(100) NULL,
                description VARCHAR(255) NULL,
                merchant VARCHAR(100) NULL,
                transaction_date DATE NOT NULL,
                payment_method VARCHAR(50) NULL,
                tags VARCHAR(255) NULL,
                is_recurring BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Subscriptions & Recurring Bills
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                name VARCHAR(100) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT 'Bills',
                billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly', -- 'monthly', 'yearly', 'weekly'
                next_billing_date DATE NOT NULL,
                account_id INT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'paused', 'cancelled'
                icon VARCHAR(20) NULL DEFAULT '🔄',
                notes VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Financial Goals & Savings Pots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_goals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                title VARCHAR(150) NOT NULL,
                target_amount DECIMAL(12,2) NOT NULL,
                current_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                target_date DATE NOT NULL,
                category VARCHAR(50) NULL DEFAULT 'General',
                color VARCHAR(20) NULL DEFAULT '#10b981',
                icon VARCHAR(20) NULL DEFAULT '🎯',
                status VARCHAR(20) NOT NULL DEFAULT 'in_progress', -- 'in_progress', 'completed'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Expenses, budget, category_budgets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                description VARCHAR(255) NULL,
                expense_date DATE NOT NULL,
                payment_method VARCHAR(50) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                monthly_budget DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_budgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                category VARCHAR(100) NOT NULL,
                allocated_amount DECIMAL(10,2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                currency_symbol VARCHAR(10) NOT NULL DEFAULT '₹',
                currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
                ai_persona VARCHAR(50) NOT NULL DEFAULT 'Finley',
                theme VARCHAR(20) NOT NULL DEFAULT 'light'
            )
        """)

    else:
        # SQLite Schemas
        # 0. Users & Authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL UNIQUE,
                phone VARCHAR(20) NULL,
                password_hash VARCHAR(255) NOT NULL,
                avatar VARCHAR(255) NULL DEFAULT '',
                is_verified BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone VARCHAR(20) NOT NULL,
                email VARCHAR(150) NOT NULL,
                otp_code VARCHAR(10) NOT NULL,
                payload TEXT NOT NULL,
                attempts INT DEFAULT 0,
                last_sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                currency VARCHAR(10) NOT NULL DEFAULT 'INR',
                card_limit DECIMAL(12,2) NULL DEFAULT 0.00,
                billing_day INT NULL DEFAULT 1,
                color VARCHAR(20) NULL DEFAULT '#4f46e5',
                icon VARCHAR(20) NULL DEFAULT '🏦',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'expense',
                account_id INT NULL,
                to_account_id INT NULL,
                amount DECIMAL(12,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                sub_category VARCHAR(100) NULL,
                description VARCHAR(255) NULL,
                merchant VARCHAR(100) NULL,
                transaction_date DATE NOT NULL,
                payment_method VARCHAR(50) NULL,
                tags VARCHAR(255) NULL,
                is_recurring BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                name VARCHAR(100) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT 'Bills',
                billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly',
                next_billing_date DATE NOT NULL,
                account_id INT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                icon VARCHAR(20) NULL DEFAULT '🔄',
                notes VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                title VARCHAR(150) NOT NULL,
                target_amount DECIMAL(12,2) NOT NULL,
                current_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                target_date DATE NOT NULL,
                category VARCHAR(50) NULL DEFAULT 'General',
                color VARCHAR(20) NULL DEFAULT '#10b981',
                icon VARCHAR(20) NULL DEFAULT '🎯',
                status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                description VARCHAR(255) NULL,
                expense_date DATE NOT NULL,
                payment_method VARCHAR(50) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                monthly_budget DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                category VARCHAR(100) NOT NULL,
                allocated_amount DECIMAL(10,2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INT NULL,
                currency_symbol VARCHAR(10) NOT NULL DEFAULT '₹',
                currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
                ai_persona VARCHAR(50) NOT NULL DEFAULT 'Finley',
                theme VARCHAR(20) NOT NULL DEFAULT 'light'
            )
        """)

    # Safe column migration for existing tables
    tables_to_upgrade = [
        "accounts", "transactions", "subscriptions",
        "financial_goals", "expenses", "budget",
        "category_budgets", "user_settings"
    ]
    for table_name in tables_to_upgrade:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN user_id INT NULL")
        except Exception:
            pass

    # Safe migration for user columns
    user_cols_to_add = [
        ("phone", "VARCHAR(20) NULL"),
        ("avatar", "VARCHAR(255) NULL DEFAULT ''"),
        ("is_verified", "BOOLEAN DEFAULT 1")
    ]
    for col_name, col_type in user_cols_to_add:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    # Safe migration for otp_verifications
    otp_cols_to_add = [
        ("attempts", "INT DEFAULT 0"),
        ("last_sent_at", "DATETIME NULL")
    ]
    for col_name, col_type in otp_cols_to_add:
        try:
            cursor.execute(f"ALTER TABLE otp_verifications ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    conn.commit()
    cursor.close()
    conn.close()


# Auto-initialize tables
init_db()