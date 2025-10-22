from flask import Blueprint, render_template, request

# url holders
auth = Blueprint('auth', __name__)

# test route
@auth.route('/login', methods=['GET', 'POST'])
def login():
    data = request.form
    return render_template("login.html", text = "testing")


@auth.route('/logout')
def logout():
    return "<p>.</p>"


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    return render_template("sign_up.html")
