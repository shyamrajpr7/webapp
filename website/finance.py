from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime
import csv
import io
import calendar
from . import db
from .models import Transaction, Budget, SpendingGoal

finance = Blueprint('finance', __name__)

EXPENSE_CATEGORIES = [
    'Food & Dining', 'Transportation', 'Housing', 'Utilities',
    'Entertainment', 'Shopping', 'Healthcare', 'Education', 'Other'
]
INCOME_CATEGORIES = [
    'Salary', 'Freelance', 'Investments', 'Business', 'Other'
]
CATEGORY_COLORS = {
    'Food & Dining': '#ef4444', 'Transportation': '#f97316', 'Housing': '#eab308',
    'Utilities': '#22c55e', 'Entertainment': '#3b82f6', 'Shopping': '#8b5cf6',
    'Healthcare': '#ec4899', 'Education': '#06b6d4', 'Other': '#6b7280',
    'Salary': '#22c55e', 'Freelance': '#3b82f6', 'Investments': '#8b5cf6',
    'Business': '#f97316'
}

@finance.route('/dashboard')
@login_required
def dashboard():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()

    if start_date and end_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d')
            ed = datetime.strptime(end_date, '%Y-%m-%d')
            monthly = [t for t in transactions if sd.date() <= t.date.date() <= ed.date()]
        except ValueError:
            monthly = [t for t in transactions if t.date.month == month and t.date.year == year]
    else:
        monthly = [t for t in transactions if t.date.month == month and t.date.year == year]

    income = sum(t.amount for t in monthly if t.type == 'income')
    expenses = sum(t.amount for t in monthly if t.type == 'expense')
    balance = income - expenses
    savings_rate = ((income - expenses) / income * 100) if income > 0 else 0

    income_count = sum(1 for t in monthly if t.type == 'income')
    expense_count = sum(1 for t in monthly if t.type == 'expense')

    today = now.date()
    today_txns = [t for t in monthly if t.date.date() == today]
    today_expenses = sum(t.amount for t in today_txns if t.type == 'expense')
    today_income = sum(t.amount for t in today_txns if t.type == 'income')
    today_count = len(today_txns)

    day_of_month = now.day
    days_in_month = calendar.monthrange(year, month)[1]
    days_left = days_in_month - day_of_month

    expense_transactions = [t for t in monthly if t.type == 'expense']

    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    budget_map = {b.category: b.amount for b in budgets}
    total_budget = sum(budget_map.values())

    remaining_budget = total_budget - expenses if total_budget > 0 else 0
    daily_allowance = remaining_budget / days_left if days_left > 0 and total_budget > 0 else 0

    avg_daily_expense = expenses / day_of_month if day_of_month > 0 else 0

    expected_pace = (total_budget * day_of_month / days_in_month) if total_budget > 0 and days_in_month > 0 else 0
    spending_pace_pct = (expenses / expected_pace * 100) if expected_pace > 0 else 0
    largest_expense = max(expense_transactions, key=lambda t: t.amount) if expense_transactions else None
    recurring_count = sum(1 for t in monthly if t.recurring)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_transactions = [t for t in transactions if t.date.month == prev_month and t.date.year == prev_year]
    prev_income = sum(t.amount for t in prev_transactions if t.type == 'income')
    prev_expenses = sum(t.amount for t in prev_transactions if t.type == 'expense')
    prev_balance = prev_income - prev_expenses

    def pct_change(current, previous):
        if previous == 0:
            return None if current == 0 else 100.0
        return ((current - previous) / previous) * 100

    comparison = {
        'income_change': pct_change(income, prev_income),
        'expense_change': pct_change(expenses, prev_expenses),
        'balance_change': pct_change(balance, prev_balance),
        'prev_income': prev_income,
        'prev_expenses': prev_expenses,
        'prev_balance': prev_balance,
    }

    expense_by_cat = {}
    for t in monthly:
        if t.type == 'expense':
            expense_by_cat[t.category] = expense_by_cat.get(t.category, 0) + t.amount

    category_counts = {}
    for t in expense_transactions:
        category_counts[t.category] = category_counts.get(t.category, 0) + 1
    most_active_category = max(category_counts, key=category_counts.get) if category_counts else None
    most_active_count = category_counts.get(most_active_category, 0) if most_active_category else 0

    summary_parts = []
    if income > 0 or expenses > 0:
        if income > 0:
            summary_parts.append(f"earned ${income:,.0f}")
        if expenses > 0:
            summary_parts.append(f"spent ${expenses:,.0f}")
        if balance >= 0 and income > 0:
            summary_parts.append(f"with a {savings_rate:.0f}% savings rate")
        elif balance < 0:
            summary_parts.append(f"overspending by ${abs(balance):,.0f}")
        if largest_expense:
            summary_parts.append(f"biggest expense was ${largest_expense.amount:,.0f} on {largest_expense.category}")
        if most_active_category and most_active_count > 1:
            summary_parts.append(f"most transactions in {most_active_category}")
    monthly_summary = f"This month you've {' '.join(summary_parts)}." if summary_parts else f"No activity recorded for {months[month - 1]} yet."

    top_categories = sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True)[:3]

    budget_usage_pct = (expenses / total_budget * 100) if total_budget > 0 else 0

    spending_goal = SpendingGoal.query.filter_by(
        user_id=current_user.id, month=month, year=year).first()
    goal_progress = 0
    if spending_goal and spending_goal.target_amount > 0:
        goal_progress = (expenses / spending_goal.target_amount * 100) if spending_goal.target_amount > 0 else 0

    spending_data = []

    spending_data = []
    for cat in EXPENSE_CATEGORIES:
        spent = expense_by_cat.get(cat, 0)
        budget = budget_map.get(cat, 0)
        spending_data.append({
            'category': cat, 'spent': spent, 'budget': budget,
            'color': CATEGORY_COLORS.get(cat, '#6b7280'),
            'percentage': min((spent / budget * 100), 100) if budget > 0 else 0
        })

    max_expense = max(expense_by_cat.values()) if expense_by_cat else 1
    chart_data = [{'category': cat, 'amount': expense_by_cat.get(cat, 0),
                    'color': CATEGORY_COLORS.get(cat, '#6b7280')}
                  for cat in EXPENSE_CATEGORIES if expense_by_cat.get(cat, 0) > 0]

    alerts = []
    for item in spending_data:
        if item['budget'] > 0:
            pct = (item['spent'] / item['budget']) * 100
            if pct >= 100:
                alerts.append({'category': item['category'], 'spent': item['spent'],
                    'budget': item['budget'], 'percentage': pct, 'level': 'exceeded'})
            elif pct >= 80:
                alerts.append({'category': item['category'], 'spent': item['spent'],
                    'budget': item['budget'], 'percentage': pct, 'level': 'warning'})

    recent = sorted(monthly, key=lambda t: (t.pinned, t.date), reverse=True)[:10]

    monthly_history = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        mt = [t for t in transactions if t.date.month == m and t.date.year == y]
        monthly_history.append({
            'month': months[m - 1][:3],
            'income': sum(t.amount for t in mt if t.type == 'income'),
            'expenses': sum(t.amount for t in mt if t.type == 'expense'),
        })

    all_vals = [h['income'] for h in monthly_history] + [h['expenses'] for h in monthly_history]
    bar_max = max(all_vals) if all_vals else 1

    return render_template('dashboard.html', user=current_user, transactions=recent,
        income=income, expenses=expenses, balance=balance,
        savings_rate=savings_rate, spending_data=spending_data, chart_data=chart_data,
        max_expense=max_expense, month=month, year=year, months=months,
        all_transactions=monthly, alerts=alerts, comparison=comparison,
        expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES,
        income_count=income_count, expense_count=expense_count,
        monthly_history=monthly_history, bar_max=bar_max, category_colors=CATEGORY_COLORS,
        today_expenses=today_expenses, today_income=today_income, today_count=today_count,
        avg_daily_expense=avg_daily_expense, day_of_month=day_of_month,
        largest_expense=largest_expense,
        total_budget=total_budget, budget_usage_pct=budget_usage_pct,
        recurring_count=recurring_count, top_categories=top_categories,
        days_left=days_left, daily_allowance=daily_allowance,
        days_in_month=days_in_month, remaining_budget=remaining_budget,
        spending_pace_pct=spending_pace_pct,
        most_active_category=most_active_category, most_active_count=most_active_count,
        monthly_summary=monthly_summary, current_month=now.month, current_year=now.year,
        start_date=start_date, end_date=end_date,
        spending_goal=spending_goal, goal_progress=goal_progress)

@finance.route('/add-transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        t_type = request.form.get('type')
        amount = request.form.get('amount', type=float)
        category = request.form.get('category')
        description = request.form.get('description', '')

        if not amount or amount <= 0:
            flash('Please enter a valid amount.', 'error')
        elif not category:
            flash('Please select a category.', 'error')
        else:
            date_str = request.form.get('date')
            tx_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
            notes = request.form.get('notes', '')
            t = Transaction(user_id=current_user.id, type=t_type,
                amount=amount, category=category, description=description,
                notes=notes, date=tx_date, recurring=bool(request.form.get('recurring')))
            db.session.add(t)
            db.session.commit()
            flash('Transaction added!', 'success')
            return redirect(url_for('finance.dashboard'))

    return render_template('add_transaction.html', user=current_user,
        expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES,
        category_colors=CATEGORY_COLORS)

@finance.route('/edit-transaction/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('finance.dashboard'))

    if request.method == 'POST':
        t.type = request.form.get('type')
        t.amount = request.form.get('amount', type=float)
        t.category = request.form.get('category')
        t.description = request.form.get('description', '')
        t.notes = request.form.get('notes', '')
        t.recurring = bool(request.form.get('recurring'))
        date_str = request.form.get('date')
        if date_str:
            t.date = datetime.strptime(date_str, '%Y-%m-%d')
        if not t.amount or t.amount <= 0:
            flash('Please enter a valid amount.', 'error')
        elif not t.category:
            flash('Please select a category.', 'error')
        else:
            db.session.commit()
            flash('Transaction updated!', 'success')
            return redirect(url_for('finance.dashboard'))

    return render_template('edit_transaction.html', user=current_user, transaction=t,
        expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES,
        category_colors=CATEGORY_COLORS)

@finance.route('/delete-transaction/<int:id>')
@login_required
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id == current_user.id:
        db.session.delete(t)
        db.session.commit()
        flash('Transaction deleted.', 'success')
    return redirect(url_for('finance.dashboard'))

@finance.route('/duplicate-transaction/<int:id>')
@login_required
def duplicate_transaction(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('finance.dashboard'))
    new_t = Transaction(user_id=current_user.id, type=t.type, amount=t.amount,
        category=t.category, description=t.description + ' (copy)',
        notes=t.notes, date=datetime.now(), recurring=t.recurring)
    db.session.add(new_t)
    db.session.commit()
    flash('Transaction duplicated!', 'success')
    return redirect(url_for('finance.dashboard'))

@finance.route('/toggle-pin/<int:id>')
@login_required
def toggle_pin(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('finance.dashboard'))
    t.pinned = not t.pinned
    db.session.commit()
    flash('Transaction pinned!' if t.pinned else 'Transaction unpinned.', 'success')
    return redirect(url_for('finance.dashboard'))

@finance.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)

    if request.method == 'POST':
        for cat in EXPENSE_CATEGORIES:
            val = request.form.get(f'budget_{cat}', type=float)
            existing = Budget.query.filter_by(
                user_id=current_user.id, category=cat, month=month, year=year).first()
            if val and val > 0:
                if existing:
                    existing.amount = val
                else:
                    db.session.add(Budget(
                        user_id=current_user.id, category=cat, amount=val,
                        month=month, year=year))
            elif existing:
                db.session.delete(existing)
        db.session.commit()
        flash('Budgets updated!', 'success')
        return redirect(url_for('finance.budgets', month=month, year=year))

    existing_budgets = Budget.query.filter_by(
        user_id=current_user.id, month=month, year=year).all()
    budget_map = {b.category: b.amount for b in existing_budgets}

    total_budget = sum(budget_map.values())
    expenses = Transaction.query.filter_by(user_id=current_user.id, type='expense').filter(
        db.extract('month', Transaction.date) == month,
        db.extract('year', Transaction.date) == year).all()
    total_spent = sum(e.amount for e in expenses)
    remaining_budget = total_budget - total_spent if total_budget > 0 else 0

    category_counts = {}
    for e in expenses:
        category_counts[e.category] = category_counts.get(e.category, 0) + 1

    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    return render_template('budgets.html', user=current_user,
        expense_categories=EXPENSE_CATEGORIES, budget_map=budget_map,
        category_colors=CATEGORY_COLORS, month=month, year=year, months=months,
        total_budget=total_budget, total_spent=total_spent, remaining_budget=remaining_budget,
        category_counts=category_counts)

@finance.route('/copy-budgets', methods=['POST'])
@login_required
def copy_budgets():
    now = datetime.now()
    month = request.form.get('month', now.month, type=int)
    year = request.form.get('year', now.year, type=int)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    prev_budgets = Budget.query.filter_by(user_id=current_user.id, month=prev_month, year=prev_year).all()
    copied = 0
    for pb in prev_budgets:
        existing = Budget.query.filter_by(user_id=current_user.id, category=pb.category, month=month, year=year).first()
        if existing:
            existing.amount = pb.amount
        else:
            db.session.add(Budget(user_id=current_user.id, category=pb.category, amount=pb.amount, month=month, year=year))
        copied += 1
    db.session.commit()
    flash(f'Copied {copied} budget(s) from {["","January","February","March","April","May","June","July","August","September","October","November","December"][prev_month]}!', 'success')
    return redirect(url_for('finance.budgets', month=month, year=year))

@finance.route('/export-csv')
@login_required
def export_csv():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    monthly = [t for t in transactions if t.date.month == month and t.date.year == year]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Category', 'Description', 'Notes', 'Amount'])
    for t in sorted(monthly, key=lambda x: x.date, reverse=True):
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.type, t.category, t.description or '', t.notes or '', f'{t.amount:.2f}'])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=transactions_{year}_{month:02d}.csv'}
    )

@finance.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    category = request.form.get('category')
    amount = request.form.get('amount', type=float)
    if category and amount and amount > 0:
        t = Transaction(user_id=current_user.id, type='expense',
            amount=amount, category=category, description='Quick add')
        db.session.add(t)
        db.session.commit()
        flash(f'Quick added ${amount:.2f} to {category}!', 'success')
    else:
        flash('Invalid quick-add data.', 'error')
    return redirect(url_for('finance.dashboard'))

@finance.route('/quick-add-income', methods=['POST'])
@login_required
def quick_add_income():
    category = request.form.get('category')
    amount = request.form.get('amount', type=float)
    if category and amount and amount > 0:
        t = Transaction(user_id=current_user.id, type='income',
            amount=amount, category=category, description='Quick add')
        db.session.add(t)
        db.session.commit()
        flash(f'Quick added ${amount:.2f} income to {category}!', 'success')
    else:
        flash('Invalid quick-add data.', 'error')
    return redirect(url_for('finance.dashboard'))

@finance.route('/export-all-csv')
@login_required
def export_all_csv():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Category', 'Description', 'Notes', 'Recurring', 'Amount'])
    for t in transactions:
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.type, t.category, t.description or '',
            t.notes or '', 'Yes' if t.recurring else 'No', f'{t.amount:.2f}'])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=all_transactions.csv'}
    )

@finance.route('/export-budgets')
@login_required
def export_budgets():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    months = ['','January','February','March','April','May','June','July','August','September','October','November','December']

    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    budget_map = {b.category: b.amount for b in budgets}

    expenses = Transaction.query.filter_by(user_id=current_user.id, type='expense').filter(
        db.extract('month', Transaction.date) == month,
        db.extract('year', Transaction.date) == year).all()
    spent_map = {}
    for e in expenses:
        spent_map[e.category] = spent_map.get(e.category, 0) + e.amount

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Category', 'Budget', 'Spent', 'Remaining'])
    for cat in EXPENSE_CATEGORIES:
        b = budget_map.get(cat, 0)
        s = spent_map.get(cat, 0)
        r = b - s if b > 0 else 0
        writer.writerow([cat, f'{b:.2f}', f'{s:.2f}', f'{r:.2f}'])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=budgets_{year}_{month:02d}.csv'}
    )

@finance.route('/set-spending-goal', methods=['POST'])
@login_required
def set_spending_goal():
    now = datetime.now()
    month = request.form.get('month', now.month, type=int)
    year = request.form.get('year', now.year, type=int)
    target = request.form.get('target_amount', type=float)

    if not target or target <= 0:
        flash('Please enter a valid goal amount.', 'error')
    else:
        existing = SpendingGoal.query.filter_by(
            user_id=current_user.id, month=month, year=year).first()
        if existing:
            existing.target_amount = target
        else:
            db.session.add(SpendingGoal(
                user_id=current_user.id, target_amount=target,
                month=month, year=year))
        db.session.commit()
        flash(f'Spending goal set to ${target:,.0f}!', 'success')
    return redirect(url_for('finance.dashboard', month=month, year=year))

@finance.route('/delete-spending-goal', methods=['POST'])
@login_required
def delete_spending_goal():
    now = datetime.now()
    month = request.form.get('month', now.month, type=int)
    year = request.form.get('year', now.year, type=int)
    goal = SpendingGoal.query.filter_by(
        user_id=current_user.id, month=month, year=year).first()
    if goal:
        db.session.delete(goal)
        db.session.commit()
        flash('Spending goal removed.', 'success')
    return redirect(url_for('finance.dashboard', month=month, year=year))
