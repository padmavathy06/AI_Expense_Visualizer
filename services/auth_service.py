import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection


def validate_email(email):
    """Validates standard email regex format."""
    if not email:
        return False
    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(email_regex, email.strip()) is not None


def validate_phone(phone):
    """Validates standard phone/mobile number format (10 to 15 digits)."""
    if not phone:
        return False
    clean_phone = re.sub(r"[\s\-\+\(\)]", "", phone.strip())
    return clean_phone.isdigit() and len(clean_phone) >= 10 and len(clean_phone) <= 15


def clean_phone_number(phone):
    """Normalizes phone number to clean 10-digit or full digit string."""
    if not phone:
        return ""
    clean = re.sub(r"[\s\-\+\(\)]", "", phone.strip())
    if len(clean) > 10 and clean.startswith("91"):
        return clean[-10:]
    return clean


def register_user(name, email, phone, password, avatar=None):
    """
    Registers a new user account directly without OTP verification.
    Hashes password, saves to database, and initializes starter accounts/budget.
    Returns: (user_dict, error_message)
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    phone = clean_phone_number(phone)
    password = (password or "").strip()
    avatar = avatar or ""

    if not name:
        return None, "Please enter your full name."
    if not email or not validate_email(email):
        return None, "Please enter a valid email address."
    if not phone or not validate_phone(phone):
        return None, "Please enter a valid 10-digit mobile number."
    if not password or len(password) < 6:
        return None, "Password must be at least 6 characters long."

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Check if email already exists
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return None, "An account with this email address already exists. Please log in."

    # 2. Check if phone already exists
    cursor.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return None, "An account with this mobile number already exists. Please log in."

    # 3. Hash password and insert user
    password_hash = generate_password_hash(password)

    cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, avatar, is_verified)
        VALUES (%s, %s, %s, %s, %s, 1)
    """, (name, email, phone, password_hash, avatar))
    user_id = cursor.lastrowid

    # 4. Initialize starter accounts
    starter_accounts = [
        ("Primary Bank Account", "Bank", 0.00, "INR", 0.00, "#4f46e5", "🏦"),
        ("Credit Card", "Credit Card", 0.00, "INR", 50000.00, "#f43f5e", "💳"),
        ("UPI Wallet", "Wallet", 0.00, "INR", 0.00, "#06b6d4", "📱"),
        ("Cash in Hand", "Cash", 0.00, "INR", 0.00, "#10b981", "💵")
    ]
    for acc_name, acc_type, bal, curr, limit, col, ico in starter_accounts:
        cursor.execute("""
            INSERT INTO accounts (user_id, name, type, balance, currency, card_limit, color, icon)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, acc_name, acc_type, bal, curr, limit, col, ico))

    # 5. Initialize default monthly budget
    cursor.execute("""
        INSERT INTO budget (user_id, monthly_budget)
        VALUES (%s, %s)
    """, (user_id, 25000.00))

    conn.commit()
    cursor.close()
    conn.close()

    user_data = {
        "id": user_id,
        "name": name,
        "email": email,
        "phone": phone,
        "avatar": avatar
    }
    return user_data, None


def authenticate_user(login_identifier, password):
    """
    Authenticates user via Email OR Mobile Number and password.
    Returns: user_dict on success, None on invalid credentials.
    """
    identifier = (login_identifier or "").strip().lower()
    password = (password or "").strip()

    if not identifier or not password:
        return None

    clean_phone = clean_phone_number(identifier)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, email, phone, password_hash, avatar, is_verified, created_at
        FROM users
        WHERE email = %s OR phone = %s
    """, (identifier, clean_phone if clean_phone else identifier))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return None

    if check_password_hash(user["password_hash"], password):
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "phone": user.get("phone") or "",
            "avatar": user.get("avatar") or "",
            "created_at": user.get("created_at")
        }
    return None


def get_user_by_id(user_id):
    """Retrieves user profile by ID."""
    if not user_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, phone, avatar, created_at FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        if not user.get("avatar"):
            user["avatar"] = ""
    return user


def update_user_profile(user_id, name, email, phone, avatar=None, new_password=None, current_password=None):
    """
    Updates user personal details, avatar, and handles password change.
    Returns: (updated_user_dict, error_message)
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    phone = clean_phone_number(phone)

    if not name:
        return None, "Name cannot be blank."
    if not email or not validate_email(email):
        return None, "Please enter a valid email address."
    if not phone or not validate_phone(phone):
        return None, "Please enter a valid 10-digit mobile number."

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Check if email or phone is taken by another user
    cursor.execute("SELECT id, email, phone FROM users WHERE (email = %s OR phone = %s) AND id != %s", (email, phone, user_id))
    conflict = cursor.fetchone()
    if conflict:
        cursor.close()
        conn.close()
        if conflict.get("email") == email:
            return None, "This email address is already in use by another account."
        else:
            return None, "This mobile number is already in use by another account."

    # 2. Check password change if requested
    if new_password:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        curr = cursor.fetchone()
        if not curr or not check_password_hash(curr["password_hash"], current_password or ""):
            cursor.close()
            conn.close()
            return None, "Current password is incorrect. Unable to update password."
        if len(new_password) < 6:
            cursor.close()
            conn.close()
            return None, "New password must be at least 6 characters."

        new_password_hash = generate_password_hash(new_password)
        if avatar is not None:
            cursor.execute("""
                UPDATE users
                SET name = %s, email = %s, phone = %s, avatar = %s, password_hash = %s
                WHERE id = %s
            """, (name, email, phone, avatar, new_password_hash, user_id))
        else:
            cursor.execute("""
                UPDATE users
                SET name = %s, email = %s, phone = %s, password_hash = %s
                WHERE id = %s
            """, (name, email, phone, new_password_hash, user_id))
    else:
        if avatar is not None:
            cursor.execute("""
                UPDATE users
                SET name = %s, email = %s, phone = %s, avatar = %s
                WHERE id = %s
            """, (name, email, phone, avatar, user_id))
        else:
            cursor.execute("""
                UPDATE users
                SET name = %s, email = %s, phone = %s
                WHERE id = %s
            """, (name, email, phone, user_id))

    conn.commit()

    # Fetch updated user object
    cursor.execute("SELECT id, name, email, phone, avatar, created_at FROM users WHERE id = %s", (user_id,))
    updated_user = cursor.fetchone()
    cursor.close()
    conn.close()

    return updated_user, None


def remove_user_avatar(user_id, app_root_path=None):
    """
    Deletes the physical avatar image from the server filesystem and resets user avatar in DB.
    Returns: (updated_user_dict, error_message)
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT avatar FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        return None, "User not found."

    old_avatar = user.get("avatar") or ""
    if old_avatar and app_root_path:
        clean_rel = old_avatar.lstrip("/").replace("/", os.sep)
        full_disk_path = os.path.join(app_root_path, clean_rel)
        try:
            if os.path.exists(full_disk_path):
                os.remove(full_disk_path)
        except Exception:
            pass

    cursor.execute("UPDATE users SET avatar = '' WHERE id = %s", (user_id,))
    conn.commit()

    cursor.execute("SELECT id, name, email, phone, avatar, created_at FROM users WHERE id = %s", (user_id,))
    updated_user = cursor.fetchone()
    cursor.close()
    conn.close()

    return updated_user, None
