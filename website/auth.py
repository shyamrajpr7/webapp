from flask import Blueprint

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return "<p> login </P>"

@auth.route('/logout')
def logout():
    return "<p> logout </P>"

@auth.route('/sign-up')
def sign_up():
    return "<p> sign Up </P>"
