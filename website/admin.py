from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from sqlalchemy import text
from flask_login import login_required, current_user
from .models import User, Request
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

@admin.route('/edit-profile/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_profile(user_id):

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        if not name or not email:
            flash("Please fill out all required fields.", "warning")
            return redirect(url_for('views.edit_profile'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != user.id:
            flash("Email is already in use.", "danger")
            return redirect(url_for('edit_profile', id=user.id))

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

                # ✅ Safe reset for all database types
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


# Function: Create User Profiles for PIN/CSR Rep/Platform Manager/Volunteer with temporary password
ALLOWED_ROLES = {"CSR", "Platform Manager", "Volunteer", "PIN"}
ALLOWED_STATUSES = {"Active", "Pending", "Suspended"}  # pick the set your app actually uses

@admin.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    # Authorize: adjust to your real admin role(s)
    if getattr(current_user, "role", "").lower() != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'POST':
        fullname = (request.form.get('fullname') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        temp_pw = (request.form.get('password') or '').strip()
        role = (request.form.get('role') or '').strip()
        status = (request.form.get('status') or '').strip()

        # Normalize status text from form (e.g., "activated" -> "Active")
        status_map = {
            "activated": "Active",
            "active": "Active",
            "pending": "Pending",
            "suspended": "Suspended",
        }
        status_normalized = status_map.get(status.lower(), status)

        # ---- Correct validation ----
        # 1) All fields present
        if not (fullname and email and temp_pw and role and status):
            flash("Please fill all fields.", "warning")
            return redirect(url_for('admin.create_user'))

        # 2) Role must be in allowed roles
        if role not in ALLOWED_ROLES:
            flash("Invalid role selected.", "danger")
            return redirect(url_for('admin.create_user'))

        # 3) Status must be in allowed statuses
        if status_normalized not in ALLOWED_STATUSES:
            flash("Invalid status. Please select a valid status.", "danger")
            return redirect(url_for('admin.create_user'))

        # 4) Unique email
        if User.query.filter_by(email=email).first():
            flash("Email is already in use.", "danger")
            return redirect(url_for('admin.create_user'))

        # Create user (hash password explicitly)
        user = User(
            name=fullname,
            email=email,
            password=generate_password_hash(temp_pw, method='pbkdf2:sha256'), # consider adding flag/function where user logging in w temp password FORCED to change pw
            role=role,
            status=status_normalized,
        )
        db.session.add(user)
        db.session.commit()

        flash(f"User '{fullname}' ({role}) created with status '{status_normalized}'.", "success")
        return redirect(url_for('admin.dashboard'))

    # GET -> render form
    return render_template(
        'admin_dashboard_create_user_profile.html',
        allowed_roles=sorted(ALLOWED_ROLES),
        allowed_statuses=sorted(ALLOWED_STATUSES)
    )