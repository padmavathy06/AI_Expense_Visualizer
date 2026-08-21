import os
import uuid
from functools import wraps
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response, session, send_from_directory
from werkzeug.utils import secure_filename
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

import database
from services import (
    auth_service,
    expense_service,
    ai_service,
    account_service,
    transaction_service,
    subscription_service,
    goal_service,
    analytics_service
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-ai-expense-key-2026")
app.jinja_env.globals.update(min=min, max=max)

UPLOAD_AVATAR_FOLDER = os.path.join(app.root_path, "static", "uploads", "avatars")
os.makedirs(UPLOAD_AVATAR_FOLDER, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def allowed_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def get_canonical_site_url():
    """
    Returns the canonical public site URL for SEO, robots.txt, sitemap.xml, and canonical tags.
    Defaults to deployed URL: https://expense-visualizer-app.onrender.com
    """
    env_site_url = os.getenv("SITE_URL", "").strip()
    if env_site_url:
        return env_site_url.rstrip("/")
    
    # If deployed on Render or cloud host, detect from incoming request
    if request:
        host = (request.host or "").lower()
        if "127.0.0.1" not in host and "localhost" not in host and host:
            scheme = request.headers.get("X-Forwarded-Proto", request.scheme or "https")
            return f"{scheme}://{request.host}".rstrip("/")
            
    return "https://expense-visualizer-app.onrender.com"


# ============================================================================
# AUTHENTICATION DECORATOR & CONTEXT PROCESSOR
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))
        # Verify the user actually exists in the database
        user = auth_service.get_user_by_id(user_id)
        if not user:
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_global_seo_and_user():
    site_url = get_canonical_site_url()

    user_dict = None
    if "user_id" in session:
        user = auth_service.get_user_by_id(session.get("user_id"))
        if user:
            user_dict = user
            session["user_avatar"] = user.get("avatar") or ""
        else:
            user_dict = {
                "id": session.get("user_id"),
                "name": session.get("user_name"),
                "email": session.get("user_email"),
                "avatar": session.get("user_avatar", "")
            }

    return {
        "current_user": user_dict,
        "site_url": site_url,
        "site_name": "AI Expense Visualizer",
        "site_title": "AI Expense Visualizer | AI-Powered Expense Tracker",
        "site_tagline": "Track, analyze and understand your expenses with AI.",
        "site_description": "AI Expense Visualizer is an AI-powered expense tracker that helps users track, analyze, visualize, and understand their personal expenses.",
        "site_keywords": "AI Expense Visualizer, AI expense tracker, expense tracker, personal expense tracker, expense management, expense analytics, AI financial insights, spending analysis",
        "google_site_verification": os.getenv("GOOGLE_SITE_VERIFICATION", "")
    }


# ============================================================================
# SEARCH ENGINE OPTIMIZATION (ROBOTS.TXT & SITEMAP.XML)
# ============================================================================

@app.route("/robots.txt", methods=["GET"])
def robots_txt():
    site_url = get_canonical_site_url()
    content = f"""# robots.txt for AI Expense Visualizer
User-agent: *
Allow: /
Allow: /login
Allow: /register
Allow: /static/
Disallow: /transactions
Disallow: /expenses
Disallow: /accounts
Disallow: /subscriptions
Disallow: /goals
Disallow: /analytics
Disallow: /ai-insights
Disallow: /profile
Disallow: /import
Disallow: /add-expense
Disallow: /edit-expense/
Disallow: /delete-expense/
Disallow: /api/
Disallow: /logout

# Sitemap Location
Sitemap: {site_url}/sitemap.xml
"""
    response = Response(content, mimetype="text/plain")
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response


@app.route("/sitemap.xml", methods=["GET"])
def sitemap_xml():
    site_url = get_canonical_site_url()
    today = date.today().isoformat()
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{site_url}/</loc>
        <lastmod>{today}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{site_url}/login</loc>
        <lastmod>{today}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>{site_url}/register</loc>
        <lastmod>{today}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.8</priority>
    </url>
</urlset>"""
    response = Response(xml_content, mimetype="application/xml")
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response


# ============================================================================
# USER AUTHENTICATION & REGISTRATION
# ============================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return render_template("register.html")

        avatar_path = ""
        if "avatar" in request.files:
            file = request.files["avatar"]
            if file and file.filename and allowed_image_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()
                unique_filename = f"avatar_reg_{uuid.uuid4().hex[:10]}.{ext}"
                filepath = os.path.join(UPLOAD_AVATAR_FOLDER, unique_filename)
                file.save(filepath)
                avatar_path = f"/static/uploads/avatars/{unique_filename}"

        user, err = auth_service.register_user(name, email, phone, password, avatar=avatar_path)
        if err:
            flash(err, "error")
            return render_template("register.html")

        # Auto login newly registered user
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_avatar"] = user.get("avatar", "")
        flash(f"Account created successfully! Welcome to your personal dashboard, {user['name']}.", "success")
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = auth_service.authenticate_user(identifier, password)
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_avatar"] = user.get("avatar", "")
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid email/mobile number or password. Please try again.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))


# ============================================================================
# USER PROFILE & SETTINGS
# ============================================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session.get("user_id")
    user = auth_service.get_user_by_id(user_id)

    if request.method == "POST":
        action_type = request.form.get("action_type", "update_info")

        if action_type == "update_info":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            new_phone = request.form.get("phone", "").strip()

            avatar_path = None
            if "avatar" in request.files:
                file = request.files["avatar"]
                if file and file.filename and allowed_image_file(file.filename):
                    ext = file.filename.rsplit(".", 1)[1].lower()
                    unique_filename = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
                    filepath = os.path.join(UPLOAD_AVATAR_FOLDER, unique_filename)
                    file.save(filepath)
                    avatar_path = f"/static/uploads/avatars/{unique_filename}"

            updated_user, err = auth_service.update_user_profile(
                user_id=user_id,
                name=name,
                email=email,
                phone=new_phone,
                avatar=avatar_path
            )
            if err:
                flash(err, "error")
            else:
                session["user_name"] = updated_user["name"]
                session["user_email"] = updated_user["email"]
                if updated_user.get("avatar") is not None:
                    session["user_avatar"] = updated_user.get("avatar", "")
                flash("Profile details updated successfully!", "success")
            return redirect(url_for("profile"))

        elif action_type == "change_password":
            current_pass = request.form.get("current_password", "").strip()
            new_pass = request.form.get("new_password", "").strip()
            confirm_pass = request.form.get("confirm_password", "").strip()

            if new_pass != confirm_pass:
                flash("New passwords do not match.", "error")
                return redirect(url_for("profile"))

            updated_user, err = auth_service.update_user_profile(
                user_id=user_id,
                name=user["name"],
                email=user["email"],
                phone=user.get("phone") or "",
                new_password=new_pass,
                current_password=current_pass
            )
            if err:
                flash(err, "error")
            else:
                flash("Password changed successfully!", "success")
            return redirect(url_for("profile"))

        elif action_type == "remove_avatar":
            updated_user, err = auth_service.remove_user_avatar(user_id, app_root_path=app.root_path)
            if err:
                flash(err, "error")
            else:
                session["user_avatar"] = ""
                flash("Profile picture removed successfully.", "success")
            return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/profile/remove-avatar", methods=["POST"])
@login_required
def remove_avatar():
    user_id = session.get("user_id")
    updated_user, err = auth_service.remove_user_avatar(user_id, app_root_path=app.root_path)
    if err:
        flash(err, "error")
    else:
        session["user_avatar"] = ""
        flash("Profile picture removed successfully.", "success")
    return redirect(url_for("profile"))


# ============================================================================
# 1. EXECUTIVE COMMON DASHBOARD (With Calendar Date/Month Picker)
# ============================================================================

@app.route("/")
@login_required
def home():
    user_id = session.get("user_id")
    selected_date = request.args.get("date", "").strip()
    selected_month = request.args.get("month", "").strip()
    selected_year = request.args.get("year", str(date.today().year)).strip()

    target_year_int = int(selected_year) if selected_year.isdigit() else date.today().year

    data = expense_service.get_common_dashboard_data(
        target_year=target_year_int,
        target_month=selected_month if selected_month else None,
        target_date=selected_date if selected_date else None,
        user_id=user_id
    )

    # AI Health Analysis
    ai_analysis = ai_service.analyze_spending(
        expenses=data["recent_expenses"],
        budget=data["budget"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"]
    )

    return render_template(
        "index.html",
        net_worth=data["net_worth"],
        total_assets=data["total_assets"],
        liquid_assets=data["liquid_assets"],
        liabilities=data["liabilities"],
        accounts=data["accounts"],
        sub_summary=data["sub_summary"],
        goals=data["goals"],
        compliance=data["compliance"],
        total_expenses=data["total_expenses"],
        monthly_expenses=data["monthly_expenses"],
        monthly_count=data["monthly_count"],
        transaction_count=data["transaction_count"],
        budget=data["budget"],
        budget_remaining=data["budget_remaining"],
        recent_expenses=data["recent_expenses"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"],
        payment_data=data["payment_data"],
        category_budget_comparison=data["category_budget_comparison"],
        ai_analysis=ai_analysis,
        all_12_months=data["all_12_months"],
        available_years=data["available_years"],
        selected_month=data["selected_month"],
        selected_month_label=data["selected_month_label"],
        selected_date=data["selected_date"],
        current_year=data["current_year"]
    )


# ============================================================================
# 2. UNIFIED TRANSACTIONS & LEDGER
# ============================================================================

@app.route("/transactions")
@app.route("/expenses")
@login_required
def transactions():
    user_id = session.get("user_id")
    search = request.args.get("search", "").strip()
    selected_type = request.args.get("type", "all")
    selected_category = request.args.get("category", "all")
    selected_account = request.args.get("account_id", "all")
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    selected_month = request.args.get("month", "all").strip()
    selected_year = request.args.get("year", str(date.today().year)).strip()

    target_year_int = int(selected_year) if selected_year.isdigit() else date.today().year

    tx_list = transaction_service.get_transactions(
        user_id=user_id,
        txn_type=selected_type if selected_type != "all" else None,
        account_id=int(selected_account) if selected_account.isdigit() else None,
        category=selected_category if selected_category != "all" else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        search=search if search else None
    )

    if selected_month and selected_month != "all":
        tx_list = [t for t in tx_list if str(t.get("transaction_date", ""))[:7] == selected_month]
    elif selected_year and selected_year != "all":
        tx_list = [t for t in tx_list if str(t.get("transaction_date", ""))[:4] == str(target_year_int)]

    total_income = sum(float(t["amount"]) for t in tx_list if t["type"] == "income")
    total_expense = sum(float(t["amount"]) for t in tx_list if t["type"] == "expense")
    net_flow = total_income - total_expense

    accounts = account_service.get_all_accounts(user_id=user_id)
    all_12_months = expense_service.get_available_months(target_year_int)
    available_years = expense_service.get_available_years(user_id=user_id)

    return render_template(
        "transactions.html",
        transactions=tx_list,
        total_income=total_income,
        total_expense=total_expense,
        net_flow=net_flow,
        accounts=accounts,
        categories=expense_service.CATEGORIES,
        income_categories=["Salary", "Freelance", "Dividends", "Investments", "Rental", "Refund", "Other"],
        all_12_months=all_12_months,
        available_years=available_years,
        search=search,
        selected_type=selected_type,
        selected_category=selected_category,
        selected_account=selected_account,
        selected_month=selected_month,
        selected_year=target_year_int,
        start_date=start_date,
        end_date=end_date
    )


# ============================================================================
# 3. MULTI-ACCOUNT BANKING & TRANSFERS HUB
# ============================================================================

@app.route("/accounts")
@login_required
def accounts():
    user_id = session.get("user_id")
    summary = account_service.get_net_worth_summary(user_id=user_id)
    return render_template(
        "accounts.html",
        accounts=summary["accounts"],
        net_worth=summary["net_worth"],
        total_assets=summary["total_assets"],
        liquid_assets=summary["liquid_assets"],
        liabilities=summary["liabilities"],
        account_types=account_service.ACCOUNT_TYPES
    )


@app.route("/api/accounts/create", methods=["POST"])
@login_required
def api_create_account():
    user_id = session.get("user_id")
    name = request.form.get("name", "").strip()
    acc_type = request.form.get("type", "Bank")
    balance = float(request.form.get("balance", 0.0))
    card_limit = float(request.form.get("card_limit", 0.0))

    if name:
        account_service.create_account(name, acc_type, balance, "INR", card_limit, user_id=user_id)
        flash(f"Account '{name}' linked successfully!", "success")
    return redirect(url_for("accounts"))


@app.route("/api/accounts/delete/<int:account_id>", methods=["POST"])
@login_required
def api_delete_account(account_id):
    user_id = session.get("user_id")
    account_service.delete_account(account_id, user_id=user_id)
    flash("Account removed.", "success")
    return redirect(url_for("accounts"))


@app.route("/api/accounts/transfer", methods=["POST"])
@login_required
def api_transfer_funds():
    user_id = session.get("user_id")
    try:
        from_id = int(request.form.get("from_account_id"))
        to_id = int(request.form.get("to_account_id"))
        amount = float(request.form.get("amount", 0.0))
        notes = request.form.get("notes", "")

        if from_id == to_id:
            flash("Source and destination accounts must be different.", "error")
        elif amount <= 0:
            flash("Transfer amount must be positive.", "error")
        else:
            account_service.transfer_funds(from_id, to_id, amount, None, notes, user_id=user_id)
            flash(f"Transferred ₹{amount:,.2f} successfully!", "success")
    except Exception as e:
        flash(f"Transfer error: {str(e)}", "error")
    return redirect(request.referrer or url_for("accounts"))


# ============================================================================
# 4. SUBSCRIPTIONS & RECURRING BILLS
# ============================================================================

@app.route("/subscriptions")
@login_required
def subscriptions():
    user_id = session.get("user_id")
    summary = subscription_service.get_subscription_summary(user_id=user_id)
    accounts = account_service.get_all_accounts(user_id=user_id)
    return render_template(
        "subscriptions.html",
        subscriptions=summary["subscriptions"],
        monthly_recurring=summary["monthly_recurring"],
        annual_recurring=summary["annual_recurring"],
        active_count=summary["active_count"],
        upcoming_due=summary["upcoming_due"],
        accounts=accounts,
        categories=expense_service.CATEGORIES
    )


@app.route("/api/subscriptions/create", methods=["POST"])
@login_required
def api_create_subscription():
    user_id = session.get("user_id")
    name = request.form.get("name", "").strip()
    amount = float(request.form.get("amount", 0.0))
    cycle = request.form.get("billing_cycle", "monthly")
    next_date = request.form.get("next_billing_date", date.today().isoformat())
    notes = request.form.get("notes", "")
    category = request.form.get("category", "Bills")

    if name and amount > 0:
        subscription_service.create_subscription(name, amount, category, cycle, next_date, None, notes, user_id=user_id)
        flash(f"Subscription '{name}' added!", "success")
    return redirect(url_for("subscriptions"))


@app.route("/api/subscriptions/delete/<int:sub_id>", methods=["POST"])
@login_required
def api_delete_subscription(sub_id):
    user_id = session.get("user_id")
    subscription_service.delete_subscription(sub_id, user_id=user_id)
    flash("Subscription removed.", "success")
    return redirect(url_for("subscriptions"))


# ============================================================================
# 5. FINANCIAL GOALS & SAVINGS POTS
# ============================================================================

@app.route("/goals")
@login_required
def goals():
    user_id = session.get("user_id")
    all_goals = goal_service.get_goals(user_id=user_id)
    accounts = account_service.get_all_accounts(user_id=user_id)
    total_saved = sum(float(g["current_amount"]) for g in all_goals)
    total_target = sum(float(g["target_amount"]) for g in all_goals)
    overall_pct = round((total_saved / total_target * 100), 1) if total_target > 0 else 0.0

    return render_template(
        "goals.html",
        goals=all_goals,
        total_saved=total_saved,
        total_target=total_target,
        overall_pct=overall_pct,
        accounts=accounts
    )


@app.route("/api/goals/create", methods=["POST"])
@login_required
def api_create_goal():
    user_id = session.get("user_id")
    title = request.form.get("title", "").strip()
    target_amount = float(request.form.get("target_amount", 0.0))
    current_amount = float(request.form.get("current_amount", 0.0))
    target_date = request.form.get("target_date", date.today().isoformat())

    if title and target_amount > 0:
        goal_service.create_goal(title, target_amount, current_amount, target_date, user_id=user_id)
        flash(f"Goal '{title}' created!", "success")
    return redirect(url_for("goals"))


@app.route("/api/goals/contribute/<int:goal_id>", methods=["POST"])
@login_required
def api_contribute_goal(goal_id):
    user_id = session.get("user_id")
    amount = float(request.form.get("amount", 0.0))
    account_id = request.form.get("account_id")
    if amount > 0:
        goal_service.contribute_to_goal(goal_id, amount, int(account_id) if account_id and account_id.isdigit() else None, user_id=user_id)
        flash(f"Deposited ₹{amount:,.2f} to goal!", "success")
    return redirect(url_for("goals"))


@app.route("/api/goals/delete/<int:goal_id>", methods=["POST"])
@login_required
def api_delete_goal(goal_id):
    user_id = session.get("user_id")
    goal_service.delete_goal(goal_id, user_id=user_id)
    flash("Goal deleted.", "success")
    return redirect(url_for("goals"))


# ============================================================================
# 6. DEEP ANALYTICS & 70-DAY HEATMAP
# ============================================================================

@app.route("/analytics")
@login_required
def analytics():
    user_id = session.get("user_id")
    data = expense_service.get_common_dashboard_data(user_id=user_id)
    heatmap = analytics_service.get_daily_heatmap_matrix(days=70, user_id=user_id)
    cashflow_trends = analytics_service.get_cash_flow_trends(user_id=user_id)

    return render_template(
        "analytics.html",
        heatmap=heatmap,
        cashflow_trends=cashflow_trends,
        compliance=data["compliance"],
        payment_data=data["payment_data"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"]
    )


# ============================================================================
# 7. AI INSIGHTS & MULTI-PERSONA ADVISOR + MONTE CARLO LAB
# ============================================================================

@app.route("/ai-insights")
@login_required
def ai_insights():
    user_id = session.get("user_id")
    data = expense_service.get_common_dashboard_data(user_id=user_id)
    all_expenses = expense_service.get_filtered_expenses(user_id=user_id)

    analysis = ai_service.analyze_spending(
        expenses=all_expenses,
        budget=data["budget"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"]
    )

    starting_wealth = data["net_worth"] if data["net_worth"] > 0 else 50000.0
    monte_carlo = ai_service.simulate_monte_carlo_cashflow(
        starting_net_worth=starting_wealth,
        monthly_income=max(35000.0, data["monthly_expenses"] * 1.5),
        monthly_expenses=data["monthly_expenses"],
        months=12
    )

    return render_template(
        "ai_insights.html",
        analysis=analysis,
        budget=data["budget"],
        monthly_expenses=data["monthly_expenses"],
        total_expenses=data["total_expenses"],
        category_data=data["category_data"],
        monte_carlo=monte_carlo,
        personas=ai_service.PERSONAS
    )


# ============================================================================
# 8. BANK STATEMENT CSV IMPORTER
# ============================================================================

@app.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    user_id = session.get("user_id")
    accounts = account_service.get_all_accounts(user_id=user_id)
    if request.method == "POST":
        if "statement_file" not in request.files:
            flash("Please upload a CSV file.", "error")
            return redirect(url_for("import_csv"))

        file = request.files["statement_file"]
        if not file or not file.filename.endswith(".csv"):
            flash("Invalid file format. Please upload a .csv bank statement.", "error")
            return redirect(url_for("import_csv"))

        account_id = request.form.get("account_id")
        account_id = int(account_id) if account_id and account_id.isdigit() else None

        content = file.read().decode("utf-8", errors="ignore")
        txs = transaction_service.parse_bank_statement_csv(content)

        for t in txs:
            transaction_service.add_transaction(
                amount=t["amount"],
                category=t["category"],
                description=t["description"],
                transaction_date=t["transaction_date"],
                payment_method="Bank Transfer",
                txn_type=t["type"],
                account_id=account_id,
                user_id=user_id
            )

        flash(f"Successfully imported and categorized {len(txs)} transactions!", "success")
        return redirect(url_for("transactions"))

    return render_template("import.html", accounts=accounts)


# ============================================================================
# 9. EXPENSE CRUD & BULK ACTIONS
# ============================================================================

@app.route("/add-expense", methods=["GET", "POST"])
@login_required
def add_expense():
    user_id = session.get("user_id")
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            category = request.form["category"]
            expense_date = request.form.get("date", date.today().isoformat())
            payment_method = request.form.get("payment", "UPI")
            description = request.form.get("description", "").strip()

            expense_service.add_expense(amount, category, description, expense_date, payment_method, user_id=user_id)
            flash("Expense logged successfully!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            flash(f"Error adding expense: {str(e)}", "error")

    return render_template(
        "add_expense.html",
        categories=expense_service.CATEGORIES,
        payment_methods=expense_service.PAYMENT_METHODS,
        today=date.today().isoformat()
    )


@app.route("/edit-expense/<int:id>", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    user_id = session.get("user_id")
    expense = expense_service.get_expense_by_id(id, user_id=user_id)
    if not expense:
        flash("Expense not found", "error")
        return redirect(url_for("transactions"))

    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            category = request.form["category"]
            expense_date = request.form["date"]
            payment_method = request.form["payment"]
            description = request.form.get("description", "").strip()

            expense_service.update_expense(id, amount, category, description, expense_date, payment_method, user_id=user_id)
            flash("Expense updated!", "success")
            return redirect(url_for("transactions"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=expense_service.CATEGORIES,
        payment_methods=expense_service.PAYMENT_METHODS
    )


@app.route("/delete-expense/<int:id>", methods=["POST"])
@login_required
def delete_expense(id):
    user_id = session.get("user_id")
    try:
        expense_service.delete_expense(id, user_id=user_id)
        flash("Expense deleted.", "success")
    except Exception as e:
        flash(f"Error deleting: {str(e)}", "error")
    return redirect(request.referrer or url_for("transactions"))


@app.route("/delete-all-expenses", methods=["POST"])
@login_required
def delete_all_expenses():
    """Wipes all recorded expenses for current user."""
    user_id = session.get("user_id")
    try:
        expense_service.delete_all_expenses(user_id=user_id)
        flash("All expenses deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("home"))


@app.route("/delete-selected-expenses", methods=["POST"])
@login_required
def delete_selected_expenses():
    """Bulk deletes selected rows for current user."""
    user_id = session.get("user_id")
    try:
        ids_raw = request.form.getlist("selected_ids")
        if ids_raw:
            id_list = [int(i) for i in ids_raw if i.isdigit()]
            expense_service.delete_multiple_expenses(id_list, user_id=user_id)
            flash(f"Deleted {len(id_list)} selected expenses!", "success")
        else:
            flash("No expenses selected.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(request.referrer or url_for("transactions"))


# ============================================================================
# 10. REST APIS (AI Quick Add, Chat, Receipt, Seed Demo)
# ============================================================================

@app.route("/api/ai/quick-parse", methods=["POST"])
@login_required
def api_quick_parse():
    req_data = request.get_json(force=True, silent=True) or {}
    text = req_data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    parsed = ai_service.parse_natural_language_expense(text)
    return jsonify(parsed)


@app.route("/api/ai/quick-add", methods=["POST"])
@login_required
def api_quick_add():
    user_id = session.get("user_id")
    req_data = request.get_json(force=True, silent=True) or {}
    text = req_data.get("text", "").strip()

    if not text:
        return jsonify({"success": False, "error": "Please enter expense details."}), 400

    parsed = ai_service.parse_natural_language_expense(text)
    if parsed.get("amount", 0) > 0:
        new_id = expense_service.add_expense(
            amount=parsed["amount"],
            category=parsed["category"],
            description=parsed["description"],
            expense_date=parsed["expense_date"],
            payment_method=parsed["payment_method"],
            user_id=user_id
        )
        parsed["id"] = new_id
        return jsonify({"success": True, "expense": parsed})
    else:
        return jsonify({"success": False, "error": "Could not extract amount from text."}), 422


@app.route("/api/ai/chat", methods=["POST"])
@login_required
def api_ai_chat():
    user_id = session.get("user_id")
    req_data = request.get_json(force=True, silent=True) or {}
    user_message = req_data.get("message", "").strip()
    history = req_data.get("history", [])
    persona = req_data.get("persona", "Finley")

    data = expense_service.get_common_dashboard_data(user_id=user_id)
    reply = ai_service.chat_with_advisor(
        user_message=user_message,
        history=history,
        financial_context=data,
        persona=persona
    )
    return jsonify({"reply": reply})


@app.route("/api/ai/scan-receipt", methods=["POST"])
@login_required
def api_scan_receipt():
    if "receipt" not in request.files:
        return jsonify({"success": False, "error": "No receipt image provided"}), 400
    file = request.files["receipt"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400
    result = ai_service.scan_receipt_image(file)
    return jsonify(result)


@app.route("/api/export/csv")
@login_required
def api_export_csv():
    user_id = session.get("user_id")
    month = request.args.get("month", "all").strip()
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all")

    expenses = expense_service.get_filtered_expenses(
        user_id=user_id,
        search=search if search else None,
        category=category if category != "all" else None,
        target_month=month if month != "all" else None
    )

    csv_data = expense_service.export_expenses_to_csv(expenses)
    filename = f"expenses_{date.today().isoformat()}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@app.route("/set-budget", methods=["POST"])
@login_required
def set_budget():
    user_id = session.get("user_id")
    try:
        monthly_budget = float(request.form["monthly_budget"])
        expense_service.set_monthly_budget(monthly_budget, user_id=user_id)
        flash(f"Monthly budget updated to ₹{monthly_budget:,.2f}", "success")
    except Exception as e:
        flash(f"Invalid budget: {str(e)}", "error")
    return redirect(request.referrer or url_for("home"))


@app.route("/api/seed-demo-data", methods=["POST"])
@login_required
def api_seed_demo_data():
    """Populates realistic demo datasets for the current user."""
    user_id = session.get("user_id")
    count = expense_service.seed_sample_data(user_id=user_id)
    flash(f"Sample dataset loaded successfully ({count}+ records across accounts, subscriptions & goals)!", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)