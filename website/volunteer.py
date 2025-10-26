from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from .models import Request, Review, Volunteer, User
from . import db

volunteer = Blueprint('volunteer', __name__)

# Volunteer Dashboard
@volunteer.route('/volunteer/dashboard')
@login_required
def volunteer_dashboard():
    # Ensure the user has the volunteer role
    if current_user.role != 'Volunteer':
        flash('Access denied. Volunteer role required.', 'danger')
        return redirect(url_for('views.home'))
    
    if current_user.status != 'Active':
        flash('Your account is not active. Access denied.', 'danger')
        return redirect(url_for('views.home'))

    # Get volunteer profile
    volunteer_profile = Volunteer.query.filter_by(user_id=current_user.id).first()
    
    if not volunteer_profile:
        flash('Volunteer profile not found.', category='error')
        return redirect(url_for('views.home'))
    
    upcoming_requests = Request.query.filter(
        Request.volunteer_id == volunteer_profile.id,
        Request.status.in_(['Assigned', 'In Progress'])
).order_by(Request.date_created.desc()).all()
    
    
    # Get completed requests
    completed_requests = Request.query.filter(
        Request.volunteer_id == volunteer_profile.id,
        Request.status == 'Completed'
    ).order_by(Request.date_created.desc()).all()
    
    # Calculate review statistics
    reviews = Review.query.filter_by(volunteer_id=volunteer_profile.id).all()
    total_reviews = len(reviews)
    avg_rating = sum(r.rating for r in reviews) / total_reviews if total_reviews > 0 else None

    # volunteer_profile.is_available = True
    # db.session.commit()

    return render_template(
        'volunteer_dashboard.html',
        volunteer=volunteer_profile,
        upcoming_requests=upcoming_requests,
        completed_requests=completed_requests,
        total_reviews=total_reviews,
        avg_rating=avg_rating
    )

# Volunteer accepts Request
@volunteer.route('/request/<int:request_id>/volunteer_accept', methods=['POST'])
@login_required
def volunteer_accept_task(request_id):
    """Volunteer confirms they are working on the assigned task"""
    
    
    if current_user.role != 'Volunteer':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    
    volunteer_profile = current_user.volunteer_profile

    if not volunteer_profile:
        flash('Volunteer profile not found.', 'danger')
        return redirect(url_for('views.home'))
    
    req = Request.query.get_or_404(request_id)
    
    # Verify this request is assigned to this volunteer
    # if req.volunteer_id != volunteer_profile.id:
    #     flash('This request is not assigned to you.', 'danger')
    #     return redirect(url_for('volunteer.volunteer_dashboard'))
    
    # if req.status != 'Assigned':
    #     flash('This task cannot be started at this time.', 'warning')
    #     return redirect(url_for('volunteer.volunteer_dashboard'))
    
    try:
        volunteer_profile.is_available = False
        req.status = "In Progress"
        db.session.commit()
        flash(f'You have started working on: "{req.title}". Good luck!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting task: {str(e)}', 'danger')
    
    return redirect(url_for('volunteer.volunteer_dashboard'))


# Volunteer declines Request
@volunteer.route('/volunteer/request/<int:request_id>/decline', methods=['POST'])
@login_required
def decline_task(request_id):
    """Volunteer declines a task"""
    if current_user.role != 'Volunteer':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    
    volunteer_profile = current_user.volunteer_profile
    if not volunteer_profile:
        flash('Volunteer profile not found.', 'danger')
        return redirect(url_for('views.home'))
    
    req = Request.query.get_or_404(request_id)
    
    # Verify this request is assigned to this volunteer
    if req.volunteer_id != volunteer_profile.id:
        flash('This request is not assigned to you.', 'danger')
        return redirect(url_for('volunteer.volunteer_dashboard'))
    
    try:
        # Unassign the volunteer and reset status
        req.volunteer_id = None
        req.status = 'Accepted'
        # FIXED: Make volunteer available again when declining
        volunteer_profile.is_available = True
        db.session.commit()
        flash(f'You have declined the task: "{req.title}". It has been returned to pending.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error declining task: {str(e)}', 'danger')
    
    return redirect(url_for('volunteer.volunteer_dashboard'))

# Volunteer completes Request
@volunteer.route('/volunteer/request/<int:request_id>/complete', methods=['POST'])
@login_required
def complete_task(request_id):
    """Volunteer marks a task as completed"""
    if current_user.role != 'Volunteer':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    
    volunteer_profile = current_user.volunteer_profile
    if not volunteer_profile:
        flash('Volunteer profile not found.', 'danger')
        return redirect(url_for('views.home'))
    
    req = Request.query.get_or_404(request_id)
    
    # Verify this request is assigned to this volunteer
    if req.volunteer_id != volunteer_profile.id:
        flash('This request is not assigned to you.', 'danger')
        return redirect(url_for('volunteer.volunteer_dashboard'))
    
    try:
        # Mark as completed and increment volunteer's count
        req.status = 'Completed'
        volunteer_profile.total_tasks_completed += 1
        volunteer_profile.is_available = True
        db.session.commit()
        flash(f'Congratulations! You have completed the task: "{req.title}". Total completed: {volunteer_profile.total_tasks_completed}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error completing task: {str(e)}', 'danger')
    
    return redirect(url_for('volunteer.volunteer_dashboard'))