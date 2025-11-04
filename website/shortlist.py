from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
import datetime
from .models import User, Request, Shortlist
from . import db

shortlist = Blueprint('shortlist', __name__)


@shortlist.route('/request/<int:request_id>/csr_shortlist', methods=['POST'])
@login_required
def shortlist_request(request_id):
    csr_account_id = current_user.id

    # check if the item is already shortlisted
    existing_entry = Shortlist.query.get((csr_account_id, request_id))

    redirect_page = request.referrer or url_for('default_page')

    if existing_entry:
        flash('Item is already in your shortlist.', 'info')
        return redirect(redirect_page)

    # create and add the new entry
    new_shortlist = Shortlist(
        user_id=csr_account_id,
        shortlist_request_id=request_id
    )

    try:
        db.session.add(new_shortlist)
        db.session.commit()
        flash(f'Request successfully added to shortlist!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Database Error: {e}")
        flash('An error occurred while saving to the shortlist.', 'danger')

    return redirect(redirect_page)