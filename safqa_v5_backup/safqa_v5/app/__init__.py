# -*- coding: utf-8 -*-
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import Markup

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default="user")

    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        return check_password_hash(self.password_hash, p)

    @property
    def is_admin(self):
        return self.role == "admin"


class Tender(db.Model):
    __tablename__ = "tenders"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    agency = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.String(50), nullable=False)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///safqa.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "routes.login"

    app.jinja_env.globals["csrf_input"] = lambda: Markup(
        f'<input type="hidden" name="csrf_token" value="{generate_csrf()}">')

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    from app.routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role="admin").first():
            email = os.getenv("ADMIN_EMAIL", "admin@safqa.dz")
            password = os.getenv("ADMIN_PASSWORD", "admin123456")
            admin = User(email=email, full_name="Administrateur", role="admin")
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"\n[OK] Admin: {email} / {password}\n")
        if Tender.query.count() == 0:
            for t in [
                ("Travaux route Sidi Bel Abbes - Telagh", "Direction des TP", "2026-12-25"),
                ("Materiel informatique - Universite", "Universite Djillali Liabes", "2026-12-15"),
                ("Services nettoyage - CHU", "CHU Abdelkader", "2027-01-10"),
            ]:
                db.session.add(Tender(title=t[0], agency=t[1], deadline=t[2]))
            db.session.commit()
            print("[OK] 3 offres de demonstration ajoutees\n")
    return app
