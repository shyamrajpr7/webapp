from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

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
        if current_user.is_authenticated:
            from .models import Transaction
            now = datetime.now()
            tx_count = Transaction.query.filter_by(user_id=current_user.id).filter(
                db.extract('month', Transaction.date) == now.month,
                db.extract('year', Transaction.date) == now.year
            ).count()
        return dict(tx_count=tx_count)

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

    return app
