from datetime import datetime
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True) # unique id for each user

    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

    date_created = db.Column(db.DateTime(timezone=True), default=func.now())

    role = db.Column(db.String(50), default='PIN')  # user role: PIN, Platform Manager, RSP

    is_admin = db.Column(db.Boolean, default=False) # admin 
    status = db.Column(db.String(20), default='Pending')  # account status: Pending, Approved, Suspended, Rejected


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Accepted, Completed
    view_count = db.Column(db.Integer, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign key link to the user who created it
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationship to user
    user = db.relationship('User', backref='requests', lazy=True)