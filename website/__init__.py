from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager

from werkzeug.security import generate_password_hash

db = SQLAlchemy()
DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'test123'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'

    db.init_app(app)

    from .views import views
    from .auth import auth
    from .admin import admin
    from .csr import csr
    from .pin import pin
    from .volunteer import volunteer
    from .platform import platform
    from .shortlist import shortlist

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(pin, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/')
    app.register_blueprint(csr, url_prefix='/')
    app.register_blueprint(volunteer, url_prefix='/')
    app.register_blueprint(platform, url_prefix='/')
    app.register_blueprint(shortlist, url_prefix='/')


    from .models import User

    create_database(app)
    create_admin(app)

    login_manager = LoginManager()

    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    return app

# Create the daatabase if it doesn't exist
def create_database(app):   
    with app.app_context():
        if not path.exists('website/' + DB_NAME):
            db.create_all()
            print('Created Database!')

# Create an admin account if it doesn't exist (One admin only)
def create_admin(app):
    from .models import User
    with app.app_context():
        admin = User.query.filter_by(role='Admin').first()
        if not admin:
            admin_user = User(
                name='Admin',
                email='admin',
                password=generate_password_hash("admin", method='pbkdf2:sha256'),
                role='Admin',
                status='Active'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin account created automatically!")
        else:
            print("Admin account already exists.")