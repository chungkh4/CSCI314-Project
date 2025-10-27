from datetime import datetime
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    # Account details
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

    date_created = db.Column(db.DateTime(timezone=True), default=func.now())

    # Role: PIN, CSR, Platform Manager, Volunteer
    role = db.Column(db.String(50), default='PIN')

    status = db.Column(db.String(20), default='Pending')  # Pending, Approved, Suspended


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(250))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)


class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Link to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    user = db.relationship('User', backref=db.backref('volunteer_profile', uselist=False))

    # Single category (many-to-one relationship)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', backref='volunteers', foreign_keys=[category_id])

    is_available = db.Column(db.Boolean, default=True)
    total_tasks_completed = db.Column(db.Integer, default=0)


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', backref='requests')

    status = db.Column(db.String(20), default='Pending')  # Pending, Accepted, Completed

    scheduled_datetime = db.Column(db.DateTime, nullable=False)

    view_count = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign key to user who created the request
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Foreign key to volunteer assigned to this request
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteer.id'), nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('requests', lazy=True, cascade='all, delete-orphan'), lazy=True)
    volunteer = db.relationship('Volunteer', backref=db.backref('assigned_requests', lazy=True), lazy=True)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)  # e.g., 1–5 stars
    comment = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Link to the request being reviewed
    request_id = db.Column(db.Integer, db.ForeignKey('request.id'), nullable=False)
    request = db.relationship('Request', backref=db.backref('review', uselist=False, cascade='all, delete-orphan'))

    # Link to the volunteer
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteer.id'), nullable=False)
    volunteer = db.relationship('Volunteer', backref=db.backref('reviews', lazy=True))

    # Link to the user (PIN) who wrote the review
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('reviews_written', lazy=True))


class Logout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    DateTime = db.Column(db.Integer, nullable=False)
