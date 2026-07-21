from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

CATEGORY_EMOJIS = {
    'Food & Dining': '\U0001f35c', 'Transportation': '\U0001f697', 'Housing': '\U0001f3e0',
    'Utilities': '\U0001f4a1', 'Entertainment': '\U0001f3ac', 'Shopping': '\U0001f6d2',
    'Healthcare': '\U0001fa7a', 'Education': '\U0001f4da', 'Other': '\U0001f4cc',
    'Salary': '\U0001f4b0', 'Freelance': '\U0001f4bb', 'Investments': '\U0001f4c8',
    'Business': '\U0001f3e2'
}

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'hikkmnnaapp'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @app.context_processor
    def inject_globals():
        tx_count = 0
        sidebar_recent = []
        sidebar_sparkline = []
        if current_user.is_authenticated:
            from .models import Transaction
            now = datetime.now()
            tx_count = Transaction.query.filter_by(user_id=current_user.id).filter(
                db.extract('month', Transaction.date) == now.month,
                db.extract('year', Transaction.date) == now.year
            ).count()
            sidebar_recent = Transaction.query.filter_by(user_id=current_user.id).order_by(
                Transaction.date.desc()).limit(5).all()
            all_txns = Transaction.query.filter_by(user_id=current_user.id).all()
            for i in range(5, -1, -1):
                m = now.month - i
                y = now.year
                while m <= 0:
                    m += 12
                    y -= 1
                mt = [t for t in all_txns if t.date.month == m and t.date.year == y and t.type == 'expense']
                sidebar_sparkline.append(sum(t.amount for t in mt))
        return dict(tx_count=tx_count, page_load_time=datetime.now().strftime('%b %d, %Y %I:%M %p'),
                    datetime=datetime, sidebar_recent=sidebar_recent,
                    category_emojis=CATEGORY_EMOJIS, sidebar_sparkline=sidebar_sparkline)

    from .views import views
    from .auth import auth
    from .finance import finance

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(finance, url_prefix='/')

    with app.app_context():
        from . import models
        db.create_all()
        try:
            db.session.execute(db.text('ALTER TABLE "transaction" ADD COLUMN recurring BOOLEAN DEFAULT 0'))
            db.session.commit()
        except Exception:
            pass
        try:
            db.session.execute(db.text('ALTER TABLE "transaction" ADD COLUMN notes TEXT DEFAULT \'\''))
            db.session.commit()
        except Exception:
            pass
        try:
            db.session.execute(db.text('ALTER TABLE "transaction" ADD COLUMN pinned BOOLEAN DEFAULT 0'))
            db.session.commit()
        except Exception:
            pass

    return app
