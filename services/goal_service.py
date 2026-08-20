from datetime import date, datetime
from database import get_db_connection

DEFAULT_GOAL_ICONS = {
    "Emergency": "🛡️",
    "Tech": "💻",
    "Travel": "✈️",
    "Vehicle": "🚗",
    "House": "🏠",
    "General": "🎯"
}


def get_goals():
    """Fetches all savings goals with completion percentage and milestone status."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM financial_goals ORDER BY target_date ASC, id ASC")
    goals = cursor.fetchall()

    today = date.today()
    for g in goals:
        target = float(g.get("target_amount") or 1.0)
        current = float(g.get("current_amount") or 0.0)
        pct = (current / target) * 100.0 if target > 0 else 100.0
        g["target_amount"] = target
        g["current_amount"] = current
        g["percentage"] = round(min(100.0, max(0.0, pct)), 1)
        g["remaining_amount"] = round(max(0.0, target - current), 2)
        g["is_completed"] = current >= target

        # Calculate days until target
        try:
            t_date = g["target_date"]
            if isinstance(t_date, str):
                t_date = datetime.strptime(t_date, "%Y-%m-%d").date()
            g["days_remaining"] = max(0, (t_date - today).days)
        except Exception:
            g["days_remaining"] = 0

    cursor.close()
    conn.close()
    return goals


def create_goal(title, target_amount, current_amount=0.0, target_date=None,
                category="General", color="#10b981", icon=None):
    """Creates a financial savings goal."""
    if not target_date:
        from datetime import timedelta
        target_date = (date.today() + timedelta(days=180)).isoformat()
    if not icon:
        icon = DEFAULT_GOAL_ICONS.get(category, "🎯")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO financial_goals (title, target_amount, current_amount, target_date, category, color, icon, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'in_progress')
    """, (title, target_amount, current_amount, target_date, category, color, icon))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_goal(goal_id, title, target_amount, current_amount, target_date, category="General", color="#10b981", icon="🎯", status="in_progress"):
    """Updates existing goal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE financial_goals
        SET title = %s, target_amount = %s, current_amount = %s, target_date = %s, category = %s, color = %s, icon = %s, status = %s
        WHERE id = %s
    """, (title, target_amount, current_amount, target_date, category, color, icon, status, goal_id))
    conn.commit()
    cursor.close()
    conn.close()


def contribute_to_goal(goal_id, amount, from_account_id=None):
    """
    Deposits money towards a goal. Optionally deducts from a source bank account.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE financial_goals SET current_amount = current_amount + %s WHERE id = %s", (amount, goal_id))
        if from_account_id:
            cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_account_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def delete_goal(goal_id):
    """Deletes a financial goal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM financial_goals WHERE id = %s", (goal_id,))
    conn.commit()
    cursor.close()
    conn.close()


def seed_default_goals():
    """Seeds starter financial goals if none exist."""
    goals = get_goals()
    if not goals:
        from datetime import timedelta
        today = date.today()
        defaults = [
            ("6-Month Emergency Fund", 150000.00, 65000.00, (today + timedelta(days=120)).isoformat(), "Emergency", "#10b981", "🛡️"),
            ("MacBook Pro M3 Max", 185000.00, 110000.00, (today + timedelta(days=60)).isoformat(), "Tech", "#4f46e5", "💻"),
            ("Japan Autumn Vacation", 220000.00, 45000.00, (today + timedelta(days=240)).isoformat(), "Travel", "#f59e0b", "✈️"),
            ("Electric Vehicle Downpayment", 300000.00, 95000.00, (today + timedelta(days=365)).isoformat(), "Vehicle", "#06b6d4", "🚗")
        ]
        for title, target, current, t_date, cat, color, icon in defaults:
            create_goal(title, target, current, t_date, cat, color, icon)
