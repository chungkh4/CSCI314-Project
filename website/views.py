from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from . import db
from website.models import Category, Request, User

from datetime import datetime

# url holders
views = Blueprint('views', __name__)


# Home Page
@views.route('/')
def home():
    # Redirect unauthenticated users to login
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    # Get all categories from database
    categories = Category.query.order_by(Category.name).all()

    # Get filter parameters
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', 'newest')

    # Start with base query
    query = Request.query

    # Apply search filter (searches in title and description)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Request.title.ilike(search_pattern),
                Request.description.ilike(search_pattern)
            )
        )

    # Apply category filter
    if category_filter:
        query = query.join(Category).filter(Category.name == category_filter)

    # Apply status filter
    if status_filter:
        query = query.filter(Request.status == status_filter)

    # Apply sorting
    if sort_by == 'oldest':
        query = query.order_by(Request.date_created.asc())
    elif sort_by == 'views':
        query = query.order_by(Request.view_count.desc())
    elif sort_by == 'title':
        query = query.order_by(Request.title.asc())
    else:  # newest (default)
        query = query.order_by(Request.date_created.desc())

    # Execute query
    requests = query.all()

    return render_template(
        'home.html',
        user=current_user,
        requests=requests,
        categories=categories
    )


# Edit Profile For all user
@views.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        if not name or not email:
            flash("Please fill out all required fields.", "danger")
            return redirect(url_for('views.edit_profile'))

        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != current_user.id:
            flash("Email is already in use.", "danger")
            return redirect(url_for('views.edit_profile'))

        # Update user info
        current_user.name = name
        current_user.email = email
        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('views.home'))

    return render_template('edit_profile.html', user=current_user)


@views.route('/csr/profile')
@login_required
def csr_profile():
    if current_user.role != 'CSR':
        flash('Cannot access this Profile.', 'danger')
        return redirect(url_for('views.home'))
    return render_template('csr_profile.html', user=current_user)


@views.route('/platform-manager/profile')
@login_required
def platform_manager_profile():
    if current_user.role != 'Platform Manager':
        flash('Cannot access this Profile.', 'danger')
        return redirect(url_for('views.home'))
    return render_template('platform_manager_profile.html', user=current_user)


# views other users' profiles
@views.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)

    # Check if the current user is viewing their own profile
    is_owner = (current_user.id == user.id)

    return render_template('profile.html', user=user, is_owner=is_owner)


# Create Requests
@views.route('/create-request', methods=['GET', 'POST'])
@login_required
def create_request():
    now_str = datetime.now().strftime('%Y-%m-%dT%H:%M')

    if request.method == 'POST':
        title = request.form['title']
        category_id = request.form['category_id']
        description = request.form['description']
        scheduled_datetime = request.form['scheduled_datetime']

        if not category_id:
            flash('Please select a category.', 'danger')
            return redirect(url_for('views.create_request'))

        # Convert to Python datetime object
        scheduled_datetime = datetime.fromisoformat(scheduled_datetime)

        new_request = Request(
            title=title,
            category_id=category_id,
            description=description,
            scheduled_datetime=scheduled_datetime,
            user_id=current_user.id
        )
        db.session.add(new_request)
        db.session.commit()
        flash('Request created successfully!', 'success')
        return redirect(url_for('pin.pin_profile'))

    categories = Category.query.all()
    return render_template('create_request.html', categories=categories, now_str=now_str)


# Edit Requests by ID
@views.route('/request/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_request(id):
    req = Request.query.get_or_404(id)
    categories = Category.query.all()

    if req.user_id != current_user.id:
        flash("You can only edit your own requests.", "danger")
        return redirect(url_for('home'))

    if req.status != 'Pending':
        flash("Only pending requests can be edited.", "warning")
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        req.title = request.form['title']
        req.description = request.form['description']
        req.category_id = request.form['category_id']  # assuming you store category by ID
        scheduled_datetime = request.form.get('scheduled_datetime')
        if scheduled_datetime:
            from datetime import datetime
            req.scheduled_datetime = datetime.fromisoformat(scheduled_datetime)
        db.session.commit()

        flash("Request updated successfully!", "success")
        return redirect(url_for('views.home'))

    return render_template('edit_request.html', req=req, categories=categories)


@views.route('/approve/<int:id>')
@login_required
def approve_request(id):
    if current_user.role != 'Platform Manager':
        flash("Only platform managers can approve requests.", "danger")
        return redirect(url_for('home'))

    req = Request.query.get_or_404(id)
    req.status = 'Approved'
    db.session.commit()
    flash(f"Request '{req.title}' approved successfully.", "success")
    return redirect(url_for('views.home'))


# Update Requests
@views.route('/update_request/<int:id>', methods=['POST'])
@login_required
def update_request(id):
    req = Request.query.get_or_404(id)

    # Only CSR or Platform Manager can update
    if current_user.role not in ['CSR', 'Platform Manager']:
        flash("Only CSR or Platform Manager can update requests.", "danger")
        return redirect(url_for('views.home'))

    new_status = request.form.get('status')
    if new_status not in ['Accepted', 'Completed', 'Pending']:
        flash("Invalid status value.", "danger")
        return redirect(url_for('views.home'))

    req.status = new_status
    db.session.commit()
    flash(f"Request '{req.title}' status updated to {new_status}.", "success")
    return redirect(url_for('views.csr_profile'))


# View Specific Request with ID
@views.route('/request/<int:id>')
@login_required
def view_request(id):
    # Get the request, or 404 if it doesn't exist
    req = Request.query.get_or_404(id)

    # Increment view count if the viewer is NOT the owner
    if req.user_id != current_user.id:
        req.view_count += 1
        db.session.commit()

    # Pass request and owner info to template
    owner = User.query.get(req.user_id)
    return render_template('view_req.html', req=req, owner=owner)
