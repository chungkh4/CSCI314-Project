from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from .models import User, Request
from . import db

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
    # if current_user.role != 'Admin':
    #     flash("Only admin can access this page!.", "danger")
    #     return redirect(url_for('views.home'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        # role = request.form.get('role') # Uncomment if role change is allowed

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
