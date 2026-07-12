from flask import Blueprint, redirect, url_for
from flask_login import login_required

views = Blueprint('views', __name__)

@views.route('/')
@login_required
def home():
    return redirect(url_for('finance.dashboard'))
