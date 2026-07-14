from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime
import csv
import io
from . import db
from .models import Transaction, Budget

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

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    monthly = [t for t in transactions if t.date.month == month and t.date.year == year]

    income = sum(t.amount for t in monthly if t.type == 'income')
    expenses = sum(t.amount for t in monthly if t.type == 'expense')
    balance = income - expenses

    income_count = sum(1 for t in monthly if t.type == 'income')
    expense_count = sum(1 for t in monthly if t.type == 'expense')

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

    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    budget_map = {b.category: b.amount for b in budgets}

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

    recent = sorted(monthly, key=lambda t: t.date, reverse=True)[:10]

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

    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    return render_template('dashboard.html', user=current_user, transactions=recent,
        income=income, expenses=expenses, balance=balance,
        spending_data=spending_data, chart_data=chart_data,
        max_expense=max_expense, month=month, year=year, months=months,
        all_transactions=monthly, alerts=alerts, comparison=comparison,
        expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES,
        income_count=income_count, expense_count=expense_count,
        monthly_history=monthly_history)

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
            t = Transaction(user_id=current_user.id, type=t_type,
                amount=amount, category=category, description=description, date=tx_date)
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

    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    return render_template('budgets.html', user=current_user,
        expense_categories=EXPENSE_CATEGORIES, budget_map=budget_map,
        category_colors=CATEGORY_COLORS, month=month, year=year, months=months)

@finance.route('/export-csv')
@login_required
def export_csv():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    monthly = [t for t in transactions if t.date.month == month and t.date.year == year]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Category', 'Description', 'Amount'])
    for t in sorted(monthly, key=lambda x: x.date, reverse=True):
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.type, t.category, t.description or '', f'{t.amount:.2f}'])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=transactions_{year}_{month:02d}.csv'}
    )
