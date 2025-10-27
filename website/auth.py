import datetime
from flask import Blueprint, Request, render_template, request, flash, redirect, url_for
from .models import Category, User, Volunteer, Logout
from . import db
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import login_user, logout_user, login_required, current_user

auth = Blueprint('auth', __name__)


# CREATE Account
@auth.route('/signup', methods=['GET', 'POST'])
def sign_up():
    categories = Category.query.all()

    if request.method == 'POST':
        email = request.form.get('email')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        username = request.form.get('userName')
        role = request.form.get('role')

        category_id = request.form.get('categories')

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
            new_user = User(email=email, name=username,
                            password=generate_password_hash(password1, method='pbkdf2:sha256'), status='Pending',
                            role=role)

            db.session.add(new_user)
            db.session.commit()

            if role == 'Volunteer':
                # Create Volunteer profile
                new_volunteer = Volunteer(user_id=new_user.id, category_id=int(category_id) if category_id else None)  #

                db.session.add(new_volunteer)
                db.session.commit()

            # login_user(new_user, remember=True)
            flash('Account created!', category='success')

            return redirect(url_for('auth.login'))

    return render_template('sign_up.html', categories=categories)


# LOGIN User Account
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


# Logout User Account
@auth.route('/logout')
def logout():
    userid = current_user.id
    logout_datetime = datetime.datetime.now()

    logout_info = Logout(user_id=userid, DateTime=logout_datetime)
    db.session.add(logout_info)
    db.session.commit()
    logout_user()
    flash('Logged out successfully!', category='success')
    return redirect(url_for('auth.login'))


# DELETE Users Account
@auth.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    user = current_user  # Get the logged-in(current) user

    if user.role == 'Platform Manager':
        flash('Platform Manager accounts cannot be deleted. Please contact system administrator.', category='danger')
        return redirect(url_for('views.manager_profile'))

    try:
        # 1. Delete all user's requests first
        Request.query.filter_by(user_id=user.id).delete()

        # 2. If user is a volunteer, handle volunteer profile
        if user.role == 'Volunteer' and user.volunteer_profile:
            volunteer = user.volunteer_profile

            # Unassign all requests assigned to this volunteer
            assigned_requests = Request.query.filter_by(volunteer_id=volunteer.id).all()
            for req in assigned_requests:
                req.volunteer_id = None
                req.status = 'Pending'  # Reset status back to Pending

            # 3. Delete volunteer profile
            db.session.delete(volunteer)

        # 4. Finally, delete the user
        db.session.delete(user)
        db.session.commit()

        # 5. Log them out
        logout_user()

        flash('Your account has been deleted successfully.', category='success')
        return redirect(url_for('auth.login'))

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting your account. Please try again.', category='danger')
        print("Error deleting account:", e)
        return redirect(url_for('views.home'))


# User changes password
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
