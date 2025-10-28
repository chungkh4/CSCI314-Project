from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
import datetime
from .models import User, Request, Shortlist
from . import db

shortlist = Blueprint('shortlist', __name__)


@shortlist.route('/request/<int:request_id>/csr_shortlist', methods=['POST'])
@login_required
def shortlist_item(request_id):
    # Use the IDs matching your database columns and context
    person_account_id = current_user.id
    item_id = request_id

    # 1. Check if the item is already shortlisted (Query uses the composite PK columns)
    existing_entry = Shortlist.query.get((person_account_id, item_id))

    redirect_page = request.referrer or url_for('default_page')

    if existing_entry:
        flash('Item is already in your shortlist.', 'info')
        return redirect(redirect_page)

    # 2. Create and add the new entry (Initialization uses the model's property names)
    new_shortlist = Shortlist(
        user_id=person_account_id,  # Matches the 'user_id' column
        shortlist_request_id=item_id  # Matches the 'shortlist_request_id' column
    )

    try:
        db.session.add(new_shortlist)
        db.session.commit()
        flash(f'Request successfully added to shortlist!', 'success')
    except Exception as e:
        db.session.rollback()
        # Log the error (crucial for debugging)
        print(f"Database Error: {e}")
        flash('An error occurred while saving to the shortlist.', 'danger')

    return redirect(redirect_page)