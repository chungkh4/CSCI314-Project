from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from .models import Request, Category, User, Volunteer
from . import db

csr = Blueprint('csr', __name__)

# CSR Dashboard
@csr.route('/csr/dashboard')
def csr_dashboard():
    # Only allow CSR role to access
    if current_user.role != 'CSR':
        flash('Only CSR can access!', 'danger')
        return redirect(url_for('views.home'))
    
    categories = Category.query.order_by(Category.name).all()

    # Get all requests with their users
    requests = Request.query.order_by(Request.date_created.desc()).all()
    requests_with_users = [(req, req.user) for req in requests]
    
    # Get all volunteers (regardless of approval status for now)
    # TODO: Later you can filter by User.status == 'Approved' if needed
    volunteers = Volunteer.query.join(User).filter(
        User.role == 'Volunteer'
    ).all()
    
    # Get all users
    users = User.query.all()

        
    volunteers = Volunteer.query.all()
    for v in volunteers:
        print(f"{v.user.name}: is_available = {v.is_available}")
    
    return render_template('csr_dashboard.html', 
                         categories=categories,
                         requests_with_users=requests_with_users,
                         volunteers=volunteers,
                         users=users)

# Accept Request
@csr.route('/request/<int:request_id>/accept', methods=['POST'])
@login_required
def csr_accept_request(request_id):
    req = Request.query.get_or_404(request_id)

    req.status = 'Accepted'
    db.session.commit()

    flash('Request has been accepted successfully.', 'success')
    return redirect(url_for('csr.csr_dashboard'))

# Assign Request to Volunteer
@csr.route('/request/<int:request_id>/assign', methods=['POST'])
@login_required
def assign_request(request_id):
    # Get the volunteer_id from the form
    volunteer_id = request.form.get('volunteer_id')
    # Get the request
    req = Request.query.get_or_404(request_id)
    
    if not volunteer_id:
        flash('Please select a volunteer to assign.', 'warning')
        return redirect(url_for('csr.csr_dashboard'))
    
    # Get the volunteer
    volunteer = Volunteer.query.get_or_404(volunteer_id)
    
    # Check if request is already assigned
    if req.status == 'Assigned' or req.status == 'Completed':
        flash('This request has already been assigned or completed.', 'warning')
        return redirect(url_for('csr.csr_dashboard'))
    
    # Check if volunteer is available
    if not volunteer.is_available:
        flash(f'{volunteer.user.name} is not currently available.', category='error')
        return redirect(url_for('csr.csr_dashboard'))
    
    if volunteer.user.status != 'Active':
        flash(f'{volunteer.user.name} does not have an active account.', category='warning')
        return redirect(url_for('csr.csr_dashboard'))
    
    # Assign the volunteer
    req.volunteer_id = volunteer.id
    req.status = 'Assigned'
    volunteer.is_available = False  # Mark volunteer as unavailable (FIXED)
    db.session.commit()
    
    flash(f'Request assigned to {volunteer.user.name} successfully!', category='success')
    return redirect(url_for('csr.csr_dashboard'))


# Complete Reqeust
@csr.route('/request/<int:request_id>/complete', methods=['POST'])
@login_required
def complete_request(request_id):
    req = Request.query.get_or_404(request_id)
    
    if req.status == 'Assigned':
        try:
            req.status = 'Completed'
            
            # Increment volunteer's completed tasks count
            if req.volunteer:
                req.volunteer.total_tasks_completed += 1
                volunteer_name = req.volunteer.user.name
                flash(f'Request "{req.title}" completed by {volunteer_name}. Total tasks completed: {req.volunteer.total_tasks_completed}', 'success')
            else:
                flash(f'Request "{req.title}" has been marked as completed.', 'success')
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error completing request: {str(e)}', 'danger')
    else:
        flash('Only assigned requests can be completed.', 'warning')
    
    return redirect(url_for('csr.csr_dashboard'))

# Delete Request
@csr.route('/request/<int:request_id>/delete', methods=["POST"])
@login_required
def delete_request(request_id):
    req = Request.query.get_or_404(request_id)
    db.session.delete(req)
    db.session.commit()
    flash('Request deleted successfully.', 'danger')
    if current_user.role == 'CSR':
        return redirect(url_for('csr.csr_dashboard'))
    else:
        return redirect(url_for('views.home'))
