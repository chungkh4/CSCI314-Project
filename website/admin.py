from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from sqlalchemy import text
from flask_login import login_required, current_user
from .models import User, Request
from . import db
from werkzeug.security import generate_password_hash
# website/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from . import db
from .models import User, Category, Volunteer, Csr   # <-- add this line


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

@admin.route('/edit-profile/<int:user_id>', methods=['GET', 'POST'])
# @login_required
def edit_profile(user_id):
    # assume page alreaday enforces only user admin can access admin dashboard
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        if not name or not email:
            flash("Please fill out all required fields.", "warning")
            return redirect(url_for('views.edit_profile'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != user.id:
            flash("Email is already in use by another user.", "warning")
            return render_template('edit_profile.html', user=user)

        # Update user info
        user.name = name
        user.email = email
        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('admin.dashboard'))

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


### Create User Profiles for PIN/CSR Rep/Platform Manager/Volunteer with "temporary" password ###"
ALLOWED_ROLES = {"CSR", "Platform Manager", "Volunteer", "PIN"}
ALLOWED_STATUSES = {"Active", "Pending", "Suspended"}
#fallback just in case
TEMP_PREFIX = "temp-" #"temp-" associated to new "temp" user profiles created
    

def get_allowed_roles():
    try:
        rows = db.session.execute(
            db.select(User.role).distinct().order_by(User.role)
        ).all()
        db_roles = [r[0] for r in rows if r[0]]
    except Exception:
        db_roles = []

    roles = sorted(set(db_roles).union(ALLOWED_ROLES)) 
    roles = [r for r in roles if r.lower() != "admin"] #role admin not allowed.
    
    return roles


def get_allowed_statuses():
    try:
        rows = db.session.execute(
            db.select(User.status).distinct().order_by(User.status)
        ).all()
        db_statuses = [s[0] for s in rows if s[0]]
    except Exception:
        db_statuses = []
    return sorted(set(db_statuses).union(ALLOWED_STATUSES))


TEMP_PREFIX = "temp-"  
@admin.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    allowed_roles = get_allowed_roles() or ['CSR', 'Platform Manager', 'Volunteer', 'PIN']
    allowed_statuses = get_allowed_statuses() or ['Pending', 'Active', 'Suspended']
    categories = Category.query.order_by(Category.name.asc()).all()

    if request.method == 'POST':
        fullname = (request.form.get('fullname') or '').strip()
        email = (request.form.get('email') or '').strip()
        temp_pw = (request.form.get('password') or '').strip()
        role = (request.form.get('role') or '').strip()
        status = (request.form.get('status') or '').strip()

        category_id_raw = (request.form.get('category_id') or '').strip()
        category_id = int(category_id_raw) if category_id_raw.isdigit() else None

        # basic validation check
        if not (fullname and email and temp_pw and role and status):
            flash("Please fill all fields.", "warning")
            return redirect(url_for('admin.create_user'))
        if role not in allowed_roles:
            flash("{role} role is not allowed.", "danger")
            return redirect(url_for('admin.create_user'))
        if status not in allowed_statuses:
            flash("{status} is not allowed.", "danger")
            return redirect(url_for('admin.create_user'))
        if len(temp_pw) < 7:
            flash('New password must be at least 7 characters.', "warning")
            return redirect(url_for('admin.create_user'))
        if User.query.filter_by(email=email).first():
            flash("Email is already in use.", "danger")
            return redirect(url_for('admin.create_user'))

        # ensure that volunteer role has associated category
        if role == 'Volunteer':
            if not category_id:
                flash("Please select a service category for Volunteer.", "warning")
                return redirect(url_for('admin.create_user'))
            if not Category.query.get(category_id):
                flash("Selected service category was not found.", "danger")
                return redirect(url_for('admin.create_user'))

        display_name = fullname
        if not display_name.lower().startswith(TEMP_PREFIX):
            display_name = f"{TEMP_PREFIX}{display_name}"

        user = User(
            name=display_name,
            email=email,
            password=generate_password_hash(temp_pw, method='pbkdf2:sha256'),
            role=role,
            status=status,
        )
        db.session.add(user)
        db.session.flush()  

        if role == 'Volunteer':
            db.session.add(Volunteer(user_id=user.id, category_id=category_id))
        elif role == 'CSR':
            db.session.add(Csr(user_id=user.id, name=fullname, role=role))

        db.session.commit()
        flash(f"User {fullname} ({role}) has successfully been created with status: {status}.", "success")
        return redirect(url_for('admin.dashboard'))

    return render_template(
        'admin_dashboard_create_user_profile.html',
        allowed_roles=allowed_roles,
        allowed_statuses=allowed_statuses,
        categories=categories
    )
