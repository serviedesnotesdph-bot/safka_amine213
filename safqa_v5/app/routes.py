# -*- coding: utf-8 -*-
import csv
import io
import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy import or_, func
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session, abort, current_app, send_file,
)
from flask_login import login_user, logout_user, login_required, current_user

from app import (
    db, User, Tender, Favorite, TenderFollow, ChecklistItem,
    DeadlineReminderLog, SavedAlert, Notification, PremiumRequest,
    AuditLog, PartnershipAd, Ad, Professional,
    ChatConversation, ChatMessage,
    AD_FORMULAS, FOLLOW_STATUSES, CHECKLIST_ITEMS, SECURITY_QUESTIONS,
)
from app.constants import SECTORS, COMMUNES, PROFESSIONAL_CATEGORIES

bp = Blueprint("routes", __name__)
  




def _log(action, target_type=None, target_id=None, details=None):
    if current_user.is_authenticated and current_user.is_admin:
        db.session.add(AuditLog(
            admin_id=current_user.id, action=action,
            target_type=target_type, target_id=target_id,
            details=(details or "")[:500], ip_address=request.remote_addr
        ))


def _has_pending_request(user_id):
    return PremiumRequest.query.filter(
        PremiumRequest.user_id == user_id,
        PremiumRequest.status.in_(["pending", "paid"])
    ).first() is not None


# ============================================================
# PAGE D'ACCUEIL
# ============================================================
@bp.route("/")
def index():
    sector = request.args.get("sector", "")
    commune = request.args.get("commune", "")
    q = request.args.get("q", "").strip()
    show_expired = request.args.get("expired") == "1"

    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    query = Tender.query.filter_by(is_active=True)

    if not show_expired:
        query = query.filter(Tender.deadline >= today_str)

    if sector and sector in SECTORS:
        query = query.filter(Tender.sector == sector)
    if commune and commune in COMMUNES:
        if commune != "Toute la wilaya":
            query = query.filter(Tender.commune.in_([commune, "Toute la wilaya"]))
    if q:
        search = f"%{q}%"
        query = query.filter(or_(
            Tender.title.ilike(search),
            Tender.agency.ilike(search),
            Tender.description.ilike(search)
        ))

    # ============================================================
    # FREEMIUM : les offres < 48h sont réservées aux Premium
    # ============================================================
    cutoff = datetime.utcnow() - timedelta(hours=48)
    is_premium_user = current_user.is_authenticated and current_user.is_premium
    if not is_premium_user:
        query = query.filter(Tender.created_at <= cutoff)

    tenders = query.order_by(Tender.created_at.desc()).all()

    # Compter les offres récentes masquées
    locked_count = 0
    if not is_premium_user:
        locked_count = Tender.query.filter(
            Tender.is_active == True,
            Tender.created_at > cutoff,
            Tender.deadline >= today_str,
        ).count()

    expired_count = 0
    if not show_expired:
        expired_count = Tender.query.filter(
            Tender.is_active == True,
            Tender.deadline < today_str,
        ).count()

    fav_ids = set()
    if current_user.is_authenticated:
        fav_ids = {f.tender_id for f in Favorite.query.filter_by(user_id=current_user.id)}

    sponsored_ads = Ad.query.filter_by(is_approved=True, is_active=True).all()
    sponsored_ads = [a for a in sponsored_ads if a.is_currently_active]
    sponsored_ads.sort(key=lambda a: (a.formula != "featured", -a.id))
    sponsored_ads = sponsored_ads[:5]
    for ad in sponsored_ads:
        ad.views += 1
    if sponsored_ads:
        db.session.commit()

    return render_template("index.html", tenders=tenders, fav_ids=fav_ids,
                           sector=sector, commune=commune, q=q,
                           locked_count=locked_count,
                           is_premium_user=is_premium_user,
                           sponsored_ads=sponsored_ads,
                           show_expired=show_expired,
                           expired_count=expired_count,
                           today_str=today_str)
    
             
# ============================================================
# DÉTAIL OFFRE + SUIVI + CHECKLIST
# ============================================================
@bp.route("/tenders/<int:tid>")
def tender_detail(tid):
    t = db.session.get(Tender, tid)
    if not t:
        flash("Offre introuvable", "error")
        return redirect(url_for("routes.index"))

    # ============================================================
    # FREEMIUM : bloquer les offres récentes aux non-Premium
    # ============================================================
    cutoff = datetime.utcnow() - timedelta(hours=48)
    is_premium_user = current_user.is_authenticated and current_user.is_premium
    if t.created_at > cutoff and not is_premium_user:
        flash("Cette offre est récente (< 48h). Passez Premium pour la voir immédiatement.", "warning")
        return redirect(url_for("routes.pricing"))

    fav = False
    follow = None
    done = set()
    if current_user.is_authenticated:
        fav = Favorite.query.filter_by(user_id=current_user.id, tender_id=tid).first() is not None
        follow = TenderFollow.query.filter_by(user_id=current_user.id, tender_id=tid).first()
        done = {c.item_key for c in ChecklistItem.query.filter_by(user_id=current_user.id, tender_id=tid)}

    similar = Tender.query.filter(
        Tender.sector == t.sector, Tender.id != t.id
    ).order_by(Tender.created_at.desc()).limit(3).all()

    total_items = len(CHECKLIST_ITEMS)
    done_count = len(done)
    progress_pct = round(100 * done_count / total_items) if total_items else 0

    return render_template("tender_detail.html", t=t, fav=fav, similar=similar,
                           follow=follow, done=done,
                           progress_pct=progress_pct,
                           done_count=done_count,
                           total_items=total_items)              


@bp.route("/tenders/<int:tid>/follow", methods=["POST"])
@login_required
def tender_follow(tid):
    """Créer ou mettre à jour le suivi d'un marché."""
    t = db.session.get(Tender, tid)
    if not t:
        abort(404)

    status = request.form.get("status", "a_etudier")
    if status not in FOLLOW_STATUSES:
        status = "a_etudier"

    notes = request.form.get("notes", "").strip()[:1000]

    follow = TenderFollow.query.filter_by(user_id=current_user.id, tender_id=tid).first()
    if follow:
        follow.status = status
        if notes:
            follow.notes = notes
    else:
        follow = TenderFollow(
            user_id=current_user.id, tender_id=tid,
            status=status, notes=notes or None
        )
        db.session.add(follow)

    db.session.commit()
    flash(f"Marché mis à jour : {FOLLOW_STATUSES[status]['label']}", "success")
    return redirect(url_for("routes.tender_detail", tid=tid))


@bp.route("/tenders/<int:tid>/unfollow", methods=["POST"])
@login_required
def tender_unfollow(tid):
    follow = TenderFollow.query.filter_by(user_id=current_user.id, tender_id=tid).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash("Marché retiré de votre suivi", "success")
    return redirect(url_for("routes.tender_detail", tid=tid))


@bp.route("/tenders/<int:tid>/checklist/<key>", methods=["POST"])
@login_required
def tender_checklist_toggle(tid, key):
    """Cocher/décocher une pièce du dossier."""
    t = db.session.get(Tender, tid)
    if not t:
        abort(404)

    valid_keys = {item[0] for item in CHECKLIST_ITEMS}
    if key not in valid_keys:
        abort(404)

    existing = ChecklistItem.query.filter_by(
        user_id=current_user.id, tender_id=tid, item_key=key
    ).first()

    if existing:
        db.session.delete(existing)
    else:
        db.session.add(ChecklistItem(
            user_id=current_user.id, tender_id=tid, item_key=key
        ))
    db.session.commit()

    return redirect(url_for("routes.tender_detail", tid=tid) + "#checklist")


# ============================================================
# AUTHENTIFICATION
# ============================================================
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("routes.index"))
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        phone = request.form.get("phone", "").strip() or None
        name = request.form.get("full_name", "").strip()
        pw = request.form.get("password", "")
        cf = request.form.get("confirm", "")
        sq = request.form.get("security_question", "")
        sa = request.form.get("security_answer", "").strip()

        errors = []
        if len(name) < 3: errors.append("Nom trop court")
        if "@" not in email: errors.append("Email invalide")
        if len(pw) < 8: errors.append("Mot de passe: 8 caracteres minimum")
        if pw != cf: errors.append("Mots de passe differents")
        if User.query.filter_by(email=email).first(): errors.append("Email deja utilise")
        if phone and User.query.filter_by(phone=phone).first(): errors.append("Telephone deja utilise")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("register.html", form=request.form), 400

        u = User(email=email, phone=phone, full_name=name)
        u.set_password(pw)
        if sq in SECURITY_QUESTIONS and len(sa) >= 2:
            u.security_question = sq
            u.set_security_answer(sa)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash(f"Bienvenue {name} !", "success")
        return redirect(url_for("routes.index"))
    return render_template("register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        pw = request.form.get("password", "")
        u = User.query.filter_by(email=email).first()
        if u and u.active and u.check_password(pw):
            login_user(u)
            flash(f"Bienvenue {u.full_name} !", "success")
            return redirect(url_for("routes.dashboard"))
        flash("Email ou mot de passe incorrect", "error")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        u = User.query.filter_by(email=email).first()
        if u and u.security_question:
            session["reset_uid"] = u.id
            return redirect(url_for("routes.reset_password"))
        flash("Email inconnu ou aucune question de securite definie.", "error")
    return render_template("forgot_password.html")


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    uid = session.get("reset_uid")
    if not uid:
        return redirect(url_for("routes.forgot_password"))
    u = db.session.get(User, int(uid))
    if not u:
        return redirect(url_for("routes.forgot_password"))

    if request.method == "POST":
        if (u.security_attempts or 0) >= 5:
            flash("Trop de tentatives.", "error")
            return render_template("reset_password.html", user=u), 429
        ans = request.form.get("security_answer", "")
        pw = request.form.get("password", "")
        cf = request.form.get("confirm", "")
        if len(pw) < 8 or pw != cf:
            flash("Mot de passe: 8 caracteres minimum, identiques.", "error")
            return render_template("reset_password.html", user=u), 400
        if not u.check_security_answer(ans):
            u.security_attempts = (u.security_attempts or 0) + 1
            db.session.commit()
            flash("Reponse incorrecte.", "error")
            return render_template("reset_password.html", user=u), 400
        u.set_password(pw)
        u.security_attempts = 0
        db.session.commit()
        session.pop("reset_uid", None)
        flash("Mot de passe modifie. Connectez-vous.", "success")
        return redirect(url_for("routes.login"))
    return render_template("reset_password.html", user=u)


# ============================================================
# FAVORIS
# ============================================================
@bp.route("/favorites")
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    return render_template("favorites.html", favs=favs)


@bp.route("/favorites/toggle/<int:tid>", methods=["POST"])
@login_required
def favorite_toggle(tid):
    t = db.session.get(Tender, tid)
    if not t:
        flash("Offre introuvable", "error")
        return redirect(url_for("routes.index"))
    fav = Favorite.query.filter_by(user_id=current_user.id, tender_id=tid).first()
    if fav:
        db.session.delete(fav)
        flash("Retire des favoris", "success")
    else:
        db.session.add(Favorite(user_id=current_user.id, tender_id=tid))
        flash("Ajoute aux favoris", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("routes.index"))


# ============================================================
# ALERTES
# ============================================================
@bp.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
   
    if request.method == "POST":
        sector = request.form.get("sector", "").strip()
        commune = request.form.get("commune", "").strip()
        kws = request.form.get("keywords", "").strip()[:300]
        sector = sector if sector in SECTORS else ""
        commune = commune if commune in COMMUNES else ""

        if not (sector or commune or kws):
            flash("Choisissez au moins un critère", "error")
        else:
            email_notif = request.form.get("email_notifications") == "on"
            sms_notif = request.form.get("sms_notifications") == "on" and current_user.is_premium

            db.session.add(SavedAlert(
                user_id=current_user.id,
                sector=sector or None,
                commune=commune or None,
                keywords=kws or None,
                email_notifications=email_notif,
                sms_notifications=sms_notif,
            ))
            db.session.commit()
            flash("Alerte créée !", "success")
        return redirect(url_for("routes.alerts"))

    user_alerts = SavedAlert.query.filter_by(user_id=current_user.id).order_by(SavedAlert.created_at.desc()).all()
    return render_template("alerts.html", alerts=user_alerts)
@bp.route("/alerts/<int:aid>/delete", methods=["POST"])
@login_required
def alert_delete(aid):
    a = db.session.get(SavedAlert, aid)
    if not a or a.user_id != current_user.id:
        flash("Alerte introuvable", "error")
        return redirect(url_for("routes.alerts"))
    db.session.delete(a)
    db.session.commit()
    flash("Alerte supprimee", "success")
    return redirect(url_for("routes.alerts"))


# ============================================================
# NOTIFICATIONS
# ============================================================
@bp.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return render_template("notifications.html", notifs=notifs)


@bp.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Notifications marquees comme lues", "success")
    return redirect(url_for("routes.notifications"))


# ============================================================
# DASHBOARD (avec suivi)
# ============================================================


@bp.route("/dashboard")
@login_required
def dashboard():
    # Redirection admin : seulement si vraiment admin
    if current_user.is_admin:
        return redirect(url_for("routes.admin"))

    from app.constants import FAVORITE_SECTORS

    favs = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).limit(5).all()
    user_alerts = SavedAlert.query.filter_by(user_id=current_user.id).all()
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    has_premium_request = _has_pending_request(current_user.id)

    follows = TenderFollow.query.filter_by(user_id=current_user.id).order_by(
        TenderFollow.updated_at.desc()
    ).all()

    status_counts = {}
    for key in FOLLOW_STATUSES:
        status_counts[key] = sum(1 for f in follows if f.status == key)

    favorite_keys = current_user.favorite_sector_list
    favorite_infos = [
        {"key": k, **FAVORITE_SECTORS[k]}
        for k in favorite_keys if k in FAVORITE_SECTORS
    ]

    followed_ids = {f.tender_id for f in follows}
    fav_ids = {f.tender_id for f in favs}

    recommended = []
    if favorite_keys:
        all_tenders = Tender.query.filter_by(is_active=True).order_by(Tender.created_at.desc()).all()
        for t in all_tenders:
            if t.id in followed_ids or t.id in fav_ids:
                continue
            text = f"{t.title} {t.agency} {t.description or ''}".lower()
            matched = []
            for k in favorite_keys:
                info = FAVORITE_SECTORS.get(k)
                if not info:
                    continue
                keywords = info.get("keywords", [])
                if any(kw.lower() in text for kw in keywords):
                    matched.append(info["label"])
            if matched:
                recommended.append({
                    "tender": t,
                    "matched_labels": matched,
                    "match_count": len(matched),
                })
        recommended.sort(key=lambda x: (-x["match_count"], x["tender"].created_at), reverse=False)
        recommended = recommended[:5]

    return render_template("dashboard.html",
                           favs=favs, alerts=user_alerts, notifs=notifs,
                           unread=unread, has_premium_request=has_premium_request,
                           follows=follows, status_counts=status_counts,
                           favorite_infos=favorite_infos,
                           recommended=recommended)
      
# ============================================================
# UPGRADE PREMIUM
# ============================================================
@bp.route("/upgrade", methods=["GET"])
@login_required
def upgrade_page():
    if current_user.plan == "premium" or current_user.role == "admin":
        flash("Vous etes deja Premium", "success")
        return redirect(url_for("routes.dashboard"))

    existing = PremiumRequest.query.filter(
        PremiumRequest.user_id == current_user.id,
        PremiumRequest.status.in_(["pending", "paid"])
    ).first()

    from app.services import chargily
    return render_template("upgrade.html",
                           existing=existing,
                           chargily_ready=chargily.is_configured(),
                           price=1500)


@bp.route("/upgrade/manual", methods=["POST"])
@login_required
def upgrade_manual():
    if current_user.plan == "premium" or current_user.role == "admin":
        flash("Vous etes deja Premium", "success")
        return redirect(url_for("routes.dashboard"))
    if _has_pending_request(current_user.id):
        flash("Vous avez deja une demande en cours", "error")
        return redirect(url_for("routes.upgrade_page"))

    file = request.files.get("receipt")
    if not file or not file.filename:
        flash("Veuillez attacher votre recu de virement", "error")
        return redirect(url_for("routes.upgrade_page"))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jpg", "jpeg", "png", "pdf"):
        flash("Format accepte : JPG, PNG ou PDF", "error")
        return redirect(url_for("routes.upgrade_page"))

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 2 * 1024 * 1024:
        flash("Le fichier ne doit pas depasser 2 Mo", "error")
        return redirect(url_for("routes.upgrade_page"))

    receipts_dir = os.path.join(current_app.root_path, "static", "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    filename = f"premium_{current_user.id}_{secrets.token_hex(8)}.{ext}"
    file.save(os.path.join(receipts_dir, filename))

    db.session.add(PremiumRequest(
        user_id=current_user.id, method="manual", status="pending",
        receipt_path=f"receipts/{filename}", amount_dzd=1500,
    ))
    db.session.commit()
    flash("Recu envoye. Un admin va verifier votre paiement.", "success")
    return redirect(url_for("routes.dashboard"))


@bp.route("/upgrade/chargily", methods=["POST"])
@login_required
def upgrade_chargily():
    from app.services import chargily
    if current_user.plan == "premium" or current_user.role == "admin":
        flash("Vous etes deja Premium", "success")
        return redirect(url_for("routes.dashboard"))
    if _has_pending_request(current_user.id):
        flash("Vous avez deja une demande en cours", "error")
        return redirect(url_for("routes.upgrade_page"))
    if not chargily.is_configured():
        flash("Le paiement en ligne n'est pas encore disponible. Utilisez le virement CCP.", "warning")
        return redirect(url_for("routes.upgrade_page"))

    base = os.getenv("PUBLIC_BASE_URL", request.url_root.rstrip("/"))
    result = chargily.create_checkout(
        amount_dzd=1500,
        success_url=f"{base}/upgrade/chargily/success",
        failure_url=f"{base}/upgrade/chargily/fail",
        metadata=[{"user_id": current_user.id}],
    )
    if not result.get("ok"):
        flash(f"Erreur paiement : {result.get('error', 'inconnue')}", "error")
        return redirect(url_for("routes.upgrade_page"))

    db.session.add(PremiumRequest(
        user_id=current_user.id, method="chargily", status="pending",
        chargily_checkout_id=result["checkout_id"], amount_dzd=1500,
    ))
    db.session.commit()
    return redirect(result["checkout_url"])


@bp.route("/upgrade/chargily/success")
@login_required
def upgrade_chargily_success():
    from app.services import chargily
    checkout_id = request.args.get("checkout_id", "")
    if not checkout_id:
        flash("Parametre checkout_id manquant", "error")
        return redirect(url_for("routes.upgrade_page"))
    req = PremiumRequest.query.filter_by(
        chargily_checkout_id=checkout_id, user_id=current_user.id
    ).first()
    if not req:
        flash("Demande de paiement introuvable", "error")
        return redirect(url_for("routes.upgrade_page"))
    status_result = chargily.get_checkout_status(checkout_id)
    if status_result.get("ok") and status_result.get("paid"):
        req.status = "paid"
        db.session.commit()
        flash("Paiement confirme ! Un admin va activer votre compte.", "success")
    else:
        flash("Le paiement n'est pas encore confirme.", "warning")
    return redirect(url_for("routes.dashboard"))


@bp.route("/upgrade/chargily/fail")
@login_required
def upgrade_chargily_fail():
    flash("Le paiement a echoue. Vous pouvez reessayer.", "error")
    return redirect(url_for("routes.upgrade_page"))


# ============================================================
# PRÉFÉRENCES NOTIFICATIONS
# ============================================================
@bp.route("/profile/notifications", methods=["GET", "POST"])
@login_required
def profile_notifications():
    
    if request.method == "POST":
        current_user.email_notifications = request.form.get("email_notifications") == "on"

        if current_user.is_premium:
            current_user.sms_notifications = request.form.get("sms_notifications") == "on"
        else:
            current_user.sms_notifications = False

        favorite_sectors_list = request.form.getlist("favorite_sectors")
        current_user.favorite_sectors = ",".join(favorite_sectors_list) or None

        current_user.company = request.form.get("company", "").strip()[:150] or None
        current_user.sector_activity = request.form.get("sector_activity", "").strip() or None
        current_user.commune = request.form.get("commune", "").strip() or None

        db.session.commit()
        flash("Préférences enregistrées !", "success")
        return redirect(url_for("routes.profile_notifications"))

    return render_template("profile_notifications.html")

# ============================================================
# TARIFS / STATS / API / ICS / ABOUT / PWA
# ============================================================
@bp.route("/pricing")
def pricing():
    return render_template("pricing.html")


@bp.route("/stats")
def stats():
    total = Tender.query.count()
    by_sector = db.session.query(Tender.sector, func.count(Tender.id)) \
        .group_by(Tender.sector).order_by(func.count(Tender.id).desc()).all()
    by_commune = db.session.query(Tender.commune, func.count(Tender.id)) \
        .group_by(Tender.commune).order_by(func.count(Tender.id).desc()).limit(10).all()
    sector_counts = [(SECTORS.get(s, s), n) for s, n in by_sector]
    max_sector = max([n for _, n in sector_counts], default=1)
    max_commune = max([n for _, n in by_commune], default=1)
    return render_template("stats.html", total=total,
                           sector_counts=sector_counts, max_sector=max_sector,
                           commune_counts=by_commune, max_commune=max_commune)


@bp.route("/api/tenders")
def api_tenders():
    limit = min(request.args.get("limit", 50, type=int), 100)
    tenders = Tender.query.order_by(Tender.created_at.desc()).limit(limit).all()
    return jsonify([{
        "id": t.id, "title": t.title, "agency": t.agency,
        "deadline": t.deadline, "sector": t.sector,
        "commune": t.commune, "budget_dzd": t.budget_dzd,
    } for t in tenders])


def _ics_escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_event(t, base_url):
    return [
        "BEGIN:VEVENT", f"UID:tender-{t.id}@safqa",
        f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{t.deadline.replace('-', '')}",
        f"DTEND;VALUE=DATE:{t.deadline.replace('-', '')}",
        f"SUMMARY:{_ics_escape('Echeance : ' + t.title)}",
        f"DESCRIPTION:{_ics_escape(t.agency)}\n{base_url}/tenders/{t.id}",
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Rappel",
        "TRIGGER:-P3D", "END:VALARM", "END:VEVENT",
    ]


def _ics_response(tenders, filename):
    base = request.url_root.rstrip("/")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Safqa//FR", "CALSCALE:GREGORIAN"]
    for t in tenders:
        lines += _ics_event(t, base)
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", mimetype="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@bp.route("/tenders/<int:tid>/calendar.ics")
def tender_ics(tid):
    t = db.session.get(Tender, tid)
    if not t:
        abort(404)
    return _ics_response([t], f"offre-{tid}.ics")


@bp.route("/my-calendar.ics")
@login_required
def my_calendar():
    follows = TenderFollow.query.filter_by(user_id=current_user.id).all()
    tenders = [f.tender for f in follows if f.tender]
    return _ics_response(tenders, "mes-echeances.ics")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/manifest.json")
def manifest():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "manifest.json", mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ============================================================
# GROUPEMENTS
# ============================================================
def _score_compatibility(user_a, ad):
    score = 0
    max_score = 0
    if ad.sector_wanted:
        max_score += 40
        if user_a.sector_activity and user_a.sector_activity != ad.sector_wanted:
            score += 40
        elif user_a.sector_activity == ad.sector_wanted:
            score += 10
    if ad.commune_wanted and ad.commune_wanted != "Toute la wilaya":
        max_score += 30
        if user_a.commune == ad.commune_wanted:
            score += 30
        elif user_a.commune == "Toute la wilaya":
            score += 15
    if user_a.phone:
        max_score += 15
        score += 15
    if user_a.company:
        max_score += 15
        score += 15
    if max_score == 0:
        return 0
    return round(100 * score / max_score)


@bp.route("/partnerships")
@login_required
def partnerships():
    ads = PartnershipAd.query.filter_by(is_open=True).order_by(PartnershipAd.created_at.desc()).all()
    scored_ads = []
    for ad in ads:
        if ad.user_id == current_user.id:
            continue
        scored_ads.append({"ad": ad, "score": _score_compatibility(current_user, ad)})
    scored_ads.sort(key=lambda x: -x["score"])
    my_ads = PartnershipAd.query.filter_by(user_id=current_user.id).order_by(PartnershipAd.created_at.desc()).all()
    return render_template("partnerships.html", scored_ads=scored_ads, my_ads=my_ads)


@bp.route("/partnerships/new", methods=["POST"])
@login_required
def partnership_new():
    tender_title = request.form.get("tender_title", "").strip()[:300]
    looking_for = request.form.get("looking_for", "").strip()[:300]
    sector_wanted = request.form.get("sector_wanted", "").strip()
    commune_wanted = request.form.get("commune_wanted", "").strip()
    message = request.form.get("message", "").strip()[:1000]
    contact_phone = request.form.get("contact_phone", "").strip()[:20]

    if not tender_title or not looking_for:
        flash("Titre et profil obligatoires", "error")
        return redirect(url_for("routes.partnerships"))

    if not contact_phone and current_user.phone:
        contact_phone = current_user.phone

    ad = PartnershipAd(
        user_id=current_user.id, tender_title=tender_title,
        looking_for=looking_for, sector_wanted=sector_wanted or None,
        commune_wanted=commune_wanted or None, message=message or None,
        contact_phone=contact_phone or None,
    )
    db.session.add(ad)
    db.session.commit()
    _notify_compatible_users(ad)
    count = _count_matches(ad)
    flash(f"Annonce publiee ! {count} entreprise(s) notifiee(s)", "success")
    return redirect(url_for("routes.partnerships"))


@bp.route("/partnerships/<int:pid>")
@login_required
def partnership_detail(pid):
    ad = db.session.get(PartnershipAd, pid)
    if not ad:
        abort(404)
    if not ad.is_open and ad.user_id != current_user.id:
        flash("Cette annonce est fermee", "error")
        return redirect(url_for("routes.partnerships"))
    author = db.session.get(User, ad.user_id)
    score = _score_compatibility(current_user, ad) if ad.user_id != current_user.id else 100
    return render_template("partnership_detail.html", ad=ad, author=author, score=score)


@bp.route("/partnerships/<int:pid>/close", methods=["POST"])
@login_required
def partnership_close(pid):
    ad = db.session.get(PartnershipAd, pid)
    if not ad or ad.user_id != current_user.id:
        abort(403)
    ad.is_open = False
    db.session.commit()
    flash("Annonce fermee", "success")
    return redirect(url_for("routes.partnerships"))


def _notify_compatible_users(ad):
    from app.services.notifier import send_email
    all_users = User.query.filter(User.active == True, User.id != ad.user_id).all()
    for u in all_users:
        score = _score_compatibility(u, ad)
        if score >= 60 and u.email_notifications:
            subject = f"Opportunite de groupement : {ad.tender_title[:60]}"
            body = f"""<html><body><h2 style="color:#0e7c66;">Nouvelle opportunite de groupement</h2>
            <p>Bonjour {u.full_name},</p>
            <h3>{ad.tender_title}</h3>
            <p><strong>Profil recherche :</strong> {ad.looking_for}</p>
            <p><strong>Compatibilite :</strong> {score}%</p>
            <p><a href="http://localhost:5000/partnerships/{ad.id}">Voir l'annonce</a></p>
            </body></html>"""
            send_email(u.email, subject, body)


def _count_matches(ad):
    all_users = User.query.filter(User.active == True, User.id != ad.user_id).all()
    return sum(1 for u in all_users if _score_compatibility(u, ad) >= 60)


# ============================================================
# PUBLICITÉS (annonceur + paiement)
# ============================================================
@bp.route("/advertisers")
@login_required
def advertisers_home():
    my_ads = Ad.query.filter_by(user_id=current_user.id).order_by(Ad.created_at.desc()).all()
    total_views = sum(a.views for a in my_ads)
    total_clicks = sum(a.clicks for a in my_ads)
    total_spent = sum(a.price_dzd for a in my_ads if a.payment_status == "paid")
    active_count = sum(1 for a in my_ads if a.is_currently_active)
    return render_template("advertisers.html",
                           my_ads=my_ads,
                           total_views=total_views,
                           total_clicks=total_clicks,
                           total_spent=total_spent,
                           active_count=active_count,
                           formulas=AD_FORMULAS)


@bp.route("/advertisers/new", methods=["GET", "POST"])
@login_required
def advertiser_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:200]
        description = request.form.get("description", "").strip()[:2000]
        link = request.form.get("link", "").strip()[:500]
        company_name = request.form.get("company_name", "").strip()[:150]
        contact_phone = request.form.get("contact_phone", "").strip()[:20]
        formula_key = request.form.get("formula", "basic")

        if formula_key not in AD_FORMULAS:
            formula_key = "basic"

        if not title or not description:
            flash("Titre et description obligatoires", "error")
            return redirect(url_for("routes.advertiser_new"))

        if link and not (link.startswith("http://") or link.startswith("https://")):
            flash("Le lien doit commencer par http:// ou https://", "error")
            return redirect(url_for("routes.advertiser_new"))

        f = AD_FORMULAS[formula_key]

        ad = Ad(
            user_id=current_user.id, title=title, description=description,
            link=link or None, company_name=company_name or None,
            contact_phone=contact_phone or current_user.phone,
            formula=formula_key, duration_days=f["days"], price_dzd=f["price"],
            payment_status="awaiting_payment", is_approved=False, is_active=False,
        )
        db.session.add(ad)
        db.session.commit()
        _log("create_ad", "ad", ad.id, f"{title[:60]} ({formula_key})")
        flash(f"Campagne creee ! Montant : {f['price']} DA. Reglez puis envoyez votre recu.", "success")
        return redirect(url_for("routes.advertiser_pay", ad_id=ad.id))

    return render_template("advertiser_new.html", formulas=AD_FORMULAS)


@bp.route("/advertisers/<int:ad_id>/pay", methods=["GET", "POST"])
@login_required
def advertiser_pay(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad or ad.user_id != current_user.id:
        abort(404)
    if ad.payment_status == "paid":
        flash("Cette campagne est deja payee", "success")
        return redirect(url_for("routes.advertiser_detail", ad_id=ad_id))

    if request.method == "POST":
        file = request.files.get("receipt")
        if not file or not file.filename:
            flash("Veuillez attacher votre recu", "error")
            return redirect(url_for("routes.advertiser_pay", ad_id=ad_id))

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("jpg", "jpeg", "png", "pdf"):
            flash("Format : JPG, PNG ou PDF", "error")
            return redirect(url_for("routes.advertiser_pay", ad_id=ad_id))

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > 2 * 1024 * 1024:
            flash("Max 2 Mo", "error")
            return redirect(url_for("routes.advertiser_pay", ad_id=ad_id))

        receipts_dir = os.path.join(current_app.root_path, "static", "receipts")
        os.makedirs(receipts_dir, exist_ok=True)
        filename = f"ad_{ad_id}_{secrets.token_hex(8)}.{ext}"
        file.save(os.path.join(receipts_dir, filename))

        ad.receipt_path = f"receipts/{filename}"
        ad.payment_method = "manual"
        ad.payment_status = "awaiting_validation"
        db.session.commit()
        _log("ad_receipt_uploaded", "ad", ad.id, ad.title[:60])
        flash("Recu envoye ! Un admin va verifier votre paiement.", "success")
        return redirect(url_for("routes.advertisers_home"))

    return render_template("advertiser_pay.html", ad=ad, formulas=AD_FORMULAS)


@bp.route("/advertisers/<int:ad_id>")
@login_required
def advertiser_detail(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad or ad.user_id != current_user.id:
        abort(404)
    return render_template("advertiser_detail.html", ad=ad, formulas=AD_FORMULAS)


@bp.route("/advertisers/<int:ad_id>/toggle", methods=["POST"])
@login_required
def advertiser_toggle(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad or ad.user_id != current_user.id:
        abort(403)
    if ad.payment_status != "paid":
        flash("Campagne doit etre payee d'abord", "error")
        return redirect(url_for("routes.advertiser_detail", ad_id=ad_id))
    ad.is_active = not ad.is_active
    db.session.commit()
    flash(f"Campagne {'activee' if ad.is_active else 'mise en pause'}", "success")
    return redirect(url_for("routes.advertiser_detail", ad_id=ad_id))


@bp.route("/advertisers/<int:ad_id>/delete", methods=["POST"])
@login_required
def advertiser_delete(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad or ad.user_id != current_user.id:
        abort(403)
    if ad.is_currently_active:
        flash("Impossible de supprimer une campagne en cours", "error")
        return redirect(url_for("routes.advertiser_detail", ad_id=ad_id))
    db.session.delete(ad)
    db.session.commit()
    _log("delete_ad", "ad", ad_id, f"user={current_user.id}")
    flash("Campagne supprimee", "success")
    return redirect(url_for("routes.advertisers_home"))


@bp.route("/ads/click/<int:ad_id>")
def ad_click(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad or not ad.is_currently_active:
        abort(404)
    ad.clicks += 1
    db.session.commit()
    if ad.link:
        return redirect(ad.link)
    return redirect(url_for("routes.index"))


# ============================================================
# ADMIN
# ============================================================
def _generate_notifications(tender):
    """Crée les notifications pour les alertes qui correspondent à l'offre."""
    from app.services.notifier import alert_matches
    alerts = SavedAlert.query.join(User).filter(User.active.is_(True)).all()
    created = 0
    seen_users = set()
    for alert in alerts:
        if alert.user_id in seen_users:
            continue
        try:
            if not alert_matches(alert, tender):
                continue
        except Exception:
            continue
        user = alert.user
        seen_users.add(alert.user_id)
        db.session.add(Notification(user_id=user.id, tender_id=tender.id))
        created += 1
    db.session.commit()
    return created
    



@bp.route("/admin")
@login_required
def admin():
  
    if not current_user.is_admin:
        abort(403)

    tab = request.args.get("tab", "dashboard")

    pending_premium = PremiumRequest.query.filter_by(status="pending").all()
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    pending_ads = Ad.query.filter(Ad.payment_status.in_(["awaiting_validation"])).order_by(Ad.created_at.desc()).all()
    all_ads = Ad.query.order_by(Ad.created_at.desc()).all()
    pending_professionals = Professional.query.filter(
        Professional.payment_status.in_(["awaiting_validation"])
    ).order_by(Professional.created_at.desc()).all()
    all_professionals = Professional.query.order_by(Professional.created_at.desc()).all()

    stats_data = {
        "users": User.query.count(),
        "premium": User.query.filter_by(plan="premium").count(),
        "tenders": Tender.query.count(),
        "pending_premium": len(pending_premium),
        "pending_ads": len(pending_ads),
        "pending_professionals": len(pending_professionals),
        "notifs": Notification.query.count(),
    }

    tenders_query = Tender.query
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status_filter", "")

    if q:
        search = f"%{q}%"
        tenders_query = tenders_query.filter(or_(
            Tender.title.ilike(search),
            Tender.agency.ilike(search),
            Tender.commune.ilike(search),
        ))

    if status_filter == "active":
        tenders_query = tenders_query.filter(Tender.is_active == True)
    elif status_filter == "inactive":
        tenders_query = tenders_query.filter(Tender.is_active == False)
    elif status_filter == "expired":
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        tenders_query = tenders_query.filter(Tender.deadline < today_str)

    filtered_tenders = tenders_query.order_by(Tender.created_at.desc()).all()

    return render_template("admin.html", tab=tab, stats=stats_data,
                           users=User.query.order_by(User.created_at.desc()).all(),
                           tenders=filtered_tenders,
                           pending_premium=pending_premium,
                           recent_audit=recent_audit,
                           pending_ads=pending_ads,
                           all_ads=all_ads,
                           pending_professionals=pending_professionals,
                           all_professionals=all_professionals,
                           formulas=AD_FORMULAS)  
@bp.route("/admin/user/<int:uid>/<action>", methods=["POST"])
@login_required
def admin_user_action(uid, action):
    if not current_user.is_admin: abort(403)
    u = db.session.get(User, uid)
    if not u:
        flash("Utilisateur introuvable", "error")
        return redirect(url_for("routes.admin", tab="users"))
    if u.id == current_user.id and action in ("delete", "toggle_admin"):
        flash("Impossible de modifier votre propre compte", "error")
        return redirect(url_for("routes.admin", tab="users"))
    if action == "toggle_active":
        u.active = not u.active
        _log("toggle_active", "user", uid, f"{u.email} -> active={u.active}")
        flash(f"Utilisateur {'active' if u.active else 'desactive'}", "success")
    elif action == "toggle_admin":
        u.role = "user" if u.role == "admin" else "admin"
        _log("toggle_admin", "user", uid, f"{u.email} -> {u.role}")
        flash(f"Role : {u.role}", "success")
    elif action == "delete":
        AuditLog.query.filter_by(admin_id=uid).update({"admin_id": None})
        Favorite.query.filter_by(user_id=uid).delete()
        TenderFollow.query.filter_by(user_id=uid).delete()
        ChecklistItem.query.filter_by(user_id=uid).delete()
        DeadlineReminderLog.query.filter_by(user_id=uid).delete()
        SavedAlert.query.filter_by(user_id=uid).delete()
        Notification.query.filter_by(user_id=uid).delete()
        PremiumRequest.query.filter_by(user_id=uid).delete()
        PartnershipAd.query.filter_by(user_id=uid).delete()
        Ad.query.filter_by(user_id=uid).delete()
        _log("delete_user", "user", uid, u.email)
        db.session.delete(u)
        flash("Utilisateur supprime", "success")
    else:
        abort(404)
    db.session.commit()
    return redirect(url_for("routes.admin", tab="users"))


@bp.route("/admin/premium/<int:uid>/<action>", methods=["POST"])
@login_required
def admin_premium_action(uid, action):
    if not current_user.is_admin: abort(403)
    u = db.session.get(User, uid)
    if not u: abort(404)
    req = PremiumRequest.query.filter(
        PremiumRequest.user_id == uid,
        PremiumRequest.status.in_(["pending", "paid"])
    ).first()
    if action == "approve":
        u.plan = "premium"
        if req:
            req.status = "approved"
            req.processed_at = datetime.utcnow()
        _log("approve_premium", "user", uid, u.email)
        flash(f"{u.full_name} est maintenant Premium", "success")
    elif action == "reject":
        if req:
            req.status = "rejected"
            req.processed_at = datetime.utcnow()
        _log("reject_premium", "user", uid, u.email)
        flash("Demande rejetee", "success")
    elif action == "downgrade":
        u.plan = "free"
        _log("downgrade_premium", "user", uid, u.email)
        flash(f"{u.full_name} est repasse en gratuit", "success")
    else:
        abort(404)
    db.session.commit()
    return redirect(url_for("routes.admin", tab="premium"))


@bp.route("/admin/ad/<int:ad_id>/<action>", methods=["POST"])
@login_required
def admin_ad_action(ad_id, action):
    if not current_user.is_admin: abort(403)
    ad = db.session.get(Ad, ad_id)
    if not ad: abort(404)
    now = datetime.utcnow()
    if action == "approve":
        ad.payment_status = "paid"
        ad.is_approved = True
        ad.is_active = True
        ad.starts_at = now
        ad.ends_at = now + timedelta(days=ad.duration_days)
        _log("approve_ad", "ad", ad_id, f"{ad.title[:60]} ({ad.duration_days}j)")
        flash(f"Campagne activee jusqu'au {ad.ends_at.strftime('%d/%m/%Y')}", "success")
    elif action == "reject":
        ad.payment_status = "rejected"
        ad.is_approved = False
        ad.is_active = False
        _log("reject_ad", "ad", ad_id, ad.title[:60])
        flash("Campagne rejetee", "success")
    elif action == "pause":
        ad.is_active = False
        _log("pause_ad", "ad", ad_id)
        flash("Campagne en pause", "success")
    elif action == "delete":
        _log("delete_ad_admin", "ad", ad_id, ad.title[:60])
        db.session.delete(ad)
        db.session.commit()
        flash("Campagne supprimee", "success")
        return redirect(url_for("routes.admin", tab="ads"))
    else:
        abort(404)
    db.session.commit()
    return redirect(url_for("routes.admin", tab="ads"))


@bp.route("/admin/import", methods=["POST"])
@login_required
def admin_import():
    if not current_user.is_admin: abort(403)
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        flash("Fichier CSV requis", "error")
        return redirect(url_for("routes.admin", tab="import"))
    try:
        text = file.read(2_000_000).decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Le fichier doit etre en UTF-8", "error")
        return redirect(url_for("routes.admin", tab="import"))
    reader = csv.DictReader(io.StringIO(text), delimiter=",")
    if reader.fieldnames is None:
        flash("CSV vide", "error")
        return redirect(url_for("routes.admin", tab="import"))
    added = errors = 0
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        title = row.get("title", "")
        agency = row.get("agency", "")
        deadline = row.get("deadline", "")
        if not title or not agency or not deadline:
            errors += 1
            continue
        sector = row.get("sector", "services")
        commune = row.get("commune", "Toute la wilaya")
        if sector not in SECTORS: sector = "services"
        if commune not in COMMUNES: commune = "Toute la wilaya"
        budget = None
        try:
            if row.get("budget_dzd"):
                budget = int(row["budget_dzd"].replace(" ", "").replace(",", ""))
        except ValueError: pass
        db.session.add(Tender(title=title, agency=agency, deadline=deadline,
                              sector=sector, commune=commune,
                              description=row.get("description") or None,
                              budget_dzd=budget))
        added += 1
    _log("import_csv", "tender", None, f"{added} ajoutees, {errors} erreurs")
    db.session.commit()
    flash(f"Import termine : {added} ajoutee(s), {errors} erreur(s)", "success")
    return redirect(url_for("routes.admin", tab="tenders"))


@bp.route("/admin/tender/new", methods=["POST"])
@login_required
def admin_tender_new():
    if not current_user.is_admin: abort(403)
    title = request.form.get("title", "").strip()
    agency = request.form.get("agency", "").strip()
    deadline = request.form.get("deadline", "").strip()
    sector = request.form.get("sector", "services")
    commune = request.form.get("commune", "Toute la wilaya")
    description = request.form.get("description", "").strip()
    if not title or not agency or not deadline:
        flash("Titre, organisme et date limite obligatoires", "error")
        return redirect(url_for("routes.admin", tab="tenders"))
    t = Tender(title=title, agency=agency, deadline=deadline,
               sector=sector if sector in SECTORS else "services",
               commune=commune if commune in COMMUNES else "Toute la wilaya",
               description=description or None)
    db.session.add(t)
    db.session.commit()
    _log("add_tender", "tender", t.id, title[:100])
    notif_count = _generate_notifications(t)
    flash(f"Offre ajoutee ! {notif_count} notification(s)", "success")
    return redirect(url_for("routes.admin", tab="tenders"))


@bp.route("/admin/tender/<int:tid>/delete", methods=["POST"])
@login_required
def admin_tender_delete(tid):
    if not current_user.is_admin: abort(403)
    t = db.session.get(Tender, tid)
    if t:
        Notification.query.filter_by(tender_id=tid).delete()
        Favorite.query.filter_by(tender_id=tid).delete()
        TenderFollow.query.filter_by(tender_id=tid).delete()
        ChecklistItem.query.filter_by(tender_id=tid).delete()
        DeadlineReminderLog.query.filter_by(tender_id=tid).delete()
        _log("delete_tender", "tender", tid, t.title[:100])
        db.session.delete(t)
        db.session.commit()
        flash("Offre supprimee", "success")
    return redirect(url_for("routes.admin", tab="tenders"))

@bp.route("/admin/tender/<int:tid>/toggle", methods=["POST"])
@login_required
def admin_tender_toggle(tid):
    """Activer / désactiver une offre sans la supprimer."""
    if not current_user.is_admin:
        abort(403)
    t = db.session.get(Tender, tid)
    if not t:
        abort(404)
    t.is_active = not t.is_active
    _log("toggle_tender", "tender", tid, f"{t.title[:60]} -> active={t.is_active}")
    db.session.commit()
    flash(f"Offre {'activée' if t.is_active else 'désactivée'}", "success")
    return redirect(url_for("routes.admin", tab="tenders"))
@bp.route("/admin/tender/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def admin_tender_edit(tid):
    if not current_user.is_admin:
        abort(403)
    t = db.session.get(Tender, tid)
    if not t:
        abort(404)

    if request.method == "POST":
        t.title = request.form.get("title", "").strip()[:500]
        t.agency = request.form.get("agency", "").strip()[:200]
        t.deadline = request.form.get("deadline", "").strip()
        sector = request.form.get("sector", "services")
        commune = request.form.get("commune", "Toute la wilaya")
        t.sector = sector if sector in SECTORS else "services"
        t.commune = commune if commune in COMMUNES else "Toute la wilaya"
        t.description = request.form.get("description", "").strip() or None

        budget_str = request.form.get("budget_dzd", "").strip().replace(" ", "").replace(",", "")
        try:
            t.budget_dzd = int(budget_str) if budget_str else None
        except ValueError:
            t.budget_dzd = None

        _log("edit_tender", "tender", t.id, t.title[:100])
        db.session.commit()
        flash(f"Offre modifiée : {t.title[:60]}", "success")
        return redirect(url_for("routes.admin", tab="tenders"))

    return render_template("admin_tender_edit.html", t=t)

@bp.route("/admin/export.csv")
@login_required
def export_csv():
    if not current_user.is_admin: abort(403)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["id", "title", "agency", "deadline", "sector", "commune", "budget_dzd", "description"])
    for t in Tender.query.order_by(Tender.created_at.desc()).all():
        writer.writerow([t.id, t.title, t.agency, t.deadline,
                        t.sector, t.commune, t.budget_dzd or "",
                        (t.description or "").replace("\n", " ")])
    _log("export_csv", "tender", None, f"{Tender.query.count()} offres")
    db.session.commit()
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=offres_safqa.csv"})


@bp.route("/admin/audit")
@login_required
def admin_audit():
    if not current_user.is_admin: abort(403)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin_audit.html", logs=logs)


# ============================================================
# ADMIN — LANCER LES RAPPELS MANUELLEMENT
# ============================================================
@bp.route("/admin/send-reminders", methods=["POST"])
@login_required
def admin_send_reminders():
    if not current_user.is_admin: abort(403)
    from app.services.deadline_reminder import send_all_reminders
    count = send_all_reminders()
    _log("send_reminders", None, None, f"{count} rappels envoyes")
    db.session.commit()
    flash(f"{count} rappel(s) d'echeance envoye(s)", "success")
    return redirect(url_for("routes.admin", tab="dashboard"))
    

# ============================================================
# CHATBOT IA — Analyse de cahiers des charges + Questions services
# ============================================================
@bp.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    from app.services.ai_chatbot import analyze_chat_request, analyze_tender_text

    analysis = None
    question = ""
    response_text = None

    # Lire chat_type depuis GET (?type=tender ou ?type=service)
    chat_type = request.args.get("type", "tender")
    if chat_type not in ("tender", "service"):
        chat_type = "tender"

    if request.method == "POST":
        chat_type = request.form.get("chat_type", "tender")
        content = request.form.get("content", "").strip()

        if not content:
            flash("Veuillez saisir un texte ou une question", "error")
        elif len(content) > 10000:
            flash("Le texte est trop long (max 10 000 caractères)", "error")
        else:
            conv_id = None
            if current_user.is_authenticated:
                conv = ChatConversation(
                    user_id=current_user.id,
                    conversation_type=chat_type,
                )
                db.session.add(conv)
                db.session.flush()
                conv_id = conv.id

                db.session.add(ChatMessage(
                    conversation_id=conv_id, role="user", content=content[:5000]
                ))

            # Traiter avec le chatbot
            response_text = analyze_chat_request(chat_type, content)

            if conv_id:
                db.session.add(ChatMessage(
                    conversation_id=conv_id, role="assistant", content=response_text
                ))
                db.session.commit()

            if chat_type == "tender":
                analysis = analyze_tender_text(content)
            question = content

    return render_template("chatbot.html",
                           analysis=analysis,
                           question=question,
                           response_text=response_text,
                           chat_type=chat_type)
            
           

   


@bp.route("/chatbot/history")
@login_required
def chatbot_history():
    conversations = ChatConversation.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatConversation.created_at.desc()).limit(20).all()

    return render_template("chatbot_history.html", conversations=conversations)


@bp.route("/chatbot/conversation/<int:conv_id>")
@login_required
def chatbot_conversation(conv_id):
    conv = db.session.get(ChatConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        abort(404)

    messages = ChatMessage.query.filter_by(
        conversation_id=conv_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return render_template("chatbot_conversation.html", conv=conv, messages=messages)


# ============================================================
# ANNUAIRE PROFESSIONNEL
# ============================================================
@bp.route("/directory")
def directory():
    category = request.args.get("category", "")
    commune = request.args.get("commune", "")
    q = request.args.get("q", "").strip()

    query = Professional.query.filter_by(is_approved=True, is_active=True)

    if category and category in PROFESSIONAL_CATEGORIES:
        query = query.filter(Professional.category == category)

    if commune and commune in COMMUNES:
        query = query.filter(Professional.commune == commune)

    if q:
        q_lower = q.lower().strip()
        # Recherche dans les catégories (clé ou label, insensible aux accents/casse)
        matched_categories = []
        for key, info in PROFESSIONAL_CATEGORIES.items():
            key_lower = key.lower()
            label_lower = info["label"].lower()
            if q_lower in key_lower or q_lower in label_lower:
                matched_categories.append(key)
            # Aussi chercher sans accent dans le label
            label_no_accent = (info["label"]
                .lower()
                .replace("é", "e").replace("è", "e").replace("ê", "e")
                .replace("à", "a").replace("ç", "c").replace("ô", "o"))
            q_no_accent = (q_lower
                .replace("é", "e").replace("è", "e").replace("ê", "e")
                .replace("à", "a").replace("ç", "c").replace("ô", "o"))
            if q_no_accent in label_no_accent:
                matched_categories.append(key)

        matched_categories = list(set(matched_categories))

        # Recherche textuelle (nom, description, services)
        search = f"%{q}%"
        text_filter = or_(
            Professional.business_name.ilike(search),
            Professional.description.ilike(search),
            Professional.services.ilike(search),
        )

        if matched_categories:
            # Si le mot-clé correspond à une catégorie → chercher dans la catégorie
            query = query.filter(or_(
                Professional.category.in_(matched_categories),
                text_filter,
            ))
        else:
            query = query.filter(text_filter)

    professionals = query.order_by(Professional.created_at.desc()).all()
    professionals = [p for p in professionals if p.is_published]

    category_counts = {}
    for cat_key in PROFESSIONAL_CATEGORIES:
        category_counts[cat_key] = sum(1 for p in professionals if p.category == cat_key)

    return render_template("directory.html",
                           professionals=professionals,
                           category=category,
                           commune=commune,
                           q=q,
                           category_counts=category_counts)
                    


@bp.route("/directory/<int:prof_id>")
def professional_profile(prof_id):
    """Page publique du profil professionnel."""
    prof = db.session.get(Professional, prof_id)
    if not prof or not prof.is_published:
        flash("Ce profil n'est pas disponible", "error")
        return redirect(url_for("routes.directory"))

    # Incrémenter les vues (une fois par session)
    session_key = f"viewed_prof_{prof_id}"
    if not session.get(session_key):
        prof.views += 1
        db.session.commit()
        session[session_key] = True

    return render_template("professional_profile.html", prof=prof)


@bp.route("/directory/<int:prof_id>/phone-click")
def professional_phone_click(prof_id):
    """Enregistre un clic sur le bouton téléphone."""
    prof = db.session.get(Professional, prof_id)
    if prof and prof.is_published:
        prof.phone_clicks += 1
        db.session.commit()
    return redirect(url_for("routes.professional_profile", prof_id=prof_id))


@bp.route("/my-professional")
@login_required
def my_professional():
    """Page de gestion de l'inscription au annuaire pour l'utilisateur connecté."""
    prof = Professional.query.filter_by(user_id=current_user.id).first()
    return render_template("my_professional.html", prof=prof)


@bp.route("/my-professional/register", methods=["GET", "POST"])
@login_required
def professional_register():
    """Inscription au annuaire."""
    existing = Professional.query.filter_by(user_id=current_user.id).first()
    if existing:
        flash("Vous avez déjà un profil dans l'annuaire", "info")
        return redirect(url_for("routes.my_professional"))

    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()[:150]
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()[:2000]
        services = request.form.get("services", "").strip()[:1000]
        phone = request.form.get("phone", "").strip()[:20]
        whatsapp = request.form.get("whatsapp", "").strip()[:20]
        email_public = request.form.get("email_public", "").strip()[:150]
        address = request.form.get("address", "").strip()[:300]
        commune = request.form.get("commune", "").strip()
        years = request.form.get("years_experience", "").strip()

        errors = []
        if not business_name: errors.append("Nom de l'entreprise requis")
        if category not in PROFESSIONAL_CATEGORIES: errors.append("Catégorie invalide")
        if not description or len(description) < 30: errors.append("Description trop courte (30 caractères min.)")
        if not phone: errors.append("Téléphone requis")
        if commune not in COMMUNES: errors.append("Commune invalide")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("professional_register.html", form=request.form), 400

        years_int = None
        try:
            if years:
                years_int = int(years)
        except ValueError:
            pass
        prof = Professional(
            user_id=current_user.id,
            business_name=business_name,
            category=category,
            description=description,
            services=services or None,
            phone=phone,
            whatsapp=whatsapp or None,
            email_public=email_public or None,
            address=address or None,
            commune=commune,
            years_experience=years_int,
            payment_status="awaiting_payment",
            price_dzd=3000,
            duration_days=180,
            is_approved=False,
            is_active=True,
        )
        db.session.add(prof)
        db.session.flush()

        # Upload photo de profil
        photo = request.files.get("photo")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
            if ext in ("jpg", "jpeg", "png", "webp"):
                uploads_dir = os.path.join(
                    current_app.root_path, "static", "uploads", "professionals"
                )
                os.makedirs(uploads_dir, exist_ok=True)
                filename = f"prof_{prof.id}_{secrets.token_hex(6)}.{ext}"
                photo.save(os.path.join(uploads_dir, filename))
                prof.photo_url = f"uploads/professionals/{filename}"

        db.session.commit()
        _log("create_professional", "professional", prof.id, business_name[:60])
        flash("Profil créé ! Réglez maintenant les frais d'inscription (3 000 DA) pour être publié.", "success")
        return redirect(url_for("routes.professional_pay", prof_id=prof.id))

    return render_template("professional_register.html", form={})


@bp.route("/my-professional/<int:prof_id>/pay", methods=["GET", "POST"])
@login_required
def professional_pay(prof_id):
    """Page de paiement pour l'inscription annuaire."""
    prof = db.session.get(Professional, prof_id)
    if not prof or prof.user_id != current_user.id:
        abort(404)

    if prof.payment_status == "paid":
        flash("Votre inscription est déjà payée", "success")
        return redirect(url_for("routes.my_professional"))

    if request.method == "POST":
        file = request.files.get("receipt")
        if not file or not file.filename:
            flash("Veuillez attacher votre reçu", "error")
            return redirect(url_for("routes.professional_pay", prof_id=prof_id))

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("jpg", "jpeg", "png", "pdf"):
            flash("Format accepté : JPG, PNG ou PDF", "error")
            return redirect(url_for("routes.professional_pay", prof_id=prof_id))

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > 2 * 1024 * 1024:
            flash("Max 2 Mo", "error")
            return redirect(url_for("routes.professional_pay", prof_id=prof_id))

        receipts_dir = os.path.join(current_app.root_path, "static", "receipts")
        os.makedirs(receipts_dir, exist_ok=True)
        filename = f"prof_{prof_id}_{secrets.token_hex(8)}.{ext}"
        file.save(os.path.join(receipts_dir, filename))

        prof.receipt_path = f"receipts/{filename}"
        prof.payment_method = "manual"
        prof.payment_status = "awaiting_validation"
        db.session.commit()
        _log("professional_receipt_uploaded", "professional", prof.id, prof.business_name[:60])
        flash("Reçu envoyé ! Un admin va vérifier votre paiement et publier votre profil.", "success")
        return redirect(url_for("routes.my_professional"))

    return render_template("professional_pay.html", prof=prof)



      
@bp.route("/my-professional/edit", methods=["GET", "POST"])
@login_required
def professional_edit():
    prof = Professional.query.filter_by(user_id=current_user.id).first()
    if not prof:
        flash("Vous n'avez pas encore de profil dans l'annuaire", "info")
        return redirect(url_for("routes.professional_register"))

    if request.method == "POST":
        prof.business_name = request.form.get("business_name", "").strip()[:150]
        category = request.form.get("category", "").strip()
        if category in PROFESSIONAL_CATEGORIES:
            prof.category = category
        prof.description = request.form.get("description", "").strip()[:2000]
        prof.services = request.form.get("services", "").strip()[:1000] or None
        prof.phone = request.form.get("phone", "").strip()[:20]
        prof.whatsapp = request.form.get("whatsapp", "").strip()[:20] or None
        prof.email_public = request.form.get("email_public", "").strip()[:150] or None
        prof.address = request.form.get("address", "").strip()[:300] or None
        commune = request.form.get("commune", "").strip()
        if commune in COMMUNES:
            prof.commune = commune

        years = request.form.get("years_experience", "").strip()
        try:
            prof.years_experience = int(years) if years else None
        except ValueError:
            pass

        # Upload photo de profil
        photo = request.files.get("photo")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
            if ext in ("jpg", "jpeg", "png", "webp"):
                photo.seek(0, 2)
                size = photo.tell()
                photo.seek(0)
                if size <= 5 * 1024 * 1024:  # 5 Mo
                    uploads_dir = os.path.join(
                        current_app.root_path, "static", "uploads", "professionals"
                    )
                    os.makedirs(uploads_dir, exist_ok=True)
                    filename = f"prof_{prof.id}_{secrets.token_hex(6)}.{ext}"
                    photo.save(os.path.join(uploads_dir, filename))
                    prof.photo_url = f"uploads/professionals/{filename}"
                else:
                    flash("La photo ne doit pas dépasser 5 Mo", "warning")
            else:
                flash("Format photo accepté : JPG, PNG ou WebP", "warning")

        # Galerie (jusqu'à 3 photos)
        for i in range(3):
            gal = request.files.get(f"gallery_{i}")
            if gal and gal.filename:
                ext = gal.filename.rsplit(".", 1)[-1].lower() if "." in gal.filename else ""
                if ext in ("jpg", "jpeg", "png", "webp"):
                    gal.seek(0, 2)
                    size = gal.tell()
                    gal.seek(0)
                    if size <= 5 * 1024 * 1024:
                        uploads_dir = os.path.join(
                            current_app.root_path, "static", "uploads", "professionals"
                        )
                        os.makedirs(uploads_dir, exist_ok=True)
                        filename = f"gal_{prof.id}_{secrets.token_hex(6)}.{ext}"
                        gal.save(os.path.join(uploads_dir, filename))
                        new_url = f"uploads/professionals/{filename}"
                        current_gallery = prof.gallery.split(",") if prof.gallery else []
                        current_gallery = [g for g in current_gallery if g.strip()][:2]
                        current_gallery.append(new_url)
                        prof.gallery = ",".join(current_gallery)

        db.session.commit()
        _log("edit_professional", "professional", prof.id, prof.business_name[:60])
        flash("Profil mis à jour", "success")
        return redirect(url_for("routes.my_professional"))

    return render_template("professional_edit.html", prof=prof)

@bp.route("/my-professional/toggle", methods=["POST"])
@login_required
def professional_toggle():
    """Activer/mettre en pause la publication du profil."""
    prof = Professional.query.filter_by(user_id=current_user.id).first()
    if not prof or prof.payment_status != "paid":
        flash("Vous devez d'abord payer pour activer votre profil", "error")
        return redirect(url_for("routes.my_professional"))

    prof.is_active = not prof.is_active
    db.session.commit()
    flash(f"Profil {'activé' if prof.is_active else 'mis en pause'}", "success")
    return redirect(url_for("routes.my_professional"))


# ============================================================
# ADMIN — Validation des profils annuaire
# ============================================================
@bp.route("/admin/professional/<int:prof_id>/<action>", methods=["POST"])
@login_required
def admin_professional_action(prof_id, action):
    if not current_user.is_admin:
        abort(403)
    prof = db.session.get(Professional, prof_id)
    if not prof:
        abort(404)

    now = datetime.utcnow()

    if action == "approve":
        prof.payment_status = "paid"
        prof.is_approved = True
        prof.is_active = True
        prof.starts_at = now
        prof.ends_at = now + timedelta(days=prof.duration_days)
        _log("approve_professional", "professional", prof_id, prof.business_name[:60])
        flash(f"Profil publié jusqu'au {prof.ends_at.strftime('%d/%m/%Y')}", "success")
    elif action == "reject":
        prof.payment_status = "rejected"
        prof.is_approved = False
        prof.is_active = False
        _log("reject_professional", "professional", prof_id, prof.business_name[:60])
        flash("Profil rejeté", "success")
    elif action == "delete":
        _log("delete_professional", "professional", prof_id, prof.business_name[:60])
        db.session.delete(prof)
        db.session.commit()
        flash("Profil supprimé", "success")
        return redirect(url_for("routes.admin", tab="directory"))
    else:
        abort(404)

    db.session.commit()
    return redirect(url_for("routes.admin", tab="directory"))