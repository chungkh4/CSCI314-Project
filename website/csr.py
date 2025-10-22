from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from .models import Request, User
from . import db

csr = Blueprint('csr', __name__)
@csr.route('/csr/dashboard')
def csr_dashboard():
    # Only allow Platform Managers
    # if not hasattr(current_user, 'role') or current_user.role != 'Platform Manager':
    #     flash("Access denied. Platform Managers only.", category='danger')
    #     return redirect(url_for('views.home'))

    # Get all requests (or filter by status if needed)
    all_requests = Request.query.order_by(Request.date_created.desc()).all()

    # Optional: get all users if you want to show statistics
    users = User.query.order_by(User.date_created.desc()).all()

    requests_with_users = [(req, User.query.get(req.user_id)) for req in all_requests]

    return render_template(
        "csr_dashboard.html",
        requests_with_users=requests_with_users,
        users=users,
        user=current_user
    )

# Accept Request
@csr.route('/request/<int:request_id>/accept', methods=['POST'])
@login_required
def accept_request(request_id):
    req = Request.query.get_or_404(request_id)
    req.status = 'Accepted'
    db.session.commit()
    flash('Request has been accepted successfully.', 'success')
    return redirect(url_for('csr.csr_dashboard'))


# Assign to Volunteer
@csr.route('/request/<int:request_id>/assign', methods=['POST'])
@login_required
def assign_request(request_id):
    volunteer_id = request.form.get('volunteer_id')
    if not volunteer_id:
        flash('Please select a volunteer to assign.', 'warning')
        return redirect(url_for('csr.csr_dashboard'))
    
    req = Request.query.get_or_404(request_id)
    req.assigned_to = volunteer_id
    req.status = 'assigned'
    db.session.commit()
    flash(f'Request has been assigned to Volunteer #{volunteer_id}.', 'success')
    return redirect(url_for('csr.csr_dashboard'))


# Delete Request
@csr.route('/request/<int:request_id>/delete')
@login_required
def delete_request(request_id):
    req = Request.query.get_or_404(request_id)
    db.session.delete(req)
    db.session.commit()
    flash('Request deleted successfully.', 'danger')
    return redirect(url_for('csr.csr_dashboard'))
