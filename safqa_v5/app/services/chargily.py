# -*- coding: utf-8 -*-
"""Service Chargily Pay — paiement en ligne (mode test/sandbox ou live)."""
import logging
import os
import requests

logger = logging.getLogger(__name__)


def is_configured():
    """Retourne True si la clé secrète Chargily est configurée."""
    return bool(os.getenv("CHARGILY_SECRET_KEY", "").strip())


def _base_url():
    mode = os.getenv("CHARGILY_MODE", "test").lower()
    return "https://pay.chargily.net/test/api/v2" if mode == "test" else "https://pay.chargily.net/api/v2"


def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('CHARGILY_SECRET_KEY', '')}",
        "Content-Type": "application/json",
    }


def create_checkout(amount_dzd, success_url, failure_url, metadata=None):
    """
    Crée un checkout Chargily.
    Retourne dict {"ok": bool, "checkout_url": str, "checkout_id": str, "error": str}
    """
    if not is_configured():
        return {"ok": False, "error": "Chargily non configuré (CHARGILY_SECRET_KEY manquante)"}

    payload = {
        "amount": int(amount_dzd),
        "currency": "dzd",
        "success_url": success_url,
        "failure_url": failure_url,
        "payment_method": "edahabia",  # edahabia ou cib
        "locale": "fr",
        "description": "Abonnement Premium Safqa Belabbès (30 jours)",
        "metadata": metadata or [],
    }

    try:
        r = requests.post(
            f"{_base_url()}/checkouts",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        if r.status_code not in (200, 201):
            logger.error(f"[CHARGILY CREATE] {r.status_code} {r.text[:300]}")
            return {"ok": False, "error": f"Erreur Chargily ({r.status_code})"}

        data = r.json()
        return {
            "ok": True,
            "checkout_url": data.get("checkout_url"),
            "checkout_id": data.get("id"),
        }
    except requests.RequestException as e:
        logger.error(f"[CHARGILY CREATE] Exception: {e}")
        return {"ok": False, "error": "Chargily injoignable"}


def get_checkout_status(checkout_id):
    """
    Vérifie le statut d'un checkout auprès de Chargily.
    Retourne dict {"ok": bool, "paid": bool, "status": str, "error": str}
    """
    if not is_configured():
        return {"ok": False, "error": "Chargily non configuré"}

    try:
        r = requests.get(
            f"{_base_url()}/checkouts/{checkout_id}",
            headers=_headers(),
            timeout=15,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"Erreur statut ({r.status_code})"}

        data = r.json()
        status = data.get("status", "unknown")  # paid | pending | failed | expired
        return {
            "ok": True,
            "paid": status == "paid",
            "status": status,
            "amount": data.get("amount"),
        }
    except requests.RequestException as e:
        logger.error(f"[CHARGILY GET] Exception: {e}")
        return {"ok": False, "error": "Chargily injoignable"}