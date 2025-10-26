from flask import Blueprint, render_template, flash, redirect, request, url_for
from flask_login import login_required, current_user
from .models import Category, Volunteer, Review, Request, User
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
# @login_required
def add_category():
    name = request.form.get('name')
    description = request.form.get('description')
    
    if not name:
        flash('category name is required.', category='warning')
        return redirect(url_for('platform.platform_manager_dashboard'))
    
    # Check if category already exists
    existing_category = Category.query.filter_by(name=name).first()
    if existing_category:
        flash(f'category "{name}" already exists.', category='danger')
        return redirect(url_for('platform.platform_manager_dashboard'))
    
    # Create new category
    new_category = Category(name=name, description=description)
    db.session.add(new_category)
    db.session.commit()
    
    flash(f'category "{name}" added successfully!', category='success')
    return redirect(url_for('platform.platform_manager_dashboard'))


@platform.route('/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash(f'Category "{category.name}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting category.', 'danger')
    return redirect(url_for('platform.platform_manager_dashboard')) 