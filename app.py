import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response
from dotenv import load_dotenv

import database
from services import expense_service, ai_service, account_service, transaction_service, subscription_service, goal_service, analytics_service

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-ai-expense-key-2026")


# ============================================================================
# 1. EXECUTIVE WEALTH DASHBOARD
# ============================================================================

@app.route("/")
def home():
    data = expense_service.get_dashboard_data()
    all_expenses = expense_service.get_filtered_expenses()

    ai_analysis = ai_service.analyze_spending(
        expenses=all_expenses,
        budget=data["budget"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"]
    )

    # 50-30-20 Compliance
    compliance = analytics_service.get_50_30_20_compliance(
        category_data=data["category_data"],
        monthly_income=data.get("monthly_expenses", 0) * 1.5,
        monthly_expenses=data["monthly_expenses"]
    )

    # Heatmap snippet (last 30 days)
    heatmap = analytics_service.get_daily_heatmap_matrix(days=30)

    return render_template(
        "index.html",
        total_expenses=data["total_expenses"],
        monthly_expenses=data["monthly_expenses"],
        transaction_count=data["transaction_count"],
        budget=data["budget"],
        budget_remaining=data["budget_remaining"],
        recent_expenses=data["recent_expenses"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"],
        payment_data=data["payment_data"],
        category_budget_comparison=data["category_budget_comparison"],
        net_worth=data["net_worth"],
        liquid_assets=data["liquid_assets"],
        total_assets=data["total_assets"],
        liabilities=data["liabilities"],
        accounts=data["accounts"],
        sub_summary=data["sub_summary"],
        goals=data["goals"],
        ai_analysis=ai_analysis,
        compliance=compliance,
        heatmap=heatmap
    )


# ============================================================================
# 2. UNIFIED TRANSACTIONS & LEDGER
# ============================================================================

@app.route("/transactions")
@app.route("/expenses")
def transactions():
    txn_type = request.args.get("type", "all")
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all")
    account_id = request.args.get("account_id", "all")
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    sort_by = request.args.get("sort_by", "transaction_date")
    sort_order = request.args.get("sort_order", "DESC")

    txn_list = transaction_service.get_transactions(
        txn_type=txn_type if txn_type != "all" else None,
        search=search if search else None,
        category=category if category != "all" else None,
        account_id=int(account_id) if account_id != "all" and account_id.isdigit() else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        sort_by=sort_by,
        sort_order=sort_order
    )

    accounts = account_service.get_all_accounts()
    total_income = sum(t["amount"] for t in txn_list if t["type"] == "income")
    total_expense = sum(t["amount"] for t in txn_list if t["type"] == "expense")
    net_flow = total_income - total_expense

    return render_template(
        "transactions.html",
        transactions=txn_list,
        accounts=accounts,
        total_income=total_income,
        total_expense=total_expense,
        net_flow=net_flow,
        categories=expense_service.CATEGORIES,
        income_categories=transaction_service.INCOME_CATEGORIES,
        payment_methods=expense_service.PAYMENT_METHODS,
        selected_type=txn_type,
        search=search,
        selected_category=category,
        selected_account=account_id,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order
    )


# ============================================================================
# 3. MULTI-ACCOUNT BANKING & WALLETS
# ============================================================================

@app.route("/accounts")
def accounts():
    summary = account_service.get_net_worth_summary()
    return render_template(
        "accounts.html",
        accounts=summary["accounts"],
        net_worth=summary["net_worth"],
        liquid_assets=summary["liquid_assets"],
        total_assets=summary["total_assets"],
        liabilities=summary["liabilities"],
        account_types=account_service.ACCOUNT_TYPES
    )


@app.route("/api/accounts/create", methods=["POST"])
def api_create_account():
    try:
        name = request.form["name"]
        acc_type = request.form["type"]
        balance = float(request.form.get("balance", 0.0))
        card_limit = float(request.form.get("card_limit", 0.0))
        color = request.form.get("color")
        icon = request.form.get("icon")

        account_service.create_account(name, acc_type, balance, "INR", card_limit, 1, color, icon)
        flash(f"Account '{name}' created successfully!", "success")
    except Exception as e:
        flash(f"Error creating account: {str(e)}", "error")
    return redirect(url_for("accounts"))


@app.route("/api/accounts/transfer", methods=["POST"])
def api_account_transfer():
    try:
        from_acc = int(request.form["from_account_id"])
        to_acc = int(request.form["to_account_id"])
        amount = float(request.form["amount"])
        notes = request.form.get("notes", "Inter-account Transfer")

        account_service.transfer_funds(from_acc, to_acc, amount, None, notes)
        flash(f"Transferred ₹{amount:,.2f} successfully!", "success")
    except Exception as e:
        flash(f"Error processing transfer: {str(e)}", "error")
    return redirect(request.referrer or url_for("accounts"))


@app.route("/api/accounts/delete/<int:id>", methods=["POST"])
def api_delete_account(id):
    try:
        account_service.delete_account(id)
        flash("Account removed.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("accounts"))


# ============================================================================
# 4. SUBSCRIPTIONS & RECURRING BILLS
# ============================================================================

@app.route("/subscriptions")
def subscriptions():
    summary = subscription_service.get_subscription_summary()
    accounts = account_service.get_all_accounts()
    return render_template(
        "subscriptions.html",
        subscriptions=summary["subscriptions"],
        active_count=summary["active_count"],
        monthly_recurring=summary["monthly_recurring"],
        annual_recurring=summary["annual_recurring"],
        upcoming_due=summary["upcoming_due"],
        accounts=accounts,
        categories=expense_service.CATEGORIES
    )


@app.route("/api/subscriptions/create", methods=["POST"])
def api_create_subscription():
    try:
        name = request.form["name"]
        amount = float(request.form["amount"])
        category = request.form.get("category", "Bills")
        cycle = request.form.get("billing_cycle", "monthly")
        next_date = request.form.get("next_billing_date")
        account_id = request.form.get("account_id")
        account_id = int(account_id) if account_id and account_id.isdigit() else None
        notes = request.form.get("notes", "")

        subscription_service.create_subscription(name, amount, category, cycle, next_date, account_id, notes)
        flash(f"Subscription '{name}' added!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("subscriptions"))


@app.route("/api/subscriptions/delete/<int:id>", methods=["POST"])
def api_delete_subscription(id):
    subscription_service.delete_subscription(id)
    flash("Subscription deleted.", "success")
    return redirect(url_for("subscriptions"))


# ============================================================================
# 5. FINANCIAL GOALS & SAVINGS POTS
# ============================================================================

@app.route("/goals")
def goals():
    all_goals = goal_service.get_goals()
    accounts = account_service.get_all_accounts()
    total_saved = sum(g["current_amount"] for g in all_goals)
    total_target = sum(g["target_amount"] for g in all_goals)
    overall_pct = round((total_saved / total_target * 100), 1) if total_target > 0 else 0

    return render_template(
        "goals.html",
        goals=all_goals,
        accounts=accounts,
        total_saved=total_saved,
        total_target=total_target,
        overall_pct=overall_pct
    )


@app.route("/api/goals/create", methods=["POST"])
def api_create_goal():
    try:
        title = request.form["title"]
        target = float(request.form["target_amount"])
        current = float(request.form.get("current_amount", 0.0))
        target_date = request.form["target_date"]
        category = request.form.get("category", "General")
        color = request.form.get("color", "#10b981")
        icon = request.form.get("icon", "🎯")

        goal_service.create_goal(title, target, current, target_date, category, color, icon)
        flash(f"Goal '{title}' created!", "success")
    except Exception as e:
        flash(f"Error creating goal: {str(e)}", "error")
    return redirect(url_for("goals"))


@app.route("/api/goals/contribute/<int:id>", methods=["POST"])
def api_contribute_goal(id):
    try:
        amount = float(request.form["amount"])
        account_id = request.form.get("account_id")
        account_id = int(account_id) if account_id and account_id.isdigit() else None

        goal_service.contribute_to_goal(id, amount, account_id)
        flash(f"Deposited ₹{amount:,.2f} towards goal!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("goals"))


@app.route("/api/goals/delete/<int:id>", methods=["POST"])
def api_delete_goal(id):
    goal_service.delete_goal(id)
    flash("Goal removed.", "success")
    return redirect(url_for("goals"))


# ============================================================================
# 6. DEEP ANALYTICS & HEATMAP SUITE
# ============================================================================

@app.route("/analytics")
def analytics():
    data = expense_service.get_dashboard_data()
    heatmap = analytics_service.get_daily_heatmap_matrix(days=70)
    cashflow_trends = analytics_service.get_cash_flow_trends()
    compliance = analytics_service.get_50_30_20_compliance(
        category_data=data["category_data"],
        monthly_income=data.get("monthly_expenses", 0) * 1.6,
        monthly_expenses=data["monthly_expenses"]
    )

    return render_template(
        "analytics.html",
        heatmap=heatmap,
        cashflow_trends=cashflow_trends,
        compliance=compliance,
        category_data=data["category_data"],
        payment_data=data["payment_data"],
        monthly_data=data["monthly_data"]
    )


# ============================================================================
# 7. AI INSIGHTS, MONTE CARLO & MULTI-PERSONA ADVISOR
# ============================================================================

@app.route("/ai-insights")
def ai_insights():
    data = expense_service.get_dashboard_data()
    all_expenses = expense_service.get_filtered_expenses()

    analysis = ai_service.analyze_spending(
        expenses=all_expenses,
        budget=data["budget"],
        category_data=data["category_data"],
        monthly_data=data["monthly_data"]
    )

    monte_carlo = ai_service.simulate_monte_carlo_cashflow(
        starting_net_worth=data["net_worth"] if data["net_worth"] > 0 else 50000.0,
        monthly_income=max(40000.0, data["monthly_expenses"] * 1.5),
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
def import_statement():
    accounts = account_service.get_all_accounts()
    if request.method == "POST":
        if "statement_file" not in request.files:
            flash("No CSV file selected.", "error")
            return redirect(url_for("import_statement"))

        file = request.files["statement_file"]
        if file.filename == "":
            flash("Empty filename.", "error")
            return redirect(url_for("import_statement"))

        target_account_id = request.form.get("account_id")
        target_account_id = int(target_account_id) if target_account_id and target_account_id.isdigit() else None

        parsed_txns = transaction_service.parse_bank_statement_csv(file)
        if not parsed_txns:
            flash("Could not detect valid transactions in the uploaded CSV format.", "error")
            return redirect(url_for("import_statement"))

        # Batch insert parsed transactions
        imported_count = 0
        for tx in parsed_txns:
            transaction_service.add_transaction(
                amount=tx["amount"],
                category=tx["category"],
                description=tx["description"],
                transaction_date=tx["transaction_date"],
                payment_method=tx["payment_method"],
                txn_type=tx["type"],
                account_id=target_account_id
            )
            imported_count += 1

        flash(f"Successfully imported and AI-categorized {imported_count} transactions!", "success")
        return redirect(url_for("transactions"))

    return render_template("import.html", accounts=accounts)


# ============================================================================
# 9. GENERAL REST API ENDPOINTS
# ============================================================================

@app.route("/api/ai/quick-parse", methods=["POST"])
def api_quick_parse():
    req_data = request.get_json(force=True, silent=True) or {}
    text = req_data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    parsed = ai_service.parse_natural_language_expense(text)
    return jsonify(parsed)


@app.route("/api/ai/quick-add", methods=["POST"])
def api_quick_add():
    req_data = request.get_json(force=True, silent=True) or {}
    text = req_data.get("text", "").strip()
    account_id = req_data.get("account_id")

    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400

    parsed = ai_service.parse_natural_language_expense(text)
    if parsed.get("amount", 0) > 0:
        new_id = transaction_service.add_transaction(
            amount=parsed["amount"],
            category=parsed["category"],
            description=parsed["description"],
            transaction_date=parsed["expense_date"],
            payment_method=parsed["payment_method"],
            txn_type="expense",
            account_id=account_id
        )
        parsed["id"] = new_id
        return jsonify({"success": True, "expense": parsed})
    else:
        return jsonify({"success": False, "error": "Could not extract expense amount.", "parsed": parsed}), 422


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    req_data = request.get_json(force=True, silent=True) or {}
    user_message = req_data.get("message", "").strip()
    history = req_data.get("history", [])
    persona = req_data.get("persona", "Finley")

    data = expense_service.get_dashboard_data()
    reply = ai_service.chat_with_advisor(
        user_message=user_message,
        history=history,
        financial_context=data,
        persona=persona
    )
    return jsonify({"reply": reply})


@app.route("/api/ai/scan-receipt", methods=["POST"])
def api_scan_receipt():
    if "receipt" not in request.files:
        return jsonify({"success": False, "error": "No receipt image provided"}), 400
    file = request.files["receipt"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400
    result = ai_service.scan_receipt_image(file)
    return jsonify(result)


@app.route("/api/export/csv")
def api_export_csv():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all")
    payment = request.args.get("payment", "all")
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    expenses = expense_service.get_filtered_expenses(
        search=search if search else None,
        category=category if category != "all" else None,
        payment_method=payment if payment != "all" else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )

    csv_data = expense_service.export_expenses_to_csv(expenses)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=financial_export_{date.today().isoformat()}.csv"}
    )


@app.route("/api/seed-demo-data", methods=["POST"])
def api_seed_demo():
    count = expense_service.seed_sample_data()
    flash(f"Successfully seeded {count} transactions, 5 accounts, 6 subscriptions, and 4 financial goals!", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/set-budget", methods=["POST"])
def set_budget():
    try:
        monthly_budget = float(request.form["monthly_budget"])
        expense_service.set_monthly_budget(monthly_budget)
        flash(f"Monthly budget updated to ₹{monthly_budget:,.2f}", "success")
    except Exception as e:
        flash(f"Invalid budget: {str(e)}", "error")
    return redirect(request.referrer or url_for("home"))


@app.route("/set-category-budget", methods=["POST"])
def set_category_budget():
    try:
        category = request.form["category"]
        amount = float(request.form["amount"])
        expense_service.set_category_budget(category, amount)
        flash(f"Budget for {category} updated to ₹{amount:,.2f}", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(request.referrer or url_for("home"))


@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():
    accounts = account_service.get_all_accounts()
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            category = request.form["category"]
            expense_date = request.form.get("date", date.today().isoformat())
            payment_method = request.form.get("payment", "UPI")
            description = request.form.get("description", "").strip()
            account_id = request.form.get("account_id")
            account_id = int(account_id) if account_id and account_id.isdigit() else None

            transaction_service.add_transaction(
                amount=amount,
                category=category,
                description=description,
                transaction_date=expense_date,
                payment_method=payment_method,
                txn_type="expense",
                account_id=account_id
            )
            flash("Expense logged successfully!", "success")
            return redirect(url_for("transactions"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    return render_template(
        "add_expense.html",
        categories=expense_service.CATEGORIES,
        payment_methods=expense_service.PAYMENT_METHODS,
        accounts=accounts,
        today=date.today().isoformat()
    )


@app.route("/edit-expense/<int:id>", methods=["GET", "POST"])
def edit_expense(id):
    expense = expense_service.get_expense_by_id(id)
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

            expense_service.update_expense(id, amount, category, description, expense_date, payment_method)
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
def delete_expense(id):
    transaction_service.delete_transaction(id)
    expense_service.delete_expense(id)
    flash("Expense deleted.", "success")
    return redirect(request.referrer or url_for("transactions"))


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    app.run(debug=True, port=5000)