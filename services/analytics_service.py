from datetime import date, timedelta, datetime
from database import get_db_connection

NEEDS_CATEGORIES = ["Bills", "Health", "Education", "Food"]
WANTS_CATEGORIES = ["Shopping", "Entertainment", "Travel", "Other"]


def get_daily_heatmap_matrix(days=60, user_id=None):
    """
    Computes daily spending intensity matrix for the last N days for user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    start_date = (date.today() - timedelta(days=days)).isoformat()
    if user_id is not None:
        cursor.execute("""
            SELECT
                DATE_FORMAT(expense_date, '%Y-%m-%d') as dt,
                SUM(amount) as total,
                COUNT(*) as count
            FROM expenses
            WHERE expense_date >= %s AND user_id = %s
            GROUP BY DATE_FORMAT(expense_date, '%Y-%m-%d')
            ORDER BY dt ASC
        """, (start_date, user_id))
    else:
        cursor.execute("""
            SELECT
                DATE_FORMAT(expense_date, '%Y-%m-%d') as dt,
                SUM(amount) as total,
                COUNT(*) as count
            FROM expenses
            WHERE expense_date >= %s
            GROUP BY DATE_FORMAT(expense_date, '%Y-%m-%d')
            ORDER BY dt ASC
        """, (start_date,))
    rows = cursor.fetchall()
    spend_map = {r["dt"]: {"amount": float(r["total"]), "count": int(r["count"])} for r in rows}

    cursor.close()
    conn.close()

    heatmap = []
    max_spend = max([v["amount"] for v in spend_map.values()], default=1000.0)

    for i in range(days, -1, -1):
        dt_str = (date.today() - timedelta(days=i)).isoformat()
        item = spend_map.get(dt_str, {"amount": 0.0, "count": 0})
        amt = item["amount"]
        if amt == 0:
            level = 0
        elif amt < (max_spend * 0.25):
            level = 1
        elif amt < (max_spend * 0.50):
            level = 2
        elif amt < (max_spend * 0.75):
            level = 3
        else:
            level = 4

        heatmap.append({
            "date": dt_str,
            "amount": amt,
            "count": item["count"],
            "level": level
        })

    return heatmap


def get_cash_flow_trends(user_id=None):
    """
    Computes monthly Income vs Expenses vs Net Savings comparisons for user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if user_id is not None:
        cursor.execute("""
            SELECT
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
            FROM transactions
            WHERE user_id = %s
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month ASC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
            FROM transactions
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month ASC
        """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    trends = []
    for r in rows:
        inc = float(r.get("income") or 0.0)
        exp = float(r.get("expense") or 0.0)
        savings = inc - exp
        rate = (savings / inc * 100) if inc > 0 else 0.0
        trends.append({
            "month": r["month"],
            "income": inc,
            "expense": exp,
            "net_savings": savings,
            "savings_rate": round(rate, 1)
        })

    return trends


def get_50_30_20_compliance(category_data: list, monthly_income: float = 0.0, monthly_expenses: float = 0.0):
    """
    Audits actual spending breakdown against the 50/30/20 budget benchmark.
    """
    needs_total = 0.0
    wants_total = 0.0

    for cat_item in category_data:
        cat = cat_item.get("category", "")
        amt = float(cat_item.get("total", 0.0))
        if cat in NEEDS_CATEGORIES:
            needs_total += amt
        else:
            wants_total += amt

    total_spend = max(1.0, needs_total + wants_total)
    needs_pct = round((needs_total / total_spend) * 100, 1)
    wants_pct = round((wants_total / total_spend) * 100, 1)

    effective_income = max(monthly_income, total_spend * 1.25)
    savings_amount = max(0.0, effective_income - total_spend)
    savings_pct = round((savings_amount / effective_income) * 100, 1)

    return {
        "needs_amount": round(needs_total, 2),
        "needs_pct": needs_pct,
        "needs_target_pct": 50,
        "wants_amount": round(wants_total, 2),
        "wants_pct": wants_pct,
        "wants_target_pct": 30,
        "savings_amount": round(savings_amount, 2),
        "savings_pct": savings_pct,
        "savings_target_pct": 20,
        "effective_income": round(effective_income, 2)
    }
