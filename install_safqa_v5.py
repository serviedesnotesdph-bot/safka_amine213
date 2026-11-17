# -*- coding: utf-8 -*-
"""Installateur Safqa Belabbès v5 — Architecture modulaire Flask (Blueprints).
Usage : python install_safqa_v5.py && pip install -r requirements.txt && python run.py
"""
import sys
from pathlib import Path

FILES = {}

# ============ requirements.txt ============
FILES['requirements.txt'] = """Flask>=3.0,<4
Flask-SQLAlchemy>=3.1,<4
Flask-Login>=0.6.3,<0.7
Flask-WTF>=1.2,<2
Flask-Limiter>=3.5,<4
requests>=2.31
beautifulsoup4>=4.12
python-dotenv>=1.0
gunicorn>=21.2
pytest>=8.0
"""

# ============ .env.example ============
FILES['.env.example'] = """APP_ENV=development
SECRET_KEY=change-this-to-a-long-random-string
DATABASE_URL=sqlite:///safqa.db

ADMIN_EMAIL=admin@safqa.dz
ADMIN_PASSWORD=admin123456
ADMIN_PHONE=0500000000

DEMO_DATA=true
FREE_PLAN_DELAY_HOURS=48
PREMIUM_PRICE_DZD=1500
PREMIUM_DAYS=30

SMS_MODE=demo
SMS_WEBHOOK_URL=
TELEGRAM_TOKEN=
PUBLIC_BASE_URL=http://localhost:5000
PORTAL_URL=https://www.marches-publics.gov.dz/
"""

# ============ .gitignore ============
FILES['.gitignore'] = '.env\ninstance/\n*.db\n__pycache__/\n*.pyc\n.venv/\nvenv/\n.pytest_cache/\n'

# ============ config.py ============
FILES['config.py'] = '''# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
load_dotenv()


def _bool(n, d=False):
    return os.getenv(n, str(d)).lower() in {"1", "true", "yes", "on"}


def _int(n, d):
    try:
        return int(os.getenv(n, d))
    except (TypeError, ValueError):
        return d


def _db_url():
    u = os.getenv("DATABASE_URL", "sqlite:///safqa.db")
    if u.startswith("postgres://"):
        u = u.replace("postgres://", "postgresql://", 1)
    return u


ENV = os.getenv("APP_ENV", "development").lower()


class Config:
    APP_VERSION = "5.0.0"
    ENV = ENV
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENV == "production"

    FREE_PLAN_DELAY_HOURS = _int("FREE_PLAN_DELAY_HOURS", 48)
    PREMIUM_PRICE_DZD = _int("PREMIUM_PRICE_DZD", 1500)
    PREMIUM_DAYS = _int("PREMIUM_DAYS", 30)
    FREE_ALERT_LIMIT = _int("FREE_ALERT_LIMIT", 3)
    PREMIUM_ALERT_LIMIT = _int("PREMIUM_ALERT_LIMIT", 20)

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@safqa.dz").lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123456")
    ADMIN_PHONE = os.getenv("ADMIN_PHONE", "0500000000")

    DEMO_DATA = _bool("DEMO_DATA", ENV != "production")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
    SMS_MODE = os.getenv("SMS_MODE", "demo")
    SMS_WEBHOOK_URL = os.getenv("SMS_WEBHOOK_URL", "")
    PORTAL_URL = os.getenv("PORTAL_URL", "https://www.marches-publics.gov.dz/")
    ITEMS_PER_PAGE = 12
'''

# ============ run.py ============
FILES['run.py'] = '''# -*- coding: utf-8 -*-
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG") == "1")
'''

# ============ app/__init__.py ============
FILES['app/__init__.py'] = '''# -*- coding: utf-8 -*-
import logging
import os
import secrets
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from markupsafe import Markup
from config import Config
from app.extensions import db, login_manager, csrf, limiter
from app.constants import COMMUNE_AR, COMMUNES, SECTORS, SECURITY_QUESTIONS
from app.i18n import current_lang, translate
from app.models import User
from app.utils import today_dz, whatsapp_link


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    logging.basicConfig(level=logging.INFO)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(uid):
        u = db.session.get(User, int(uid))
        return u if u and u.active else None

    @login_manager.unauthorized_handler
    def unauth():
        flash(translate("login_required"), "warning")
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    _template_helpers(app)
    _register_blueprints(app)
    _register_errors(app)

    with app.app_context():
        db.create_all()
        _bootstrap_admin(app)
        if app.config["DEMO_DATA"]:
            from app.services.scraper import seed_demo
            seed_demo()
    return app


def _template_helpers(app):
    app.jinja_env.globals["csrf_input"] = lambda: Markup(
        f'<input type="hidden" name="csrf_token" value="{generate_csrf()}">')

    @app.template_filter("budget")
    def fmt_budget(v):
        if v is None:
            return translate("budget_undefined")
        return f"{v:,}".replace(",", "\\u202f") + (" \\u062f\\u062c" if current_lang() == "ar" else " DA")

    @app.template_filter("dmy")
    def fmt_date(v):
        return v.strftime("%d/%m/%Y") if v else "\\u2014"

    @app.context_processor
    def inject():
        lang = current_lang()
        return {"tr": translate, "lang": lang,
                "dir": "rtl" if lang == "ar" else "ltr",
                "other_lang": "ar" if lang == "fr" else "fr",
                "sector_label": lambda k: SECTORS.get(k, {}).get(lang, k or "\\u2014"),
                "commune_label": lambda c: COMMUNE_AR.get(c, c) if lang == "ar" else (c or "\\u2014"),
                "sectors": SECTORS, "communes": COMMUNES,
                "wa": whatsapp_link, "today": today_dz(),
                "app_version": app.config["APP_VERSION"],
                "premium_price": app.config["PREMIUM_PRICE_DZD"],
                "delay_hours": app.config["FREE_PLAN_DELAY_HOURS"],
                "portal_url": app.config["PORTAL_URL"],
                "security_questions": SECURITY_QUESTIONS}


def _register_blueprints(app):
    from app.modules.auth import bp as auth_bp
    from app.modules.main import bp as main_bp
    from app.modules.tenders import bp as tenders_bp
    from app.modules.dashboard import bp as dash_bp
    from app.modules.admin import bp as admin_bp
    from app.modules.transparency import bp as trans_bp
    from app.modules.partners import bp as part_bp
    from app.modules.ads import bp as ads_bp
    from app.modules.reports import bp as rep_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(tenders_bp, url_prefix="/tenders")
    app.register_blueprint(dash_bp, url_prefix="/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(trans_bp, url_prefix="/transparency")
    app.register_blueprint(part_bp, url_prefix="/partners")
    app.register_blueprint(ads_bp, url_prefix="/ads")
    app.register_blueprint(rep_bp, url_prefix="/reports")


def _register_errors(app):
    def page(code, key):
        return render_template("error.html", code=code, message=translate(key)), code

    @app.errorhandler(403)
    def e403(_): return page(403, "err_forbidden")
    @app.errorhandler(404)
    def e404(_): return page(404, "err_notfound")
    @app.errorhandler(500)
    def e500(_):
        db.session.rollback()
        return page(500, "err_server")
    @app.errorhandler(CSRFError)
    def ecsrf(_): return page(400, "err_csrf")


def _bootstrap_admin(app):
    if User.query.filter_by(role="admin").first():
        return
    cfg = app.config
    admin = User(full_name="Administrateur", email=cfg["ADMIN_EMAIL"],
                 phone=cfg["ADMIN_PHONE"], role="admin", plan="premium")
    admin.set_password(cfg["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()
    print(f"\\n[Safqa] Admin cree : {cfg['ADMIN_EMAIL']} / {cfg['ADMIN_PASSWORD']}\\n", flush=True)
'''

# ============ app/extensions.py ============
FILES['app/extensions.py'] = '''# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
'''

# ============ app/constants.py ============
FILES['app/constants.py'] = '''# -*- coding: utf-8 -*-
SECTORS = {
    "travaux": {"fr": "Travaux", "ar": "\\u0623\\u0634\\u063a\\u0627\\u0644"},
    "fournitures": {"fr": "Fournitures", "ar": "\\u0644\\u0648\\u0627\\u0632\\u0645"},
    "services": {"fr": "Services", "ar": "\\u062e\\u062f\\u0645\\u0627\\u062a"},
    "etudes": {"fr": "\\u00c9tudes", "ar": "\\u062f\\u0631\\u0627\\u0633\\u0627\\u062a"},
}

WILAYA_WIDE = "Toute la wilaya"
WILAYA_WIDE_AR = "\\u0643\\u0627\\u0645\\u0644 \\u0627\\u0644\\u0648\\u0644\\u0627\\u064a\\u0629"

COMMUNES = [
    (WILAYA_WIDE, WILAYA_WIDE_AR),
    ("Sidi Bel Abbes", "\\u0633\\u064a\\u062f\\u064a \\u0628\\u0644\\u0639\\u0628\\u0627\\u0633"),
    ("Telagh", "\\u062a\\u0644\\u0627\\u063a"),
    ("Tessala", "\\u062a\\u0633\\u0627\\u0644\\u0629"),
    ("Sfisef", "\\u0633\\u0641\\u064a\\u0632\\u0641"),
    ("Ben Badis", "\\u0628\\u0646 \\u0628\\u0627\\u062f\\u064a\\u0633"),
    ("Ras El Ma", "\\u0631\\u0623\\u0633 \\u0627\\u0644\\u0645\\u0627\\u0621"),
    ("Ain Thrid", "\\u0639\\u064a\\u0646 \\u062b\\u0631\\u064a\\u062f"),
    ("Sidi Lahcene", "\\u0633\\u064a\\u062f\\u064a \\u0644\\u062d\\u0633\\u0646"),
    ("Sidi Ali Boussidi", "\\u0633\\u064a\\u062f\\u064a \\u0639\\u0644\\u064a \\u0628\\u0648\\u0633\\u064a\\u062f\\u064a"),
    ("Merine", "\\u0645\\u0631\\u064a\\u0646"),
    ("Mostefa Ben Brahim", "\\u0645\\u0635\\u0637\\u0641\\u0649 \\u0628\\u0646 \\u0628\\u0631\\u0627\\u0647\\u064a\\u0645"),
    ("Sidi Brahim", "\\u0633\\u064a\\u062f\\u064a \\u0627\\u0628\\u0631\\u0627\\u0647\\u064a\\u0645"),
    ("Sidi Hamadouche", "\\u0633\\u064a\\u062f\\u064a \\u062d\\u0645\\u0627\\u062f\\u0648\\u0634"),
    ("Moulay Slissen", "\\u0645\\u0648\\u0644\\u0627\\u064a \\u0633\\u0644\\u064a\\u0633\\u0646"),
    ("Lamtar", "\\u0644\\u0645\\u0637\\u0627\\u0631"),
    ("Hassi Zahana", "\\u062d\\u0627\\u0633\\u064a \\u0632\\u0647\\u0627\\u0646\\u0629"),
    ("Tabia", "\\u062a\\u0627\\u0628\\u064a\\u0629"),
    ("Ain El Berd", "\\u0639\\u064a\\u0646 \\u0627\\u0644\\u0628\\u0631\\u062f"),
    ("Bir El Hammam", "\\u0628\\u0626\\u0631 \\u0627\\u0644\\u062d\\u0645\\u0627\\u0645"),
]
COMMUNE_NAMES = [c[0] for c in COMMUNES]
COMMUNE_AR = dict(COMMUNES)

SECURITY_QUESTIONS = {
    "mother_name": {"fr": "Nom de jeune fille de votre mere", "ar": "\\u0627\\u0633\\u0645 \\u0639\\u0627\\u0626\\u0644\\u0629 \\u0648\\u0627\\u0644\\u062f\\u062a\\u0643"},
    "birth_city": {"fr": "Ville de naissance", "ar": "\\u0645\\u062f\\u064a\\u0646\\u0629 \\u0627\\u0644\\u0645\\u064a\\u0644\\u0627\\u062f"},
    "first_school": {"fr": "Premiere ecole primaire", "ar": "\\u0627\\u0644\\u0645\\u062f\\u0631\\u0633\\u0629 \\u0627\\u0644\\u0627\\u0628\\u062a\\u062f\\u0627\\u0626\\u064a\\u0629"},
    "favorite_teacher": {"fr": "Professeur prefere", "ar": "\\u0627\\u0644\\u0623\\u0633\\u062a\\u0627\\u0630 \\u0627\\u0644\\u0645\\u0641\\u0636\\u0644"},
}
'''

# ============ app/utils.py ============
FILES['app/utils.py'] = '''# -*- coding: utf-8 -*-
import re
import unicodedata
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    DZ_TZ = ZoneInfo("Africa/Algiers")
except Exception:
    DZ_TZ = timezone(timedelta(hours=1))


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_dz():
    return datetime.now(DZ_TZ).date()


_AR_MAP = str.maketrans({"\\u0623": "\\u0627", "\\u0625": "\\u0627", "\\u0649": "\\u064a", "\\u0629": "\\u0647"})
_DIGITS = str.maketrans("\\u0660\\u0661\\u0662\\u0663\\u0664\\u0665\\u0666\\u0667\\u0668\\u0669", "0123456789")


def normalize_text(text):
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_AR_MAP).lower().replace("\\u2019", "'").replace("-", " ")
    return re.sub(r"\\s+", " ", s).strip()


def normalize_phone(raw):
    s = re.sub(r"[\\s\\-\\.\\(\\)]", "", (raw or "")).translate(_DIGITS)
    if s.startswith("+213"): s = "0" + s[4:]
    elif s.startswith("00213"): s = "0" + s[5:]
    return s if re.fullmatch(r"0[5-7]\\d{8}", s) else None


def whatsapp_link(phone):
    return "https://wa.me/213" + phone[1:] if phone and phone.startswith("0") else None


def parse_date(raw):
    s = (raw or "").strip().translate(_DIGITS)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: continue
    return None


def parse_budget(raw):
    digits = re.sub(r"\\D", "", (raw or "").translate(_DIGITS))
    return int(digits) if digits else None


def is_http_url(url):
    return url and url.startswith(("http://", "https://"))


def safe_next_url(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def like_escape(term):
    return term.replace("\\\\", "\\\\\\\\").replace("%", r"\\%").replace("_", r"\\_")
'''

# ============ app/i18n.py ============
FILES['app/i18n.py'] = '''# -*- coding: utf-8 -*-
from flask import has_request_context, request, session

LANGS = ("fr", "ar")

T = {
    "fr": {
        "app_name": "Safqa Belabbes", "tagline": "Ne ratez plus aucun appel d'offres",
        "subtitle": "Veille des marches publics de Sidi Bel Abbes.",
        "nav_tenders": "Offres", "nav_stats": "Statistiques", "nav_partners": "Partenaires",
        "nav_directory": "Annuaire", "nav_ads": "Annonces", "nav_pricing": "Tarifs",
        "nav_dashboard": "Mon espace", "nav_admin": "Admin", "nav_transparency": "Transparence",
        "nav_reports": "Signalement",
        "login": "Connexion", "register": "Creer un compte", "logout": "Deconnexion",
        "login_required": "Connectez-vous pour acceder a cette page.",
        "register_cta": "Creer un compte gratuit", "upgrade_cta": "Passer Premium",
        "stat_active": "offres actives", "stat_new": "nouvelles (48h)", "stat_closing": "cloture 7j",
        "stat_members": "membres",
        "search_ph": "Rechercher...", "all_sectors": "Tous les secteurs",
        "all_communes": "Toutes les communes", "sort_label": "Tri",
        "sort_new": "Plus recentes", "sort_deadline": "Cloture proche",
        "include_expired": "Inclure expirees", "filter": "Filtrer",
        "reset": "Reinitialiser", "results_count": "{n} offre(s)",
        "no_results": "Aucune offre.", "local_ads": "Annonces",
        "no_ads": "Aucune annonce.", "more_info": "En savoir plus",
        "new": "Nouveau", "demo": "DEMO", "expired": "Expiree", "last_day": "Dernier jour",
        "days_left": "{n}j", "budget_undefined": "Non precise", "view_details": "Voir",
        "favorite_add": "Suivre", "favorite_remove": "Ne plus suivre", "match": "Pertinence",
        "locked_title": "Offre Premium", "locked_hint": "Accessible dans {h}h.",
        "locked_cta": "Debloquer", "locked_msg": "Accessible dans {h}h.",
        "agency": "Organisme", "commune_label": "Commune", "budget": "Budget",
        "deadline": "Date limite", "published": "Publiee", "reference": "Reference",
        "no_description": "Pas de description.", "source_link": "Voir l'avis officiel",
        "back": "Retour", "find_partner": "Chercher un partenaire",
        "full_name": "Nom complet", "email": "Email", "phone": "Telephone",
        "phone_hint": "Format 05/06/07", "company": "Entreprise", "activity": "Secteur",
        "password": "Mot de passe", "password_hint": "8 caracteres min.",
        "confirm": "Confirmer", "create_account": "Creer", "have_account": "Deja inscrit ?",
        "no_account": "Pas de compte ?", "identifier": "Email ou telephone",
        "forgot_link": "Mot de passe oublie ?", "public_profile_opt": "Annuaire public",
        "forgot_title": "Mot de passe oublie", "forgot_hint": "Choisissez votre methode.",
        "reset_by_sms": "Par SMS", "reset_by_question": "Par question de securite",
        "security_question": "Question de securite", "security_answer": "Reponse",
        "security_hint": "Choisissez une question et memorisez la reponse.",
        "answer_question": "Repondre", "security_answer_error": "Reponse incorrecte.",
        "security_no_question": "Methode indisponible.", "security_attempts_exceeded": "Trop de tentatives.",
        "portal_link": "Portail officiel", "back_to_portal": "Portail officiel",
        "enter_identifier": "Email ou telephone",
        "send_code": "Envoyer le code", "back_login": "Retour", "code_label": "Code SMS",
        "new_password": "Nouveau mot de passe", "validate": "Valider", "resend_code": "Renvoyer",
        "demo_code": "Mode demo - code : {code}",
        "err_name": "Nom trop court.", "err_email": "Email invalide.", "err_phone": "Numero invalide.",
        "err_password": "Mot de passe invalide.", "err_confirm": "Mots de passe differents.",
        "err_email_taken": "Email deja utilise.", "err_phone_taken": "Numero deja utilise.",
        "err_credentials": "Identifiants incorrects.", "err_throttle": "Trop de tentatives.",
        "ok_registered": "Bienvenue !", "ok_reset_sent": "Si le numero existe, code envoye.",
        "err_code": "Code invalide.", "ok_reset_done": "Mot de passe modifie.",
        "err_required": "Champs obligatoires.", "err_link": "Lien invalide.",
        "err_forbidden": "Acces refuse.", "err_notfound": "Page introuvable.",
        "err_server": "Erreur interne.", "err_csrf": "Session expiree.",
        "hello": "Bonjour, {name}", "plan_label": "Mon abonnement", "plan_free": "Gratuit",
        "premium_until": "jusqu'au {d}", "premium_active_hint": "Acces immediat + Telegram.",
        "free_delay_hint": "Offres apres {h}h. Premium = immediat.",
        "upgrade_btn": "Passer Premium - {p} DA/mois", "simulation": "simulation",
        "upgrade_done": "Premium active.", "notifications": "Notifications",
        "no_notifications": "Aucune notification.", "mark_read": "Tout marquer lu",
        "my_alerts": "Mes alertes", "alerts_intro": "Soyez prevenu.",
        "no_alerts": "Aucune alerte.", "alert_keywords": "Mots-cles",
        "alert_new": "Creer", "delete": "Supprimer", "alert_created": "Alerte creee.",
        "err_alert_empty": "Choisissez un critere.", "err_alert_limit": "Limite {n}.",
        "my_profile": "Mon profil", "keywords_label": "Mots-cles",
        "keywords_hint": "Separes par virgules.", "bio_label": "Presentation",
        "telegram_label": "Telegram ID", "telegram_hint": "@userinfobot",
        "save": "Enregistrer", "saved_ok": "Enregistre.",
        "my_favorites": "Offres suivies", "no_favorites": "Aucune.",
        "partners_title": "Groupements", "partners_intro": "Publiez votre recherche.",
        "p_tender": "Offre", "p_looking": "Profil recherche", "p_looking_ph": "ex: electricien",
        "p_looking_short": "Recherche", "p_message": "Message", "publish": "Publier",
        "p_visible_note": "Telephone visible.", "p_posted": "Publiee.",
        "p_closed": "Close.", "close_ad": "Cloturer", "no_partners": "Aucune annonce.",
        "ads_title": "Annonces (gratuit)", "ads_intro": "Moderation avant publication.",
        "ad_title": "Titre", "ad_desc": "Description", "ad_link": "Lien (opt)",
        "submit_ad": "Soumettre", "my_ads": "Mes annonces", "approved_ads": "Annonces publiees",
        "status_approved": "Publiee", "status_pending": "En attente", "ad_submitted": "Soumise.",
        "stats_title": "Chiffres", "by_sector": "Par secteur", "by_commune": "Par commune",
        "pricing_title": "Tarifs", "pricing_intro": "Gratuit pour demarrer.",
        "month": "mois", "choose_premium": "Choisir Premium",
        "f_browse": "Toutes les offres", "f_delay": "Nouvelles apres {h}h",
        "f_alerts_free": "3 alertes", "f_alerts_premium": "20 alertes",
        "f_instant": "Acces immediat", "f_telegram": "Telegram",
        "f_score": "Score", "f_partners": "Partenaires",
        "admin_title": "Administration", "a_users": "Utilisateurs", "a_tenders": "Offres",
        "a_active": "actives", "a_upgrade_requests": "Demandes Premium",
        "a_ads_pending": "Annonces a moderer", "a_none": "Rien.",
        "approve": "Valider", "reject": "Refuser", "downgrade": "Repasser gratuit",
        "activate": "Activer", "deactivate": "Desactiver", "delete_confirm": "Supprimer ?",
        "add_tender": "Ajouter", "t_title": "Titre", "t_agency": "Organisme",
        "t_budget": "Budget", "t_deadline": "Date limite", "t_url": "Lien officiel",
        "t_desc": "Description", "t_auto": "Auto", "tender_added": "Ajoutee.",
        "tender_dup": "Existante.", "import_csv": "Importer CSV", "csv_hint": "Colonnes:",
        "err_csv_encoding": "UTF-8 requis.", "imported": "{n} ajout, {s} dup, {e} err.",
        "back_offers": "Retour aux offres", "browse_offers": "Voir offres",
        "theme": "Theme", "transparency_title": "Transparence",
        "transparency_intro": "Analyse des attributions et indicateurs de vigilance.",
        "awards_list": "Attributions recentes", "winner": "Attributaire",
        "amount": "Montant attribue", "offers_count": "Nb offres",
        "transparency_score": "Indice de transparence",
        "transparency_disclaimer": "Ces indicateurs ne sont pas des preuves de corruption.",
        "reports_title": "Signalement confidentiel",
        "reports_intro": "Transmettez anonymement une information.",
        "report_category": "Categorie", "report_description": "Description",
        "report_submit": "Envoyer", "report_success": "Signalement enregistre. Code : {code}",
        "report_tracking": "Code de suivi",
    },
    "ar": {
        "app_name": "\\u0635\\u0641\\u0642\\u0629 \\u0628\\u0644\\u0639\\u0628\\u0627\\u0633",
        "tagline": "\\u0644\\u0627 \\u062a\\u0641\\u0648\\u0651\\u062a \\u0623\\u064a \\u0645\\u0646\\u0627\\u0642\\u0635\\u0629",
        "subtitle": "\\u0631\\u0635\\u062f \\u0627\\u0644\\u0635\\u0641\\u0642\\u0627\\u062a \\u0627\\u0644\\u0639\\u0645\\u0648\\u0645\\u064a\\u0629.",
        "nav_tenders": "\\u0627\\u0644\\u0639\\u0631\\u0648\\u0636", "nav_stats": "\\u0625\\u062d\\u0635\\u0627\\u0626\\u064a\\u0627\\u062a",
        "nav_partners": "\\u0627\\u0644\\u0634\\u0631\\u0643\\u0627\\u0621", "nav_directory": "\\u0627\\u0644\\u062f\\u0644\\u064a\\u0644",
        "nav_ads": "\\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a", "nav_pricing": "\\u0627\\u0644\\u0623\\u0633\\u0639\\u0627\\u0631",
        "nav_dashboard": "\\u0641\\u0636\\u0627\\u0626\\u064a", "nav_admin": "\\u0627\\u0644\\u0625\\u062f\\u0627\\u0631\\u0629",
        "nav_transparency": "\\u0627\\u0644\\u0634\\u0641\\u0627\\u0641\\u064a\\u0629", "nav_reports": "\\u0627\\u0644\\u062a\\u0628\\u0644\\u064a\\u063a",
        "login": "\\u062f\\u062e\\u0648\\u0644", "register": "\\u0625\\u0646\\u0634\\u0627\\u0621 \\u062d\\u0633\\u0627\\u0628",
        "logout": "\\u062e\\u0631\\u0648\\u062c", "login_required": "\\u0633\\u062c\\u0651\\u0644 \\u0627\\u0644\\u062f\\u062e\\u0648\\u0644.",
        "register_cta": "\\u0625\\u0646\\u0634\\u0627\\u0621 \\u062d\\u0633\\u0627\\u0628", "upgrade_cta": "\\u0628\\u0631\\u064a\\u0645\\u064a\\u0648\\u0645",
        "stat_active": "\\u0639\\u0631\\u0636", "stat_new": "\\u062c\\u062f\\u064a\\u062f",
        "stat_closing": "\\u0642\\u0631\\u064a\\u0628", "stat_members": "\\u0639\\u0636\\u0648",
        "search_ph": "\\u0628\\u062d\\u062b...", "all_sectors": "\\u0643\\u0644 \\u0627\\u0644\\u0642\\u0637\\u0627\\u0639\\u0627\\u062a",
        "all_communes": "\\u0643\\u0644 \\u0627\\u0644\\u0628\\u0644\\u062f\\u064a\\u0627\\u062a", "sort_label": "\\u062a\\u0631\\u062a\\u064a\\u0628",
        "sort_new": "\\u0627\\u0644\\u0623\\u062d\\u062f\\u062b", "sort_deadline": "\\u0627\\u0644\\u0623\\u0642\\u0631\\u0628",
        "include_expired": "\\u0627\\u0644\\u0645\\u0646\\u062a\\u0647\\u064a\\u0629", "filter": "\\u062a\\u0635\\u0641\\u064a\\u0629",
        "reset": "\\u0625\\u0639\\u0627\\u062f\\u0629", "results_count": "{n} \\u0639\\u0631\\u0636",
        "no_results": "\\u0644\\u0627 \\u0646\\u062a\\u0627\\u0626\\u062c.", "local_ads": "\\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a",
        "no_ads": "\\u0644\\u0627 \\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a.", "more_info": "\\u0627\\u0644\\u0645\\u0632\\u064a\\u062f",
        "new": "\\u062c\\u062f\\u064a\\u062f", "demo": "\\u062a\\u062c\\u0631\\u064a\\u0628\\u064a",
        "expired": "\\u0645\\u0646\\u062a\\u0647\\u064a", "last_day": "\\u0622\\u062e\\u0631 \\u064a\\u0648\\u0645",
        "days_left": "{n}\\u064a", "budget_undefined": "\\u063a\\u064a\\u0631 \\u0645\\u062d\\u062f\\u062f",
        "view_details": "\\u0639\\u0631\\u0636", "favorite_add": "\\u0645\\u062a\\u0627\\u0628\\u0639\\u0629",
        "favorite_remove": "\\u0625\\u0644\\u063a\\u0627\\u0621", "match": "\\u0645\\u0644\\u0627\\u0621\\u0645\\u0629",
        "locked_title": "\\u0639\\u0631\\u0636 \\u0628\\u0631\\u064a\\u0645\\u064a\\u0648\\u0645", "locked_hint": "\\u0628\\u0639\\u062f {h}\\u0633.",
        "locked_cta": "\\u0627\\u0641\\u062a\\u062d", "locked_msg": "\\u0628\\u0639\\u062f {h}\\u0633.",
        "agency": "\\u0627\\u0644\\u0647\\u064a\\u0626\\u0629", "commune_label": "\\u0627\\u0644\\u0628\\u0644\\u062f\\u064a\\u0629",
        "budget": "\\u0627\\u0644\\u0645\\u064a\\u0632\\u0627\\u0646\\u064a\\u0629", "deadline": "\\u0623\\u062c\\u0644",
        "published": "\\u0646\\u0634\\u0631", "reference": "\\u0645\\u0631\\u062c\\u0639",
        "no_description": "\\u0644\\u0627 \\u0648\\u0635\\u0641.", "source_link": "\\u0627\\u0644\\u0625\\u0639\\u0644\\u0627\\u0646 \\u0627\\u0644\\u0631\\u0633\\u0645\\u064a",
        "back": "\\u0631\\u062c\\u0648\\u0639", "find_partner": "\\u0634\\u0631\\u064a\\u0643",
        "full_name": "\\u0627\\u0644\\u0627\\u0633\\u0645", "email": "\\u0627\\u0644\\u0628\\u0631\\u064a\\u062f",
        "phone": "\\u0627\\u0644\\u0647\\u0627\\u062a\\u0641", "phone_hint": "05/06/07",
        "company": "\\u0627\\u0644\\u0645\\u0624\\u0633\\u0633\\u0629", "activity": "\\u0627\\u0644\\u0642\\u0637\\u0627\\u0639",
        "password": "\\u0643\\u0644\\u0645\\u0629 \\u0627\\u0644\\u0645\\u0631\\u0648\\u0631", "password_hint": "8 \\u0623\\u062d\\u0631\\u0641",
        "confirm": "\\u062a\\u0623\\u0643\\u064a\\u062f", "create_account": "\\u0625\\u0646\\u0634\\u0627\\u0621",
        "have_account": "\\u0644\\u062f\\u064a\\u0643 \\u062d\\u0633\\u0627\\u0628\\u061f", "no_account": "\\u0644\\u0627 \\u062d\\u0633\\u0627\\u0628\\u061f",
        "identifier": "\\u0628\\u0631\\u064a\\u062f \\u0623\\u0648 \\u0647\\u0627\\u062a\\u0641", "forgot_link": "\\u0646\\u0633\\u064a\\u062a\\u061f",
        "public_profile_opt": "\\u0627\\u0644\\u0638\\u0647\\u0648\\u0631 \\u0641\\u064a \\u0627\\u0644\\u062f\\u0644\\u064a\\u0644",
        "forgot_title": "\\u0646\\u0633\\u064a\\u062a \\u0643\\u0644\\u0645\\u0629 \\u0627\\u0644\\u0645\\u0631\\u0648\\u0631", "forgot_hint": "\\u0627\\u062e\\u062a\\u0631 \\u0627\\u0644\\u0637\\u0631\\u064a\\u0642\\u0629.",
        "reset_by_sms": "\\u0639\\u0628\\u0631 SMS", "reset_by_question": "\\u0639\\u0628\\u0631 \\u0633\\u0624\\u0627\\u0644 \\u0627\\u0644\\u0623\\u0645\\u0627\\u0646",
        "security_question": "\\u0633\\u0624\\u0627\\u0644 \\u0627\\u0644\\u0623\\u0645\\u0627\\u0646", "security_answer": "\\u0627\\u0644\\u062c\\u0648\\u0627\\u0628",
        "security_hint": "\\u0627\\u062e\\u062a\\u0631 \\u0633\\u0624\\u0627\\u0644\\u064b\\u0627.", "answer_question": "\\u0625\\u062c\\u0627\\u0628\\u0629",
        "security_answer_error": "\\u062c\\u0648\\u0627\\u0628 \\u062e\\u0627\\u0637\\u0626.", "security_no_question": "\\u063a\\u064a\\u0631 \\u0645\\u062a\\u0627\\u062d.",
        "security_attempts_exceeded": "\\u0645\\u062d\\u0627\\u0648\\u0644\\u0627\\u062a \\u0643\\u062b\\u064a\\u0631\\u0629.",
        "portal_link": "\\u0627\\u0644\\u0628\\u0648\\u0627\\u0628\\u0629 \\u0627\\u0644\\u0631\\u0633\\u0645\\u064a\\u0629", "back_to_portal": "\\u0627\\u0644\\u0628\\u0648\\u0627\\u0628\\u0629",
        "enter_identifier": "\\u0628\\u0631\\u064a\\u062f \\u0623\\u0648 \\u0647\\u0627\\u062a\\u0641",
        "send_code": "\\u0625\\u0631\\u0633\\u0627\\u0644", "back_login": "\\u0631\\u062c\\u0648\\u0639", "code_label": "\\u0627\\u0644\\u0631\\u0645\\u0632",
        "new_password": "\\u0643\\u0644\\u0645\\u0629 \\u062c\\u062f\\u064a\\u062f\\u0629", "validate": "\\u062a\\u0623\\u0643\\u064a\\u062f",
        "resend_code": "\\u0625\\u0639\\u0627\\u062f\\u0629", "demo_code": "\\u0631\\u0645\\u0632: {code}",
        "err_name": "\\u0627\\u0633\\u0645 \\u0642\\u0635\\u064a\\u0631.", "err_email": "\\u0628\\u0631\\u064a\\u062f \\u063a\\u064a\\u0631 \\u0635\\u0627\\u0644\\u062d.",
        "err_phone": "\\u0631\\u0642\\u0645 \\u063a\\u064a\\u0631 \\u0635\\u0627\\u0644\\u062d.", "err_password": "\\u0643\\u0644\\u0645\\u0629 \\u063a\\u064a\\u0631 \\u0635\\u0627\\u0644\\u062d\\u0629.",
        "err_confirm": "\\u063a\\u064a\\u0631 \\u0645\\u062a\\u0637\\u0627\\u0628\\u0642\\u0629.", "err_email_taken": "\\u0627\\u0644\\u0628\\u0631\\u064a\\u062f \\u0645\\u0633\\u062a\\u0639\\u0645\\u0644.",
        "err_phone_taken": "\\u0627\\u0644\\u0631\\u0642\\u0645 \\u0645\\u0633\\u062a\\u0639\\u0645\\u0644.", "err_credentials": "\\u0628\\u064a\\u0627\\u0646\\u0627\\u062a \\u062e\\u0627\\u0637\\u0626\\u0629.",
        "err_throttle": "\\u0645\\u062d\\u0627\\u0648\\u0644\\u0627\\u062a \\u0643\\u062b\\u064a\\u0631\\u0629.", "ok_registered": "\\u0645\\u0631\\u062d\\u0628\\u064b\\u0627!",
        "ok_reset_sent": "\\u0625\\u0646 \\u0643\\u0627\\u0646 \\u0627\\u0644\\u0631\\u0642\\u0645 \\u0645\\u0633\\u062c\\u0644\\u064b\\u0627.",
        "err_code": "\\u0631\\u0645\\u0632 \\u063a\\u064a\\u0631 \\u0635\\u0627\\u0644\\u062d.", "ok_reset_done": "\\u062a\\u0645 \\u0627\\u0644\\u062a\\u063a\\u064a\\u064a\\u0631.",
        "err_required": "\\u062d\\u0642\\u0648\\u0644 \\u0625\\u062c\\u0628\\u0627\\u0631\\u064a\\u0629.", "err_link": "\\u0631\\u0627\\u0628\\u0637 \\u063a\\u064a\\u0631 \\u0635\\u0627\\u0644\\u062d.",
        "err_forbidden": "\\u0645\\u0645\\u0646\\u0648\\u0639.", "err_notfound": "\\u063a\\u064a\\u0631 \\u0645\\u0648\\u062c\\u0648\\u062f.",
        "err_server": "\\u062e\\u0637\\u0623.", "err_csrf": "\\u0627\\u0646\\u062a\\u0647\\u062a \\u0627\\u0644\\u062c\\u0644\\u0633\\u0629.",
        "hello": "\\u0645\\u0631\\u062d\\u0628\\u064b\\u0627\\u060c {name}", "plan_label": "\\u0627\\u0634\\u062a\\u0631\\u0627\\u0643\\u064a",
        "plan_free": "\\u0645\\u062c\\u0627\\u0646\\u064a", "premium_until": "\\u062d\\u062a\\u0649 {d}",
        "premium_active_hint": "\\u0648\\u0635\\u0648\\u0644 \\u0641\\u0648\\u0631\\u064a.", "free_delay_hint": "\\u0628\\u0639\\u062f {h}\\u0633.",
        "upgrade_btn": "\\u0628\\u0631\\u064a\\u0645\\u064a\\u0648\\u0645 - {p} \\u062f\\u062c", "simulation": "\\u0645\\u062d\\u0627\\u0643\\u0627\\u0629",
        "upgrade_done": "\\u062a\\u0645 \\u0627\\u0644\\u062a\\u0641\\u0639\\u064a\\u0644.", "notifications": "\\u0625\\u0634\\u0639\\u0627\\u0631\\u0627\\u062a",
        "no_notifications": "\\u0644\\u0627 \\u0625\\u0634\\u0639\\u0627\\u0631\\u0627\\u062a.", "mark_read": "\\u062a\\u0639\\u0644\\u064a\\u0645 \\u0643\\u0645\\u0642\\u0631\\u0648\\u0621",
        "my_alerts": "\\u062a\\u0646\\u0628\\u064a\\u0647\\u0627\\u062a\\u064a", "alerts_intro": "\\u0646\\u0628\\u0651\\u0647\\u0643.",
        "no_alerts": "\\u0644\\u0627 \\u062a\\u0646\\u0628\\u064a\\u0647\\u0627\\u062a.", "alert_keywords": "\\u0643\\u0644\\u0645\\u0627\\u062a",
        "alert_new": "\\u0625\\u0646\\u0634\\u0627\\u0621", "delete": "\\u062d\\u0630\\u0641", "alert_created": "\\u062a\\u0645.",
        "err_alert_empty": "\\u0627\\u062e\\u062a\\u0631 \\u0645\\u0639\\u064a\\u0627\\u0631\\u064b\\u0627.", "err_alert_limit": "\\u062d\\u062f {n}.",
        "my_profile": "\\u0645\\u0644\\u0641\\u064a", "keywords_label": "\\u0643\\u0644\\u0645\\u0627\\u062a",
        "keywords_hint": "\\u0628\\u0641\\u0648\\u0627\\u0635\\u0644.", "bio_label": "\\u062a\\u0639\\u0631\\u064a\\u0641",
        "telegram_label": "Telegram ID", "telegram_hint": "@userinfobot",
        "save": "\\u062d\\u0641\\u0638", "saved_ok": "\\u062a\\u0645.",
        "my_favorites": "\\u0627\\u0644\\u0645\\u062a\\u0627\\u0628\\u0639\\u0629", "no_favorites": "\\u0644\\u0627 \\u0634\\u064a\\u0621.",
        "partners_title": "\\u0627\\u0644\\u062a\\u062c\\u0645\\u0651\\u0639\\u0627\\u062a", "partners_intro": "\\u0627\\u0646\\u0634\\u0631 \\u0628\\u062d\\u062b\\u0643.",
        "p_tender": "\\u0627\\u0644\\u0639\\u0631\\u0636", "p_looking": "\\u0627\\u0644\\u0645\\u0637\\u0644\\u0648\\u0628",
        "p_looking_ph": "\\u0645\\u062b\\u0627\\u0644: \\u0643\\u0647\\u0631\\u0628\\u0627\\u0626\\u064a", "p_looking_short": "\\u064a\\u0628\\u062d\\u062b \\u0639\\u0646",
        "p_message": "\\u0631\\u0633\\u0627\\u0644\\u0629", "publish": "\\u0646\\u0634\\u0631",
        "p_visible_note": "\\u0627\\u0644\\u0647\\u0627\\u062a\\u0641 \\u0645\\u0631\\u0626\\u064a.", "p_posted": "\\u062a\\u0645 \\u0627\\u0644\\u0646\\u0634\\u0631.",
        "p_closed": "\\u0623\\u064f\\u063a\\u0644\\u0642.", "close_ad": "\\u0625\\u063a\\u0644\\u0627\\u0642", "no_partners": "\\u0644\\u0627 \\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a.",
        "ads_title": "\\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a (\\u0645\\u062c\\u0627\\u0646\\u0627)", "ads_intro": "\\u0645\\u0631\\u0627\\u062c\\u0639\\u0629 \\u0642\\u0628\\u0644 \\u0627\\u0644\\u0646\\u0634\\u0631.",
        "ad_title": "\\u0627\\u0644\\u0639\\u0646\\u0648\\u0627\\u0646", "ad_desc": "\\u0627\\u0644\\u0648\\u0635\\u0641", "ad_link": "\\u0631\\u0627\\u0628\\u0637",
        "submit_ad": "\\u0625\\u0631\\u0633\\u0627\\u0644", "my_ads": "\\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a\\u064a",
        "approved_ads": "\\u0627\\u0644\\u0645\\u0646\\u0634\\u0648\\u0631\\u0629", "status_approved": "\\u0645\\u0646\\u0634\\u0648\\u0631",
        "status_pending": "\\u0642\\u064a\\u062f \\u0627\\u0644\\u0645\\u0631\\u0627\\u062c\\u0639\\u0629", "ad_submitted": "\\u062a\\u0645 \\u0627\\u0644\\u0625\\u0631\\u0633\\u0627\\u0644.",
        "stats_title": "\\u0627\\u0644\\u0623\\u0631\\u0642\\u0627\\u0645", "by_sector": "\\u062d\\u0633\\u0628 \\u0627\\u0644\\u0642\\u0637\\u0627\\u0639",
        "by_commune": "\\u062d\\u0633\\u0628 \\u0627\\u0644\\u0628\\u0644\\u062f\\u064a\\u0629",
        "pricing_title": "\\u0627\\u0644\\u0623\\u0633\\u0639\\u0627\\u0631", "pricing_intro": "\\u0645\\u062c\\u0627\\u0646\\u064a.",
        "month": "\\u0634\\u0647\\u0631", "choose_premium": "\\u0628\\u0631\\u064a\\u0645\\u064a\\u0648\\u0645",
        "f_browse": "\\u0643\\u0644 \\u0627\\u0644\\u0639\\u0631\\u0648\\u0636", "f_delay": "\\u0628\\u0639\\u062f {h}\\u0633",
        "f_alerts_free": "3 \\u062a\\u0646\\u0628\\u064a\\u0647\\u0627\\u062a", "f_alerts_premium": "20 \\u062a\\u0646\\u0628\\u064a\\u0647\\u064b\\u0627",
        "f_instant": "\\u0641\\u0648\\u0631\\u064a", "f_telegram": "Telegram", "f_score": "\\u062f\\u0631\\u062c\\u0629",
        "f_partners": "\\u0634\\u0631\\u0643\\u0627\\u0621",
        "admin_title": "\\u0627\\u0644\\u0625\\u062f\\u0627\\u0631\\u0629", "a_users": "\\u0645\\u0633\\u062a\\u062e\\u062f\\u0645\\u0648\\u0646",
        "a_tenders": "\\u0639\\u0631\\u0648\\u0636", "a_active": "\\u0646\\u0634\\u0637\\u0629",
        "a_upgrade_requests": "\\u0637\\u0644\\u0628\\u0627\\u062a \\u0628\\u0631\\u064a\\u0645\\u064a\\u0648\\u0645",
        "a_ads_pending": "\\u0625\\u0639\\u0644\\u0627\\u0646\\u0627\\u062a \\u0644\\u0644\\u0645\\u0631\\u0627\\u062c\\u0639\\u0629", "a_none": "\\u0644\\u0627 \\u0634\\u064a\\u0621.",
        "approve": "\\u0642\\u0628\\u0648\\u0644", "reject": "\\u0631\\u0641\\u0636", "downgrade": "\\u0645\\u062c\\u0627\\u0646\\u064a",
        "activate": "\\u062a\\u0641\\u0639\\u064a\\u0644", "deactivate": "\\u062a\\u0639\\u0637\\u064a\\u0644",
        "delete_confirm": "\\u062d\\u0630\\u0641\\u061f", "add_tender": "\\u0625\\u0636\\u0627\\u0641\\u0629",
        "t_title": "\\u0639\\u0646\\u0648\\u0627\\u0646", "t_agency": "\\u0647\\u064a\\u0626\\u0629",
        "t_budget": "\\u0645\\u064a\\u0632\\u0627\\u0646\\u064a\\u0629", "t_deadline": "\\u0623\\u062c\\u0644",
        "t_url": "\\u0631\\u0627\\u0628\\u0637", "t_desc": "\\u0648\\u0635\\u0641", "t_auto": "\\u062a\\u0644\\u0642\\u0627\\u0626\\u064a",
        "tender_added": "\\u062a\\u0645.", "tender_dup": "\\u0645\\u0648\\u062c\\u0648\\u062f.",
        "import_csv": "CSV", "csv_hint": "\\u0623\\u0639\\u0645\\u062f\\u0629:",
        "err_csv_encoding": "UTF-8.", "imported": "{n}\\u0645\\u0636\\u0627\\u0641 {s}\\u0645\\u0643\\u0631\\u0631 {e}\\u062e\\u0637\\u0623",
        "back_offers": "\\u0627\\u0644\\u0639\\u0631\\u0648\\u0636", "browse_offers": "\\u0639\\u0631\\u0636",
        "theme": "\\u0627\\u0644\\u0648\\u0636\\u0639",
        "transparency_title": "\\u0627\\u0644\\u0634\\u0641\\u0627\\u0641\\u064a\\u0629",
        "transparency_intro": "\\u062a\\u062d\\u0644\\u064a\\u0644 \\u0627\\u0644\\u0627\\u0633\\u062a\\u062d\\u0648\\u0627\\u0630\\u0627\\u062a.",
        "awards_list": "\\u0627\\u0644\\u0627\\u0633\\u062a\\u062d\\u0648\\u0627\\u0630\\u0627\\u062a", "winner": "\\u0627\\u0644\\u0641\\u0627\\u0626\\u0632",
        "amount": "\\u0627\\u0644\\u0645\\u0628\\u0644\\u063a", "offers_count": "\\u0639\\u062f\\u062f \\u0627\\u0644\\u0639\\u0631\\u0648\\u0636",
        "transparency_score": "\\u0645\\u0624\\u0634\\u0631",
        "transparency_disclaimer": "\\u0644\\u064a\\u0633\\u062a \\u0623\\u062f\\u0644\\u0629 \\u0639\\u0644\\u0649 \\u0627\\u0644\\u0641\\u0633\\u0627\\u062f.",
        "reports_title": "\\u0627\\u0644\\u062a\\u0628\\u0644\\u064a\\u063a \\u0627\\u0644\\u0633\\u0631\\u064a",
        "reports_intro": "\\u0623\\u0631\\u0633\\u0644 \\u0645\\u0639\\u0644\\u0648\\u0645\\u0629 \\u0628\\u0623\\u0645\\u0627\\u0646.",
        "report_category": "\\u0627\\u0644\\u0641\\u0626\\u0629", "report_description": "\\u0627\\u0644\\u0648\\u0635\\u0641",
        "report_submit": "\\u0625\\u0631\\u0633\\u0627\\u0644", "report_success": "\\u062a\\u0645. \\u0627\\u0644\\u0631\\u0645\\u0632: {code}",
        "report_tracking": "\\u0631\\u0645\\u0632 \\u0627\\u0644\\u062a\\u062a\\u0628\\u0639",
    },
}

MISSING = set()


def current_lang():
    if has_request_context():
        lg = session.get("lang")
        if lg in LANGS: return lg
        best = request.accept_languages.best_match(LANGS)
        if best: return best
    return "fr"


def translate(key, **kwargs):
    lg = current_lang()
    txt = T[lg].get(key)
    if txt is None:
        MISSING.add((lg, key))
        txt = T["fr"].get(key, key)
    try:
        return txt.format(**kwargs) if kwargs else txt
    except (KeyError, IndexError):
        return txt
'''

# ============ app/models.py ============
FILES['app/models.py'] = '''# -*- coding: utf-8 -*-
import re
import secrets
from datetime import timedelta
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.utils import today_dz, utcnow, normalize_text


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(150))
    activity = db.Column(db.String(30))
    commune = db.Column(db.String(100))
    keywords = db.Column(db.String(300))
    bio = db.Column(db.Text)
    public_profile = db.Column(db.Boolean, default=True, nullable=False)
    telegram_chat_id = db.Column(db.String(40))
    role = db.Column(db.String(20), default="user", nullable=False)
    plan = db.Column(db.String(20), default="free", nullable=False)
    premium_until = db.Column(db.Date)
    upgrade_requested = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    security_question = db.Column(db.String(40))
    security_answer_hash = db.Column(db.String(255))
    security_attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    alerts = db.relationship("SavedAlert", backref="user", cascade="all, delete-orphan")

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)
    def set_security_answer(self, a):
        n = normalize_text(a or "")
        if n: self.security_answer_hash = generate_password_hash(n)
    def check_security_answer(self, a):
        if not self.security_answer_hash: return False
        return check_password_hash(self.security_answer_hash, normalize_text(a or ""))

    @property
    def is_active(self): return self.active
    @property
    def is_admin(self): return self.role == "admin"
    @property
    def is_premium(self):
        if self.role == "admin": return True
        if self.plan != "premium": return False
        return self.premium_until is None or self.premium_until >= today_dz()
    @property
    def keyword_list(self):
        return [k.strip() for k in re.split(r"[,;\\u060c\\n]", self.keywords or "") if len(k.strip()) >= 3]
    @property
    def alert_limit(self):
        return current_app.config["PREMIUM_ALERT_LIMIT" if self.is_premium else "FREE_ALERT_LIMIT"]


class Tender(db.Model):
    __tablename__ = "tenders"
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, index=True, nullable=False)
    reference = db.Column(db.String(100))
    title = db.Column(db.String(500), nullable=False)
    agency = db.Column(db.String(200), nullable=False)
    sector = db.Column(db.String(30), nullable=False, index=True)
    commune = db.Column(db.String(100), nullable=False, index=True)
    budget_dzd = db.Column(db.BigInteger)
    deadline = db.Column(db.Date, nullable=False, index=True)
    source_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    @property
    def days_left(self): return (self.deadline - today_dz()).days
    @property
    def urgency(self):
        d = self.days_left
        if d < 0: return "expired"
        if d <= 3: return "urgent"
        if d <= 10: return "soon"
        return "ok"
    @property
    def is_new(self): return utcnow() - self.created_at <= timedelta(hours=72)
    @property
    def unlock_at(self): return self.created_at + timedelta(hours=current_app.config["FREE_PLAN_DELAY_HOURS"])
    @property
    def hours_until_unlock(self):
        delta = self.unlock_at - utcnow()
        return max(0, int(delta.total_seconds() // 3600) + 1)
    def locked_for(self, user):
        if user is not None and getattr(user, "is_authenticated", False) and user.is_premium:
            return False
        return utcnow() < self.unlock_at


class Award(db.Model):
    __tablename__ = "awards"
    id = db.Column(db.Integer, primary_key=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False, index=True)
    winner_company = db.Column(db.String(200), nullable=False)
    winner_rc = db.Column(db.String(50))
    amount_dzd = db.Column(db.BigInteger)
    offers_count = db.Column(db.Integer)
    transparency_score = db.Column(db.Integer, default=100)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    tender = db.relationship("Tender")


class SavedAlert(db.Model):
    __tablename__ = "saved_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sector = db.Column(db.String(30))
    commune = db.Column(db.String(100))
    keywords = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    @property
    def keyword_list(self):
        return [k.strip() for k in re.split(r"[,;\\u060c\\n]", self.keywords or "") if len(k.strip()) >= 3]


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "tender_id", name="uq_fav"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    tender = db.relationship("Tender")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False)
    available_at = db.Column(db.DateTime, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    tender = db.relationship("Tender")


class Ad(db.Model):
    __tablename__ = "ads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User")


class PartnershipAd(db.Model):
    __tablename__ = "partnership_ads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"))
    tender_title = db.Column(db.String(300), nullable=False)
    looking_for = db.Column(db.String(300), nullable=False)
    message = db.Column(db.Text)
    is_open = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User")
    tender = db.relationship("Tender")


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    tracking_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="new", nullable=False)
    handler_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @staticmethod
    def new_tracking():
        return secrets.token_urlsafe(12)[:16]


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    target_table = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
'''

# ============ app/services/__init__.py ============
FILES['app/services/__init__.py'] = ''

# ============ app/services/classifier.py ============
FILES['app/services/classifier.py'] = '''# -*- coding: utf-8 -*-
"""Classification automatique des offres : secteur, commune, mots-cles."""
import re
from app.constants import COMMUNES, SECTORS, WILAYA_WIDE
from app.utils import normalize_text

SECTOR_KEYWORDS = {
    "etudes": ["etude", "suivi", "controle", "expertise", "audit", "\\u062f\\u0631\\u0627\\u0633\\u0629", "\\u0645\\u062a\\u0627\\u0628\\u0639\\u0629"],
    "services": ["nettoyage", "gardiennage", "maintenance", "transport", "restauration", "formation", "\\u062e\\u062f\\u0645\\u0627\\u062a", "\\u0646\\u0638\\u0627\\u0641\\u0629", "\\u0635\\u064a\\u0627\\u0646\\u0629"],
    "fournitures": ["fourniture", "acquisition", "equipement", "materiel", "achat", "\\u0627\\u0642\\u062a\\u0646\\u0627\\u0621", "\\u062a\\u0648\\u0631\\u064a\\u062f", "\\u0644\\u0648\\u0627\\u0632\\u0645"],
    "travaux": ["travaux", "realisation", "construction", "amenagement", "route", "voirie", "\\u0623\\u0634\\u063a\\u0627\\u0644", "\\u0625\\u0646\\u062c\\u0627\\u0632", "\\u0637\\u0631\\u064a\\u0642"],
}


def classify_sector(text):
    n = normalize_text(text)
    for key, words in SECTOR_KEYWORDS.items():
        if any(normalize_text(w) in n for w in words):
            return key
    return "services"


def detect_commune(text):
    n = normalize_text(text)
    best = WILAYA_WIDE
    best_len = 0
    for fr, ar in COMMUNES[1:]:
        for candidate in (normalize_text(fr), normalize_text(ar)):
            if candidate and candidate in n and len(candidate) > best_len:
                best = fr
                best_len = len(candidate)
    return best


def extract_keywords(text, limit=10):
    words = re.findall(r"[\\w\\u0600-\\u06FF]{4,}", (text or "").lower())
    stop = {"dans", "pour", "avec", "cette", "travaux", "entre", "selon", "sous", "fait", "faites"}
    freq = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda k: -freq[k])[:limit]
'''

# ============ app/services/scoring.py ============
FILES['app/services/scoring.py'] = '''# -*- coding: utf-8 -*-
"""Score de pertinence entre profil utilisateur et offre (0-100)."""
from app.constants import WILAYA_WIDE
from app.utils import normalize_text


def keyword_hits(keywords, tender):
    hay = normalize_text(f"{tender.title} {tender.agency} {tender.description or ''}")
    hits = []
    for kw in keywords:
        nk = normalize_text(kw)
        if len(nk) >= 3 and nk in hay:
            hits.append(kw)
    return hits


def score_tender(user, tender):
    max_pts, pts, reasons = 0, 0, []
    if user.activity:
        max_pts += 40
        if user.activity == tender.sector:
            pts += 40
            reasons.append(("sector", None))
    if user.commune and user.commune != WILAYA_WIDE:
        max_pts += 30
        if tender.commune == user.commune:
            pts += 30
            reasons.append(("commune", None))
        elif tender.commune == WILAYA_WIDE:
            pts += 20
            reasons.append(("wilaya", None))
    kws = user.keyword_list
    if kws:
        max_pts += 30
        hits = keyword_hits(kws, tender)
        if hits:
            pts += 20 if len(hits) == 1 else 30
            reasons.append(("keyword", ", ".join(hits)))
    if max_pts == 0:
        return None, []
    return round(100 * pts / max_pts), reasons
'''

# ============ app/services/notifications.py ============
FILES['app/services/notifications.py'] = '''# -*- coding: utf-8 -*-
import logging
import requests
from flask import current_app
from app.extensions import db
from app.models import Notification, SavedAlert, User
from app.utils import utcnow

logger = logging.getLogger(__name__)


def alert_matches(alert, tender):
    if alert.sector and alert.sector != tender.sector: return False
    if alert.commune and alert.commune != WILAYA_WIDE_CHECK(alert.commune):
        if tender.commune not in (alert.commune, "Toute la wilaya"): return False
    kws = alert.keyword_list
    if kws:
        from app.services.scoring import keyword_hits
        if not keyword_hits(kws, tender): return False
    return True


def WILAYA_WIDE_CHECK(c): return c != "Toute la wilaya"


def dispatch_new_tender(tender):
    alerts = SavedAlert.query.join(User).filter(User.active.is_(True)).all()
    seen, created = set(), 0
    for alert in alerts:
        if alert.user_id in seen or not alert_matches(alert, tender): continue
        seen.add(alert.user_id)
        user = alert.user
        available = utcnow() if user.is_premium else tender.unlock_at
        db.session.add(Notification(user_id=user.id, tender_id=tender.id, available_at=available))
        created += 1
        if user.is_premium and user.telegram_chat_id:
            send_telegram(user.telegram_chat_id, f"\\U0001f4e2 {tender.title}\\n{tender.deadline}")
    db.session.commit()
    return created


def send_telegram(chat_id, text):
    token = current_app.config["TELEGRAM_TOKEN"]
    if not token or not chat_id: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.ok
    except Exception as e:
        logger.error(f"Telegram: {e}")
        return False
'''

# ============ app/services/scraper.py ============
FILES['app/services/scraper.py'] = '''# -*- coding: utf-8 -*-
import hashlib
from datetime import timedelta
from app.extensions import db
from app.models import Tender
from app.services.classifier import classify_sector, detect_commune
from app.utils import normalize_text, today_dz, utcnow


def _fingerprint(title, agency, deadline):
    raw = "|".join([normalize_text(title), normalize_text(agency), deadline.isoformat()])
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def upsert_tender(data, demo=False, notify=True):
    title = (data.get("title") or "").strip()[:500]
    agency = (data.get("agency") or "").strip()[:200]
    deadline = data.get("deadline")
    if not title or not agency or not deadline: return None
    ctx = f"{title} {agency} {data.get('description') or ''}"
    sector = data.get("sector") or classify_sector(ctx)
    commune = data.get("commune") or detect_commune(ctx)
    ext = data.get("external_id") or _fingerprint(title, agency, deadline)
    if Tender.query.filter_by(external_id=ext).first(): return None
    t = Tender(external_id=ext, title=title, agency=agency, sector=sector,
               commune=commune, budget_dzd=data.get("budget_dzd"),
               deadline=deadline, source_url=data.get("source_url"),
               description=data.get("description"), is_demo=demo,
               created_at=data.get("created_at") or utcnow())
    db.session.add(t)
    db.session.commit()
    if notify:
        try:
            from app.services.notifications import dispatch_new_tender
            dispatch_new_tender(t)
        except Exception:
            pass
    return t


def seed_demo():
    if Tender.query.count() > 0: return 0
    today, now = today_dz(), utcnow()
    rows = [
        ("Travaux de rehabilitation de la route Sidi Bel Abbes - Telagh",
         "Direction des Travaux Publics", "Telagh", 45_000_000, 21, timedelta(days=9)),
        ("Acquisition de materiel informatique - Universite Djillali Liabes",
         "Universite Djillali Liabes", "Sidi Bel Abbes", 8_500_000, 12, timedelta(days=4)),
        ("Services de nettoyage et gardiennage - CHU",
         "CHU Abdelkader Hassani", "Sidi Bel Abbes", 12_000_000, 33, timedelta(days=3)),
        ("Reseau d'assainissement - commune de Tessala",
         "APC de Tessala", "Tessala", 18_750_000, 27, timedelta(hours=30)),
        ("Ecole primaire 6 classes a Sfisef",
         "Direction des Equipements Publics", "Sfisef", 62_000_000, 40, timedelta(hours=20)),
        ("Denrees alimentaires pour cantines scolaires",
         "Direction de l'Education", "Toute la wilaya", 6_200_000, 15, timedelta(hours=8)),
        ("Etude et suivi marche couvert de Ben Badis",
         "APC de Ben Badis", "Ben Badis", 3_400_000, 18, timedelta(hours=3)),
        ("Maintenance eclairage public - Ras El Ma",
         "APC de Ras El Ma", "Ras El Ma", 2_900_000, 9, timedelta(days=6)),
    ]
    added = 0
    for title, agency, commune, budget, days, age in rows:
        t = upsert_tender({"title": title, "agency": agency, "commune": commune,
                           "budget_dzd": budget, "deadline": today + timedelta(days=days),
                           "created_at": now - age, "description": "Offre de demonstration."},
                          demo=True, notify=False)
        added += 1 if t else 0
    return added
'''# ============ app/modules/__init__.py ============
FILES['app/modules/__init__.py'] = ''

# ============ app/modules/main/__init__.py ============
FILES['app/modules/main/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, session, url_for
from sqlalchemy import func, or_
from app.constants import COMMUNE_NAMES, SECTORS, WILAYA_WIDE
from app.extensions import db
from app.i18n import LANGS, translate
from app.models import Ad, Favorite, Tender, User
from app.utils import like_escape, safe_next_url, today_dz, utcnow
from datetime import timedelta

bp = Blueprint("main", __name__)


def filtered_query(args):
    q = Tender.query.filter_by(is_active=True)
    if args.get("expired") != "1":
        q = q.filter(Tender.deadline >= today_dz())
    sector = args.get("sector", "")
    commune = args.get("commune", "")
    text = (args.get("q") or "").strip()
    if sector in SECTORS: q = q.filter(Tender.sector == sector)
    if commune in COMMUNE_NAMES and commune != WILAYA_WIDE:
        q = q.filter(or_(Tender.commune == commune, Tender.commune == WILAYA_WIDE))
    if text:
        like = f"%{like_escape(text[:80])}%"
        q = q.filter(or_(Tender.title.ilike(like, escape="\\\\"),
                         Tender.agency.ilike(like, escape="\\\\")))
    if args.get("sort") == "deadline":
        return q.order_by(Tender.deadline.asc(), Tender.id.desc())
    return q.order_by(Tender.created_at.desc(), Tender.id.desc())


@bp.route("/")
def index():
    from flask_login import current_user
    from flask import current_app
    page = request.args.get("page", 1, type=int)
    pag = filtered_query(request.args).paginate(page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False)
    favs = set()
    if current_user.is_authenticated:
        favs = {x.tender_id for x in Favorite.query.filter_by(user_id=current_user.id)}
    from app.services.scoring import score_tender
    items = []
    for t in pag.items:
        score, reasons = (None, [])
        if current_user.is_authenticated:
            score, reasons = score_tender(current_user, t)
        items.append({"tender": t, "locked": t.locked_for(current_user),
                      "score": score, "reasons": reasons, "fav": t.id in favs})
    base = Tender.query.filter(Tender.is_active.is_(True), Tender.deadline >= today_dz())
    cfg = current_app.config
    cutoff = utcnow() - timedelta(hours=cfg["FREE_PLAN_DELAY_HOURS"])
    stats = {"active": base.count(),
             "new": base.filter(Tender.created_at >= utcnow() - timedelta(hours=48)).count(),
             "closing": base.filter(Tender.deadline <= today_dz() + timedelta(days=7)).count()}
    premium = current_user.is_authenticated and current_user.is_premium
    locked_count = 0 if premium else base.filter(Tender.created_at > cutoff).count()
    ads = Ad.query.filter_by(is_approved=True).order_by(Ad.created_at.desc()).limit(4).all()
    return render_template("index.html", items=items, pagination=pag, stats=stats,
                           locked_count=locked_count, ads=ads, args=request.args,
                           page_url=lambda p: url_for("main.index", **{**request.args.to_dict(), "page": p}))


@bp.route("/stats")
def stats():
    base = Tender.query.filter(Tender.is_active.is_(True), Tender.deadline >= today_dz())
    ids = base.with_entities(Tender.id)
    by_sector = (db.session.query(Tender.sector, func.count(Tender.id))
                 .filter(Tender.id.in_(ids)).group_by(Tender.sector)
                 .order_by(func.count(Tender.id).desc()).all())
    by_commune = (db.session.query(Tender.commune, func.count(Tender.id))
                  .filter(Tender.id.in_(ids)).group_by(Tender.commune)
                  .order_by(func.count(Tender.id).desc()).limit(10).all())
    data = {"total": base.count(),
            "new48": base.filter(Tender.created_at >= utcnow() - timedelta(hours=48)).count(),
            "closing": base.filter(Tender.deadline <= today_dz() + timedelta(days=7)).count(),
            "members": User.query.filter_by(active=True).count()}
    return render_template("stats.html", data=data, by_sector=by_sector, by_commune=by_commune)


@bp.route("/pricing")
def pricing():
    return render_template("stats.html", data={"total":0,"new48":0,"closing":0,"members":0},
                           by_sector=[], by_commune=[])


@bp.route("/lang/<code>")
def set_lang(code):
    if code in LANGS: session["lang"] = code
    ref = request.referrer or ""
    return redirect(safe_next_url(ref) or url_for("main.index"))


@bp.get("/api/tenders")
def api_tenders():
    from flask import jsonify
    q = filtered_query(request.args)
    limit = min(request.args.get("limit", 50, type=int), 100)
    return jsonify([{"id": t.id, "title": t.title, "agency": t.agency,
                     "sector": t.sector, "commune": t.commune,
                     "deadline": t.deadline.isoformat(), "days_left": t.days_left}
                    for t in q.limit(limit).all()])


@bp.get("/health")
def health():
    from flask import jsonify
    return jsonify({"status": "ok"})
'''

# ============ app/modules/auth/__init__.py ============
FILES['app/modules/auth/__init__.py'] = '''# -*- coding: utf-8 -*-
import hashlib
import hmac
import secrets
from datetime import timedelta
from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app
from flask_login import current_user, login_required, login_user, logout_user
from app.constants import COMMUNE_NAMES, SECURITY_QUESTIONS, SECTORS
from app.extensions import db, limiter
from app.i18n import translate
from app.models import PasswordReset, User
from app.utils import normalize_phone, safe_next_url, utcnow

bp = Blueprint("auth", __name__)


def _code_hash(phone, code):
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _f(name):
    return (request.form.get(name) or "").strip()


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        name = _f("full_name"); email = _f("email").lower()
        pw = request.form.get("password", ""); cf = request.form.get("confirm", "")
        phone = normalize_phone(_f("phone")); errors = []
        if len(name) < 3: errors.append("err_name")
        if "@" not in email: errors.append("err_email")
        if not phone: errors.append("err_phone")
        if len(pw) < 8: errors.append("err_password")
        elif pw != cf: errors.append("err_confirm")
        if not errors and User.query.filter_by(email=email).first(): errors.append("err_email_taken")
        if not errors and User.query.filter_by(phone=phone).first(): errors.append("err_phone_taken")
        if errors:
            for e in errors: flash(translate(e), "error")
            return render_template("register.html", form=request.form), 400
        activity = _f("activity"); commune = _f("commune")
        u = User(full_name=name, email=email, phone=phone,
                 company=_f("company")[:150] or None,
                 activity=activity if activity in SECTORS else None,
                 commune=commune if commune in COMMUNE_NAMES else None,
                 public_profile=request.form.get("public_profile") == "on")
        sq = _f("security_question"); sa = _f("security_answer")
        if sq in SECURITY_QUESTIONS and len(sa) >= 2: u.security_question = sq
        u.set_password(pw)
        if u.security_question: u.set_security_answer(sa)
        db.session.add(u); db.session.commit()
        login_user(u)
        flash(translate("ok_registered"), "success")
        return redirect(url_for("dashboard.home"))
    return render_template("register.html", form={"public_profile": "on"})


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        ident = _f("identifier").lower(); pw = request.form.get("password", "")
        u = (User.query.filter_by(email=ident).first() if "@" in ident
             else User.query.filter_by(phone=normalize_phone(ident) or "-").first())
        if u and u.active and u.check_password(pw):
            login_user(u, remember=True)
            return redirect(safe_next_url(request.args.get("next")) or url_for("dashboard.home"))
        flash(translate("err_credentials"), "error")
        return render_template("login.html"), 401
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        phone = normalize_phone(_f("phone"))
        if not phone:
            flash(translate("err_phone"), "error")
            return render_template("forgot_password.html"), 400
        user = User.query.filter_by(phone=phone, active=True).first()
        if user:
            code = "".join(secrets.choice("0123456789") for _ in range(6))
            db.session.add(PasswordReset(phone=phone, code_hash=_code_hash(phone, code),
                                         expires_at=utcnow() + timedelta(minutes=15)))
            db.session.commit()
            if current_app.config["SMS_MODE"] == "demo":
                flash(translate("demo_code", code=code), "warning")
        flash(translate("ok_reset_sent"), "success")
        session["reset_phone"] = phone
        return redirect(url_for("auth.reset_password"))
    return render_template("forgot_password.html")


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    phone = session.get("reset_phone")
    if not phone: return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        code = _f("code"); pw = request.form.get("password", ""); cf = request.form.get("confirm", "")
        if len(pw) < 8 or pw != cf:
            flash(translate("err_password"), "error"); return render_template("reset_password.html"), 400
        r = (PasswordReset.query.filter_by(phone=phone, used=False)
             .order_by(PasswordReset.id.desc()).first())
        if r and r.expires_at > utcnow() and r.attempts < 5 and hmac.compare_digest(r.code_hash, _code_hash(phone, code)):
            u = User.query.filter_by(phone=phone).first()
            u.set_password(pw); r.used = True; db.session.commit()
            session.pop("reset_phone", None)
            flash(translate("ok_reset_done"), "success")
            return redirect(url_for("auth.login"))
        if r: r.attempts += 1; db.session.commit()
        flash(translate("err_code"), "error")
        return render_template("reset_password.html"), 400
    return render_template("reset_password.html")


@bp.route("/forgot-password/question", methods=["GET", "POST"])
def forgot_password_question():
    if request.method == "POST":
        ident = _f("identifier").lower()
        u = (User.query.filter_by(email=ident, active=True).first() if "@" in ident
             else User.query.filter_by(phone=normalize_phone(ident) or "-", active=True).first())
        if not u or not u.security_question:
            flash(translate("security_no_question"), "error")
            return render_template("forgot_password.html"), 400
        session["reset_user_id"] = u.id
        return redirect(url_for("auth.reset_password_question"))
    return render_template("forgot_password.html")


@bp.route("/reset-password/question", methods=["GET", "POST"])
def reset_password_question():
    uid = session.get("reset_user_id")
    if not uid: return redirect(url_for("auth.forgot_password"))
    u = db.session.get(User, int(uid))
    if not u or not u.security_question: return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        if u.security_attempts >= 5:
            flash(translate("security_attempts_exceeded"), "error")
            return render_template("reset_password_question.html", user=u), 429
        ans = _f("security_answer"); pw = request.form.get("password", ""); cf = request.form.get("confirm", "")
        if len(pw) < 8 or pw != cf:
            flash(translate("err_password"), "error"); return render_template("reset_password_question.html", user=u), 400
        if not u.check_security_answer(ans):
            u.security_attempts = (u.security_attempts or 0) + 1
            db.session.commit()
            flash(translate("security_answer_error"), "error")
            return render_template("reset_password_question.html", user=u), 400
        u.set_password(pw); u.security_attempts = 0; db.session.commit()
        session.pop("reset_user_id", None)
        flash(translate("ok_reset_done"), "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password_question.html", user=u)
'''

# ============ app/modules/tenders/__init__.py ============
FILES['app/modules/tenders/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, abort, redirect, url_for, flash, render_template, Response
from flask_login import current_user, login_required
from app.extensions import db
from app.i18n import translate
from app.models import Favorite, Tender
from app.services.scoring import score_tender
from app.utils import today_dz, utcnow
from datetime import timedelta

bp = Blueprint("tenders", __name__)


@bp.route("/<int:tid>")
@login_required
def detail(tid):
    t = db.get_or_404(Tender, tid)
    if not t.is_active and not current_user.is_admin: abort(404)
    if t.locked_for(current_user):
        flash(translate("locked_msg", h=t.hours_until_unlock), "warning")
        return redirect(url_for("main.index"))
    score, reasons = score_tender(current_user, t)
    fav = Favorite.query.filter_by(user_id=current_user.id, tender_id=tid).first() is not None
    return render_template("tender_detail.html", tender=t, score=score, reasons=reasons, fav=fav)


@bp.post("/<int:tid>/favorite")
@login_required
def toggle_favorite(tid):
    t = db.get_or_404(Tender, tid)
    if t.locked_for(current_user): abort(403)
    fav = Favorite.query.filter_by(user_id=current_user.id, tender_id=tid).first()
    if fav: db.session.delete(fav)
    else: db.session.add(Favorite(user_id=current_user.id, tender_id=tid))
    db.session.commit()
    return redirect(url_for("tenders.detail", tid=tid))


@bp.get("/<int:tid>/calendar.ics")
@login_required
def ics(tid):
    t = db.get_or_404(Tender, tid)
    if t.locked_for(current_user): abort(403)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Safqa//FR", "BEGIN:VEVENT",
             f"UID:tender-{t.id}@safqa", f"DTSTAMP:{utcnow():%Y%m%dT%H%M%SZ}",
             f"DTSTART;VALUE=DATE:{t.deadline:%Y%m%d}",
             f"DTEND;VALUE=DATE:{(t.deadline + timedelta(days=1)):%Y%m%d}",
             f"SUMMARY:{t.title}", f"DESCRIPTION:{t.agency}", "END:VEVENT", "END:VCALENDAR"]
    return Response("\\r\\n".join(lines) + "\\r\\n", mimetype="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=offre-{tid}.ics"})
'''

# ============ app/modules/dashboard/__init__.py ============
FILES['app/modules/dashboard/__init__.py'] = '''# -*- coding: utf-8 -*-
from datetime import timedelta
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required
from app.constants import COMMUNE_NAMES, SECURITY_QUESTIONS, SECTORS
from app.extensions import db
from app.i18n import translate
from app.models import Favorite, Notification, SavedAlert, User
from app.utils import today_dz, utcnow

bp = Blueprint("dashboard", __name__)


def _f(n): return (request.form.get(n) or "").strip()


@bp.route("/")
@login_required
def home():
    favorites = (Favorite.query.filter_by(user_id=current_user.id)
                 .order_by(Favorite.created_at.desc()).limit(20).all())
    notifs = (Notification.query.filter(Notification.user_id == current_user.id,
                                        Notification.available_at <= utcnow())
              .order_by(Notification.created_at.desc()).limit(15).all())
    unread = sum(1 for n in notifs if not n.is_read)
    reminders = sorted((f.tender for f in favorites if 0 <= f.tender.days_left <= 7),
                       key=lambda t: t.deadline)
    return render_template("dashboard.html", user=current_user, favorites=favorites,
                           notifs=notifs, unread=unread, reminders=reminders,
                           alerts=SavedAlert.query.filter_by(user_id=current_user.id).all())


@bp.post("/profile")
@login_required
def update_profile():
    u = current_user
    u.company = _f("company")[:150] or None
    u.activity = _f("activity") if _f("activity") in SECTORS else None
    u.commune = _f("commune") if _f("commune") in COMMUNE_NAMES else None
    u.keywords = _f("keywords")[:300] or None
    u.public_profile = request.form.get("public_profile") == "on"
    db.session.commit()
    flash(translate("saved_ok"), "success")
    return redirect(url_for("dashboard.home"))


@bp.post("/security")
@login_required
def update_security():
    sq = _f("security_question"); sa = _f("security_answer")
    if sq in SECURITY_QUESTIONS and len(sa) >= 2:
        current_user.security_question = sq
        current_user.set_security_answer(sa)
        current_user.security_attempts = 0
        db.session.commit()
        flash(translate("saved_ok"), "success")
    else:
        flash(translate("err_required"), "error")
    return redirect(url_for("dashboard.home"))


@bp.post("/alerts/new")
@login_required
def alert_new():
    sector = _f("sector"); commune = _f("commune"); kws = _f("keywords")[:300]
    sector = sector if sector in SECTORS else ""
    commune = commune if commune in COMMUNE_NAMES else ""
    if not (sector or commune or kws):
        flash(translate("err_alert_empty"), "error")
    elif SavedAlert.query.filter_by(user_id=current_user.id).count() >= current_user.alert_limit:
        flash(translate("err_alert_limit", n=current_user.alert_limit), "error")
    else:
        db.session.add(SavedAlert(user_id=current_user.id,
                                  sector=sector or None, commune=commune or None, keywords=kws or None))
        db.session.commit()
        flash(translate("alert_created"), "success")
    return redirect(url_for("dashboard.home"))


@bp.post("/alerts/<int:aid>/delete")
@login_required
def alert_delete(aid):
    a = db.get_or_404(SavedAlert, aid)
    if a.user_id != current_user.id: return "", 403
    db.session.delete(a); db.session.commit()
    return redirect(url_for("dashboard.home"))


@bp.post("/notifications/read")
@login_required
def notif_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("dashboard.home"))


@bp.post("/upgrade")
@login_required
def upgrade():
    if current_user.is_premium: return redirect(url_for("dashboard.home"))
    current_user.plan = "premium"
    current_user.premium_until = today_dz() + timedelta(days=current_app.config["PREMIUM_DAYS"])
    db.session.commit()
    flash(translate("upgrade_done"), "success")
    return redirect(url_for("dashboard.home"))
'''

# ============ app/modules/admin/__init__.py ============
FILES['app/modules/admin/__init__.py'] = '''# -*- coding: utf-8 -*-
from datetime import timedelta
from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required
from app.extensions import db
from app.i18n import translate
from app.models import Ad, AuditLog, Tender, User
from app.services.scraper import upsert_tender
from app.utils import parse_budget, parse_date, today_dz

bp = Blueprint("admin", __name__)


def admin_required(fn):
    @login_required
    def inner(*a, **k):
        if not current_user.is_admin: abort(403)
        return fn(*a, **k)
    return wraps(fn)(inner)


def _f(n): return (request.form.get(n) or "").strip()


def _log(action, target_table=None, target_id=None):
    db.session.add(AuditLog(admin_id=current_user.id, action=action,
                            target_table=target_table, target_id=target_id,
                            ip_address=request.remote_addr))


@bp.route("/")
@admin_required
def panel():
    stats = {"users": User.query.count(),
             "premium": User.query.filter_by(plan="premium").count(),
             "tenders": Tender.query.count(),
             "active": Tender.query.filter_by(is_active=True).count()}
    return render_template("admin.html", stats=stats,
                           requests_=User.query.filter_by(upgrade_requested=True).all(),
                           pending_ads=Ad.query.filter_by(is_approved=False).all(),
                           tenders=Tender.query.order_by(Tender.created_at.desc()).limit(40).all(),
                           users=User.query.order_by(User.created_at.desc()).limit(50).all())


@bp.post("/tender/new")
@admin_required
def tender_new():
    try:
        t = upsert_tender({"title": _f("title"), "agency": _f("agency"),
                           "deadline": parse_date(_f("deadline")),
                           "sector": _f("sector"), "commune": _f("commune"),
                           "budget_dzd": parse_budget(_f("budget")),
                           "source_url": _f("source_url"), "description": _f("description")})
    except ValueError:
        flash(translate("err_required"), "error"); return redirect(url_for("admin.panel"))
    flash(translate("tender_added") if t else translate("tender_dup"), "success")
    return redirect(url_for("admin.panel"))


@bp.post("/tender/<int:tid>/<action>")
@admin_required
def tender_action(tid, action):
    t = db.get_or_404(Tender, tid)
    if action == "toggle": t.is_active = not t.is_active
    elif action == "delete": db.session.delete(t)
    else: abort(404)
    _log(action, "tenders", tid); db.session.commit()
    return redirect(url_for("admin.panel"))


@bp.post("/user/<int:uid>/<action>")
@admin_required
def user_action(uid, action):
    u = db.get_or_404(User, uid)
    if action == "approve":
        u.plan = "premium"; u.upgrade_requested = False
        u.premium_until = today_dz() + timedelta(days=current_app.config["PREMIUM_DAYS"])
    elif action == "reject": u.upgrade_requested = False
    elif action == "downgrade": u.plan = "free"; u.premium_until = None
    elif action == "toggle" and u.id != current_user.id: u.active = not u.active
    else: abort(404)
    _log(action, "users", uid); db.session.commit()
    flash(translate("saved_ok"), "success")
    return redirect(url_for("admin.panel"))


@bp.post("/ad/<int:aid>/toggle")
@admin_required
def ad_toggle(aid):
    a = db.get_or_404(Ad, aid)
    a.is_approved = not a.is_approved
    db.session.commit()
    return redirect(url_for("admin.panel"))
'''

# ============ app/modules/transparency/__init__.py ============
FILES['app/modules/transparency/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, render_template
from app.models import Award
from app.extensions import db

bp = Blueprint("transparency", __name__)


@bp.route("/")
def home():
    awards = Award.query.order_by(Award.created_at.desc()).limit(50).all()
    return render_template("transparency.html", awards=awards)
'''

# ============ app/modules/partners/__init__.py ============
FILES['app/modules/partners/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.i18n import translate
from app.models import PartnershipAd, Tender

bp = Blueprint("partners", __name__)


def _f(n): return (request.form.get(n) or "").strip()


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        title = _f("tender_title")[:300]; looking = _f("looking_for")[:300]
        if not title or not looking:
            flash(translate("err_required"), "error")
        else:
            db.session.add(PartnershipAd(user_id=current_user.id,
                                          tender_title=title, looking_for=looking,
                                          message=_f("message")[:1000] or None))
            db.session.commit()
            flash(translate("p_posted"), "success")
        return redirect(url_for("partners.home"))
    ads = PartnershipAd.query.filter_by(is_open=True).order_by(PartnershipAd.created_at.desc()).limit(60).all()
    return render_template("partners.html", ads=ads)


@bp.post("/<int:pid>/close")
@login_required
def close(pid):
    a = db.get_or_404(PartnershipAd, pid)
    if a.user_id != current_user.id and not current_user.is_admin: return "", 403
    a.is_open = False; db.session.commit()
    flash(translate("p_closed"), "success")
    return redirect(url_for("partners.home"))
'''

# ============ app/modules/ads/__init__.py ============
FILES['app/modules/ads/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.i18n import translate
from app.models import Ad
from app.utils import is_http_url

bp = Blueprint("ads", __name__)


def _f(n): return (request.form.get(n) or "").strip()


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        title = _f("title")[:200]; desc = _f("description")[:2000]; link = _f("link")[:500]
        if not title or not desc:
            flash(translate("err_required"), "error")
        elif link and not is_http_url(link):
            flash(translate("err_link"), "error")
        else:
            db.session.add(Ad(user_id=current_user.id, title=title, description=desc, link=link or None))
            db.session.commit()
            flash(translate("ad_submitted"), "success")
        return redirect(url_for("ads.home"))
    return render_template("ads.html",
                           my_ads=Ad.query.filter_by(user_id=current_user.id).order_by(Ad.created_at.desc()).all(),
                           approved=Ad.query.filter_by(is_approved=True).order_by(Ad.created_at.desc()).limit(30).all())
'''

# ============ app/modules/reports/__init__.py ============
FILES['app/modules/reports/__init__.py'] = '''# -*- coding: utf-8 -*-
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db, limiter
from app.i18n import translate
from app.models import Report

bp = Blueprint("reports", __name__)


def _f(n): return (request.form.get(n) or "").strip()


@bp.route("/", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def home():
    if request.method == "POST":
        cat = _f("category")[:50]; desc = _f("description")[:5000]
        if not cat or len(desc) < 20:
            flash(translate("err_required"), "error")
            return render_template("reports.html"), 400
        code = Report.new_tracking()
        db.session.add(Report(tracking_code=code, category=cat, description=desc))
        db.session.commit()
        flash(translate("report_success", code=code), "success")
        return redirect(url_for("reports.home"))
    return render_template("reports.html")
'''

# ============ TEMPLATES ============
FILES['app/templates/base.html'] = '''<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ dir }}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}{{ tr('app_name') }}{% endblock %}</title>
<script>try{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
<header class="site-header"><div class="container bar">
  <a class="brand" href="{{ url_for('main.index') }}"><span class="brand-mark">\\u0635</span>{{ tr('app_name') }}</a>
  <button class="menu-toggle" type="button" data-toggle="#nav">\\u2630</button>
  <nav id="nav" class="nav">
    <a href="{{ url_for('main.index') }}">{{ tr('nav_tenders') }}</a>
    <a href="{{ url_for('main.stats') }}">{{ tr('nav_stats') }}</a>
    <a href="{{ url_for('transparency.home') }}">{{ tr('nav_transparency') }}</a>
    <a href="{{ url_for('reports.home') }}">{{ tr('nav_reports') }}</a>
    {% if current_user.is_authenticated %}
      <a href="{{ url_for('partners.home') }}">{{ tr('nav_partners') }}</a>
      <a href="{{ url_for('ads.home') }}">{{ tr('nav_ads') }}</a>
    {% endif %}
    <a href="{{ portal_url }}" target="_blank" rel="noopener">\\U0001f3db\\ufe0f {{ tr('portal_link') }}</a>
    <span class="nav-sep"></span>
    <button class="linklike" type="button" data-theme-toggle>\\u25d0</button>
    <a class="lang" href="{{ url_for('main.set_lang', code=other_lang) }}">{{ '\\u0627\\u0644\\u0639\\u0631\\u0628\\u064a\\u0629' if lang == 'fr' else 'Fran\\u00e7ais' }}</a>
    {% if current_user.is_authenticated %}
      {% if current_user.is_admin %}<a href="{{ url_for('admin.panel') }}">{{ tr('nav_admin') }}</a>{% endif %}
      <a href="{{ url_for('dashboard.home') }}">{{ tr('nav_dashboard') }}</a>
      <form method="post" action="{{ url_for('auth.logout') }}" class="inline">{{ csrf_input() }}<button class="linklike" type="submit">{{ tr('logout') }}</button></form>
    {% else %}
      <a href="{{ url_for('auth.login') }}">{{ tr('login') }}</a>
      <a class="btn btn-accent btn-sm" href="{{ url_for('auth.register') }}">{{ tr('register') }}</a>
    {% endif %}
  </nav>
</div></header>
<main class="container">
{% with messages = get_flashed_messages(with_categories=true) %}
{% for cat, msg in messages %}<div class="flash flash-{{ cat }}">{{ msg }}</div>{% endfor %}
{% endwith %}
{% block content %}{% endblock %}
</main>
<footer class="site-footer"><div class="container">
<p>\\u00a9 {{ today.year }} {{ tr('app_name') }} \\u00b7 v{{ app_version }}</p>
</div></footer>
<script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body></html>
'''

FILES['app/templates/_macros.html'] = '''{% macro deadline_text(t) -%}
{%- if t.days_left < 0 -%}{{ tr('expired') }}
{%- elif t.days_left == 0 -%}{{ tr('last_day') }}
{%- else -%}{{ tr('days_left', n=t.days_left) }}{%- endif -%}
{%- endmacro %}

{% macro score_bar(score, reasons) -%}
<div class="score"><div class="score-label"><span>{{ tr('match') }}</span><strong>{{ score }}%</strong></div>
<div class="score-track"><span style="width:{{ score }}%"></span></div></div>
{%- endmacro %}

{% macro filter_selects(sel_sector='', sel_commune='') -%}
<select name="sector"><option value="">{{ tr('all_sectors') }}</option>
{% for k in sectors %}<option value="{{ k }}" {{ 'selected' if k == sel_sector }}>{{ sector_label(k) }}</option>{% endfor %}</select>
<select name="commune"><option value="">{{ tr('all_communes') }}</option>
{% for fr, ar in communes %}<option value="{{ fr }}" {{ 'selected' if fr == sel_commune }}>{{ commune_label(fr) }}</option>{% endfor %}</select>
{%- endmacro %}
'''

FILES['app/templates/_card.html'] = '''{% from "_macros.html" import deadline_text, score_bar with context %}
{% set t = it.tender %}
{% if it.locked %}
<article class="card card-locked">
  <div class="card-top"><span class="chip sector-{{ t.sector }}">{{ sector_label(t.sector) }}</span></div>
  <h3>\\U0001f512 {{ tr('locked_title') }}</h3>
  <p class="muted small">{{ tr('locked_hint', h=t.hours_until_unlock) }}</p>
</article>
{% else %}
<article class="card urgency-{{ t.urgency }}">
  <div class="card-top">
    <span class="chip sector-{{ t.sector }}">{{ sector_label(t.sector) }}</span>
    {% if t.is_new %}<span class="chip chip-new">{{ tr('new') }}</span>{% endif %}
    {% if t.is_demo %}<span class="chip chip-demo">{{ tr('demo') }}</span>{% endif %}
  </div>
  <h3><a href="{{ url_for('tenders.detail', tid=t.id) }}">{{ t.title }}</a></h3>
  <p class="muted">{{ t.agency }}</p>
  <ul class="facts">
    <li>\\U0001f4cd {{ commune_label(t.commune) }}</li>
    <li>\\U0001f4b0 {{ t.budget_dzd | budget }}</li>
    <li class="deadline">\\u23f3 {{ deadline_text(t) }} ({{ t.deadline | dmy }})</li>
  </ul>
  {% if it.score is not none %}{{ score_bar(it.score, it.reasons) }}{% endif %}
  <div class="card-actions">
    {% if current_user.is_authenticated %}
      <a class="btn btn-sm" href="{{ url_for('tenders.detail', tid=t.id) }}">{{ tr('view_details') }}</a>
    {% else %}
      <a class="btn btn-sm" href="{{ url_for('auth.login', next=url_for('tenders.detail', tid=t.id)) }}">{{ tr('view_details') }}</a>
    {% endif %}
  </div>
</article>
{% endif %}
'''

FILES['app/templates/index.html'] = '''{% extends "base.html" %}
{% from "_macros.html" import filter_selects with context %}
{% block content %}
<section class="hero">
  <h1>{{ tr('tagline') }}</h1><p>{{ tr('subtitle') }}</p>
  <div class="stat-row">
    <div class="stat"><strong>{{ stats.active }}</strong><span>{{ tr('stat_active') }}</span></div>
    <div class="stat"><strong>{{ stats.new }}</strong><span>{{ tr('stat_new') }}</span></div>
    <div class="stat"><strong>{{ stats.closing }}</strong><span>{{ tr('stat_closing') }}</span></div>
  </div>
</section>
<form method="get" class="filter-bar">
  <input type="search" name="q" value="{{ args.get('q','') }}" placeholder="{{ tr('search_ph') }}">
  {{ filter_selects(args.get('sector',''), args.get('commune','')) }}
  <select name="sort">
    <option value="new" {{ 'selected' if args.get('sort') != 'deadline' }}>{{ tr('sort_new') }}</option>
    <option value="deadline" {{ 'selected' if args.get('sort') == 'deadline' }}>{{ tr('sort_deadline') }}</option>
  </select>
  <button class="btn" type="submit">{{ tr('filter') }}</button>
  <a class="btn btn-ghost" href="{{ url_for('main.index') }}">{{ tr('reset') }}</a>
</form>
{% if locked_count > 0 %}
<div class="banner"><strong>{{ tr('hidden_banner', n=locked_count, h=delay_hours) }}</strong></div>
{% endif %}
<p class="muted small">{{ tr('results_count', n=pagination.total) }}</p>
<div class="grid">
{% for it in items %}{% include "_card.html" %}{% else %}<p class="empty">{{ tr('no_results') }}</p>{% endfor %}
</div>
{% if pagination.pages > 1 %}
<nav class="pager">
  {% if pagination.has_prev %}<a class="btn btn-ghost btn-sm" href="{{ page_url(pagination.prev_num) }}">\\u2039</a>{% endif %}
  <span>{{ pagination.page }}/{{ pagination.pages }}</span>
  {% if pagination.has_next %}<a class="btn btn-ghost btn-sm" href="{{ page_url(pagination.next_num) }}">\\u203a</a>{% endif %}
</nav>
{% endif %}
{% endblock %}
'''

FILES['app/templates/login.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow"><h1>{{ tr('login') }}</h1>
<form method="post" class="form">{{ csrf_input() }}
  <label>{{ tr('identifier') }}<input type="text" name="identifier" required></label>
  <label>{{ tr('password') }}<input type="password" name="password" required></label>
  <button class="btn" type="submit">{{ tr('login') }}</button>
</form>
<p class="center small"><a href="{{ url_for('auth.forgot_password') }}">{{ tr('forgot_link') }}</a></p>
<p class="center small">{{ tr('no_account') }} <a href="{{ url_for('auth.register') }}">{{ tr('register') }}</a></p>
</section>
{% endblock %}
'''

FILES['app/templates/register.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow"><h1>{{ tr('register') }}</h1>
<form method="post" class="form">{{ csrf_input() }}
  <label>{{ tr('full_name') }} *<input type="text" name="full_name" value="{{ form.get('full_name','') }}" required></label>
  <label>{{ tr('email') }} *<input type="email" name="email" value="{{ form.get('email','') }}" required></label>
  <label>{{ tr('phone') }} *<input type="tel" name="phone" value="{{ form.get('phone','') }}" placeholder="0550 12 34 56" required></label>
  <label>{{ tr('company') }}<input type="text" name="company" value="{{ form.get('company','') }}"></label>
  <div class="row">
    <label>{{ tr('activity') }}<select name="activity"><option value="">\\u2014</option>
      {% for k in sectors %}<option value="{{ k }}">{{ sector_label(k) }}</option>{% endfor %}</select></label>
    <label>{{ tr('commune_label') }}<select name="commune"><option value="">\\u2014</option>
      {% for fr, ar in communes %}<option value="{{ fr }}">{{ commune_label(fr) }}</option>{% endfor %}</select></label>
  </div>
  <label>{{ tr('password') }} *<input type="password" name="password" minlength="8" required></label>
  <label>{{ tr('confirm') }} *<input type="password" name="confirm" minlength="8" required></label>
  <label>{{ tr('security_question') }}<select name="security_question"><option value="">\\u2014</option>
    {% for k, q in security_questions.items() %}<option value="{{ k }}">{{ q[lang] }}</option>{% endfor %}</select></label>
  <label>{{ tr('security_answer') }}<input type="text" name="security_answer" maxlength="100"></label>
  <label class="check"><input type="checkbox" name="public_profile" checked> {{ tr('public_profile_opt') }}</label>
  <button class="btn btn-accent" type="submit">{{ tr('create_account') }}</button>
</form>
<p class="center small">{{ tr('have_account') }} <a href="{{ url_for('auth.login') }}">{{ tr('login') }}</a></p>
</section>
{% endblock %}
'''

FILES['app/templates/forgot_password.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow"><h1>{{ tr('forgot_title') }}</h1>
<p class="muted">{{ tr('forgot_hint') }}</p>
<form method="post" class="form">{{ csrf_input() }}
  <label>{{ tr('phone') }}<input type="tel" name="phone" required></label>
  <button class="btn" type="submit">{{ tr('send_code') }}</button>
</form>
<p class="center small"><a href="{{ url_for('auth.forgot_password_question') }}">{{ tr('reset_by_question') }} \\u2192</a></p>
<p class="center small"><a href="{{ url_for('auth.login') }}">{{ tr('back_login') }}</a></p>
</section>
{% endblock %}
'''

FILES['app/templates/reset_password_question.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow"><h1>{{ tr('reset_by_question') }}</h1>
{% set q = security_questions.get(user.security_question) %}
<p><strong>{{ tr('security_question') }}:</strong> {{ q[lang] if q else user.security_question }}</p>
<form method="post" class="form">{{ csrf_input() }}
  <label>{{ tr('security_answer') }}<input type="text" name="security_answer" required></label>
  <label>{{ tr('new_password') }}<input type="password" name="password" minlength="8" required></label>
  <label>{{ tr('confirm') }}<input type="password" name="confirm" minlength="8" required></label>
  <button class="btn" type="submit">{{ tr('validate') }}</button>
</form>
</section>
{% endblock %}
'''

FILES['app/templates/reset_password.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow"><h1>{{ tr('code_label') }}</h1>
<form method="post" class="form">{{ csrf_input() }}
  <label>{{ tr('code_label') }}<input type="text" name="code" maxlength="6" required></label>
  <label>{{ tr('new_password') }}<input type="password" name="password" minlength="8" required></label>
  <label>{{ tr('confirm') }}<input type="password" name="confirm" minlength="8" required></label>
  <button class="btn" type="submit">{{ tr('validate') }}</button>
</form>
</section>
{% endblock %}
'''

FILES['app/templates/tender_detail.html'] = '''{% extends "base.html" %}
{% from "_macros.html" import deadline_text, score_bar with context %}
{% block content %}
<article class="panel detail">
  <div class="card-top">
    <span class="chip sector-{{ tender.sector }}">{{ sector_label(tender.sector) }}</span>
    <span class="chip urgency-{{ tender.urgency }}">\\u23f3 {{ deadline_text(tender) }}</span>
  </div>
  <h1>{{ tender.title }}</h1>
  <dl class="meta">
    <div><dt>{{ tr('agency') }}</dt><dd>{{ tender.agency }}</dd></div>
    <div><dt>{{ tr('commune_label') }}</dt><dd>{{ commune_label(tender.commune) }}</dd></div>
    <div><dt>{{ tr('budget') }}</dt><dd>{{ tender.budget_dzd | budget }}</dd></div>
    <div><dt>{{ tr('deadline') }}</dt><dd>{{ tender.deadline | dmy }}</dd></div>
  </dl>
  <p class="description">{{ tender.description or tr('no_description') }}</p>
  {% if score is not none %}{{ score_bar(score, reasons) }}{% endif %}
  <div class="card-actions">
    {% if tender.source_url %}<a class="btn" href="{{ tender.source_url }}" target="_blank">{{ tr('source_link') }} \\u2197</a>{% endif %}
    <a class="btn btn-ghost" href="{{ portal_url }}" target="_blank">{{ tr('back_to_portal') }}</a>
    <form method="post" action="{{ url_for('tenders.toggle_favorite', tid=tender.id) }}" class="inline">{{ csrf_input() }}<button class="btn btn-ghost">{{ '\\u2605' if fav else '\\u2606' }} {{ tr('favorite_remove') if fav else tr('favorite_add') }}</button></form>
    <a class="btn btn-ghost" href="{{ url_for('tenders.ics', tid=tender.id) }}">\\U0001f4c5 .ics</a>
    <a class="btn btn-ghost" href="{{ url_for('main.index') }}">\\u2190 {{ tr('back') }}</a>
  </div>
</article>
{% endblock %}
'''

FILES['app/templates/dashboard.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('hello', name=user.full_name) }}</h1>
<div class="cols">
<section class="panel">
  <h2>{{ tr('plan_label') }}</h2>
  <p><span class="chip {{ 'chip-premium' if user.is_premium }}">{{ 'Premium' if user.is_premium else tr('plan_free') }}</span></p>
  {% if not user.is_premium %}
  <form method="post" action="{{ url_for('dashboard.upgrade') }}">{{ csrf_input() }}
    <button class="btn btn-accent" type="submit">{{ tr('upgrade_btn', p=premium_price) }}</button></form>
  {% endif %}
</section>
<section class="panel">
  <h2>{{ tr('notifications') }}</h2>
  {% for n in notifs %}<div class="notif {{ '' if n.is_read else 'unread' }}"><a href="{{ url_for('tenders.detail', tid=n.tender.id) }}">{{ n.tender.title }}</a></div>
  {% else %}<p class="muted small">{{ tr('no_notifications') }}</p>{% endfor %}
</section>
</div>
<section class="panel">
  <h2>{{ tr('my_profile') }}</h2>
  <form method="post" action="{{ url_for('dashboard.update_profile') }}" class="form">{{ csrf_input() }}
    <label>{{ tr('company') }}<input type="text" name="company" value="{{ user.company or '' }}"></label>
    <label>{{ tr('activity') }}<select name="activity"><option value="">\\u2014</option>
      {% for k in sectors %}<option value="{{ k }}" {{ 'selected' if user.activity == k }}>{{ sector_label(k) }}</option>{% endfor %}</select></label>
    <label>{{ tr('keywords_label') }}<input type="text" name="keywords" value="{{ user.keywords or '' }}"></label>
    <label class="check"><input type="checkbox" name="public_profile" {{ 'checked' if user.public_profile }}> {{ tr('public_profile_opt') }}</label>
    <button class="btn" type="submit">{{ tr('save') }}</button>
  </form>
</section>
<section class="panel">
  <h2>\\U0001f510 {{ tr('security_question') }}</h2>
  <form method="post" action="{{ url_for('dashboard.update_security') }}" class="form">{{ csrf_input() }}
    <label>{{ tr('security_question') }}<select name="security_question">
      {% for k, q in security_questions.items() %}<option value="{{ k }}" {{ 'selected' if user.security_question == k }}>{{ q[lang] }}</option>{% endfor %}
    </select></label>
    <label>{{ tr('security_answer') }}<input type="text" name="security_answer" required></label>
    <button class="btn" type="submit">{{ tr('save') }}</button>
  </form>
</section>
<section class="panel">
  <h2>{{ tr('my_alerts') }}</h2>
  {% for a in alerts %}<div class="notif">{{ a.sector or '-' }} {{ a.commune or '-' }} {{ a.keywords or '' }}
    <form method="post" action="{{ url_for('dashboard.alert_delete', aid=a.id) }}" class="inline">{{ csrf_input() }}<button class="linklike danger">{{ tr('delete') }}</button></form></div>
  {% else %}<p class="muted small">{{ tr('no_alerts') }}</p>{% endfor %}
  <form method="post" action="{{ url_for('dashboard.alert_new') }}" class="filter-bar">{{ csrf_input() }}
    <select name="sector"><option value="">{{ tr('all_sectors') }}</option>{% for k in sectors %}<option value="{{ k }}">{{ sector_label(k) }}</option>{% endfor %}</select>
    <select name="commune"><option value="">{{ tr('all_communes') }}</option>{% for fr, ar in communes %}<option value="{{ fr }}">{{ commune_label(fr) }}</option>{% endfor %}</select>
    <input type="text" name="keywords" placeholder="{{ tr('alert_keywords') }}">
    <button class="btn btn-sm" type="submit">{{ tr('alert_new') }}</button>
  </form>
</section>
{% endblock %}
'''

FILES['app/templates/admin.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('admin_title') }}</h1>
<div class="stat-row stat-row-light">
  <div class="stat"><strong>{{ stats.users }}</strong><span>{{ tr('a_users') }}</span></div>
  <div class="stat"><strong>{{ stats.premium }}</strong><span>Premium</span></div>
  <div class="stat"><strong>{{ stats.tenders }}</strong><span>{{ tr('a_tenders') }}</span></div>
</div>
<section class="panel"><h2>{{ tr('add_tender') }}</h2>
<form method="post" action="{{ url_for('admin.tender_new') }}" class="form">{{ csrf_input() }}
  <label>{{ tr('t_title') }} *<input type="text" name="title" required></label>
  <label>{{ tr('t_agency') }} *<input type="text" name="agency" required></label>
  <label>{{ tr('t_deadline') }} *<input type="date" name="deadline" required></label>
  <label>{{ tr('t_budget') }}<input type="text" name="budget"></label>
  <button class="btn" type="submit">{{ tr('add_tender') }}</button>
</form></section>
<section class="panel"><h2>{{ tr('a_tenders') }}</h2>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>{{ tr('t_title') }}</th><th>{{ tr('commune_label') }}</th><th></th></tr></thead>
<tbody>{% for t in tenders %}
<tr><td>{{ t.id }}</td><td>{{ t.title[:60] }}</td><td>{{ t.commune }}</td>
<td>
<form method="post" action="{{ url_for('admin.tender_action', tid=t.id, action='toggle') }}" class="inline">{{ csrf_input() }}<button class="linklike">{{ tr('activate') }}</button></form>
<form method="post" action="{{ url_for('admin.tender_action', tid=t.id, action='delete') }}" class="inline">{{ csrf_input() }}<button class="linklike danger">{{ tr('delete') }}</button></form>
</td></tr>{% endfor %}</tbody></table></div></section>
<section class="panel"><h2>{{ tr('a_users') }}</h2>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>{{ tr('full_name') }}</th><th>{{ tr('phone') }}</th><th>{{ tr('plan_label') }}</th><th></th></tr></thead>
<tbody>{% for u in users %}
<tr><td>{{ u.id }}</td><td>{{ u.full_name }}</td><td>{{ u.phone }}</td><td>{{ u.plan }}</td>
<td>{% if not u.is_admin %}
<form method="post" action="{{ url_for('admin.user_action', uid=u.id, action='approve') }}" class="inline">{{ csrf_input() }}<button class="linklike">{{ tr('approve') }}</button></form>
<form method="post" action="{{ url_for('admin.user_action', uid=u.id, action='downgrade') }}" class="inline">{{ csrf_input() }}<button class="linklike">{{ tr('downgrade') }}</button></form>
{% endif %}</td></tr>{% endfor %}</tbody></table></div></section>
{% endblock %}
'''

FILES['app/templates/transparency.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('transparency_title') }}</h1>
<p class="muted">{{ tr('transparency_intro') }}</p>
<div class="flash flash-warning">{{ tr('transparency_disclaimer') }}</div>
<section class="panel">
<h2>{{ tr('awards_list') }}</h2>
{% for a in awards %}
<div class="notif">
  <span>{{ a.tender.title[:60] if a.tender else '-' }}</span>
  <span><strong>{{ a.winner_company }}</strong> \\u2014 {{ a.amount_dzd | budget }} \\u2014 {{ tr('transparency_score') }}: {{ a.transparency_score }}</span>
</div>
{% else %}<p class="muted small">{{ tr('no_results') }}</p>{% endfor %}
</section>
{% endblock %}
'''

FILES['app/templates/partners.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('partners_title') }}</h1>
<form method="post" class="form panel">{{ csrf_input() }}
  <label>{{ tr('p_tender') }}<input type="text" name="tender_title" required></label>
  <label>{{ tr('p_looking') }}<input type="text" name="looking_for" required></label>
  <label>{{ tr('p_message') }}<textarea name="message" rows="2"></textarea></label>
  <button class="btn" type="submit">{{ tr('publish') }}</button>
</form>
<div class="grid">
{% for ad in ads %}
<article class="card">
  <h3>{{ ad.tender_title }}</h3>
  <p>{{ tr('p_looking_short') }}: {{ ad.looking_for }}</p>
  <p class="small">{{ ad.user.company or ad.user.full_name }} \\u2014 {{ ad.user.phone }}</p>
</article>
{% else %}<p class="empty">{{ tr('no_partners') }}</p>{% endfor %}
</div>
{% endblock %}
'''

FILES['app/templates/ads.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('ads_title') }}</h1>
<form method="post" class="form panel">{{ csrf_input() }}
  <label>{{ tr('ad_title') }}<input type="text" name="title" required></label>
  <label>{{ tr('ad_desc') }}<textarea name="description" required></textarea></label>
  <label>{{ tr('ad_link') }}<input type="url" name="link"></label>
  <button class="btn" type="submit">{{ tr('submit_ad') }}</button>
</form>
<h2>{{ tr('approved_ads') }}</h2>
{% for ad in approved %}
<div class="notif"><strong>{{ ad.title }}</strong> \\u2014 {{ ad.description[:80] }}</div>
{% else %}<p class="muted">{{ tr('no_ads') }}</p>{% endfor %}
{% endblock %}
'''

FILES['app/templates/reports.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('reports_title') }}</h1>
<p class="muted">{{ tr('reports_intro') }}</p>
<form method="post" class="form panel">{{ csrf_input() }}
  <label>{{ tr('report_category') }}
    <select name="category" required>
      <option value="corruption">{{ 'Corruption' if lang == 'fr' else '\\u0641\\u0633\\u0627\\u062f' }}</option>
      <option value="nepotism">{{ 'Nepotisme' if lang == 'fr' else '\\u0645\\u062d\\u0633\\u0648\\u0628\\u064a\\u0629' }}</option>
      <option value="other">{{ 'Autre' if lang == 'fr' else '\\u0623\\u062e\\u0631\\u0649' }}</option>
    </select></label>
  <label>{{ tr('report_description') }}<textarea name="description" rows="6" required minlength="20"></textarea></label>
  <button class="btn" type="submit">{{ tr('report_submit') }}</button>
</form>
{% endblock %}
'''

FILES['app/templates/stats.html'] = '''{% extends "base.html" %}
{% block content %}
<h1>{{ tr('stats_title') }}</h1>
<div class="stat-row stat-row-light">
  <div class="stat"><strong>{{ data.total }}</strong><span>{{ tr('stat_active') }}</span></div>
  <div class="stat"><strong>{{ data.new48 }}</strong><span>{{ tr('stat_new') }}</span></div>
  <div class="stat"><strong>{{ data.closing }}</strong><span>{{ tr('stat_closing') }}</span></div>
  <div class="stat"><strong>{{ data.members }}</strong><span>{{ tr('stat_members') }}</span></div>
</div>
<div class="cols">
<section class="panel"><h2>{{ tr('by_sector') }}</h2>
{% for k, n in by_sector %}<div class="bar-row"><span>{{ sector_label(k) }}</span><strong>{{ n }}</strong></div>
{% else %}<p class="muted">\\u2014</p>{% endfor %}</section>
<section class="panel"><h2>{{ tr('by_commune') }}</h2>
{% for name, n in by_commune %}<div class="bar-row"><span>{{ commune_label(name) }}</span><strong>{{ n }}</strong></div>
{% else %}<p class="muted">\\u2014</p>{% endfor %}</section>
</div>
{% endblock %}
'''

FILES['app/templates/error.html'] = '''{% extends "base.html" %}
{% block content %}
<section class="panel narrow center"><h1>{{ code }}</h1><p>{{ message }}</p>
<a class="btn" href="{{ url_for('main.index') }}">\\u2190 {{ tr('back') }}</a></section>
{% endblock %}
'''

# ============ static ============
FILES['app/static/css/style.css'] = '''*{box-sizing:border-box;margin:0;padding:0}
:root{--ink:#12263a;--muted:#5c6b7a;--bg:#f5f7f6;--card:#fff;--line:#e2e8e5;
--primary:#0e7c66;--primary-dark:#0a5c4b;--accent:#f2a900;--danger:#c0392b;
--ok-bg:#e3f5ec;--warn-bg:#fff4d6;--err-bg:#fde8e6;
--radius:14px;--shadow:0 1px 2px rgba(18,38,58,.06),0 6px 18px rgba(18,38,58,.06)}
body{font-family:"Segoe UI",Tahoma,sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;min-height:100vh;display:flex;flex-direction:column}
main{flex:1;padding:1.5rem 0 3rem}.container{width:min(1120px,100% - 2rem);margin:0 auto}
a{color:var(--primary-dark)}
h1{font-size:clamp(1.5rem,3.4vw,2.1rem);margin-bottom:.6rem}h2{font-size:1.1rem;margin-bottom:.6rem}
h3{font-size:1.02rem;margin-bottom:.35rem}
.muted{color:var(--muted)}.small{font-size:.85rem}.center{text-align:center}
.site-header{background:var(--primary);color:#fff;position:sticky;top:0;z-index:20}
.bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.7rem 0;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:.6rem;color:#fff;text-decoration:none;font-weight:700;font-size:1.15rem}
.brand-mark{display:grid;place-items:center;width:2.1rem;height:2.1rem;border-radius:10px;background:var(--accent);color:var(--ink);font-size:1.25rem}
.nav{display:flex;align-items:center;gap:.25rem;flex-wrap:wrap}
.nav a,.nav .linklike{color:#fff;text-decoration:none;padding:.4rem .7rem;border-radius:8px;font-size:.92rem;background:none;border:0;cursor:pointer}
.nav a:hover,.nav .linklike:hover{background:rgba(255,255,255,.16)}
.nav .lang{border:1px solid rgba(255,255,255,.4)}
.nav-sep{width:1px;height:1.4rem;background:rgba(255,255,255,.3);margin:0 .3rem}
.menu-toggle{display:none;background:transparent;border:1px solid rgba(255,255,255,.5);color:#fff;border-radius:8px;padding:.25rem .65rem;cursor:pointer}
@media(max-width:860px){.menu-toggle{display:block}.nav{display:none;width:100%;flex-direction:column;align-items:stretch}.nav.open{display:flex}}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.35rem;background:var(--primary);color:#fff;border:1px solid var(--primary);padding:.55rem 1.05rem;border-radius:10px;font:inherit;font-weight:600;text-decoration:none;cursor:pointer}
.btn:hover{background:var(--primary-dark)}.btn-accent{background:var(--accent);border-color:var(--accent);color:var(--ink)}
.btn-ghost{background:transparent;color:var(--primary-dark);border-color:var(--line)}
.btn-sm{padding:.3rem .7rem;font-size:.85rem}
.inline{display:inline}.linklike{background:none;border:0;font:inherit;cursor:pointer;text-decoration:underline;color:var(--primary-dark)}
.danger{color:var(--danger)!important}
.form{display:grid;gap:.9rem}.form label{display:grid;gap:.25rem;font-size:.9rem;font-weight:600}
input,select,textarea{font:inherit;padding:.55rem .7rem;border:1px solid #cdd7d3;border-radius:10px;background:#fff;color:var(--ink);width:100%}
input:focus,select:focus,textarea:focus{outline:3px solid rgba(14,124,102,.28);border-color:var(--primary)}
.check{display:flex!important;align-items:center;gap:.5rem;font-weight:400!important}.check input{width:auto}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.9rem}
.filter-bar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;background:var(--card);padding:.8rem;border-radius:var(--radius);box-shadow:var(--shadow);margin:1rem 0}
.filter-bar input[type=search],.filter-bar input[type=text]{flex:2 1 220px;width:auto}.filter-bar select{flex:1 1 160px;width:auto}
.panel{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:1.2rem;margin-bottom:1.1rem}
.panel.narrow{max-width:560px;margin:0 auto}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.1rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1rem}
.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:1.05rem;border-inline-start:5px solid var(--line);display:flex;flex-direction:column;gap:.35rem}
.card h3 a{color:var(--ink);text-decoration:none}.card h3 a:hover{color:var(--primary)}
.card-top{display:flex;gap:.35rem;flex-wrap:wrap;align-items:center}
.card-actions{display:flex;gap:.45rem;flex-wrap:wrap;align-items:center;margin-top:auto;padding-top:.5rem}
.card-locked{background:repeating-linear-gradient(135deg,#fff,#fff 12px,#f7f9f8 12px,#f7f9f8 24px);border-inline-start-color:var(--accent)}
.urgency-ok{border-inline-start-color:var(--primary)}.urgency-soon{border-inline-start-color:var(--accent)}
.urgency-urgent{border-inline-start-color:var(--danger)}.urgency-expired{opacity:.75}
.facts{list-style:none;display:grid;gap:.1rem;font-size:.9rem}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:2.5rem 0}
.pager{display:flex;gap:.8rem;justify-content:center;margin:1.4rem 0}
.chip{display:inline-block;background:#e9eeec;color:var(--ink);font-size:.74rem;font-weight:600;padding:.12rem .6rem;border-radius:999px}
.chip-new{background:#ffe3e0;color:#a02a1e}.chip-demo{background:#e5e9ff;color:#3446a8}.chip-premium{background:var(--accent);color:var(--ink)}
.sector-travaux{background:#dff1ec;color:#0a5c4b}.sector-fournitures{background:#e8e5ff;color:#4a3fb0}
.sector-services{background:#ffeccc;color:#8a5a00}.sector-etudes{background:#e1effa;color:#1c5a8c}
.score{margin:.35rem 0}.score-label{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted)}
.score-track{height:7px;background:#e6ece9;border-radius:99px;overflow:hidden}
.score-track span{display:block;height:100%;background:var(--primary)}
.hero{background:linear-gradient(135deg,var(--primary),#0b4f6c);color:#fff;padding:clamp(1.4rem,4vw,2.4rem);border-radius:20px;margin-bottom:1rem}
.hero p{max-width:62ch;opacity:.93;margin-bottom:1rem}
.stat-row{display:flex;flex-wrap:wrap;gap:.8rem;margin-bottom:1rem}
.stat{background:rgba(255,255,255,.14);border-radius:12px;padding:.6rem 1rem;min-width:130px;display:grid}
.stat strong{font-size:1.6rem;line-height:1.2}.stat span{font-size:.8rem;opacity:.9}
.stat-row-light .stat{background:var(--card);box-shadow:var(--shadow)}.stat-row-light .stat strong{color:var(--primary)}
.banner{background:var(--warn-bg);border-inline-start:5px solid var(--accent);border-radius:12px;padding:.8rem 1rem;margin-bottom:1rem}
.flash{padding:.7rem 1rem;border-radius:10px;margin-bottom:.8rem;font-size:.92rem}
.flash-success{background:var(--ok-bg)}.flash-error{background:var(--err-bg)}.flash-warning{background:var(--warn-bg)}
.detail h1{margin:.6rem 0}.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.8rem;margin:1rem 0}
.meta dt{font-size:.78rem;color:var(--muted)}.meta dd{font-weight:600}
.description{background:#f6f9f8;border-radius:12px;padding:1rem;margin:1rem 0;white-space:pre-line}
.notif{display:flex;justify-content:space-between;gap:.8rem;align-items:center;padding:.5rem 0;border-bottom:1px solid var(--line);flex-wrap:wrap}
.notif.unread{font-weight:700}
.bar-row{display:grid;grid-template-columns:9rem 1fr 2.2rem;gap:.6rem;align-items:center;margin:.35rem 0;font-size:.9rem}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{padding:.55rem;text-align:start;border-bottom:1px solid var(--line)}th{background:#eef3f1}
.site-footer{background:#0f2233;color:#b9c6d2;padding:1.4rem 0;font-size:.85rem;text-align:center}
:root[data-theme="dark"]{--ink:#e8eef2;--muted:#9db0bf;--bg:#0f1a24;--card:#16232f;--line:#263646}
:root[data-theme="dark"] input,:root[data-theme="dark"] select,:root[data-theme="dark"] textarea{background:#0f1a24;border-color:#33475a}
:root[data-theme="dark"] a{color:#6fd3b9}
'''

FILES['app/static/js/app.js'] = '''document.addEventListener("click",function(e){
var t=e.target.closest("[data-toggle]");
if(t){var el=document.querySelector(t.getAttribute("data-toggle"));if(el)el.classList.toggle("open")}
if(e.target.closest("[data-theme-toggle]")){var r=document.documentElement;var d=r.getAttribute("data-theme")==="dark";r.setAttribute("data-theme",d?"light":"dark");try{localStorage.setItem("theme",d?"light":"dark")}catch(err){}}
});
'''

# ============ README ============
FILES['README.md'] = '''# Safqa Belabbès v5 — Architecture modulaire

## Installation
```bash
python install_safqa_v5.py
pip install -r requirements.txt
cp .env.example .env
python run.py
