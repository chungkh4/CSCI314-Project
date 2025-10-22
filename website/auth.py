from flask import Blueprint, render_template, request, flash, redirect, url_for 
from .models import User
from . import db
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import login_user, logout_user, login_required, current_user

# url holders
auth = Blueprint('auth', __name__)

# Create Account For PIN
@auth.route('/signup', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        username = request.form.get('userName')
        role = request.form.get('role')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='danger')
            return redirect(url_for('auth.sign_up'))
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='danger')
            return redirect(url_for('auth.sign_up'))
        elif len(username) < 2:
            flash('Username must be greater than 1 character.', category='danger')
            return redirect(url_for('auth.sign_up'))
        elif password1 != password2:    
            flash('Passwords don\'t match.', category='danger')
            return redirect(url_for('auth.sign_up'))
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='danger')
            return redirect(url_for('auth.sign_up'))
        else:
            new_user = User(email=email, name=username, password=generate_password_hash(password1, method='pbkdf2:sha256'), status='Pending', role=role)

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            return redirect(url_for('views.home'))
    
    return render_template("sign_up.html")

# PIN Login
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')

        # Check the email
        user = User.query.filter_by(email=email).first()
        # check input fields
        if len(email) < 1 or len(password) < 1:
            flash('Please fill out all fields.', category='danger')
        elif user:
            if check_password_hash(user.password, password):

                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='danger')
        else:
            flash('Email does not exist. Create account first!', category='danger')
    
    return render_template("login.html")

# PIN Logout
@auth.route('/logout')
def logout():
    logout_user()
    flash('Logged out successfully!', category='success')
    return redirect(url_for('auth.login'))


# DELETE ACCOUNT
@auth.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    user = current_user  # Get the logged-in user
    
    try:
        # Remove user from the database
        db.session.delete(user)
        db.session.commit()

        # Log them out
        logout_user()

        flash('Your account has been deleted successfully.', category='success')
        return redirect(url_for('auth.login'))

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting your account. Please try again.', category='danger')
        print("Error deleting account:", e)
        return redirect(url_for('views.pin_profile'))

# change password
@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password1 = request.form.get('new_password1')
        new_password2 = request.form.get('new_password2')

        # Check if all fields are filled
        if not current_password or not new_password1 or not new_password2:
            flash('Please fill in all fields.', category='danger')
            return redirect(url_for('auth.change_password'))

        # Check current password
        if not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect.', category='danger')
            return redirect(url_for('auth.change_password'))

        # Check new passwords match
        if new_password1 != new_password2:
            flash('New passwords do not match.', category='danger')
            return redirect(url_for('auth.change_password'))

        # Check password strength
        if len(new_password1) < 7:
            flash('New password must be at least 7 characters long.', category='danger')
            return redirect(url_for('auth.change_password'))

        # Update password
        current_user.password = generate_password_hash(new_password1, method='pbkdf2:sha256')
        
        db.session.commit()

        flash('Password updated successfully!', category='success')
        return redirect(url_for('views.home'))

    return render_template("pin_change_password.html", user=current_user)
