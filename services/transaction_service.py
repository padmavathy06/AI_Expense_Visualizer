import csv
import io
from datetime import date
from database import get_db_connection
from services import ai_service

TRANSACTION_TYPES = ["expense", "income", "transfer"]
EXPENSE_CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Education", "Health", "Entertainment", "Other"]
INCOME_CATEGORIES = ["Salary", "Freelance", "Investment Returns", "Rental Income", "Gifts", "Cashback", "Other Income"]


def get_transactions(user_id=None, txn_type=None, search=None, category=None, account_id=None,
                     start_date=None, end_date=None, sort_by="transaction_date", sort_order="DESC"):
    """
    Queries unified transactions ledger with full-text search and user isolation.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    conditions = []
    params = []

    if user_id is not None:
        conditions.append("t.user_id = %s")
        params.append(user_id)

    if txn_type and txn_type != "all":
        conditions.append("t.type = %s")
        params.append(txn_type)

    if search:
        conditions.append("(t.description LIKE %s OR t.category LIKE %s OR t.merchant LIKE %s OR t.tags LIKE %s)")
        p = f"%{search}%"
        params.extend([p, p, p, p])

    if category and category != "all":
        conditions.append("t.category = %s")
        params.append(category)

    if account_id and account_id != "all":
        conditions.append("t.account_id = %s")
        params.append(account_id)

    if start_date:
        conditions.append("t.transaction_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("t.transaction_date <= %s")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    allowed_cols = {"transaction_date": "t.transaction_date", "amount": "t.amount", "category": "t.category", "id": "t.id"}
    col = allowed_cols.get(sort_by, "t.transaction_date")
    order = "ASC" if sort_order.upper() == "ASC" else "DESC"

    query = f"""
        SELECT t.*, a.name as account_name, a.icon as account_icon, a.type as account_type
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        {where_clause}
        ORDER BY {col} {order}, t.id DESC
    """
    cursor.execute(query, tuple(params) if params else None)
    txns = cursor.fetchall()

    for tx in txns:
        tx["amount"] = float(tx.get("amount") or 0.0)

    cursor.close()
    conn.close()
    return txns


def add_transaction(amount, category, description="", transaction_date=None,
                    payment_method="UPI", txn_type="expense", account_id=None,
                    merchant=None, tags=None, is_recurring=False, user_id=None):
    """
    Logs transaction and automatically updates account balances and legacy expense tables for user_id.
    """
    if not transaction_date:
        transaction_date = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Insert into unified transactions
    query = """
        INSERT INTO transactions (user_id, type, account_id, amount, category, description, merchant, transaction_date, payment_method, tags, is_recurring)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        user_id, txn_type, account_id, amount, category, description,
        merchant, transaction_date, payment_method, tags, 1 if is_recurring else 0
    ))
    new_id = cursor.lastrowid

    # 2. Update linked account balance if account_id is provided
    if account_id:
        if txn_type == "expense":
            cursor.execute("""
                UPDATE accounts
                SET balance = CASE
                    WHEN type = 'Credit Card' THEN balance + %s
                    ELSE balance - %s
                END
                WHERE id = %s
            """, (amount, amount, account_id))
        elif txn_type == "income":
            cursor.execute("""
                UPDATE accounts
                SET balance = CASE
                    WHEN type = 'Credit Card' THEN balance - %s
                    ELSE balance + %s
                END
                WHERE id = %s
            """, (amount, amount, account_id))

    # 3. Synchronize with expenses table
    if txn_type == "expense":
        cursor.execute("""
            INSERT INTO expenses (user_id, amount, category, description, expense_date, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, amount, category, description, transaction_date, payment_method))

    conn.commit()
    cursor.close()
    conn.close()
    return new_id


def delete_transaction(transaction_id, user_id=None):
    """Deletes transaction and reverts account balances."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if user_id is not None:
        cursor.execute("SELECT * FROM transactions WHERE id = %s AND user_id = %s", (transaction_id, user_id))
    else:
        cursor.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
    tx = cursor.fetchone()

    if tx:
        amount = float(tx["amount"])
        account_id = tx["account_id"]
        txn_type = tx["type"]

        if account_id:
            if txn_type == "expense":
                cursor.execute("""
                    UPDATE accounts
                    SET balance = CASE
                        WHEN type = 'Credit Card' THEN balance - %s
                        ELSE balance + %s
                    END
                    WHERE id = %s
                """, (amount, amount, account_id))
            elif txn_type == "income":
                cursor.execute("""
                    UPDATE accounts
                    SET balance = CASE
                        WHEN type = 'Credit Card' THEN balance + %s
                        ELSE balance - %s
                    END
                    WHERE id = %s
                """, (amount, amount, account_id))

        if user_id is not None:
            cursor.execute("DELETE FROM transactions WHERE id = %s AND user_id = %s", (transaction_id, user_id))
        else:
            cursor.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
        conn.commit()

    cursor.close()
    conn.close()


def parse_bank_statement_csv(csv_text_or_file):
    """
    Parses bank CSV statement and uses AI heuristic categorization to structure transactions.
    Supports statements from major banks (HDFC, SBI, ICICI, Chase, Amex, Generic).
    """
    if hasattr(csv_text_or_file, "read"):
        content = csv_text_or_file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
    else:
        content = csv_text_or_file

    lines = content.strip().splitlines()
    if not lines:
        return []

    reader = csv.reader(lines)
    header = next(reader, None)
    if not header:
        return []

    # Map column indexes flexibly
    header_lower = [h.strip().lower() for h in header]
    date_idx = -1
    desc_idx = -1
    amount_idx = -1
    type_idx = -1
    credit_idx = -1
    debit_idx = -1

    for idx, h in enumerate(header_lower):
        if any(k in h for k in ["date", "txn date", "transaction date", "value date"]):
            date_idx = idx
        elif any(k in h for k in ["description", "narration", "particulars", "details", "merchant"]):
            desc_idx = idx
        elif any(k in h for k in ["amount", "txn amount", "total"]):
            amount_idx = idx
        elif "debit" in h or "withdrawal" in h:
            debit_idx = idx
        elif "credit" in h or "deposit" in h:
            credit_idx = idx
        elif "type" in h or "dr/cr" in h:
            type_idx = idx

    parsed_txns = []
    for row in reader:
        if not row or len(row) < 2:
            continue
        try:
            # Extract date
            raw_date = row[date_idx].strip() if date_idx != -1 and date_idx < len(row) else date.today().isoformat()
            # Normalize date
            clean_date = raw_date.replace('/', '-')
            if len(clean_date) == 10 and clean_date[2] == '-' and clean_date[5] == '-':
                # Format: DD-MM-YYYY -> YYYY-MM-DD
                parts = clean_date.split('-')
                clean_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

            # Extract description
            desc = row[desc_idx].strip() if desc_idx != -1 and desc_idx < len(row) else "Bank Transaction"

            # Determine Amount and Type
            txn_type = "expense"
            amount = 0.0

            if debit_idx != -1 and credit_idx != -1:
                debit_val = row[debit_idx].replace(',', '').strip()
                credit_val = row[credit_idx].replace(',', '').strip()
                if debit_val and float(debit_val or 0) > 0:
                    amount = float(debit_val)
                    txn_type = "expense"
                elif credit_val and float(credit_val or 0) > 0:
                    amount = float(credit_val)
                    txn_type = "income"
            elif amount_idx != -1:
                amt_str = row[amount_idx].replace(',', '').replace('₹', '').replace('$', '').strip()
                if amt_str:
                    amount = abs(float(amt_str))
                    if type_idx != -1 and "cr" in row[type_idx].lower():
                        txn_type = "income"
                    elif float(amt_str) < 0:
                        txn_type = "expense"

            if amount > 0:
                nlp_res = ai_service.parse_natural_language_expense(desc)
                category = "Salary" if txn_type == "income" and "sal" in desc.lower() else (
                    "Income" if txn_type == "income" else nlp_res.get("category", "Other")
                )

                parsed_txns.append({
                    "transaction_date": clean_date,
                    "description": desc,
                    "amount": round(amount, 2),
                    "type": txn_type,
                    "category": category,
                    "payment_method": nlp_res.get("payment_method", "UPI")
                })
        except Exception:
            continue

    return parsed_txns
