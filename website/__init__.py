import os
import click
import csv

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import func
from werkzeug.security import generate_password_hash


# --- DB handle (shared) ---
db = SQLAlchemy()

DB_NAME = "database.db"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test123"

    # ----- Resolve absolute DB path in /instance -----
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # project root
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)  # make sure folder exists

    DB_PATH = os.path.join(INSTANCE_DIR, DB_NAME)
    DB_URI = "sqlite:///" + DB_PATH.replace("\\", "/")  # Windows-safe URI

    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # ----- Blueprints -----
    from .views import views
    from .auth import auth
    from .admin import admin
    from .csr import csr
    from .pin import pin
    from .volunteer import volunteer
    from .platform import platform
    from .shortlist import shortlist

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(auth, url_prefix="/")
    app.register_blueprint(admin, url_prefix="/")
    app.register_blueprint(csr, url_prefix="/")
    app.register_blueprint(pin, url_prefix="/")
    app.register_blueprint(volunteer, url_prefix="/")
    app.register_blueprint(platform, url_prefix="/")
    app.register_blueprint(shortlist, url_prefix="/")

    # ----- Login manager -----
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models import User
        # modern pattern; avoids extra query if already in session
        return db.session.get(User, int(user_id))

    # ----- First-run: create DB + default admin -----
    with app.app_context():
        from .models import User  # import inside app ctx to avoid circulars

        if not os.path.exists(DB_PATH):
            db.create_all()
            print("Created database at:", DB_PATH)

        # create admin once
        exists_admin = db.session.scalar(
            db.select(User.id).where(User.role == "Admin")
        )
        if not exists_admin:
            admin_user = User(
                name="Admin",
                email="admin",
                password=generate_password_hash("admin", method="pbkdf2:sha256"),
                role="Admin",
                status="Active",
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin account created.")
        else:
            print("Admin account already exists.")

    # ----- CLI: seed categories (idempotent) -----
    from .models import Category  # after db.init_app

    @app.cli.command("seed")
    @click.argument("what")
    @click.option("--file", "file_path", type=click.Path(exists=True), help="CSV with headers: name,description")
    def seed_command(what, file_path):
        """
        Usage:
          flask seed categories --file scripts/categories.csv
        """
        if what != "categories":
            click.echo("Only 'categories' is supported.")
            return
        if not file_path:
            click.echo("Please pass --file path/to/categories.csv")
            return

        inserted = 0
        with app.app_context():
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    desc = (row.get("description") or "").strip()
                    if not name:
                        continue
                    # skip if exists (case-insensitive)
                    exists = db.session.scalar(
                        db.select(Category.id).where(func.lower(Category.name) == name.lower())
                    )
                    if exists:
                        continue
                    db.session.add(Category(name=name, description=desc))
                    inserted += 1
            db.session.commit()
        click.echo(f"Inserted {inserted} categories from {file_path}.")

    # ----- CLI: seed CSR accounts (idempotent) -----
    @app.cli.command("seed_csrs")
    @click.option("--file", "file_path", type=click.Path(exists=True), help="CSV with headers: email,username,password,confirm_password,role")
    def seed_csrs(file_path):
        """
        Usage:
          flask seed_csrs --file scripts/csr_accounts.csv
        """
        if not file_path:
            click.echo("Please pass --file path/to/csr_accounts.csv")
            return

        from .models import User  # import here to avoid circular import

        created = 0
        skipped = 0
        with app.app_context():
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get("email") or "").strip()
                    username = (row.get("username") or "").strip()
                    password = (row.get("password") or "").strip()
                    role = (row.get("role") or "CSR").strip()

                    if not email or not username or not password:
                        skipped += 1
                        continue

                    # Skip if email or username already exists
                    exists = db.session.scalar(
                        db.select(User.id).where(func.lower(User.email) == email.lower())
                    )
                    if exists:
                        skipped += 1
                        continue

                    user = User(
                        name=username,
                        email=email,
                        password=generate_password_hash(password, method="pbkdf2:sha256"),
                        role=role,
                        status="Active"
                    )
                    db.session.add(user)
                    created += 1

                db.session.commit()
        click.echo(f"✅ Seeded {created} CSR accounts. Skipped {skipped} duplicates or invalid entries.")

    # ----- CLI: seed Volunteer accounts (idempotent) -----
    @app.cli.command("seed_volunteers")
    @click.option("--file", "file_path", type=click.Path(exists=True), help="CSV with headers: email,username,password,confirm_password,role,category")
    def seed_volunteers(file_path):
        """
        Usage:
          flask seed_volunteers --file scripts/volunteer_accounts.csv
        """
        if not file_path:
            click.echo("Please pass --file path/to/volunteer_accounts.csv")
            return

        from .models import User, Category  # import inside to avoid circulars

        created = 0
        skipped = 0
        with app.app_context():
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get("email") or "").strip()
                    username = (row.get("username") or "").strip()
                    password = (row.get("password") or "").strip()
                    role = (row.get("role") or "Volunteer").strip()
                    category_name = (row.get("category") or "").strip()

                    if not email or not username or not password:
                        skipped += 1
                        continue

                    # Skip duplicates
                    exists = db.session.scalar(
                        db.select(User.id).where(func.lower(User.email) == email.lower())
                    )
                    if exists:
                        skipped += 1
                        continue

                    # Find matching category (optional)
                    category = db.session.scalar(
                        db.select(Category).where(func.lower(Category.name) == category_name.lower())
                    )

                    user = User(
                        name=username,
                        email=email,
                        password=generate_password_hash(password, method="pbkdf2:sha256"),
                        role=role,
                        status="Active"
                    )

                    db.session.add(user)
                    created += 1

                db.session.commit()
        click.echo(f"✅ Seeded {created} volunteer accounts. Skipped {skipped} duplicates or invalid entries.")


    return app
