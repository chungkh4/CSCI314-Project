from flask import Blueprint, render_template, flash, redirect, request, url_for
from flask_login import login_required, current_user
from .models import Category, Volunteer, Review, Request, User, Csr
from sqlalchemy import func
from . import db

platform = Blueprint('platform', __name__)

@platform.route('/platform-manager/dashboard')
@login_required
def platform_manager_dashboard():
    # Check if user is platform manager
    if current_user.role != 'Platform Manager':
        flash('Access denied. Platform Manager role required.', category='danger')
        return redirect(url_for('views.home'))
    
    if current_user.status != 'Active':
        flash('Your account is not active. Access denied.', category='danger')
        return redirect(url_for('views.home'))
        
    # Total volunteers
    total_volunteers = Volunteer.query.count()
    
    # Total completed tasks
    total_completed_tasks = Request.query.filter_by(status='Completed').count()

    # Get all categories
    categories = Category.query.order_by(Category.name).all()
    
    # Total reviews
    total_reviews = Review.query.count()
    
    # Overall average rating
    avg_rating_result = db.session.query(func.avg(Review.rating)).scalar()
    overall_avg_rating = float(avg_rating_result) if avg_rating_result else None
    
    # Rating distribution (count of each rating 1-5)
    rating_distribution = {}
    for rating in range(5, 0, -1):  # 5 to 1 stars
        count = Review.query.filter_by(rating=rating).count()
        rating_distribution[rating] = count
    
    # Volunteer statistics with their performance
    volunteer_stats = []
    volunteers = Volunteer.query.all()
    
    for vol in volunteers:
        reviews = Review.query.filter_by(volunteer_id=vol.id).all()
        review_count = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / review_count if review_count > 0 else None
        
        volunteer_stats.append({
            'name': vol.user.name,
            'category': vol.category.name if vol.category else None,
            'tasks_completed': vol.total_tasks_completed,
            'review_count': review_count,
            'avg_rating': avg_rating
        })
    
    # Sort by average rating (descending), then by tasks completed
    volunteer_stats.sort(key=lambda x: (x['avg_rating'] or 0, x['tasks_completed']), reverse=True)
    
    # Recent reviews (last 10)
    recent_reviews_query = Review.query.order_by(Review.date_created.desc()).limit(10).all()
    recent_reviews = []
    
    for review in recent_reviews_query:
        recent_reviews.append({
            'volunteer_name': review.volunteer.user.name,
            'task_title': review.request.title,
            'rating': review.rating,
            'comment': review.comment,
            'date': review.date_created,
            'reviewer_name': review.user.name
        })
    
    return render_template(
        'platform_manager_dashboard.html',
        total_volunteers=total_volunteers,
        total_completed_tasks=total_completed_tasks,
        total_reviews=total_reviews,
        overall_avg_rating=overall_avg_rating,
        rating_distribution=rating_distribution,
        volunteer_stats=volunteer_stats,
        recent_reviews=recent_reviews,
        categories=categories
    )


# Add Categories for requests
@platform.route('/add-category', methods=['POST'])
@login_required
def add_category():
    # Only Platform Manager with Active status can add
    if current_user.role != 'Platform Manager':
        flash('Access denied. Platform Manager role required.', category='danger')
        return redirect(url_for('views.home'))
    if current_user.status != 'Active':
        flash('Your account is not active. Access denied.', category='danger')
        return redirect(url_for('views.home'))

    dashboard = url_for('platform.platform_manager_dashboard')

    # Get and normalize inputs
    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()

    if not name:
        flash('Category name is required.', category='warning')
        return redirect(dashboard)

   # Collapse internal whitespace and use that as the canonical stored value
    normalized_name = ' '.join(name.split())

    # Case-insensitive duplicate check using LOWER() to catch 'Transport' vs 'transport'
    exists = db.session.scalar(
        db.select(Category.id).where(func.lower(Category.name) == normalized_name.lower())
    )
    if exists:
        flash(f'Category "{normalized_name}" already exists.', category='danger')
        return redirect(dashboard)

    # Create & commit
    new_category = Category(name=normalized_name, description=description)
    db.session.add(new_category)
    try:
        db.session.commit()
    except IntegrityError:
        # In case two requests race and hit the unique constraint
        db.session.rollback()
        flash(f'Category "{normalized_name}" already exists.', category='danger')
        return redirect(dashboard)
    except Exception:
        db.session.rollback()
        flash('Could not add category. Please try again later.', category='danger')
        return redirect(dashboard)

    flash(f'Category "{normalized_name}" added successfully!', category='success')
    return redirect(dashboard)


### edit volunteer service category ###
@platform.route('/category/<int:category_id>/edit', methods=['POST'])
@login_required
def edit_category(category_id):
    if current_user.role != 'Platform Manager' or current_user.status != 'Active':
        flash('Access denied.', 'danger')
        return redirect(url_for('platform.platform_manager_dashboard'))

    from .models import Category
    from . import db

    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()

    if not name:
        flash('Category name is required.', 'warning')
        return redirect(url_for('platform.platform_manager_dashboard'))

    cat = Category.query.get_or_404(category_id)
    cat.name = name
    cat.description = description if description else None

    try:
        db.session.commit()
        flash('Category updated successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error updating category. Please try again.', 'danger')

    return redirect(url_for('platform.platform_manager_dashboard'))


### delete volunteer service category ###
@platform.route('/delete_category/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
   # platform manager only function: delete volunteer category 
    if current_user.role != 'Platform Manager':
        flash('Access denied. Platform Manager role required.', category='danger')
        return redirect(url_for('views.home'))
    if current_user.status != 'Active':
        flash('Your account is not active. Access denied.', category='danger')
        return redirect(url_for('views.home'))

    category = Category.query.get_or_404(category_id)

    # count dependents - check requests using the category + volunteers linked to category 
    req_count = Request.query.filter_by(category_id=category.id).count()
    vol_q = Volunteer.query.filter_by(category_id=category.id)
    vol_count = vol_q.count()

    # if there are requests linked to this category, block deletion (Request.category_id is NOT NULL)
    if req_count > 0:
        flash(
            f'Cannot delete "{category.name}" — there are {req_count} request(s) using this category. '
            'Reassign or delete those requests first.', 
            'danger'
        )
        return redirect(url_for('platform.platform_manager_dashboard'))

    # if volunteers are attached to category, remove their relation
    if vol_count > 0:
        for v in vol_q.all():
            v.category_id = None
        db.session.flush()  # stage updates so delete dont violate FKs

    try:
        db.session.delete(category)
        db.session.commit()
        if vol_count > 0:
            flash(f'Category "{category.name}" deleted. {vol_count} volunteer(s) were detached.', 'success')
        else:
            flash(f'Category "{category.name}" deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error deleting category. Please try again later.', 'danger')

    return redirect(url_for('platform.platform_manager_dashboard'))


# --- Reports: Generate & Export ---------------------------------------------
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime, timedelta
from io import StringIO, BytesIO
import csv

from .models import db, Request, Category  # adjust if your model names differ
from flask_login import login_required, current_user

# utility: require Platform Manager
def _ensure_platform_manager():
    # adjust this check to your exact role string if different
    return getattr(current_user, "role", "").lower() in {"platform manager", "platform_manager", "pm"}

def _safe_date(value, default=None):
    """Parse YYYY-MM-DD to date. Return default (or None) on failure."""
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return default


def _request_date_col():
    return Request.date_created


@platform.route("/reports", methods=["GET", "POST"])
@login_required
def platform_reports():
    if not _ensure_platform_manager():
        flash("Only Platform Managers can access reports.", "danger")
        return redirect(url_for("views.index"))

    # defaults: last 7 days
    today = datetime.utcnow().date()
    default_start = today - timedelta(days=6)
    default_end = today

    # form values
    if request.method == "POST":
        start_date = _safe_date(request.form.get("start_date"), default_start)
        end_date = _safe_date(request.form.get("end_date"), default_end)
        report_type = request.form.get("report_type") or "summary"
    else:
        start_date = _safe_date(request.args.get("start_date"), default_start)
        end_date = _safe_date(request.args.get("end_date"), default_end)
        report_type = request.args.get("report_type") or "summary"

    # normalize end to include that full day
    end_dt_inclusive = datetime.combine(end_date, datetime.max.time())
    start_dt_inclusive = datetime.combine(start_date, datetime.min.time())

    # build query
    date_col = _request_date_col()
    q = Request.query.filter(date_col.between(start_dt_inclusive, end_dt_inclusive))

    # optional: eager load category (only if you have relationship named "category")
    # q = q.options(joinedload(Request.category))

    requests = q.all()

    # --- prepare data for Summary or Detailed
    if report_type == "detailed":
        # rows for table
        detailed_rows = []
        for r in requests:
            category_name = getattr(getattr(r, "category", None), "name", "Unassigned")
            status = getattr(r, "status", "Unknown")
            title = getattr(r, "title", f"Request #{r.id}")
            created_on = getattr(r, "created_at", None) or getattr(r, "created_on", None) or getattr(r, "date", None)
            views = getattr(r, "views", 0)

            detailed_rows.append({
                "id": r.id,
                "title": title,
                "category": category_name,
                "status": status,
                "created_on": created_on,
                "views": views,
            })

        return render_template(
            "platform_reports.html",
            start_date=start_date,
            end_date=end_date,
            report_type=report_type,
            detailed=detailed_rows,
            summary=None
        )

    # summary (default): totals by category + totals by status
    by_category = {}
    by_status = {}

    for r in requests:
        cat = getattr(getattr(r, "category", None), "name", "Unassigned")
        by_category[cat] = by_category.get(cat, 0) + 1

        st = getattr(r, "status", "Unknown")
        by_status[st] = by_status.get(st, 0) + 1

    summary = {
        "total_requests": len(requests),
        "by_category": sorted(by_category.items(), key=lambda x: x[0].lower()),
        "by_status": sorted(by_status.items(), key=lambda x: x[0].lower()),
    }

    return render_template(
        "platform_reports.html",
        start_date=start_date,
        end_date=end_date,
        report_type="summary",
        summary=summary,
        detailed=None
    )

@platform.route("/reports/export", methods=["POST"])
@login_required
def platform_reports_export():
    if not _ensure_platform_manager():
        flash("Only Platform Managers can download reports.", "danger")
        return redirect(url_for("views.index"))

    start_date = _safe_date(request.form.get("start_date"))
    end_date = _safe_date(request.form.get("end_date"))
    report_type = request.form.get("report_type") or "summary"
    if not start_date or not end_date:
        flash("Please select a valid date range.", "warning")
        return redirect(url_for("platform.platform_reports"))

    date_col = _request_date_col()
    start_dt_inclusive = datetime.combine(start_date, datetime.min.time())
    end_dt_inclusive = datetime.combine(end_date, datetime.max.time())

    q = Request.query.filter(date_col.between(start_dt_inclusive, end_dt_inclusive))
    requests = q.all()

    # Create CSV in memory
    si = StringIO()
    writer = csv.writer(si)

    if report_type == "detailed":
        writer.writerow(["ID", "Title", "Category", "Status", "Created On", "Views"])
        for r in requests:
            category_name = getattr(getattr(r, "category", None), "name", "Unassigned")
            status = getattr(r, "status", "Unknown")
            title = getattr(r, "title", f"Request #{r.id}")
            created_on = getattr(r, "created_at", None) or getattr(r, "created_on", None) or getattr(r, "date", None)
            views = getattr(r, "views", 0)

            writer.writerow([r.id, title, category_name, status, created_on, views])

        filename = f"requests_detailed_{start_date}_to_{end_date}.csv"

    else:
        # summary
        by_category = {}
        by_status = {}
        for r in requests:
            cat = getattr(getattr(r, "category", None), "name", "Unassigned")
            by_category[cat] = by_category.get(cat, 0) + 1

            st = getattr(r, "status", "Unknown")
            by_status[st] = by_status.get(st, 0) + 1

        writer.writerow(["Summary", f"{start_date} to {end_date}"])
        writer.writerow(["Total Requests", len(requests)])
        writer.writerow([])
        writer.writerow(["By Category"])
        writer.writerow(["Category", "Count"])
        for k, v in sorted(by_category.items(), key=lambda x: x[0].lower()):
            writer.writerow([k, v])
        writer.writerow([])
        writer.writerow(["By Status"])
        writer.writerow(["Status", "Count"])
        for k, v in sorted(by_status.items(), key=lambda x: x[0].lower()):
            writer.writerow([k, v])

        filename = f"requests_summary_{start_date}_to_{end_date}.csv"

    output = BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )
