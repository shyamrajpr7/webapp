from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'hikkmnnaapp'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

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
