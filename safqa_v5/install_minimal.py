# -*- coding: utf-8 -*-
"""Installateur Safqa - version minimale fonctionnelle."""
import sys
from pathlib import Path

FILES = {}

FILES["requirements.txt"] = """Flask>=3.0
Flask-SQLAlchemy>=3.1
Flask-Login>=0.6.3
Flask-WTF>=1.2
python-dotenv>=1.0
"""

FILES[".env"] = """SECRET_KEY=dev-secret-key-change-me
DATABASE_URL=sqlite:///safqa.db
ADMIN_EMAIL=admin@safqa.dz
ADMIN_PASSWORD=admin123456
"""

FILES[".gitignore"] = ".env\ninstance/\n*.db\n__pycache__/\n*.pyc\nvenv/\n"

FILES["run.py"] = '''# -*- coding: utf-8 -*-
import os
from app import create_app
app = create_app()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
'''

FILES["app/__init__.py"] = '''# -*- coding: utf-8 -*-
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
            print(f"\\n[OK] Admin: {email} / {password}\\n")
        if Tender.query.count() == 0:
            for t in [
                ("Travaux route Sidi Bel Abbes - Telagh", "Direction des TP", "2026-12-25"),
                ("Materiel informatique - Universite", "Universite Djillali Liabes", "2026-12-15"),
                ("Services nettoyage - CHU", "CHU Abdelkader", "2027-01-10"),
            ]:
                db.session.add(Tender(title=t[0], agency=t[1], deadline=t[2]))
            db.session.commit()
            print("[OK] 3 offres de demonstration ajoutees\\n")
    return app
'''

FILES["app/routes.py"] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db, User, Tender

bp = Blueprint("routes", __name__)


@bp.route("/")
def index():
    tenders = Tender.query.all()
    return render_template("index.html", tenders=tenders)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        pw = request.form.get("password", "")
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(pw):
            login_user(u)
            flash(f"Bienvenue {u.full_name}!", "success")
            return redirect(url_for("routes.index"))
        flash("Email ou mot de passe incorrect", "error")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))


@bp.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        flash("Acces refuse", "error")
        return redirect(url_for("routes.index"))
    return render_template("admin.html",
                           users=User.query.all(),
                           tenders=Tender.query.all())
'''

FILES["app/templates/base.html"] = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Safqa Belabbes{% endblock %}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f5f7f6; color: #12263a; }
header { background: #0e7c66; color: #fff; padding: 1rem 2rem; }
header a { color: #fff; text-decoration: none; margin-right: 1.2rem; font-weight: 500; }
header a:hover { opacity: 0.8; }
main { max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }
h1 { margin-bottom: 1.5rem; color: #0e7c66; }
h2 { margin: 1.5rem 0 0.8rem; color: #0e7c66; }
.card { background: #fff; padding: 1.2rem; margin: 1rem 0; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.06); border-left: 4px solid #0e7c66; }
.card h3 { margin-bottom: 0.4rem; }
.card p { color: #666; font-size: 0.9rem; }
.btn { background: #0e7c66; color: #fff; padding: 0.6rem 1.2rem; border: 0; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; font-size: 1rem; }
.btn:hover { background: #0a5c4b; }
.flash { padding: 0.8rem 1rem; border-radius: 8px; margin: 0.5rem 0; }
.flash-success { background: #d4edda; color: #155724; }
.flash-error { background: #f8d7da; color: #721c24; }
form { background: #fff; padding: 1.5rem; border-radius: 10px; max-width: 400px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
label { display: block; margin-bottom: 1rem; font-weight: 600; }
input { width: 100%; padding: 0.6rem; border: 1px solid #ccc; border-radius: 6px; margin-top: 0.3rem; font-size: 1rem; }
footer { text-align: center; padding: 2rem; color: #999; font-size: 0.85rem; }
</style>
</head>
<body>
<header>
  <a href="/">🏛️ Safqa Belabbes</a>
  <a href="/admin">Admin</a>
  {% if current_user.is_authenticated %}
    <a href="/logout">Deconnexion ({{ current_user.full_name }})</a>
  {% else %}
    <a href="/login">Connexion</a>
  {% endif %}
</header>
<main>
{% with messages = get_flashed_messages(with_categories=true) %}
{% for cat, msg in messages %}<div class="flash flash-{{ cat }}">{{ msg }}</div>{% endfor %}
{% endwith %}
{% block content %}{% endblock %}
</main>
<footer>© 2026 Safqa Belabbes - v0.1</footer>
</body>
</html>
'''

FILES["app/templates/index.html"] = '''{% extends "base.html" %}
{% block content %}
<h1>📋 Offres des marches publics</h1>
<p style="margin-bottom:1rem;color:#666">Sidi Bel Abbes — {{ tenders|length }} offre(s) disponible(s)</p>
{% for t in tenders %}
<div class="card">
  <h3>{{ t.title }}</h3>
  <p><strong>Organisme :</strong> {{ t.agency }}</p>
  <p><strong>Date limite :</strong> {{ t.deadline }}</p>
</div>
{% else %}
<p>Aucune offre pour le moment.</p>
{% endfor %}
{% endblock %}
'''

FILES["app/templates/login.html"] = '''{% extends "base.html" %}
{% block content %}
<h1>🔐 Connexion</h1>
<form method="post">
  {{ csrf_input() }}
  <label>Email<input type="email" name="email" required></label>
  <label>Mot de passe<input type="password" name="password" required></label>
  <button class="btn" type="submit">Se connecter</button>
</form>
<p style="margin-top:1rem;color:#666;font-size:0.9rem">
  Admin par defaut : <code>admin@safqa.dz</code> / <code>admin123456</code>
</p>
{% endblock %}
'''

FILES["app/templates/admin.html"] = '''{% extends "base.html" %}
{% block content %}
<h1>⚙️ Administration</h1>
<h2>Utilisateurs ({{ users|length }})</h2>
{% for u in users %}
<div class="card">
  <strong>{{ u.email }}</strong> — {{ u.full_name }} — <span style="color:#0e7c66">{{ u.role }}</span>
</div>
{% endfor %}
<h2>Offres ({{ tenders|length }})</h2>
{% for t in tenders %}
<div class="card">
  <strong>{{ t.title }}</strong><br>
  <span style="color:#666">{{ t.agency }} — {{ t.deadline }}</span>
</div>
{% endfor %}
{% endblock %}
'''


def main():
    base = Path(".")
    for name, content in FILES.items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("  +", name)
    print(f"\n[OK] Projet cree ({len(FILES)} fichiers).")
    print("Suite :")
    print("  pip install -r requirements.txt")
    print("  python run.py")


if __name__ == "__main__":
    main()