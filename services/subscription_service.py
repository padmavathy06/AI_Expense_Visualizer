from datetime import date, datetime, timedelta
from database import get_db_connection

DEFAULT_SUB_ICONS = {
    "Entertainment": "🎬",
    "Bills": "⚡",
    "Education": "📚",
    "Health": "🏋️",
    "Shopping": "🛍️",
    "Other": "🔄"
}


def get_subscriptions(status_filter=None):
    """Fetches subscriptions with billing analytics and account link metadata."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT s.*, a.name as account_name, a.icon as account_icon
        FROM subscriptions s
        LEFT JOIN accounts a ON s.account_id = a.id
    """
    if status_filter and status_filter != "all":
        query += " WHERE s.status = %s"
        cursor.execute(query + " ORDER BY s.next_billing_date ASC", (status_filter,))
    else:
        cursor.execute(query + " ORDER BY s.next_billing_date ASC")

    subs = cursor.fetchall()
    today = date.today()

    for s in subs:
        s["amount"] = float(s.get("amount") or 0.0)
        # Calculate days until next renewal
        try:
            nb_date = s["next_billing_date"]
            if isinstance(nb_date, str):
                nb_date = datetime.strptime(nb_date, "%Y-%m-%d").date()
            delta = (nb_date - today).days
            s["days_remaining"] = delta
            s["is_due_soon"] = 0 <= delta <= 7
        except Exception:
            s["days_remaining"] = 0
            s["is_due_soon"] = False

    cursor.close()
    conn.close()
    return subs


def create_subscription(name, amount, category="Bills", billing_cycle="monthly",
                        next_billing_date=None, account_id=None, notes="", icon=None):
    """Creates a recurring subscription / bill record."""
    if not next_billing_date:
        next_billing_date = (date.today() + timedelta(days=30)).isoformat()
    if not icon:
        icon = DEFAULT_SUB_ICONS.get(category, "🔄")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions (name, amount, category, billing_cycle, next_billing_date, account_id, status, icon, notes)
        VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s)
    """, (name, amount, category, billing_cycle, next_billing_date, account_id, icon, notes))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_subscription(sub_id, name, amount, category, billing_cycle, next_billing_date, account_id=None, status="active", notes=""):
    """Updates existing subscription details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE subscriptions
        SET name = %s, amount = %s, category = %s, billing_cycle = %s, next_billing_date = %s, account_id = %s, status = %s, notes = %s
        WHERE id = %s
    """, (name, amount, category, billing_cycle, next_billing_date, account_id, status, notes, sub_id))
    conn.commit()
    cursor.close()
    conn.close()


def delete_subscription(sub_id):
    """Deletes a subscription record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE id = %s", (sub_id,))
    conn.commit()
    cursor.close()
    conn.close()


def get_subscription_summary():
    """
    Computes overall recurring expenses metrics:
    - Monthly recurring burn rate
    - Annualized recurring cost
    - Upcoming bills due in next 7-14 days
    """
    subs = get_subscriptions(status_filter="active")

    monthly_total = 0.0
    upcoming_due = []

    for s in subs:
        amt = float(s["amount"])
        cycle = s.get("billing_cycle", "monthly")
        if cycle == "monthly":
            monthly_total += amt
        elif cycle == "yearly":
            monthly_total += (amt / 12.0)
        elif cycle == "weekly":
            monthly_total += (amt * 4.33)

        if s.get("days_remaining", 999) <= 14:
            upcoming_due.append(s)

    annual_total = monthly_total * 12.0

    return {
        "active_count": len(subs),
        "monthly_recurring": round(monthly_total, 2),
        "annual_recurring": round(annual_total, 2),
        "upcoming_due": upcoming_due,
        "subscriptions": subs
    }


def seed_default_subscriptions():
    """Seeds realistic subscription services if table is empty."""
    subs = get_subscriptions()
    if not subs:
        today = date.today()
        defaults = [
            ("Netflix Premium 4K", 649.00, "Entertainment", "monthly", (today + timedelta(days=4)).isoformat(), "🎬", "Family sharing plan"),
            ("Spotify Individual", 119.00, "Entertainment", "monthly", (today + timedelta(days=11)).isoformat(), "🎵", "Music streaming"),
            ("Airtel Fiber Broadband", 1179.00, "Bills", "monthly", (today + timedelta(days=7)).isoformat(), "⚡", "300 Mbps unlimited home wifi"),
            ("Cult.fit Gym & Fitness", 12500.00, "Health", "yearly", (today + timedelta(days=75)).isoformat(), "🏋️", "Annual gym pass"),
            ("Google One 2TB Cloud", 6500.00, "Bills", "yearly", (today + timedelta(days=120)).isoformat(), "☁️", "Cloud storage & backup"),
            ("Amazon Prime Annual", 1499.00, "Shopping", "yearly", (today + timedelta(days=40)).isoformat(), "📦", "Fast delivery & Prime Video")
        ]
        for name, amt, cat, cycle, nb_date, icon, notes in defaults:
            create_subscription(name, amt, cat, cycle, nb_date, None, notes, icon)
