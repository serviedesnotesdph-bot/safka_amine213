# -*- coding: utf-8 -*-
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
