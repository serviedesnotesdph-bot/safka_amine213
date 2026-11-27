# -*- coding: utf-8 -*-
"""Assistant IA simulé — analyse de cahiers des charges et questions de services."""
import re
from datetime import datetime


# ============================================================
# ANALYSE DE CAHIER DES CHARGES
# ============================================================
def analyze_tender_text(text):
    """
    Analyse un texte de cahier des charges et extrait les informations clés.
    Retourne un dictionnaire avec :
    - summary : résumé structuré (str)
    - dates : liste des dates détectées
    - amounts : liste des montants détectés
    - requirements : liste des exigences détectées
    - risks : liste des risques/points d'attention
    - keywords : mots-clés importants
    - duration : durée estimée
    """
    if not text or len(text.strip()) < 20:
        return None

    text_clean = text.strip()
    text_lower = text_clean.lower()

    # ============ Détection des dates ============
    date_patterns = [
        r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b",
        r"\b(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b",
    ]
    dates = []
    for pattern in date_patterns:
        for match in re.findall(pattern, text_lower):
            if isinstance(match, tuple):
                dates.append(" ".join(match))
            else:
                dates.append(match)

    # ============ Détection des montants ============
    amount_patterns = [
        r"(\d{1,3}(?:[\s,\.]\d{3})*(?:[\s,\.]\d{2})?)\s*(?:da|dzd|dinars?|دج)",
        r"(?:montant|budget|estimation)[^\d]{0,30}(\d{1,3}(?:[\s,\.]\d{3})+)",
        r"(\d+[\.,]\d+)\s*(?:million|m)(?:\s*(?:da|dzd|dinars?))?",
    ]
    amounts = []
    for pattern in amount_patterns:
        for match in re.findall(pattern, text_lower):
            if match.strip():
                amounts.append(match.strip())

    # ============ Détection des exigences ============
    requirement_keywords = {
        "références": ["référence", "reference", "expérience", "experience", "similaire"],
        "caution": ["caution", "garantie", "soumission", "bonne exécution", "bonne execution"],
        "qualification": ["qualification", "agrément", "agrement", "certification", "label"],
        "délai": ["délai", "delai", "jours", "semaines", "mois", "durée", "duree"],
        "documents": ["registre de commerce", "cnas", "casnos", "attestation", "casier"],
        "moyens": ["moyens humains", "personnel", "matériel", "materiel", "équipement", "equipement"],
    }
    requirements = []
    for req_type, keywords in requirement_keywords.items():
        if any(kw in text_lower for kw in keywords):
            requirements.append(req_type)

    # ============ Détection des risques ============
    risks = []
    if "urgent" in text_lower or "délai court" in text_lower or "delai court" in text_lower:
        risks.append("⚠️ Délai potentiellement court")
    if any(kw in text_lower for kw in ["pénalité", "penalite", "retard"]):
        risks.append("💰 Pénalités de retard mentionnées")
    if any(kw in text_lower for kw in ["caution", "garantie"]):
        risks.append("🏦 Caution financière exigée")
    if len(requirements) > 3:
        risks.append("📋 Nombreuses exigences — dossier complexe")

    # ============ Extraction des mots-clés ============
    stop_words = {
        "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "pour", "avec",
        "sur", "dans", "par", "au", "aux", "ce", "cette", "ces", "est", "sont", "être",
        "etre", "avoir", "fait", "faire", "dont", "que", "qui", "quoi", "dont",
    }
    words = re.findall(r"\b[a-zàâçéèêëîïôûùüÿñæœ]{4,}\b", text_lower)
    word_freq = {}
    for w in words:
        if w not in stop_words:
            word_freq[w] = word_freq.get(w, 0) + 1
    keywords = sorted(word_freq, key=lambda k: -word_freq[k])[:10]

    # ============ Détection de la durée ============
    duration_match = re.search(r"(\d+)\s*(mois|jours|semaines)", text_lower)
    duration = duration_match.group(0) if duration_match else "Non spécifiée"

    # ============ Construction du résumé ============
    summary_parts = []
    summary_parts.append("📋 **RÉSUMÉ DU CAHIER DES CHARGES**\n")

    summary_parts.append(f"📊 **Type de document** : Cahier des charges")
    summary_parts.append(f"📏 **Longueur** : {len(text_clean)} caractères")

    if dates:
        summary_parts.append(f"\n📅 **Dates détectées** : {', '.join(dates[:3])}")
    if amounts:
        summary_parts.append(f"💰 **Montants détectés** : {', '.join(amounts[:3])}")
    if duration != "Non spécifiée":
        summary_parts.append(f"⏱️ **Durée** : {duration}")

    if requirements:
        req_labels = {
            "références": "Références professionnelles exigées",
            "caution": "Caution financière à fournir",
            "qualification": "Qualifications / certifications requises",
            "délai": "Délais à respecter",
            "documents": "Documents administratifs à fournir",
            "moyens": "Moyens humains et matériels requis",
        }
        summary_parts.append("\n✅ **Exigences identifiées :**")
        for r in requirements:
            summary_parts.append(f"   • {req_labels.get(r, r)}")

    if risks:
        summary_parts.append("\n⚠️ **Points d'attention :**")
        for r in risks:
            summary_parts.append(f"   • {r}")

    if keywords:
        summary_parts.append(f"\n🔍 **Mots-clés importants** : {', '.join(keywords[:5])}")

    summary_parts.append("\n💡 **Conseil** : Vérifiez toujours le document original pour les détails juridiques et les pièces exactes à fournir.")

    return {
        "summary": "\n".join(summary_parts),
        "dates": dates,
        "amounts": amounts,
        "requirements": requirements,
        "risks": risks,
        "keywords": keywords,
        "duration": duration,
    }


# ============================================================
# RÉPONSES AUX QUESTIONS DE SERVICES
# ============================================================
SERVICE_RESPONSES = {
    "prix": (
        "💰 **Nos tarifs :**\n\n"
        "• **Premium** : 1 500 DA/mois\n"
        "• **Veille personnalisée** : 5 000 DA/mois\n"
        "• **Constitution de dossier** : 8 000 DA\n"
        "• **Revue avant dépôt** : 3 000 DA\n"
        "• **Publicité** : 2 000 à 12 000 DA\n"
        "• **Annuaire professionnel** : 3 000 DA pour 6 mois\n\n"
        "💡 Tous les services sont disponibles par virement CCP."
    ),
    "premium": (
        "💎 **Premium — 1 500 DA/mois**\n\n"
        "Avantages :\n"
        "• Accès immédiat aux nouvelles offres (< 48h)\n"
        "• Alertes illimitées\n"
        "• Notifications SMS et WhatsApp\n"
        "• Support prioritaire\n\n"
        "Pour souscrire : cliquez sur **Passer Premium** dans votre dashboard."
    ),
    "dossier": (
        "📋 **Constitution de dossier — 8 000 DA**\n\n"
        "Nous vous accompagnons pour préparer :\n"
        "• Déclaration à souscrire\n"
        "• Déclaration de probité\n"
        "• Documents administratifs (registre, CNAS, casier...)\n"
        "• Offre technique et financière\n"
        "• Cahier des charges signé\n\n"
        "📞 Contactez-nous pour plus d'informations."
    ),
    "annuaire": (
        "📇 **Annuaire professionnel — 3 000 DA pour 6 mois**\n\n"
        "Fonctionnalités :\n"
        "• Profil visible dans l'annuaire\n"
        "• Recherche par catégorie (électricien, plombier, BTP...)\n"
        "• Photos de vos travaux\n"
        "• Boutons d'appel direct + WhatsApp\n"
        "• Statistiques (vues, clics téléphone)\n\n"
        "Pour vous inscrire : allez dans **Mon annuaire** → **Inscrire mon entreprise**."
    ),
    "alerte": (
        "🔔 **Alertes personnalisées**\n\n"
        "Créez des alertes selon :\n"
        "• Un secteur (Travaux, Fournitures, Services, Études)\n"
        "• Une commune\n"
        "• Des mots-clés (ex: route, électricité, école...)\n\n"
        "Recevez un email/SMS dès qu'un marché correspond.\n\n"
        "Allez dans **Mes alertes** pour créer votre première alerte."
    ),
    "paiement": (
        "💳 **Méthodes de paiement acceptées**\n\n"
        "1. **Virement CCP** (recommandé)\n"
        "   CCP : 1234567 clé 89\n"
        "   Nom : Safqa Belabbès\n\n"
        "2. **Paiement en ligne Chargily** (bientôt disponible)\n\n"
        "Après paiement, envoyez la photo du reçu depuis votre dashboard."
    ),
}


def answer_service_question(question):
    """Répond à une question sur les services proposés."""
    q = question.lower().strip()

    # Détection de l'intention
    if any(kw in q for kw in ["prix", "tarif", "combien", "coût", "cout", "cher"]):
        return SERVICE_RESPONSES["prix"]
    if any(kw in q for kw in ["premium", "abonnement", "abonner"]):
        return SERVICE_RESPONSES["premium"]
    if any(kw in q for kw in ["dossier", "constitution", "préparer", "preparer"]):
        return SERVICE_RESPONSES["dossier"]
    if any(kw in q for kw in ["annuaire", "professionnel", "inscription", "inscrire"]):
        return SERVICE_RESPONSES["annuaire"]
    if any(kw in q for kw in ["alerte", "notification", "prévenir", "prevenir", "avertir"]):
        return SERVICE_RESPONSES["alerte"]
    if any(kw in q for kw in ["paiement", "payer", "ccp", "virement", "chargily"]):
        return SERVICE_RESPONSES["paiement"]

    # Réponse par défaut
    return (
        "🤖 Je suis votre **assistant Safqa Belabbès**.\n\n"
        "Je peux vous aider sur :\n\n"
        "• 💰 **Les tarifs** — « Quels sont vos prix ? »\n"
        "• 💎 **Premium** — « C'est quoi Premium ? »\n"
        "• 📋 **Constitution de dossier** — « Comment préparer mon dossier ? »\n"
        "• 📇 **Annuaire** — « Comment m'inscrire dans l'annuaire ? »\n"
        "• 🔔 **Alertes** — « Comment créer une alerte ? »\n"
        "• 💳 **Paiement** — « Comment payer ? »\n\n"
        "Ou **collez un texte de cahier des charges** ci-dessous, "
        "et je vous générerai un résumé structuré !"
    )


def analyze_chat_request(chat_type, content):
    """
    Point d'entrée principal du chatbot.
    - chat_type = "tender" → analyse un cahier des charges
    - chat_type = "service" → répond à une question de services
    """
    if chat_type == "tender":
        result = analyze_tender_text(content)
        if not result:
            return (
                "⚠️ Le texte fourni est trop court pour être analysé.\n\n"
                "Collez au moins **20 caractères** du cahier des charges "
                "(exigences, dates, montants, conditions...)."
            )
        return result["summary"]
    else:
        return answer_service_question(content)