import io
import csv
from datetime import date, timedelta
from database import get_db_connection
from services import account_service, subscription_service, goal_service

CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Education", "Health", "Entertainment", "Other"]
PAYMENT_METHODS = ["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking"]


def get_dashboard_data():
    """Fetches comprehensive KPIs and financial health metrics for the main dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Total Expenses
    cursor.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses")
    total_row = cursor.fetchone()
    total_expenses = float(total_row["total"]) if total_row else 0.0

    # 2. This Month Expenses
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) AS monthly_total
        FROM expenses
        WHERE MONTH(expense_date) = MONTH(CURDATE())
        AND YEAR(expense_date) = YEAR(CURDATE())
    """)
    monthly_row = cursor.fetchone()
    monthly_expenses = float(monthly_row["monthly_total"]) if monthly_row else 0.0

    # 3. Transaction Count
    cursor.execute("SELECT COUNT(*) AS transaction_count FROM expenses")
    count_row = cursor.fetchone()
    transaction_count = int(count_row["transaction_count"]) if count_row else 0

    # 4. Recent Expenses
    cursor.execute("""
        SELECT *
        FROM expenses
        ORDER BY expense_date DESC, id DESC
        LIMIT 6
    """)
    recent_expenses = cursor.fetchall()

    # 5. Category-wise Expenses
    cursor.execute("""
        SELECT category, SUM(amount) AS total, COUNT(*) as count
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
    """)
    category_data = cursor.fetchall()

    # 6. Monthly Trend
    cursor.execute("""
        SELECT
            DATE_FORMAT(expense_date, '%Y-%m') AS month,
            SUM(amount) AS total,
            COUNT(*) as count
        FROM expenses
        GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
        ORDER BY month ASC
    """)
    monthly_data = cursor.fetchall()

    # 7. Payment Method Breakdown
    cursor.execute("""
        SELECT COALESCE(payment_method, 'Other') AS payment_method, SUM(amount) AS total
        FROM expenses
        GROUP BY payment_method
        ORDER BY total DESC
    """)
    payment_data = cursor.fetchall()

    # 8. Monthly Budget
    cursor.execute("""
        SELECT monthly_budget
        FROM budget
        ORDER BY id DESC
        LIMIT 1
    """)
    budget_row = cursor.fetchone()
    budget = float(budget_row["monthly_budget"]) if budget_row else 25000.00
    budget_remaining = budget - monthly_expenses

    # 9. Category Budgets
    cursor.execute("SELECT category, allocated_amount FROM category_budgets")
    cat_budgets = {row["category"]: float(row["allocated_amount"]) for row in cursor.fetchall()}

    category_budget_comparison = []
    cat_spend_map = {item["category"]: float(item["total"]) for item in category_data}
    for cat in CATEGORIES:
        spent = cat_spend_map.get(cat, 0.0)
        allocated = cat_budgets.get(cat, 0.0)
        if allocated > 0 or spent > 0:
            pct = round((spent / allocated * 100), 1) if allocated > 0 else 100.0
            category_budget_comparison.append({
                "category": cat,
                "spent": spent,
                "allocated": allocated,
                "percentage": min(100.0, pct),
                "is_over": spent > allocated if allocated > 0 else False
            })

    cursor.close()
    conn.close()

    # 10. Net Worth & Subscriptions & Goals summaries
    net_worth_data = account_service.get_net_worth_summary()
    sub_summary = subscription_service.get_subscription_summary()
    goals = goal_service.get_goals()

    return {
        "total_expenses": total_expenses,
        "monthly_expenses": monthly_expenses,
        "transaction_count": transaction_count,
        "budget": budget,
        "budget_remaining": budget_remaining,
        "recent_expenses": recent_expenses,
        "category_data": category_data,
        "monthly_data": monthly_data,
        "payment_data": payment_data,
        "category_budget_comparison": category_budget_comparison,
        "net_worth": net_worth_data["net_worth"],
        "liquid_assets": net_worth_data["liquid_assets"],
        "total_assets": net_worth_data["total_assets"],
        "liabilities": net_worth_data["liabilities"],
        "accounts": net_worth_data["accounts"],
        "sub_summary": sub_summary,
        "goals": goals[:3]  # top 3 goals
    }


def get_filtered_expenses(search=None, category=None, payment_method=None,
                          start_date=None, end_date=None, sort_by="expense_date",
                          sort_order="DESC"):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    conditions = []
    params = []

    if search:
        conditions.append("(description LIKE %s OR category LIKE %s OR payment_method LIKE %s)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    if category and category != "all":
        conditions.append("category = %s")
        params.append(category)

    if payment_method and payment_method != "all":
        conditions.append("payment_method = %s")
        params.append(payment_method)

    if start_date:
        conditions.append("expense_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("expense_date <= %s")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    allowed_sort_cols = {"expense_date": "expense_date", "amount": "amount", "category": "category", "id": "id"}
    col = allowed_sort_cols.get(sort_by, "expense_date")
    order = "ASC" if sort_order.upper() == "ASC" else "DESC"

    query = f"""
        SELECT *
        FROM expenses
        {where_clause}
        ORDER BY {col} {order}, id DESC
    """
    cursor.execute(query, tuple(params) if params else None)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def add_expense(amount, category, description, expense_date, payment_method):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO expenses (amount, category, description, expense_date, payment_method)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (amount, category, description, expense_date, payment_method))

    # Also log to unified transactions table
    cursor.execute("""
        INSERT INTO transactions (type, amount, category, description, transaction_date, payment_method)
        VALUES ('expense', %s, %s, %s, %s, %s)
    """, (amount, category, description, expense_date, payment_method))

    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def get_expense_by_id(expense_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def update_expense(expense_id, amount, category, description, expense_date, payment_method):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE expenses
        SET amount = %s, category = %s, description = %s, expense_date = %s, payment_method = %s
        WHERE id = %s
    """, (amount, category, description, expense_date, payment_method, expense_id))
    conn.commit()
    cursor.close()
    conn.close()


def delete_expense(expense_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
    conn.commit()
    cursor.close()
    conn.close()


def set_monthly_budget(amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO budget (monthly_budget) VALUES (%s)", (amount,))
    conn.commit()
    cursor.close()
    conn.close()


def set_category_budget(category, allocated_amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    if conn.is_sqlite:
        cursor.execute("""
            INSERT INTO category_budgets (category, allocated_amount)
            VALUES (%s, %s)
            ON CONFLICT(category) DO UPDATE SET allocated_amount = %s
        """, (category, allocated_amount, allocated_amount))
    else:
        cursor.execute("""
            INSERT INTO category_budgets (category, allocated_amount)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE allocated_amount = %s
        """, (category, allocated_amount, allocated_amount))
    conn.commit()
    cursor.close()
    conn.close()


def export_expenses_to_csv(expenses):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date", "Category", "Amount (INR)", "Payment Method", "Description", "Created At"])
    for exp in expenses:
        writer.writerow([
            exp.get("id"),
            exp.get("expense_date"),
            exp.get("category"),
            exp.get("amount"),
            exp.get("payment_method"),
            exp.get("description", ""),
            exp.get("created_at", "")
        ])
    return output.getvalue()


def seed_sample_data():
    """Seeds the entire ultra-deep financial ecosystem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear old data
    cursor.execute("DELETE FROM expenses")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM budget")
    cursor.execute("DELETE FROM category_budgets")
    cursor.execute("DELETE FROM accounts")
    cursor.execute("DELETE FROM subscriptions")
    cursor.execute("DELETE FROM financial_goals")

    # Set Monthly Budget
    cursor.execute("INSERT INTO budget (monthly_budget) VALUES (%s)", (28000.00,))
    conn.commit()
    cursor.close()
    conn.close()

    # Seed Accounts, Subscriptions, Goals with their own clean transactions
    account_service.seed_default_accounts()
    subscription_service.seed_default_subscriptions()
    goal_service.seed_default_goals()

    # Re-open for category budgets & demo transactions
    conn = get_db_connection()
    cursor = conn.cursor()

    # Category Budgets
    sample_cat_budgets = [
        ("Food", 8000.00),
        ("Travel", 4500.00),
        ("Shopping", 6000.00),
        ("Bills", 5000.00),
        ("Entertainment", 3000.00),
        ("Health", 2500.00)
    ]
    for cat, amt in sample_cat_budgets:
        if conn.is_sqlite:
            cursor.execute("INSERT INTO category_budgets (category, allocated_amount) VALUES (%s, %s)", (cat, amt))
        else:
            cursor.execute("INSERT INTO category_budgets (category, allocated_amount) VALUES (%s, %s)", (cat, amt))

    # Realistic Transactions
    today = date.today()
    demo_expenses = [
        (450.00, "Food", "Lunch at Cafe Mocha with team", (today - timedelta(days=1)).isoformat(), "UPI"),
        (1250.00, "Shopping", "Amazon - Ergonomic mouse & keyboard pad", (today - timedelta(days=2)).isoformat(), "Credit Card"),
        (350.00, "Travel", "Uber cab to downtown meeting", (today - timedelta(days=3)).isoformat(), "UPI"),
        (2199.00, "Bills", "Airtel Fiber Broadband & mobile recharge", (today - timedelta(days=5)).isoformat(), "Net Banking"),
        (820.00, "Food", "Dinner with friends at Domino's", (today - timedelta(days=6)).isoformat(), "UPI"),
        (1500.00, "Health", "Monthly Gym Membership renewal", (today - timedelta(days=8)).isoformat(), "UPI"),
        (649.00, "Entertainment", "PVR Cinemas movie tickets", (today - timedelta(days=10)).isoformat(), "Credit Card"),
        (2800.00, "Shopping", "Myntra weekend fashion sale", (today - timedelta(days=12)).isoformat(), "Debit Card"),
        (550.00, "Food", "Supermarket grocery staples", (today - timedelta(days=14)).isoformat(), "UPI"),
        (400.00, "Travel", "Petrol refill for two-wheeler", (today - timedelta(days=16)).isoformat(), "Cash"),
        (1200.00, "Education", "Udemy Python & AI Masterclass course", (today - timedelta(days=18)).isoformat(), "Credit Card"),
        (3500.00, "Bills", "Electricity bill payment (BESCOM)", (today - timedelta(days=20)).isoformat(), "Net Banking"),
        (300.00, "Food", "Morning breakfast & filter coffee", (today - timedelta(days=22)).isoformat(), "Cash"),
        (180.00, "Travel", "Metro train smart card topup", (today - timedelta(days=25)).isoformat(), "UPI"),
        # Past months
        (950.00, "Food", "Barbeque Nation family buffet", (today - timedelta(days=34)).isoformat(), "Credit Card"),
        (4200.00, "Shopping", "Noise Smartwatch & earphones", (today - timedelta(days=38)).isoformat(), "Credit Card"),
        (2100.00, "Bills", "Water & maintenance quarterly dues", (today - timedelta(days=42)).isoformat(), "Net Banking"),
        (850.00, "Travel", "Outstation cab toll & fuel", (today - timedelta(days=45)).isoformat(), "Cash"),
        (1400.00, "Health", "Pharmacy prescription medicines", (today - timedelta(days=50)).isoformat(), "UPI"),
        (3200.00, "Bills", "Summer AC Electricity bill", (today - timedelta(days=65)).isoformat(), "Net Banking"),
        (1100.00, "Food", "Weekend restaurant dinner", (today - timedelta(days=70)).isoformat(), "UPI"),
        (2500.00, "Shopping", "Books & desk organizer", (today - timedelta(days=75)).isoformat(), "Credit Card"),
    ]

    for amt, cat, desc, exp_date, pm in demo_expenses:
        cursor.execute("""
            INSERT INTO expenses (amount, category, description, expense_date, payment_method)
            VALUES (%s, %s, %s, %s, %s)
        """, (amt, cat, desc, exp_date, pm))
        cursor.execute("""
            INSERT INTO transactions (type, amount, category, description, transaction_date, payment_method)
            VALUES ('expense', %s, %s, %s, %s, %s)
        """, (amt, cat, desc, exp_date, pm))

    # Add Salary and Freelance Income
    cursor.execute("""
        INSERT INTO transactions (type, amount, category, description, transaction_date, payment_method)
        VALUES ('income', 75000.00, 'Salary', 'Monthly Tech Corp Salary', %s, 'Net Banking')
    """, ((today - timedelta(days=20)).isoformat(),))
    cursor.execute("""
        INSERT INTO transactions (type, amount, category, description, transaction_date, payment_method)
        VALUES ('income', 75000.00, 'Salary', 'Monthly Tech Corp Salary', %s, 'Net Banking')
    """, ((today - timedelta(days=50)).isoformat(),))
    cursor.execute("""
        INSERT INTO transactions (type, amount, category, description, transaction_date, payment_method)
        VALUES ('income', 18000.00, 'Freelance', 'Fullstack Web App Contract', %s, 'UPI')
    """, ((today - timedelta(days=15)).isoformat(),))

    conn.commit()
    cursor.close()
    conn.close()
    return len(demo_expenses)
