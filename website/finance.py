from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
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

    recent = sorted(monthly, key=lambda t: t.date, reverse=True)[:10]

    months = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']

    return render_template('dashboard.html', user=current_user, transactions=recent,
        income=income, expenses=expenses, balance=balance,
        spending_data=spending_data, chart_data=chart_data,
        max_expense=max_expense, month=month, year=year, months=months,
        all_transactions=monthly,
        expense_categories=EXPENSE_CATEGORIES, income_categories=INCOME_CATEGORIES)

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
            t = Transaction(user_id=current_user.id, type=t_type,
                amount=amount, category=category, description=description)
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
