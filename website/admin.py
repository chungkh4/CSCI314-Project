from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug import Request
from .models import User
from . import db

admin = Blueprint('admin', __name__)

# --- Admin Dashboard ---
@admin.route('/admin')
def dashboard():
    # Get all users
    users = User.query.order_by(User.date_created.desc()).all()
    
    return render_template("admin_dashboard.html", users=users)

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

@admin.route('/admin/user/<int:user_id>/delete')
def delete_user(user_id):
    # if not current_user.is_admin:
    #     flash("Access denied.", "danger")
    #     return redirect(url_for('views.home'))

    user = User.query.get_or_404(user_id)

    # Prevent deleting own admin account
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin.dashboard'))

    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.name} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "danger")
    return redirect(url_for('admin.dashboard'))
