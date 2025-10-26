from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from . import db
from website.models import Request, Review, User

# url holders
pin = Blueprint('pin', __name__)

@pin.route('/pin/profile')
@login_required
def pin_profile():
    if current_user.role != 'PIN':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    
    requests = Request.query.filter_by(user_id=current_user.id).order_by(Request.date_created.desc()).all()
    
    return render_template("pin_profile.html", requests=requests)

@pin.route('/request/<int:request_id>/review', methods=['GET', 'POST'])
@login_required
def review_request(request_id):
    req = Request.query.get_or_404(request_id)

    # Only the PIN who created the request can review
    if req.user_id != current_user.id:
        flash("You are not authorized to review this request.", "danger")
        return redirect(url_for('views.home'))

    # Only allow review if request is completed
    if req.status != 'Completed':
        flash("You can only review completed requests.", "warning")
        return redirect(url_for('views.home'))

    # Check if a review already exists
    if req.review:
        flash("You have already reviewed this request.", "info")
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')

        new_review = Review(
            rating=rating,
            comment=comment,
            request_id=req.id,
            volunteer_id=req.volunteer_id,
            user_id=current_user.id
        )
        db.session.add(new_review)
        db.session.commit()

        flash("Thank you for your feedback!", "success")
        return redirect(url_for('views.home'))

    return render_template('review.html', req=req)