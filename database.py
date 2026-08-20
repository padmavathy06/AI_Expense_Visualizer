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
    Connect to MySQL with automatic SQLite fallback if MySQL is unreachable.
    Returns a unified DB connection wrapper.
    """
    if DB_TYPE == "mysql":
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                connect_timeout=3
            )
            return DBWrapper(conn, is_sqlite=False)
        except Exception as e:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            return DBWrapper(conn, is_sqlite=True)
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        return DBWrapper(conn, is_sqlite=True)


def init_db():
    """Initialize ultra-deep financial tables and schemas."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if not conn.is_sqlite:
        # MySQL Schemas
        # 1. Accounts & Banking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
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

        # 5. Legacy & Compatibility Tables (expenses, budget, category_budgets, ai_chat_history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
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
                monthly_budget DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_budgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(100) NOT NULL UNIQUE,
                allocated_amount DECIMAL(10,2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                currency_symbol VARCHAR(10) NOT NULL DEFAULT '₹',
                currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
                ai_persona VARCHAR(50) NOT NULL DEFAULT 'Finley',
                theme VARCHAR(20) NOT NULL DEFAULT 'light'
            )
        """)

    else:
        # SQLite Schemas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                monthly_budget DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category VARCHAR(100) NOT NULL UNIQUE,
                allocated_amount DECIMAL(10,2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_symbol VARCHAR(10) NOT NULL DEFAULT '₹',
                currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
                ai_persona VARCHAR(50) NOT NULL DEFAULT 'Finley',
                theme VARCHAR(20) NOT NULL DEFAULT 'light'
            )
        """)

    conn.commit()
    cursor.close()
    conn.close()


# Auto-initialize tables
init_db()