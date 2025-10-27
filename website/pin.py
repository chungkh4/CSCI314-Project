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
    # Write Review Here!!!
    return (".")

