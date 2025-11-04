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
        else: 
            print("Database already exists at:", DB_PATH)

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
    # ----- CLI: seed volunteers from CSV (creates user + volunteer rows) -----
    @app.cli.command("seed_volunteers")
    @click.option(
        "--file", "file_path",
        type=click.Path(exists=True),
        required=True,
        help="CSV headers: email,username,password,role,category"
    )
    def seed_volunteers(file_path):
        """
        Usage:
          flask seed_volunteers --file scripts/volunteer_accounts.csv
        Creates/updates User(role='Volunteer') and ensures a row exists in volunteer table.
        """
        from .models import User, Category, Volunteer

        created_users = 0
        created_vol_rows = 0
        skipped = 0

        with app.app_context(), open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = (row.get("email") or "").strip()
                username = (row.get("username") or "").strip()
                password = (row.get("password") or "").strip() or "1234567"
                role = (row.get("role") or "Volunteer").strip()
                category_name = (row.get("category") or "").strip()

                if not email or not username:
                    skipped += 1
                    continue

                # Find or create the user
                user = db.session.scalar(
                    db.select(User).where(func.lower(User.email) == email.lower())
                )
                if not user:
                    user = User(
                        name=username,
                        email=email,
                        password=generate_password_hash(password, method="pbkdf2:sha256"),
                        role="Volunteer",  # normalize casing
                        status="Active",
                    )
                    db.session.add(user)
                    db.session.flush()  # get user.id
                    created_users += 1
                else:
                    # make sure role/status are correct
                    user.role = "Volunteer"
                    if not user.status:
                        user.status = "Active"

                # Resolve category id (optional)
                cat_id = None
                if category_name:
                    cat_id = db.session.scalar(
                        db.select(Category.id)
                        .where(func.lower(Category.name) == category_name.lower())
                    )

                # Ensure a volunteer row exists
                exists_vol = db.session.scalar(
                    db.select(Volunteer.id).where(Volunteer.user_id == user.id)
                )
                if not exists_vol:
                    vol = Volunteer(
                        user_id=user.id,
                        category_id=cat_id,
                        is_available=True,
                        total_tasks_completed=0
                    )
                    db.session.add(vol)
                    created_vol_rows += 1

            db.session.commit()
        click.echo(f"Users created: {created_users}, volunteer rows created: {created_vol_rows}, skipped: {skipped}")

    @app.cli.command("map_volunteer_categories")
    @click.option(
        "--file", "file_path",
        type=click.Path(exists=True), required=True,
        help="CSV headers: email OR username, and category"
    )
    def map_volunteer_categories(file_path):
        """
        Usage:
          flask map_volunteer_categories --file scripts/volunteer_accounts.csv
        For each row, finds the User (by email or username), finds their Volunteer row,
        looks up Category by name, and sets volunteer.category_id.
        """
        from .models import User, Volunteer, Category

        updated = 0
        missing_user = 0
        missing_vol = 0
        missing_cat = 0

        with app.app_context(), open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = (row.get("email") or "").strip()
                username = (row.get("username") or "").strip()
                cat_name = (row.get("category") or "").strip()

                if not (email or username) or not cat_name:
                    continue

                # Find user by email first, then username
                q = db.select(User)
                if email:
                    q = q.where(func.lower(User.email) == email.lower())
                else:
                    q = q.where(func.lower(User.name) == username.lower())
                user = db.session.scalar(q)

                if not user:
                    missing_user += 1
                    continue

                vol = db.session.scalar(
                    db.select(Volunteer).where(Volunteer.user_id == user.id)
                )
                if not vol:
                    missing_vol += 1
                    continue

                cat_id = db.session.scalar(
                    db.select(Category.id)
                      .where(func.lower(Category.name) == cat_name.lower())
                )
                if not cat_id:
                    missing_cat += 1
                    continue

                if vol.category_id != cat_id:
                    vol.category_id = cat_id
                    updated += 1

            db.session.commit()

        click.echo(
            f"Updated category_id for {updated} volunteers. "
            f"Missing user: {missing_user}, missing volunteer row: {missing_vol}, "
            f"missing category: {missing_cat}."
        )


    # ----- CLI: backfill volunteer rows for existing Volunteer users -----
    @app.cli.command("backfill_volunteers")
    @click.option(
        "--default-available/--no-default-available",
        default=True,
        help="Set is_available True for backfilled rows (default: True)"
    )
    def backfill_volunteers(default_available):
        """
        Usage:
          flask backfill_volunteers
        Creates a row in volunteer table for every User with role='Volunteer' that
        doesn't already have one. Leaves category_id NULL unless you map it later.
        """
        from .models import User, Volunteer

        to_backfill = db.session.scalars(
            db.select(User).where(func.lower(User.role) == "volunteer")
        ).all()

        created = 0
        for u in to_backfill:
            exists = db.session.scalar(
                db.select(Volunteer.id).where(Volunteer.user_id == u.id)
            )
            if exists:
                continue
            db.session.add(Volunteer(
                user_id=u.id,
                category_id=None,  # set later if needed
                is_available=bool(default_available),
                total_tasks_completed=0
            ))
            created += 1

        db.session.commit()
        click.echo(f"Backfilled {created} volunteer rows.")

    # ----- CLI: seed PIN accounts (idempotent) -----
    @app.cli.command("seed_pins")
    @click.option("--file", "file_path", type=click.Path(exists=True),
                  help="CSV with headers: email,username,password,confirm_password,role")
    def seed_pins(file_path):
        """
        Usage:
          flask seed_pins --file scripts/pin_accounts.csv
        """
        if not file_path:
            click.echo("Please pass --file path/to/pin_accounts.csv")
            return

        from .models import User
        created = 0
        skipped = 0
        with app.app_context():
            import csv
            from sqlalchemy import func
            from werkzeug.security import generate_password_hash

            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = (row.get("email") or "").strip()
                    username = (row.get("username") or "").strip()
                    password = (row.get("password") or "").strip()
                    role = (row.get("role") or "PIN").strip()

                    if not email or not username or not password:
                        skipped += 1
                        continue

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
                        role=role,  # must be exactly 'PIN' to get PIN features
                        status="Active"
                    )
                    db.session.add(user)
                    created += 1
            db.session.commit()
        click.echo(f"Seeded {created} PIN accounts. Skipped {skipped}.")

    # ----- CLI: seed requests for PIN users -----
    @app.cli.command("seed_pin_requests")
    @click.option("--per-cat", default=1, show_default=True, type=int,
                  help="How many requests each PIN creates per category.")
    @click.option("--only-prefix", default="pin", show_default=True,
                  help="Only include PIN users whose name starts with this.")
    @click.option("--clear-first", is_flag=True,
                  help="Delete all existing requests before seeding.")
    def seed_pin_requests(per_cat, only_prefix, clear_first):
        """
        Example:
          py -m flask --app main.py seed_pin_requests --per-cat 1 --clear-first
        """
        from datetime import datetime, timedelta
        import random
        from .models import User, Category, Request

        def random_future_dt():
            days = random.randint(1, 45)
            hour = random.choice([9, 10, 11, 13, 14, 15, 16, 17])
            minute = random.choice([0, 15, 30, 45])
            return (datetime.utcnow().replace(second=0, microsecond=0)
                    + timedelta(days=days)).replace(hour=hour, minute=minute)

        with app.app_context():
            # 0) Optionally clear requests first
            if clear_first:
                deleted = db.session.query(Request).delete()
                db.session.commit()
                click.echo(f"🗑️ Deleted {deleted} existing requests.")

            # 1) Load categories and PIN users
            categories = db.session.scalars(db.select(Category).order_by(Category.id)).all()
            if not categories:
                click.echo("No categories found. Aborting.")
                return

            pins = db.session.scalars(
                db.select(User)
                .where(User.role == "PIN")
                .where(User.name.ilike(f"{only_prefix}%"))
                .order_by(User.id)
            ).all()
            if not pins:
                click.echo("No PIN users found. Aborting.")
                return

            # 2) Generate requests
            created = 0
            batch = 0
            titles_cache = {}

            for u in pins:
                for c in categories:
                    for k in range(per_cat):
                        # Make a short, natural title and description
                        tkey = (c.id, k)
                        if tkey not in titles_cache:
                            titles_cache[tkey] = f"{c.name}: help needed #{k + 1}"
                        title = titles_cache[tkey]
                        desc = f"Looking for support for {c.name.lower()}. Flexible timing if possible."

                        req = Request(
                            title=title,
                            description=desc,
                            category_id=c.id,
                            status="Pending",
                            scheduled_datetime=random_future_dt(),
                            view_count=0,
                            user_id=u.id,  # requester is the PIN user
                            volunteer_id=None,
                            csr_id=None,
                        )
                        db.session.add(req)
                        created += 1
                        batch += 1

                        # Commit in chunks for speed and lower memory use
                        if batch >= 1000:
                            db.session.commit()
                            batch = 0

            if batch:
                db.session.commit()

            click.echo(f"✅ Created {created} requests for {len(pins)} PIN users "
                       f"across {len(categories)} categories "
                       f"({per_cat} per category).")

    return app
