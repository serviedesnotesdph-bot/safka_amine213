# -*- coding: utf-8 -*-
"""Service d'envoi de notifications : email + SMS + matching alertes."""
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from app import db, SavedAlert, User, Notification

logger = logging.getLogger(__name__)


# ============================================================
# EMAIL
# ============================================================
def send_email(to_email, subject, body_html):
    """Envoie un email. Mode démo si SMTP non configuré (log console)."""
    cfg = current_app.config
    if not cfg["MAIL_SERVER"] or not cfg["MAIL_USERNAME"]:
        logger.info(f"[DEMO EMAIL] To: {to_email} | Subject: {subject}")
        logger.info(f"[DEMO EMAIL] Body: {body_html[:200]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        context = ssl.create_default_context()
        if cfg["MAIL_USE_TLS"]:
            with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as server:
                server.starttls(context=context)
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], context=context) as server:
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"[EMAIL ERROR] {e}")
        return False


# ============================================================
# SMS
# ============================================================
def send_sms(to_phone, message):
    """Envoie un SMS. Mode démo si webhook non configuré (log console)."""
    cfg = current_app.config
    if not cfg["SMS_PROVIDER_URL"]:
        logger.info(f"[DEMO SMS] To: {to_phone} | Message: {message[:160]}")
        return True

    try:
        import requests
        headers = {"Content-Type": "application/json"}
        if cfg["SMS_PROVIDER_TOKEN"]:
            headers["Authorization"] = f"Bearer {cfg['SMS_PROVIDER_TOKEN']}"
        r = requests.post(
            cfg["SMS_PROVIDER_URL"],
            json={"to": to_phone, "message": message[:160]},
            headers=headers,
            timeout=10,
        )
        return r.status_code < 400
    except Exception as e:
        logger.error(f"[SMS ERROR] {e}")
        return False


# ============================================================
# MATCHING ALERTES
# ============================================================
def alert_matches(alert, tender):
    """Vérifie si une offre correspond à une alerte."""
    if alert.sector and alert.sector != tender.sector:
        return False
    if alert.commune and alert.commune != "Toute la wilaya":
        if tender.commune not in (alert.commune, "Toute la wilaya"):
            return False
    if alert.keywords:
        kws = [k.strip().lower() for k in alert.keywords.split(",") if k.strip()]
        text = f"{tender.title} {tender.agency} {tender.description or ''}".lower()
        if not any(k in text for k in kws):
            return False
    return True


# ============================================================
# DISPATCH — envoi pour nouvelle offre
# ============================================================


    
        

       


       

       

    def dispatch_new_tender(tender):
    """Délègue à la fonction locale de routes.py."""
    from app.routes import _generate_notifications
    return _generate_notifications(tender)


def _send_tender_email(user, tender):
    subject = f"Nouvel appel d'offres : {tender.title[:80]}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8e5; border-radius: 10px; overflow: hidden;">
            <div style="background: #0e7c66; color: white; padding: 1rem; text-align: center;">
                <h2 style="margin: 0;">Safqa Belabbès</h2>
                <p style="margin: 0.2rem 0 0; font-size: 0.9rem;">Veille des marchés publics</p>
            </div>
            <div style="padding: 1.5rem;">
                <h3 style="color: #0e7c66;">Nouvelle offre correspondant à vos critères</h3>
                <h2 style="margin: 1rem 0 0.5rem;">{tender.title}</h2>
                <p><strong>Organisme :</strong> {tender.agency}</p>
                <p><strong>Secteur :</strong> {tender.sector}</p>
                <p><strong>Commune :</strong> {tender.commune}</p>
                <p><strong>Date limite :</strong> {tender.deadline}</p>
                {f'<p><strong>Budget :</strong> {tender.budget_dzd:,} DA</p>' if tender.budget_dzd else ''}
                <div style="margin-top: 1.5rem;">
                    <a href="{current_app.config.get('PUBLIC_BASE_URL', 'http://localhost:5000')}/tenders/{tender.id}"
                       style="background: #0e7c66; color: white; padding: 0.7rem 1.5rem; border-radius: 6px; text-decoration: none;">
                        Voir le détail
                    </a>
                </div>
            </div>
            <div style="background: #f5f7f6; padding: 0.8rem; text-align: center; font-size: 0.8rem; color: #666;">
                Vous recevez cet email car vous avez une alerte active sur Safqa Belabbès.
            </div>
        </div>
    </body>
    </html>
    """
    send_email(user.email, subject, body)


def _send_tender_sms(user, tender):
    msg = f"Safqa: {tender.title[:100]} - Limite {tender.deadline}. Plus d'infos sur votre espace."
    send_sms(user.phone, msg)