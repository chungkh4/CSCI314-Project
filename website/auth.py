import datetime
from flask import Blueprint, Request, render_template, request, flash, redirect, url_for
from .models import Category, Review, User, Volunteer, Logout, Shortlist, Csr
from .models import Request as RequestModel
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

            if role == 'CSR':
                # add to CSR database
                new_CSR = Csr(user_id=new_user.id, name=username, role=role)
                db.session.add(new_CSR)
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
        user_id = user.id
        user_role = user.role

        # 1.user is a volunteer
        if user_role == 'Volunteer':
            volunteer = Volunteer.query.filter_by(user_id=user_id).first()
            
            if volunteer:
                # Unassign all requests assigned to this volunteer
                assigned_requests = RequestModel.query.filter_by(volunteer_id=volunteer.id).all()
                for req in assigned_requests:
                    req.volunteer_id = None
                    req.status = 'Pending'  # Reset status back to Pending
                
                # Delete all reviews for this volunteer
                Review.query.filter_by(volunteer_id=volunteer.id).delete()
                
                # Delete the volunteer profile
                db.session.delete(volunteer)
        
        # 2. Delete all reviews written by this user (if PIN)
        Review.query.filter_by(user_id=user_id).delete()
        # 3. Delete all user's requests
        RequestModel.query.filter_by(user_id=user_id).delete()
        # 4. Finally, delete the user
        
        db.session.delete(user)
    
        # 5. Commit all changes
        db.session.commit()
        # Logoout User
        logout_user()
        flash('Your account has been deleted successfully.', category='success')
        return redirect(url_for('auth.login'))

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting your account. Please try again.', category='danger')
        print("Error deleting account:", e)
        print("Error type:", type(e).__name__)
        import traceback
        traceback.print_exc()  # This will print the full error traceback
        
        # If user was logged out, redirect to login
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        return redirect(url_for('volunteer.volunteer_dashboard'))


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


# Update Credentials for User Profiles Created by Admin
TEMP_PREFIX = "temp-"

## entity-facing functions ##
def temp_name_check(name: str) -> bool: 
    return (name or "").lower().startswith(TEMP_PREFIX)

def verify_currentPW_check(user, current_pw: str) -> bool:
    return check_password_hash(user.password, current_pw or "")

def strong_PW_check(pw: str) -> bool:
    return pw is not None and len(pw) >= 7

def passwords_match_check(a: str, b: str) -> bool:
    return (a or "") == (b or "")

def update_user_credentials(db, user, new_name: str, new_pw: str):
    user.name = new_name
    user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
    db.session.commit()
    return user

## boundary+controller-facing functions ##
def render_update_credentials_form(user):
    return user  

def read_update_credentials_form(db, user, form):
    # read inputs
    new_name = (form.get('new_name') or '').strip()
    current_pw = form.get('current_password') or ''
    new_pw1 = form.get('new_password1') or ''
    new_pw2 = form.get('new_password2') or ''

    # alternative flow 3a) validation check: all fields need to be filled
    if not (new_name and current_pw and new_pw1 and new_pw2):
        return False, ("Please fill in all fields.", "danger"), user

    # user MUST change username; name must not keep 'temp-' prefix
    # alternative flow 3b) name not changed
    if temp_name_check(new_name):
        return False, ("Please change your name.", "warning"), user

    # verify current password check
    # alternative flow 3c) current password mistmatch
    if not verify_currentPW_check(user, current_pw):
        return False, ("Current password is incorrect.", "danger"), user

    # new password match + strength
    # alternative flow 3d) new pw don't matcch
    # alternative flow 3d) weak new pw
    if not passwords_match_check(new_pw1, new_pw2):
        return False, ("New passwords do not match.", "danger"), user
    if not strong_PW_check(new_pw1):
        return False, ("New password must be at least 7 characters.", "danger"), user

    # stores the data into db
    try:
        update_user_credentials(db, user, new_name, new_pw1)
    except Exception as e:
        db.session.rollback()
        return False, (f"Error updating credentials: {e}", "danger"), user

    return True, ("Username and password have been updated successfully.", "success"), user

## routing
@auth.route('/update-credentials', methods=['GET', 'POST'])
@login_required
def update_credentials():
    if request.method == 'GET':
        user = render_update_credentials_form(current_user)
        return render_template('update_credentials.html', user=user)

    ok, (text, level), user = read_update_credentials_form(db, current_user, request.form)
    flash(text, level)
    if ok:
        return redirect(url_for('views.home'))
    return render_template('update_credentials.html', user=user)
