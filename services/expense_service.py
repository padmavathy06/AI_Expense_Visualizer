import io
import csv
import calendar
from datetime import date, timedelta, datetime
from database import get_db_connection
from services import account_service, subscription_service, goal_service, analytics_service

CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Education", "Health", "Entertainment", "Other"]
PAYMENT_METHODS = ["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def get_available_years(user_id=None):
    """Returns a selectable multi-year range."""
    current_y = date.today().year
    years_set = set(range(current_y - 5, current_y + 6))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if user_id is not None:
            cursor.execute("SELECT DISTINCT YEAR(expense_date) as y FROM expenses WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("SELECT DISTINCT YEAR(expense_date) as y FROM expenses")
        for r in cursor.fetchall():
            if r.get("y"):
                years_set.add(int(r["y"]))
    except Exception:
        pass
    cursor.close()
    conn.close()

    return sorted(list(years_set), reverse=True)


def get_available_months(target_year=None):
    """
    Returns ALL 12 months from January to December for the given year.
    """
    current_year = date.today().year if not target_year else int(target_year)

    months_list = []
    for month_num in range(1, 13):
        m_key = f"{current_year}-{month_num:02d}"
        m_name = MONTH_NAMES[month_num - 1]
        m_label = f"{m_name} {current_year}"

        months_list.append({
            "key": m_key,
            "month_num": month_num,
            "month_name": m_name,
            "year": current_year,
            "label": m_label
        })

    return months_list


def get_common_dashboard_data(target_year=None, target_month=None, target_date=None, user_id=None):
    """
    Fetches clean dashboard metrics based on selected date or month, strictly isolated for user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    today_iso = date.today().isoformat()
    selected_date_str = target_date.strip() if target_date else ""

    if selected_date_str:
        try:
            parsed_d = datetime.strptime(selected_date_str, "%Y-%m-%d")
            selected_month_key = parsed_d.strftime("%Y-%m")
            current_year = parsed_d.year
        except Exception:
            selected_month_key = date.today().strftime("%Y-%m")
            current_year = date.today().year
            selected_date_str = today_iso
    elif target_month and target_month != "all":
        selected_month_key = target_month
        try:
            current_year = int(target_month[:4])
        except Exception:
            current_year = date.today().year
        selected_date_str = f"{selected_month_key}-01"
    else:
        selected_month_key = "all" if target_month == "all" else date.today().strftime("%Y-%m")
        current_year = int(target_year) if target_year else date.today().year
        if not selected_date_str and selected_month_key != "all":
            selected_date_str = today_iso

    # User isolation condition helper
    user_cond = "user_id = %s" if user_id is not None else "1=1"
    user_param = [user_id] if user_id is not None else []

    # 1. Total All-Time Spend
    cursor.execute(f"SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count FROM expenses WHERE {user_cond}", tuple(user_param))
    total_row = cursor.fetchone()
    total_expenses = float(total_row["total"]) if total_row else 0.0
    transaction_count = int(total_row["count"]) if total_row else 0

    # 2. Selected Month / Period Spend
    if selected_month_key == "all":
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) AS monthly_total, COUNT(*) AS count
            FROM expenses
            WHERE {user_cond} AND YEAR(expense_date) = %s
        """, tuple(user_param + [current_year]))
    else:
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) AS monthly_total, COUNT(*) AS count
            FROM expenses
            WHERE {user_cond} AND DATE_FORMAT(expense_date, '%Y-%m') = %s
        """, tuple(user_param + [selected_month_key]))

    month_row = cursor.fetchone()
    monthly_expenses = float(month_row["monthly_total"]) if month_row else 0.0
    monthly_count = int(month_row["count"]) if month_row else 0

    # 3. Transactions for selected period
    if selected_month_key == "all":
        cursor.execute(f"""
            SELECT *
            FROM expenses
            WHERE {user_cond} AND YEAR(expense_date) = %s
            ORDER BY expense_date DESC, id DESC
            LIMIT 15
        """, tuple(user_param + [current_year]))
    else:
        cursor.execute(f"""
            SELECT *
            FROM expenses
            WHERE {user_cond} AND DATE_FORMAT(expense_date, '%Y-%m') = %s
            ORDER BY expense_date DESC, id DESC
        """, tuple(user_param + [selected_month_key]))

    recent_expenses = cursor.fetchall()
    for e in recent_expenses:
        e["amount"] = float(e.get("amount") or 0.0)

    # 4. Category-wise Distribution
    if selected_month_key == "all":
        cursor.execute(f"""
            SELECT category, SUM(amount) AS total, COUNT(*) as count
            FROM expenses
            WHERE {user_cond} AND YEAR(expense_date) = %s
            GROUP BY category
            ORDER BY total DESC
        """, tuple(user_param + [current_year]))
    else:
        cursor.execute(f"""
            SELECT category, SUM(amount) AS total, COUNT(*) as count
            FROM expenses
            WHERE {user_cond} AND DATE_FORMAT(expense_date, '%Y-%m') = %s
            GROUP BY category
            ORDER BY total DESC
        """, tuple(user_param + [selected_month_key]))

    category_data = cursor.fetchall()
    for c in category_data:
        c["total"] = float(c.get("total") or 0.0)

    # 5. FULL 12-MONTH (January to December) Trajectory Chart Data
    cursor.execute(f"""
        SELECT
            MONTH(expense_date) AS month_num,
            SUM(amount) AS total,
            COUNT(*) as count
        FROM expenses
        WHERE {user_cond} AND YEAR(expense_date) = %s
        GROUP BY MONTH(expense_date)
        ORDER BY month_num ASC
    """, tuple(user_param + [current_year]))
    month_db_rows = cursor.fetchall()
    month_spend_map = {int(r["month_num"]): float(r["total"]) for r in month_db_rows}

    monthly_12_data = []
    for m_num in range(1, 13):
        m_name = MONTH_NAMES[m_num - 1]
        monthly_12_data.append({
            "month_num": m_num,
            "month": m_name,
            "month_key": f"{current_year}-{m_num:02d}",
            "total": month_spend_map.get(m_num, 0.0)
        })

    # 6. Payment Method Breakdown
    cursor.execute(f"""
        SELECT COALESCE(payment_method, 'Other') AS payment_method, SUM(amount) AS total
        FROM expenses
        WHERE {user_cond}
        GROUP BY payment_method
        ORDER BY total DESC
    """, tuple(user_param))
    payment_data = cursor.fetchall()
    for p in payment_data:
        p["total"] = float(p.get("total") or 0.0)

    # 7. Monthly Budget
    if user_id is not None:
        cursor.execute("SELECT monthly_budget FROM budget WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
    else:
        cursor.execute("SELECT monthly_budget FROM budget ORDER BY id DESC LIMIT 1")
    budget_row = cursor.fetchone()
    budget = float(budget_row["monthly_budget"]) if budget_row else 25000.00
    budget_remaining = budget - monthly_expenses

    # 8. Category Budgets
    if user_id is not None:
        cursor.execute("SELECT category, allocated_amount FROM category_budgets WHERE user_id = %s", (user_id,))
    else:
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

    # 9. Accounts, Subscriptions, Goals summaries
    net_worth_summary = account_service.get_net_worth_summary(user_id=user_id)
    sub_summary = subscription_service.get_subscription_summary(user_id=user_id)
    goals = goal_service.get_goals(user_id=user_id)
    compliance = analytics_service.get_50_30_20_compliance(category_data)

    all_12_months = get_available_months(current_year)
    available_years = get_available_years(user_id=user_id)

    if selected_month_key == "all":
        selected_month_label = f"Full Year {current_year}"
    else:
        try:
            dt = datetime.strptime(selected_month_key, "%Y-%m")
            selected_month_label = dt.strftime("%B %Y")
        except Exception:
            selected_month_label = selected_month_key

    return {
        "total_expenses": total_expenses,
        "monthly_expenses": monthly_expenses,
        "monthly_count": monthly_count,
        "transaction_count": transaction_count,
        "budget": budget,
        "budget_remaining": budget_remaining,
        "recent_expenses": recent_expenses,
        "category_data": category_data,
        "monthly_data": monthly_12_data,
        "payment_data": payment_data,
        "category_budget_comparison": category_budget_comparison,
        "net_worth": net_worth_summary["net_worth"],
        "total_assets": net_worth_summary["total_assets"],
        "liquid_assets": net_worth_summary["liquid_assets"],
        "liabilities": net_worth_summary["liabilities"],
        "accounts": net_worth_summary["accounts"],
        "sub_summary": sub_summary,
        "goals": goals[:4],
        "compliance": compliance,
        "all_12_months": all_12_months,
        "available_years": available_years,
        "current_year": current_year,
        "selected_month": selected_month_key,
        "selected_month_label": selected_month_label,
        "selected_date": selected_date_str
    }


def get_dashboard_data(user_id=None):
    return get_common_dashboard_data(user_id=user_id)


def get_filtered_expenses(user_id=None, search=None, category=None, payment_method=None,
                          start_date=None, end_date=None, target_month=None,
                          target_year=None, sort_by="expense_date", sort_order="DESC"):
    """Query expenses across all dates, months, years with full-text search and user isolation."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    conditions = []
    params = []

    if user_id is not None:
        conditions.append("user_id = %s")
        params.append(user_id)

    if target_month and target_month != "all":
        conditions.append("DATE_FORMAT(expense_date, '%Y-%m') = %s")
        params.append(target_month)

    if target_year and target_year != "all":
        conditions.append("YEAR(expense_date) = %s")
        params.append(target_year)

    if search:
        conditions.append("(description LIKE %s OR category LIKE %s OR payment_method LIKE %s)")
        p = f"%{search}%"
        params.extend([p, p, p])

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
    allowed_cols = {"expense_date": "expense_date", "amount": "amount", "category": "category", "id": "id"}
    col = allowed_cols.get(sort_by, "expense_date")
    order = "ASC" if sort_order.upper() == "ASC" else "DESC"

    query = f"""
        SELECT *
        FROM expenses
        {where_clause}
        ORDER BY {col} {order}, id DESC
    """
    cursor.execute(query, tuple(params) if params else None)
    results = cursor.fetchall()
    for r in results:
        r["amount"] = float(r.get("amount") or 0.0)

    cursor.close()
    conn.close()
    return results


def add_expense(amount, category, description, expense_date, payment_method, user_id=None):
    """Logs expense permanently associated with user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO expenses (user_id, amount, category, description, expense_date, payment_method)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (user_id, amount, category, description, expense_date, payment_method))

    cursor.execute("""
        INSERT INTO transactions (user_id, type, amount, category, description, transaction_date, payment_method)
        VALUES (%s, 'expense', %s, %s, %s, %s, %s)
    """, (user_id, amount, category, description, expense_date, payment_method))

    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def get_expense_by_id(expense_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if user_id is not None:
        cursor.execute("SELECT * FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
    else:
        cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
    row = cursor.fetchone()
    if row:
        row["amount"] = float(row.get("amount") or 0.0)
    cursor.close()
    conn.close()
    return row


def update_expense(expense_id, amount, category, description, expense_date, payment_method, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("""
            UPDATE expenses
            SET amount = %s, category = %s, description = %s, expense_date = %s, payment_method = %s
            WHERE id = %s AND user_id = %s
        """, (amount, category, description, expense_date, payment_method, expense_id, user_id))
    else:
        cursor.execute("""
            UPDATE expenses
            SET amount = %s, category = %s, description = %s, expense_date = %s, payment_method = %s
            WHERE id = %s
        """, (amount, category, description, expense_date, payment_method, expense_id))
    conn.commit()
    cursor.close()
    conn.close()


def delete_expense(expense_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
        cursor.execute("DELETE FROM transactions WHERE id = %s AND user_id = %s", (expense_id, user_id))
    else:
        cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        cursor.execute("DELETE FROM transactions WHERE id = %s", (expense_id,))
    conn.commit()
    cursor.close()
    conn.close()


def delete_all_expenses(user_id=None):
    """Wipes ALL recorded expenses and transactions for the specified user cleanly in 1 click."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("DELETE FROM expenses WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
    else:
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM transactions")
    conn.commit()
    cursor.close()
    conn.close()


def delete_multiple_expenses(id_list, user_id=None):
    """Deletes a selected list of expense IDs for the specified user."""
    if not id_list:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ", ".join(["%s"] * len(id_list))
    if user_id is not None:
        cursor.execute(f"DELETE FROM expenses WHERE id IN ({placeholders}) AND user_id = %s", tuple(id_list + [user_id]))
        cursor.execute(f"DELETE FROM transactions WHERE id IN ({placeholders}) AND user_id = %s", tuple(id_list + [user_id]))
    else:
        cursor.execute(f"DELETE FROM expenses WHERE id IN ({placeholders})", tuple(id_list))
        cursor.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", tuple(id_list))
    conn.commit()
    cursor.close()
    conn.close()


def set_monthly_budget(amount, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("INSERT INTO budget (user_id, monthly_budget) VALUES (%s, %s)", (user_id, amount))
    else:
        cursor.execute("INSERT INTO budget (monthly_budget) VALUES (%s)", (amount,))
    conn.commit()
    cursor.close()
    conn.close()


def set_category_budget(category, allocated_amount, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if conn.is_sqlite:
        cursor.execute("""
            INSERT INTO category_budgets (user_id, category, allocated_amount)
            VALUES (%s, %s, %s)
        """, (user_id, category, allocated_amount))
    else:
        cursor.execute("""
            INSERT INTO category_budgets (user_id, category, allocated_amount)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE allocated_amount = %s
        """, (user_id, category, allocated_amount, allocated_amount))
    conn.commit()
    cursor.close()
    conn.close()


def seed_sample_data(user_id=None):
    """Seeds the multi-dimensional ecosystem for the given user."""
    account_service.seed_default_accounts(user_id=user_id)
    subscription_service.seed_default_subscriptions(user_id=user_id)
    goal_service.seed_default_goals(user_id=user_id)

    sample_txs = [
        (85000.00, "Salary", "Monthly Tech Corp Salary", "2026-08-01", "Bank Transfer", "income"),
        (12000.00, "Freelance", "Client Web App Retainer", "2026-08-10", "UPI", "income"),
        (450.00, "Food", "Subway lunch combo", "2026-08-18", "UPI", "expense"),
        (1200.00, "Bills", "Airtel Fiber Broadband", "2026-08-15", "Credit Card", "expense"),
        (850.00, "Travel", "Uber Ride Downtown", "2026-08-19", "UPI", "expense"),
        (2400.00, "Shopping", "Amazon Ergonomic Keyboard", "2026-08-12", "Debit Card", "expense"),
        (650.00, "Entertainment", "PVR IMAX Movie Tickets", "2026-08-14", "Credit Card", "expense"),
        (4800.00, "Food", "Groceries at Nature Basket", "2026-07-28", "Credit Card", "expense"),
        (15000.00, "Bills", "Apartment Rent & Maintenance", "2026-07-05", "Net Banking", "expense"),
        (3500.00, "Health", "Cult.fit Annual Gym pass", "2026-06-20", "Credit Card", "expense"),
        (85000.00, "Salary", "Monthly Tech Corp Salary", "2026-07-01", "Bank Transfer", "income"),
        (1500.00, "Food", "Dinner with Family at Barbeque Nation", "2026-07-19", "UPI", "expense"),
        (320.00, "Travel", "Metro Smartcard Recharge", "2026-07-22", "UPI", "expense"),
        (18500.00, "Education", "Fullstack AI Certification Course", "2026-06-15", "Credit Card", "expense"),
        (2200.00, "Shopping", "Zara Linen Shirt", "2026-06-08", "Debit Card", "expense"),
        (85000.00, "Salary", "Monthly Tech Corp Salary", "2026-06-01", "Bank Transfer", "income"),
        (1400.00, "Bills", "Electricity Bill BESCOM", "2026-06-18", "Net Banking", "expense"),
        (550.00, "Food", "Starbucks Cold Brew & Croissant", "2026-08-20", "UPI", "expense")
    ]

    from services import transaction_service
    for amt, cat, desc, d, pm, t_type in sample_txs:
        transaction_service.add_transaction(amt, cat, desc, d, pm, txn_type=t_type, user_id=user_id)

    return len(sample_txs)


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
