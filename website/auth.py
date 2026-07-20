from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from . import db
from .models import User, Transaction, Budget

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            remember = bool(request.form.get('remember'))
            login_user(user, remember=remember)
            return redirect(url_for('views.home'))
        else:
            flash('Invalid email or password.', category='error')
    return render_template('login.html')

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        elif len(email) < 4:
            flash('Email must be at least 4 characters.', category='error')
        elif len(username) < 2:
            flash('Username must be at least 2 characters.', category='error')
        elif password1 != password2:
            flash('Passwords do not match.', category='error')
        elif len(password1) < 6:
            flash('Password must be at least 6 characters.', category='error')
        else:
            new_user = User(
                email=email,
                username=username,
                password=generate_password_hash(password1, method='pbkdf2:sha256')
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('views.home'))
    return render_template('sign_up.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(username) < 2:
            flash('Username must be at least 2 characters.', 'error')
        elif len(email) < 4:
            flash('Email must be at least 4 characters.', 'error')
        else:
            existing = User.query.filter(User.email == email, User.id != current_user.id).first()
            if existing:
                flash('Email already in use.', 'error')
            elif current_password and new_password:
                if not check_password_hash(current_user.password, current_password):
                    flash('Current password is incorrect.', 'error')
                elif len(new_password) < 6:
                    flash('New password must be at least 6 characters.', 'error')
                elif new_password != confirm_password:
                    flash('New passwords do not match.', 'error')
                else:
                    current_user.username = username
                    current_user.email = email
                    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
                    db.session.commit()
                    flash('Profile updated!', 'success')
                    return redirect(url_for('auth.profile'))
            else:
                current_user.username = username
                current_user.email = email
                db.session.commit()
                flash('Profile updated!', 'success')
                return redirect(url_for('auth.profile'))

    tx_count = Transaction.query.filter_by(user_id=current_user.id).count()
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
    expense_count = sum(1 for t in transactions if t.type == 'expense')
    avg_expense = total_expenses / expense_count if expense_count > 0 else 0
    first_tx = min(transactions, key=lambda t: t.date) if transactions else None
    account_days = (datetime.utcnow() - first_tx.date).days + 1 if first_tx else 0
    categories_used = len(set(t.category for t in transactions))
    net_worth = total_income - total_expenses
    account_months = 0
    if first_tx:
        delta = datetime.utcnow() - first_tx.date
        account_months = (delta.days // 30) + 1

    budget_count = Budget.query.filter_by(user_id=current_user.id).count()
    score = 0
    if tx_count > 0: score += 25
    if expense_count > 0: score += 25
    if categories_used >= 3: score += 25
    if budget_count > 0: score += 25

    last_tx = max(transactions, key=lambda t: t.date) if transactions else None
    last_tx_date = last_tx.date.strftime('%b %d, %Y') if last_tx else None

    return render_template('profile.html', user=current_user, tx_count=tx_count,
        total_income=total_income, total_expenses=total_expenses,
        account_days=account_days, categories_used=categories_used,
        avg_expense=avg_expense, net_worth=net_worth, account_months=account_months,
        profile_score=score, last_tx_date=last_tx_date)

@auth.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    for t in transactions:
        db.session.delete(t)
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    for b in budgets:
        db.session.delete(b)
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('Your account has been deleted.', 'success')
    return redirect(url_for('auth.login'))
