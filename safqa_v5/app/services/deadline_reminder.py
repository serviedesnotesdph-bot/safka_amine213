# -*- coding: utf-8 -*-
"""Rappels d'échéance J-7, J-3, J-1 pour les marchés suivis."""
import logging
from datetime import datetime, timedelta
from app import db, Tender, TenderFollow, DeadlineReminderLog, User
from app.services.notifier import send_email

logger = logging.getLogger(__name__)


def _parse_deadline(deadline_str):
    """Parse une date 'YYYY-MM-DD' en datetime. Retourne None si invalide."""
    try:
        return datetime.strptime(deadline_str.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def _already_sent(user_id, tender_id, kind):
    """Vérifie si un rappel a déjà été envoyé."""
    return DeadlineReminderLog.query.filter_by(
        user_id=user_id, tender_id=tender_id, kind=kind
    ).first() is not None


def _mark_sent(user_id, tender_id, kind):
    """Enregistre l'envoi d'un rappel."""
    db.session.add(DeadlineReminderLog(
        user_id=user_id, tender_id=tender_id, kind=kind
    ))


def _send_reminder_email(user, tender, days_left, kind):
    """Envoie l'email de rappel."""
    if not user.email_notifications:
        return False

    if days_left <= 1:
        urgency = "⚠️ DERNIER JOUR"
        color = "#c0392b"
        intro = "C'est le dernier jour pour déposer votre dossier !"
    elif days_left <= 3:
        urgency = "⏰ Plus que 3 jours"
        color = "#f2a900"
        intro = "Il ne vous reste que 3 jours pour finaliser votre dossier."
    else:
        urgency = "📅 Rappel : 7 jours restants"
        color = "#0e7c66"
        intro = "Il vous reste 7 jours pour préparer votre dossier."

    subject = f"{urgency} - {tender.title[:60]}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f5f7f6; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden;">
        <div style="background: {color}; color: white; padding: 1.5rem; text-align: center;">
          <h1 style="margin: 0; font-size: 1.3rem;">{urgency}</h1>
          <p style="margin: 0.5rem 0 0; opacity: 0.9;">{intro}</p>
        </div>
        <div style="padding: 2rem;">
          <h2 style="color: #12263a; margin-top: 0;">{tender.title}</h2>
          <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
            <tr><td style="padding: 0.4rem 0; color: #666;">Organisme</td><td><strong>{tender.agency}</strong></td></tr>
            <tr><td style="padding: 0.4rem 0; color: #666;">Secteur</td><td><strong>{tender.sector}</strong></td></tr>
            <tr><td style="padding: 0.4rem 0; color: #666;">Commune</td><td><strong>{tender.commune}</strong></td></tr>
            <tr><td style="padding: 0.4rem 0; color: #666;">Date limite</td><td><strong style="color: {color};">{tender.deadline}</strong></td></tr>
          </table>
          <div style="text-align: center; margin-top: 2rem;">
            <a href="http://localhost:5000/tenders/{tender.id}"
               style="background: {color}; color: white; padding: 0.8rem 2rem; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600;">
              Voir le détail
            </a>
          </div>
        </div>
        <div style="background: #f5f7f6; padding: 1rem; text-align: center; font-size: 0.8rem; color: #666;">
          Vous recevez ce rappel car vous suivez ce marché sur Safqa Belabbès.
        </div>
      </div>
    </body>
    </html>
    """
    return send_email(user.email, subject, body)


def send_all_reminders():
    """Parcourt tous les marchés suivis et envoie les rappels nécessaires."""
    now = datetime.utcnow()
    count = 0

    follows = TenderFollow.query.all()

    for follow in follows:
        tender = db.session.get(Tender, follow.tender_id)
        user = db.session.get(User, follow.user_id)
        if not tender or not user or not user.active:
            continue

        # Skip si le suivi est terminé
        if follow.status in ("gagne", "perdu"):
            continue

        deadline_dt = _parse_deadline(tender.deadline)
        if not deadline_dt:
            continue

        # Calculer les jours restants (basé sur la date, pas l'heure)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_left = (deadline_dt - today).days

        # Envoyer le rappel approprié
        kind = None
        if days_left == 7:
            kind = "j7"
        elif days_left == 3:
            kind = "j3"
        elif days_left == 1 or days_left == 0:
            kind = "j1"

        if not kind:
            continue

        if _already_sent(follow.user_id, follow.tender_id, kind):
            continue

        if _send_reminder_email(user, tender, days_left, kind):
            _mark_sent(follow.user_id, follow.tender_id, kind)
            count += 1
            logger.info(f"[REMINDER {kind}] {user.email} -> {tender.title[:50]} (J-{days_left})")

    db.session.commit()
    return count