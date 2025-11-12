from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from sqlalchemy import text
from flask_login import login_required, current_user
from .models import User, Request, Category, Volunteer, Csr
from . import db
from werkzeug.security import generate_password_hash


admin = Blueprint('admin', __name__)

# --- Admin Dashboard ---
@admin.route('/admin')
@login_required
def dashboard():
    # if current_user.role != 'Admin':
    #     flash("Only admin can access this page!.", "danger")
    #     return redirect(url_for('views.home'))
    # Get all users
    users = User.query.order_by(User.date_created.desc()).all()
    
    return render_template("admin_dashboard.html", users=users)

# User admin activate users
@admin.route('/admin/user/<int:id>/activate')
def activate_user(id):
    user = User.query.get_or_404(id)
    user.status = 'Active'
    db.session.commit()
    flash(f"{user.name} activated.", "success")
    return redirect(url_for('admin.dashboard'))

@admin.route('/admin/user/<int:id>/suspend')
def suspend_user(id):
    user = User.query.get_or_404(id)
    user.status = 'Suspended'
    db.session.commit()
    flash(f"{user.name} suspended.", "warning")
    return redirect(url_for('admin.dashboard'))


### fixed: name and sequence diagram inconsistency 
### edit user profile ###
## entity-facing functions ##
def find_userID(User, user_id: int):
    return User.query.get_or_404(user_id)

def find_user_email(User, email: str):
    return User.query.filter_by(email=email).first()

## boundary+controller-facing functions ##
def update_user_profile(db, user, name: str, email: str):
    user.name = name
    user.email = email  
    db.session.commit()
    return user

def render_edit_user_form(User, user_id: int):
    user = find_userID(User, user_id)
    return user

def read_edit_user_form(db, User, user_id: int, form):
    # read inputs
    user = find_userID(User, user_id)
    name  = (form.get('name')  or '').strip()
    email = (form.get('email') or '').strip()

    # alternative flow 4a) validation check: all fields need to be filled
    if not name or not email:
        return False, ("Please fill out all required fields.", "warning"), user

    # alternative flow 4b) validation check: no duplicate email
    existing = find_user_email(User, email)
    if existing and existing.id != user.id:
        return False, ("Email is already in use by another user.", "warning"), user

    # stores the data into db
    try:
        update_user_profile(db, user, name, email)
    except Exception as e:
        db.session.rollback()
        return False, (f"Error updating profile: {e}", "danger"), user

    return True, ("Profile updated successfully!", "success"), user

## routing
@admin.route('/edit-profile/<int:user_id>', methods=['GET', 'POST'])
@login_required  
def edit_profile(user_id):
    if request.method == 'GET':
        user = render_edit_user_form(User, user_id)
        return render_template('edit_profile.html', user=user)

    ok, (text, level), user = read_edit_user_form(db, User, user_id, request.form)
    flash(text, level)
    if ok:
        return redirect(url_for('admin.dashboard'))

    # form re-render upon failure, use same userID
    return render_template('edit_profile.html', user=user)


@admin.route('/admin/user/<int:user_id>/delete')
def delete_user(user_id):
    # if not current_user.is_admin:
    #     flash("Access denied.", "danger")
    #     return redirect(url_for('views.home'))

    user = User.query.get_or_404(user_id)

    try:
        # 1. Delete user's requests
        Request.query.filter_by(user_id=user.id).delete()

        # 2. If volunteer, unassign requests and delete profile
        if user.role == 'Volunteer' and hasattr(user, 'volunteer_profile') and user.volunteer_profile:
            volunteer = user.volunteer_profile

            Request.query.filter_by(volunteer_id=volunteer.id).update({
                'volunteer_id': None,
                'status': 'Pending'
            })
            db.session.delete(volunteer)

        # 3. Delete user
        db.session.delete(user)
        db.session.commit()

        flash(f"User {user.name} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "danger")
        print("Error deleting user:", e)

    return redirect(url_for('admin.dashboard'))

@admin.route('/api/clear-database', methods=['DELETE'])
@login_required
def clear_database():
    if getattr(current_user, "role", "").lower() != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        meta = db.metadata
        engine = db.get_engine()

        for table in reversed(meta.sorted_tables):
            if table.name.lower() != "user":
                db.session.execute(table.delete())

                if engine.dialect.name == "sqlite":
                    # check if sqlite_sequence exists before touching it
                    exists = db.session.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
                    ).fetchone()
                    if exists:
                        db.session.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{table.name}'"))
                elif engine.dialect.name == "mysql":
                    db.session.execute(text(f"ALTER TABLE `{table.name}` AUTO_INCREMENT = 1"))
                elif engine.dialect.name == "postgresql":
                    db.session.execute(text(f"ALTER SEQUENCE {table.name}_id_seq RESTART WITH 1"))

        db.session.commit()
        return jsonify({"message": "Database cleared (except users) and auto-increment reset."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


### fixed: name and sequence diagram inconsistency 
# Create User Profiles for PIN/CSR Rep/Platform Manager/Volunteer with "temporary" password ###"
## entity-facing functions ##
ALLOWED_ROLES = {"CSR", "Platform Manager", "Volunteer", "PIN"}  
ALLOWED_STATUSES = {"Active", "Pending", "Suspended"}
#fallback roles and status established
TEMP_PREFIX = "temp-" #"temp-" associated to new "temp" user profiles created

def get_allowed_roles(db, User):
    try:
        rows = db.session.execute(
            db.select(User.role).distinct().order_by(User.role)
        ).all()
        db_roles = [r[0] for r in rows if r[0]]
    except Exception:
        db_roles = []
    roles = sorted(set(db_roles).union(ALLOWED_ROLES))
    roles = [r for r in roles if r.lower() != "admin"]   # NO ADMIN 
    return roles or ['CSR', 'Platform Manager', 'Volunteer', 'PIN']

def get_allowed_statuses(db, User):
    try:
        rows = db.session.execute(
            db.select(User.status).distinct().order_by(User.status)
        ).all()
        db_statuses = [s[0] for s in rows if s[0]]
    except Exception:
        db_statuses = []
    statuses = sorted(set(db_statuses).union(ALLOWED_STATUSES))
    return statuses or ['Pending', 'Active', 'Suspended']

def email_duplicate_check(db, User, email: str) -> bool:
    return db.session.query(db.exists().where(User.email == email)).scalar()

def enforce_temp_display_name(fullname: str) -> str:
    return fullname if fullname.lower().startswith(TEMP_PREFIX) else f"{TEMP_PREFIX}{fullname}"

def category_exists_check(Category, category_id: int) -> bool:
    return bool(Category.query.get(category_id))


## boundary+controller-facing functions ##
def render_create_user_form(db, User, Category):
    roles = get_allowed_roles(db, User)
    statuses = get_allowed_statuses(db, User)
    categories = Category.query.order_by(Category.name.asc()).all()
    return roles, statuses, categories

def read_user_form(db, User, Volunteer, Csr, Category, form):
    # read inputs
    fullname = (form.get('fullname') or '').strip()
    email    = (form.get('email') or '').strip()
    temp_pw  = (form.get('password') or '').strip()
    role     = (form.get('role') or '').strip()
    status   = (form.get('status') or '').strip()

    cid_raw = (form.get('category_id') or '').strip()
    category_id = int(cid_raw) if cid_raw.isdigit() else None

    # alternative flow 4a) validation check: all fields need to be filled
    if not (fullname and email and temp_pw and role and status):
        return False, ("Please fill all fields.", "warning")

    # enforce allowed role/status
    allowed_roles = get_allowed_roles(db, User)
    allowed_statuses = get_allowed_statuses(db, User)
    if role not in allowed_roles:
        return False, (f"{role} role is not allowed.", "danger")
    if status not in allowed_statuses:
        return False, (f"{status} is not allowed.", "danger")

    # alternative flow 4b) enforce password strength: min 7 characters (align with other user registration feature)
    if len(temp_pw) < 7:
        return False, ('New password must be at least 7 characters.', "warning")

    # alternative flow 4c) validation check: no duplicate email
    if email_duplicate_check(db, User, email):
        return False, ("Email is already in use.", "danger")

    # alternative flow 3b) ensure that volunteer role has associated category
    if role == 'Volunteer':
        if not category_id:
            return False, ("Please select a service category for Volunteer.", "warning")
        if not category_exists_check(Category, category_id):
            return False, ("Selected service category was not found.", "danger")

    # stores the data into db
    display_name = enforce_temp_display_name(fullname)
    user = User(
        name=display_name,
        email=email,  
        password=generate_password_hash(temp_pw, method='pbkdf2:sha256'),
        role=role,
        status=status,
    )
    db.session.add(user)
    db.session.flush()  # get user.id

    if role == 'Volunteer':
        db.session.add(Volunteer(user_id=user.id, category_id=category_id))
    elif role == 'CSR':
        db.session.add(Csr(user_id=user.id, name=fullname, role=role))

    db.session.commit()
    return True, (f"User: {fullname} ({role}) has successfully been created with status: {status}.", "success")


## routing ##
@admin.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    if request.method == 'GET':
        roles, statuses, categories = render_create_user_form(db, User, Category)   
        return render_template(
            'admin_dashboard_create_user_profile.html',
            allowed_roles=roles,
            allowed_statuses=statuses,
            categories=categories
        )

    ok, (text, level) = read_user_form(
        db=db, User=User, Volunteer=Volunteer, Csr=Csr, Category=Category, form=request.form
    )
    flash(text, level)
    if ok:
        return redirect(url_for('admin.dashboard'))

    # form re-render upon fail
    roles, statuses, categories = render_create_user_form(db, User, Category)
    return render_template(
        'admin_dashboard_create_user_profile.html',
        allowed_roles=roles,
        allowed_statuses=statuses,
        categories=categories
    )