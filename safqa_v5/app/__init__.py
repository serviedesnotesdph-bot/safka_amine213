# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import Markup

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    plan = db.Column(db.String(20), default="free", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    security_question = db.Column(db.String(40))
    security_answer_hash = db.Column(db.String(255))
    security_attempts = db.Column(db.Integer, default=0, nullable=False)
    email_notifications = db.Column(db.Boolean, default=True, nullable=False)
    sms_notifications = db.Column(db.Boolean, default=False, nullable=False)
    company = db.Column(db.String(150))
    sector_activity = db.Column(db.String(30))
    commune = db.Column(db.String(100))
    favorite_sectors = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        return check_password_hash(self.password_hash, p)

    def set_security_answer(self, a):
        if a:
            self.security_answer_hash = generate_password_hash(a.lower().strip())

    def check_security_answer(self, a):
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, (a or "").lower().strip())

    @property
    def favorite_sector_list(self):
        if not self.favorite_sectors:
            return []
        return [s.strip() for s in self.favorite_sectors.split(",") if s.strip()]

    def wants_sector(self, sector):
        favs = self.favorite_sector_list
        if not favs:
            return True
        return sector in favs

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_premium(self):
        """True si l'utilisateur est admin OU a un plan premium actif."""
        if self.role == "admin":
            return True
        return self.plan == "premium"


class Tender(db.Model):
    __tablename__ = "tenders"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    agency = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.String(50), nullable=False)
    sector = db.Column(db.String(30), default="services")
    commune = db.Column(db.String(100), default="Toute la wilaya")
    description = db.Column(db.Text)
    budget_dzd = db.Column(db.BigInteger)
    source_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "tender_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tender = db.relationship("Tender")


class TenderFollow(db.Model):
    __tablename__ = "tender_follows"
    __table_args__ = (db.UniqueConstraint("user_id", "tender_id", name="uq_follow"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="a_etudier", nullable=False)
    notes = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tender = db.relationship("Tender")


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"
    __table_args__ = (db.UniqueConstraint("user_id", "tender_id", "item_key", name="uq_checklist"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False, index=True)
    item_key = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DeadlineReminderLog(db.Model):
    __tablename__ = "deadline_reminder_logs"
    __table_args__ = (db.UniqueConstraint("user_id", "tender_id", "kind", name="uq_reminder"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SavedAlert(db.Model):
    __tablename__ = "saved_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sector = db.Column(db.String(30))
    commune = db.Column(db.String(100))
    keywords = db.Column(db.String(300))
    email_notifications = db.Column(db.Boolean, default=True, nullable=False)
    sms_notifications = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tender = db.relationship("Tender")


class PremiumRequest(db.Model):
    __tablename__ = "premium_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    method = db.Column(db.String(20), default="manual", nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    amount_dzd = db.Column(db.Integer, default=1500)
    receipt_path = db.Column(db.String(255))
    chargily_checkout_id = db.Column(db.String(100))
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    user = db.relationship("User")


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(30))
    target_id = db.Column(db.Integer)
    details = db.Column(db.String(500))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin = db.relationship("User")


class PartnershipAd(db.Model):
    __tablename__ = "partnership_ads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=True)
    tender_title = db.Column(db.String(300), nullable=False)
    looking_for = db.Column(db.String(300), nullable=False)
    sector_wanted = db.Column(db.String(30))
    commune_wanted = db.Column(db.String(100))
    message = db.Column(db.Text)
    contact_phone = db.Column(db.String(20))
    is_open = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")
    tender = db.relationship("Tender")


class Ad(db.Model):
    __tablename__ = "ads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    company_name = db.Column(db.String(150))
    contact_phone = db.Column(db.String(20))
    formula = db.Column(db.String(20), default="basic")
    duration_days = db.Column(db.Integer, default=7)
    price_dzd = db.Column(db.Integer, default=2000)
    payment_status = db.Column(db.String(30), default="awaiting_payment", nullable=False)
    payment_method = db.Column(db.String(20))
    receipt_path = db.Column(db.String(255))
    chargily_checkout_id = db.Column(db.String(100))
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    views = db.Column(db.Integer, default=0, nullable=False)
    clicks = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")

    @property
    def is_currently_active(self):
        if not self.is_approved or not self.is_active:
            return False
        now = datetime.utcnow()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    @property
    def ctr(self):
        if not self.views or self.views == 0:
            return 0
        return round(100 * self.clicks / self.views, 1)


class Professional(db.Model):
    __tablename__ = "professionals"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    business_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    services = db.Column(db.Text)
    phone = db.Column(db.String(20), nullable=False)
    whatsapp = db.Column(db.String(20))
    email_public = db.Column(db.String(150))
    address = db.Column(db.String(300))
    commune = db.Column(db.String(100), index=True)
    photo_url = db.Column(db.String(500))
    gallery = db.Column(db.Text)
    years_experience = db.Column(db.Integer)
    payment_status = db.Column(db.String(30), default="awaiting_payment", nullable=False)
    payment_method = db.Column(db.String(20))
    receipt_path = db.Column(db.String(255))
    price_dzd = db.Column(db.Integer, default=3000)
    duration_days = db.Column(db.Integer, default=180)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    views = db.Column(db.Integer, default=0, nullable=False)
    phone_clicks = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User")

    @property
    def is_published(self):
        if not self.is_approved or not self.is_active:
            return False
        now = datetime.utcnow()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    @property
    def gallery_list(self):
        if not self.gallery:
            return []
        return [g.strip() for g in self.gallery.split(",") if g.strip()]


class ChatConversation(db.Model):
    __tablename__ = "chat_conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    tender_id = db.Column(db.Integer, db.ForeignKey("tenders.id"), nullable=True)
    conversation_type = db.Column(db.String(30), default="general")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")
    tender = db.relationship("Tender")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("chat_conversations.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


AD_FORMULAS = {
    "basic": {"label": "7 jours", "price": 2000, "days": 7, "featured": False},
    "premium": {"label": "1 mois", "price": 6000, "days": 30, "featured": False},
    "featured": {"label": "1 mois à la une", "price": 12000, "days": 30, "featured": True},
}

FOLLOW_STATUSES = {
    "a_etudier": {"label": "À étudier", "icon": "🔍", "color": "#f2a900"},
    "dossier_en_cours": {"label": "Dossier en cours", "icon": "📝", "color": "#0e7c66"},
    "depose": {"label": "Déposé", "icon": "📤", "color": "#1c5a8c"},
    "gagne": {"label": "Gagné", "icon": "🏆", "color": "#28a745"},
    "perdu": {"label": "Perdu", "icon": "❌", "color": "#c0392b"},
}

CHECKLIST_ITEMS = [
    ("declaration_souscrire", "Déclaration à souscrire", "Déclaration à souscrire"),
    ("declaration_probite", "Déclaration de probité", "Déclaration de probité"),
    ("statuts", "Statuts de l'entreprise", "Statuts de l'entreprise"),
    ("registre_commerce", "Extrait du registre de commerce", "Registre de commerce"),
    ("cnas_casnos", "Attestation CNAS / CASNOS", "Attestation CNAS/CASNOS"),
    ("role_apure", "Extrait de rôle apuré", "Rôle apuré (fiscal)"),
    ("casier", "Casier judiciaire", "Casier judiciaire"),
    ("references", "Références professionnelles", "Références"),
    ("moyens", "Moyens humains et matériels", "Moyens humains/matériels"),
    ("offre_technique", "Offre technique", "Offre technique"),
    ("offre_financiere", "Offre financière", "Offre financière"),
    ("cahier_charges", "Cahier des charges signé", "Cahier des charges signé"),
]

SECURITY_QUESTIONS = {
    "mother_name": "Nom de jeune fille de votre mere",
    "birth_city": "Ville de naissance",
    "first_school": "Nom de votre premiere ecole",
    "favorite_teacher": "Nom de votre professeur prefere",
}


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///safqa.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_FROM"] = os.getenv("MAIL_FROM", "noreply@safqa-belabbes.dz")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "routes.login"

    app.jinja_env.globals["csrf_input"] = lambda: Markup(
        f'<input type="hidden" name="csrf_token" value="{generate_csrf()}">')

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    from app.constants import SECTORS, COMMUNES, FAVORITE_SECTORS, PROFESSIONAL_CATEGORIES

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return {
            "security_questions": SECURITY_QUESTIONS,
            "sectors": SECTORS,
            "favorite_sectors": FAVORITE_SECTORS,
            "communes": COMMUNES,
            "professional_categories": PROFESSIONAL_CATEGORIES,
            "ad_formulas": AD_FORMULAS,
            "follow_statuses": FOLLOW_STATUSES,
            "checklist_items": CHECKLIST_ITEMS,
            "unread_notif": unread,
            "today_str": datetime.utcnow().strftime("%Y-%m-%d"),
        }

    from app.routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

        if not User.query.filter_by(role="admin").first():
            email = os.getenv("ADMIN_EMAIL", "admin@safqa.dz")
            password = os.getenv("ADMIN_PASSWORD", "admin123456")
            admin = User(email=email, full_name="Administrateur",
                         role="admin", plan="premium", phone="0500000000")
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"\n[OK] Admin: {email} / {password}\n")

        if Tender.query.count() == 0:
            now = datetime.utcnow()
            demo = [
                ("Travaux route Sidi Bel Abbes - Telagh", "Direction des TP",
                 "2026-12-25", "travaux", "Telagh", 45000000, 120),
                ("Materiel informatique - Universite", "Universite Djillali Liabes",
                 "2026-12-15", "fournitures", "Sidi Bel Abbes", 8500000, 96),
                ("Services nettoyage - CHU", "CHU Abdelkader",
                 "2027-01-10", "services", "Sidi Bel Abbes", 12000000, 72),
                ("Reseau assainissement Tessala", "APC de Tessala",
                 "2027-01-20", "travaux", "Tessala", 18750000, 30),
                ("Etude marche couvert Ben Badis", "APC de Ben Badis",
                 "2027-01-15", "etudes", "Ben Badis", 3400000, 6),
                ("Travaux ecole Sfisef phase 2", "Direction Equipements",
                 "2027-02-01", "travaux", "Sfisef", 28000000, 2),
            ]
            for t in demo:
                db.session.add(Tender(
                    title=t[0], agency=t[1], deadline=t[2],
                    sector=t[3], commune=t[4], budget_dzd=t[5],
                    created_at=now - timedelta(hours=t[6])
                ))
            db.session.commit()
            print(f"[OK] {len(demo)} offres de demo ajoutees\n")

    import click

    @app.cli.command("send-deadline-reminders")
    def send_deadline_reminders_cmd():
        from app.services.deadline_reminder import send_all_reminders
        count = send_all_reminders()
        click.echo(f"{count} rappel(s) envoye(s)")

    return app