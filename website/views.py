from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from . import db
from website.models import Request, User

# url holders
views = Blueprint('views', __name__)


@views.route('/')
def home():
    # Get query parameters from URL
    search_query = request.args.get('search', '')  # Get search from query string

    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    sort_option = request.args.get('sort', 'newest')

    # Start query
    requests_query = Request.query

    # Filter by status
    if status_filter:
        requests_query = requests_query.filter_by(status=status_filter)

    # Filter by category
    if category_filter:
        requests_query = requests_query.filter_by(category=category_filter)

    # Search by title or description
    if search_query:
        requests_query = requests_query.filter(
            (Request.title.ilike(f'%{search_query}%')) | 
            (Request.description.ilike(f'%{search_query}%'))
        )

    # Sorting
    if sort_option == 'newest':
        requests_query = requests_query.order_by(Request.date_created.desc())
    elif sort_option == 'oldest':
        requests_query = requests_query.order_by(Request.date_created.asc())
    elif sort_option == 'views':
        requests_query = requests_query.order_by(Request.view_count.desc())
    elif sort_option == 'title':
        requests_query = requests_query.order_by(Request.title.asc())

    # Execute query
    requests_list = requests_query.all()

    # Eager load user to display owner name (avoid multiple queries)
    for req in requests_list:
        req.user = User.query.get(req.user_id)

    return render_template('home.html', requests=requests_list)
@views.route('/pin/profile')
@login_required
def pin_profile():
    if current_user.role != 'PIN':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    
    requests = Request.query.filter_by(user_id=current_user.id).order_by(Request.date_created.desc()).all()
    
    return render_template("pin_profile.html", requests=requests)

# Edit PIN profile
@views.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.role != 'PIN':
        flash("Access denied.", "danger")
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        if not name or not email:
            flash("Please fill out all required fields.", "warning")
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
        return redirect(url_for('views.pin_profile'))

    return render_template('edit_profile.html', user=current_user)


@views.route('/csr/profile')
# @login_required
def csr_profile():
    if current_user.role != 'CSR':
        flash('Access denied.', 'danger')
        return redirect(url_for('views.home'))
    return render_template('csr_profile.html', user=current_user)


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
    if current_user.role != "PIN":
        flash("Only PINs can create requests.", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']

        new_request = Request(
            title=title,
            description=description,
            category=category,
            user_id=current_user.id
        )
        db.session.add(new_request)
        db.session.commit()

        flash("Request created successfully! Waiting for approval.", "success")
        return redirect(url_for('views.home'))

    return render_template('create_request.html')

# Edit Requests by ID
@views.route('/request/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_request(id):
    req = Request.query.get_or_404(id)

    if req.user_id != current_user.id:
        flash("You can only edit your own requests.", "danger")
        return redirect(url_for('home'))

    if req.status != 'Pending':
        flash("Only pending requests can be edited.", "warning")
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        req.title = request.form['title']
        req.description = request.form['description']
        req.category = request.form['category']
        db.session.commit()

        flash("Request updated successfully!", "success")
        return redirect(url_for('views.home'))

    return render_template('edit_request.html', req=req)


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


# Update Requests by ID (for CSR or Platform Manager)
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

