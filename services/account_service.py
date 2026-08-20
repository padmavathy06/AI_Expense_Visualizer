from database import get_db_connection

ACCOUNT_TYPES = ["Bank", "Credit Card", "Wallet", "Cash", "Investment"]
DEFAULT_COLORS = {
    "Bank": "#4f46e5",
    "Credit Card": "#f43f5e",
    "Wallet": "#06b6d4",
    "Cash": "#10b981",
    "Investment": "#8b5cf6"
}
DEFAULT_ICONS = {
    "Bank": "🏦",
    "Credit Card": "💳",
    "Wallet": "📱",
    "Cash": "💵",
    "Investment": "📈"
}


def get_all_accounts():
    """Fetches all accounts with balance, credit utilization metrics, and summary data."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM accounts ORDER BY type ASC, id ASC")
    accounts = cursor.fetchall()

    for acc in accounts:
        acc["balance"] = float(acc.get("balance") or 0.0)
        acc["card_limit"] = float(acc.get("card_limit") or 0.0)
        if acc["type"] == "Credit Card" and acc["card_limit"] > 0:
            # For Credit Cards, balance is typically the owed amount (spent)
            utilized_pct = (acc["balance"] / acc["card_limit"]) * 100
            acc["utilization_pct"] = round(min(100.0, max(0.0, utilized_pct)), 1)
            acc["available_credit"] = max(0.0, acc["card_limit"] - acc["balance"])
        else:
            acc["utilization_pct"] = 0.0
            acc["available_credit"] = 0.0

    cursor.close()
    conn.close()
    return accounts


def get_account_by_id(account_id):
    """Retrieve single account record."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM accounts WHERE id = %s", (account_id,))
    acc = cursor.fetchone()
    cursor.close()
    conn.close()
    if acc:
        acc["balance"] = float(acc.get("balance") or 0.0)
        acc["card_limit"] = float(acc.get("card_limit") or 0.0)
    return acc


def create_account(name, type, balance=0.0, currency="INR", card_limit=0.0, billing_day=1, color=None, icon=None):
    """Creates a new banking or wallet account."""
    if not color:
        color = DEFAULT_COLORS.get(type, "#4f46e5")
    if not icon:
        icon = DEFAULT_ICONS.get(type, "🏦")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO accounts (name, type, balance, currency, card_limit, billing_day, color, icon)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, type, balance, currency, card_limit, billing_day, color, icon))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_account(account_id, name, type, balance, card_limit=0.0, billing_day=1, color=None, icon=None):
    """Updates existing account metadata and balance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE accounts
        SET name = %s, type = %s, balance = %s, card_limit = %s, billing_day = %s, color = %s, icon = %s
        WHERE id = %s
    """, (name, type, balance, card_limit, billing_day, color, icon, account_id))
    conn.commit()
    cursor.close()
    conn.close()


def delete_account(account_id):
    """Deletes an account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = %s", (account_id,))
    conn.commit()
    cursor.close()
    conn.close()


def transfer_funds(from_account_id, to_account_id, amount, transfer_date=None, notes=None):
    """Performs an atomic money transfer between two accounts."""
    if not transfer_date:
        from datetime import date
        transfer_date = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Deduct from source account
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_account_id))
        # Add to destination account
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_account_id))

        # Record transfer transaction in unified ledger
        cursor.execute("""
            INSERT INTO transactions (type, account_id, to_account_id, amount, category, description, transaction_date, payment_method)
            VALUES ('transfer', %s, %s, %s, 'Transfer', %s, %s, 'Bank Transfer')
        """, (from_account_id, to_account_id, amount, notes or "Account Transfer", transfer_date))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def get_net_worth_summary():
    """
    Computes real-time Net Worth breakdown:
    - Liquid Assets (Bank Accounts + Wallets + Cash)
    - Investments
    - Liabilities (Credit Card Dues)
    - Net Worth = Assets - Liabilities
    """
    accounts = get_all_accounts()

    liquid_assets = 0.0
    investments = 0.0
    liabilities = 0.0

    for acc in accounts:
        bal = float(acc["balance"])
        acc_type = acc["type"]
        if acc_type in ["Bank", "Wallet", "Cash"]:
            liquid_assets += bal
        elif acc_type == "Investment":
            investments += bal
        elif acc_type == "Credit Card":
            liabilities += bal

    total_assets = liquid_assets + investments
    net_worth = total_assets - liabilities

    return {
        "liquid_assets": round(liquid_assets, 2),
        "investments": round(investments, 2),
        "liabilities": round(liabilities, 2),
        "total_assets": round(total_assets, 2),
        "net_worth": round(net_worth, 2),
        "accounts": accounts
    }


def seed_default_accounts():
    """Initializes standard starter accounts if none exist."""
    accounts = get_all_accounts()
    if not accounts:
        defaults = [
            ("HDFC Salary Account", "Bank", 45000.00, "INR", 0.0, 1, "#4f46e5", "🏦"),
            ("ICICI Amazon Pay Card", "Credit Card", 4250.00, "INR", 150000.0, 15, "#f43f5e", "💳"),
            ("Paytm UPI Wallet", "Wallet", 3200.00, "INR", 0.0, 1, "#06b6d4", "📱"),
            ("Emergency Cash", "Cash", 5000.00, "INR", 0.0, 1, "#10b981", "💵"),
            ("Zerodha Mutual Funds", "Investment", 120000.00, "INR", 0.0, 1, "#8b5cf6", "📈")
        ]
        for name, atype, bal, curr, limit, day, color, icon in defaults:
            create_account(name, atype, bal, curr, limit, day, color, icon)
