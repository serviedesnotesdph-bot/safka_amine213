# -*- coding: utf-8 -*-
"""
Remplit la base de données Safqa Belabbès avec des données réalistes.
Usage : python3 seed_rich_data.py
"""
from datetime import datetime, timedelta
from app import (create_app, db, User, Tender, Favorite, TenderFollow,
                 SavedAlert, PartnershipAd, Professional, PremiumRequest,
                 Ad, ChecklistItem)


app = create_app()


# ============================================================
# 20 UTILISATEURS VARIÉS (Algériens réalistes)
# ============================================================
USERS = [
    # email, full_name, phone, company, sector_activity, commune, plan, favorite_sectors
    ("karim.bouzid@gmail.com", "Karim Bouzid", "0551100001", "BTP Bouzid & Fils", "btp", "Sidi Bel Abbes", "premium", "btp,travaux"),
    ("amina.hadj@gmail.com", "Amina Hadj", "0551100002", "Informatique Solutions DZ", "informatique", "Sidi Bel Abbes", "premium", "informatique"),
    ("yacine.khelifi@gmail.com", "Yacine Khelifi", "0551100003", "Électricité Khelifi", "electricien", "Telagh", "free", "energie,btp"),
    ("sophia.merabet@gmail.com", "Sophia Merabet", "0551100004", "Cabinet Merabet Conseil", "services", "Sidi Bel Abbes", "premium", "services"),
    ("mohamed.benyahia@gmail.com", "Mohamed Benyahia", "0551100005", "EURL Benyahia Hydraulique", "hydraulique", "Tessala", "premium", "hydraulique,btp"),
    ("fatima.zohra.dj@gmail.com", "Fatima Zohra Djelloul", "0551100006", "Pharmacie Djelloul", "sante", "Sidi Bel Abbes", "free", "sante"),
    ("rachid.belkacem@gmail.com", "Rachid Belkacem", "0551100007", "Plomberie Belkacem", "plombier", "Sfisef", "free", "hydraulique,services"),
    ("nadia.berrah@gmail.com", "Nadia Berrah", "0551100008", "Agro Nadia SARL", "agroalimentaire", "Ben Badis", "premium", "agroalimentaire"),
    ("omar.taleb@gmail.com", "Omar Taleb", "0551100009", "Maçonnerie Taleb", "macon", "Ras El Ma", "free", "btp"),
    ("lyla.bouzidi@gmail.com", "Lyla Bouzidi", "0551100010", "Architecte Bouzidi", "architecte", "Sidi Bel Abbes", "premium", "btp"),
    ("hakim.saidi@gmail.com", "Hakim Saidi", "0551100011", "Transport Saidi", "transport", "Ain Thrid", "free", "services"),
    ("sonia.benali@gmail.com", "Sonia Benali", "0551100012", "Nettoyage Benali", "nettoyage", "Sidi Bel Abbes", "free", "services"),
    ("walid.meziane@gmail.com", "Walid Meziane", "0551100013", "Froid & Clim Meziane", "froid", "Sidi Lahcene", "premium", "services,informatique"),
    ("imene.bendjaballah@gmail.com", "Imene Bendjaballah", "0551100014", "Sécurité Plus", "securite", "Sidi Bel Abbes", "free", "services"),
    ("sofiane.boukhalfa@gmail.com", "Sofiane Boukhalfa", "0551100015", "Menuiserie Boukhalfa", "menuisier", "Sidi Ali Boussidi", "free", "btp"),
    ("nour.el.houda@gmail.com", "Nour El Houda Benaissa", "0551100016", "Benaissa Peinture", "peintre", "Merine", "free", "btp"),
    ("samir.hamdi@gmail.com", "Samir Hamdi", "0551100017", "Hamdi Électricité Générale", "electricien", "Mostefa Ben Brahim", "premium", "energie"),
    ("linda.bourdim@gmail.com", "Linda Bourdim", "0551100018", "Bourdim Informatique", "informatique", "Sidi Brahim", "free", "informatique"),
    ("abdelkader.senouci@gmail.com", "Abdelkader Senouci", "0551100019", "Senouci BTP", "btp", "Sidi Hamadouche", "premium", "btp,travaux"),
    ("djamila.belkheiri@gmail.com", "Djamila Belkheiri", "0551100020", "Belkheiri Conseil RH", "services", "Moulay Slissen", "free", "services"),
]


# ============================================================
# 25 ANNONCES DE GROUPEMENT
# ============================================================
PARTNERSHIPS = [
    # (email, tender_title, looking_for, sector_wanted, commune_wanted, message)
    ("karim.bouzid@gmail.com", "Réhabilitation route Sidi Bel Abbès - Telagh",
     "Entreprise électricité pour éclairage public", "electricien", "Telagh",
     "Nous cherchons un électricien pour installer l'éclairage public sur 12 km de route. Partenariat 50/50."),
    ("amina.hadj@gmail.com", "Système d'information pour la wilaya",
     "Fournisseur de matériel informatique", "informatique", "Sidi Bel Abbes",
     "Marché de 8.5M DA. Besoin d'un partenaire pour la fourniture de 50 PC et serveurs."),
    ("yacine.khelifi@gmail.com", "Construction école primaire Sfisef",
     "Entreprise BTP pour gros œuvre", "btp", "Sfisef",
     "Nous sommes spécialisés en électricité. Cherchons BTP pour le gros œuvre."),
    ("mohamed.benyahia@gmail.com", "Réseau assainissement Tessala",
     "Fournisseur de tuyaux et matériaux", "fournitures", "Tessala",
     "Chantier de 18.7M DA. Besoin d'un fournisseur pour 3 km de conduites."),
    ("lyla.bouzidi@gmail.com", "Étude et suivi marché couvert Ben Badis",
     "Bureau d'études techniques", "etudes", "Ben Badis",
     "Nous sommes architectes. Cherchons BET pour l'étude technique."),
    ("rachid.belkacem@gmail.com", "Travaux hydrauliques Sidi Ali Boussidi",
     "Entreprise de forage", "hydraulique", "Sidi Ali Boussidi",
     "Plombier spécialisé, je cherche une entreprise de forage pour un projet de 3 puits."),
    ("nadia.berrah@gmail.com", "Fourniture denrées alimentaires cantines",
     "Producteur local fruits et légumes", "agroalimentaire", "Toute la wilaya",
     "Marché de 6.2M DA. Cherchons producteurs locaux pour livraison hebdomadaire."),
    ("omar.taleb@gmail.com", "Construction mur de clôture CHU",
     "Fournisseur de ciment et béton", "fournitures", "Sidi Bel Abbes",
     "Maçon expérimenté. Besoin d'un fournisseur pour 500 tonnes de ciment."),
    ("walid.meziane@gmail.com", "Climatisation 10 écoles primaires",
     "Installateur électricité", "electricien", "Sidi Lahcene",
     "Marché de 12M DA. Cherchons électricien pour installation électrique des écoles."),
    ("sofiane.boukhalfa@gmail.com", "Menuiserie pour 20 logements AADL",
     "Fournisseur de bois", "fournitures", "Sidi Bel Abbes",
     "Menuisier. Besoin d'un fournisseur de bois pour portes et fenêtres."),
    ("karim.bouzid@gmail.com", "Étude impact environnemental - Barrage",
     "Bureau d'études spécialisé", "etudes", "Telagh",
     "Nous cherchons un bureau d'études pour l'étude d'impact du barrage."),
    ("samir.hamdi@gmail.com", "Éclairage public LED - 5 communes",
     "Fournisseur de lampadaires LED", "fournitures", "Toute la wilaya",
     "Électricien. Besoin d'un fournisseur de 500 lampadaires LED haute qualité."),
    ("abdelkader.senouci@gmail.com", "Réhabilitation 30 km de voirie",
     "Entreprise peinture routière", "peintre", "Sidi Bel Abbes",
     "BTP spécialisé. Cherchons peintre pour marquage au sol sur 30 km."),
    ("amina.hadj@gmail.com", "Digitalisation archives wilaya",
     "Prestataire numérisation", "informatique", "Sidi Bel Abbes",
     "Marché de 4M DA. Besoin d'un prestataire pour scanner 500 000 documents."),
    ("mohamed.benyahia@gmail.com", "Réhabilitation réseau AEP",
     "Entreprise de terrassement", "btp", "Tessala",
     "Hydraulique. Cherchons entreprise BTP pour le terrassement des tranchées."),
    ("lyla.bouzidi@gmail.com", "Rénovation 5 bâtiments administratifs",
     "Entreprise rénovation complète", "btp", "Sidi Bel Abbes",
     "Architecte en charge de 5 projets. Cherchons BTP pour l'exécution."),
    ("nadia.berrah@gmail.com", "Marché cantines - 30 écoles",
     "Transporteur spécialisé alimentaire", "transport", "Toute la wilaya",
     "Agroalimentaire. Besoin d'un transporteur frigorifique pour livraisons."),
    ("rachid.belkacem@gmail.com", "Installation sanitaire - 15 logements",
     "Fournisseur sanitaire", "fournitures", "Sfisef",
     "Plombier. Besoin d'un fournisseur de matériel sanitaire pour 15 logements."),
    ("walid.meziane@gmail.com", "Chambre froide - Centre de stockage",
     "Électricien industriel", "electricien", "Sidi Bel Abbes",
     "Froid & Clim. Cherchons électricien pour installation triphasée."),
    ("imene.bendjaballah@gmail.com", "Gardiennage 3 sites administratifs",
     "Société de sécurité", "securite", "Sidi Bel Abbes",
     "Marché de 5M DA. Cherchons partenaire pour surveillance 24/7."),
    ("omar.taleb@gmail.com", "Construction 40 logements promotionnels",
     "Électricien + Plombier", "electricien", "Ras El Ma",
     "Maçon. Cherchons électricien et plombier pour 40 logements."),
    ("hakim.saidi@gmail.com", "Livraison matériel informatique",
     "Transporteur spécialisé", "transport", "Sidi Bel Abbes",
     "Transport. Cherchons électricien pour l'installation chez le client final."),
    ("sonia.benali@gmail.com", "Nettoyage 10 écoles primaires",
     "Fournisseur de produits d'entretien", "fournitures", "Sidi Bel Abbes",
     "Marché de 2M DA. Besoin d'un fournisseur pour produits écologiques."),
    ("djamila.belkheiri@gmail.com", "Formation 100 agents administratifs",
     "Formateur bureautique", "informatique", "Sidi Bel Abbes",
     "Cabinet RH. Cherchons formateur pour formation Word/Excel niveau 2."),
    ("sophia.merabet@gmail.com", "Audit organisationnel wilaya",
     "Expert-comptable agréé", "services", "Sidi Bel Abbes",
     "Conseil. Cherchons expert-comptable pour audit de 5 directions."),
]


# ============================================================
# 30 PROFESSIONNELS ANNUAIRE (tous publiés)
# ============================================================
PROFESSIONALS = [
    # (email, business_name, category, description, services, commune, years, phone)
    ("yacine.khelifi@gmail.com", "Électricité Khelifi", "electricien",
     "Électricien professionnel avec 12 ans d'expérience à Telagh. Installations résidentielles et industrielles, dépannage 24/7.",
     "Installation électrique, dépannage urgent, mise aux normes, tableau électrique, éclairage LED",
     "Telagh", 12, "0551100003"),
    ("rachid.belkacem@gmail.com", "Plomberie Belkacem", "plombier",
     "Plombier agréé à Sfisef. Interventions rapides, travail soigné, devis gratuit.",
     "Dépannage fuite, installation sanitaire, chauffe-eau, débouchage, rénovation",
     "Sfisef", 8, "0551100007"),
    ("omar.taleb@gmail.com", "Maçonnerie Taleb", "macon",
     "Maçon expérimenté 15 ans. Construction, rénovation, murs, dalles, carrelage.",
     "Construction maison, mur clôture, dalle béton, carrelage, rénovation",
     "Ras El Ma", 15, "0551100009"),
    ("nour.el.houda@gmail.com", "Benaissa Peinture", "peintre",
     "Peintre décorateur à Merine. Peinture intérieure, extérieure, enduits décoratifs.",
     "Peinture intérieure, façade, enduit, papier peint, décoration",
     "Merine", 6, "0551100016"),
    ("sofiane.boukhalfa@gmail.com", "Menuiserie Boukhalfa", "menuisier",
     "Menuiserie artisanale depuis 20 ans. Portes, fenêtres, meubles sur mesure.",
     "Porte bois, fenêtre, placard, meuble cuisine, parquet, escalier",
     "Sidi Ali Boussidi", 20, "0551100015"),
    ("karim.bouzid@gmail.com", "BTP Bouzid & Fils", "btp",
     "Entreprise familiale de BTP depuis 25 ans. Réalisation de projets publics et privés.",
     "Construction, voirie, assainissement, réhabilitation, gros œuvre",
     "Sidi Bel Abbes", 25, "0551100001"),
    ("amina.hadj@gmail.com", "Informatique Solutions DZ", "informatique",
     "Solutions informatiques complètes. Réseaux, logiciels, maintenance, formation.",
     "Maintenance PC, installation réseau, création site web, formation bureautique",
     "Sidi Bel Abbes", 7, "0551100002"),
    ("walid.meziane@gmail.com", "Froid & Clim Meziane", "froid",
     "Spécialiste froid et climatisation. Installation et maintenance de chambres froides.",
     "Climatisation, chambre froide, réfrigération, entretien, dépannage",
     "Sidi Lahcene", 10, "0551100013"),
    ("hakim.saidi@gmail.com", "Transport Saidi", "transport",
     "Transporteur agréé. Livraisons dans toute la wilaya et au-delà.",
     "Transport marchandises, livraison, déménagement, transport frigorifique",
     "Ain Thrid", 14, "0551100011"),
    ("sonia.benali@gmail.com", "Nettoyage Benali", "nettoyage",
     "Société de nettoyage professionnel. Particuliers et entreprises.",
     "Nettoyage bureaux, vitres, moquettes, fin de chantier, désinfection",
     "Sidi Bel Abbes", 5, "0551100012"),
    ("imene.bendjaballah@gmail.com", "Sécurité Plus", "securite",
     "Société de gardiennage agréée. Surveillance 24/7 de vos sites.",
     "Gardiennage, surveillance, alarme, vidéosurveillance, intervention",
     "Sidi Bel Abbes", 9, "0551100014"),
    ("lyla.bouzidi@gmail.com", "Architecte Bouzidi", "architecte",
     "Cabinet d'architecture. Conception, permis de construire, suivi de chantier.",
     "Plan architectural, permis construire, rénovation, décoration intérieure",
     "Sidi Bel Abbes", 11, "0551100010"),
    ("samir.hamdi@gmail.com", "Hamdi Électricité Générale", "electricien",
     "Électricité générale industrielle et tertiaire. Interventions dans toute la wilaya.",
     "Électricité industrielle, triphasé, tableau, moteur, automatisme",
     "Mostefa Ben Brahim", 18, "0551100017"),
    ("linda.bourdim@gmail.com", "Bourdim Informatique", "informatique",
     "Services informatiques à domicile et en entreprise. Dépannage rapide.",
     "Réparation PC, installation logiciel, dépannage réseau, sauvegarde données",
     "Sidi Brahim", 4, "0551100018"),
    ("abdelkader.senouci@gmail.com", "Senouci BTP", "btp",
     "Entreprise BTP spécialisée en voirie et réseaux divers.",
     "Voirie, assainissement, terrassement, enrobé, béton",
     "Sidi Hamadouche", 22, "0551100019"),
    ("djamila.belkheiri@gmail.com", "Belkheiri Conseil RH", "services",
     "Cabinet de conseil en ressources humaines et formation professionnelle.",
     "Conseil RH, formation, recrutement, audit social, coaching",
     "Moulay Slissen", 13, "0551100020"),
    ("mohamed.benyahia@gmail.com", "EURL Benyahia Hydraulique", "btp",
     "Entreprise hydraulique. Forages, réseaux, station de pompage.",
     "Forage, pompage, réseau AEP, château d'eau, irrigation",
     "Tessala", 16, "0551100005"),
    ("sophia.merabet@gmail.com", "Cabinet Merabet Conseil", "services",
     "Cabinet de conseil en management et stratégie d'entreprise.",
     "Conseil stratégique, audit, accompagnement PME, business plan",
     "Sidi Bel Abbes", 10, "0551100004"),
]


# ============================================================
# FONCTION PRINCIPALE
# ============================================================
def create_users():
    created = 0
    for (email, full_name, phone, company, sector, commune, plan, fav_sectors) in USERS:
        if User.query.filter_by(email=email).first():
            continue
        u = User(
            email=email, phone=phone, full_name=full_name,
            company=company, sector_activity=sector, commune=commune,
            plan=plan, favorite_sectors=fav_sectors,
            email_notifications=True, sms_notifications=(plan == "premium"),
        )
        u.set_password("password123")
        db.session.add(u)
        created += 1
    db.session.commit()
    return created


def create_partnerships():
    created = 0
    for (email, tender_title, looking_for, sector_wanted, commune_wanted, message) in PARTNERSHIPS:
        user = User.query.filter_by(email=email).first()
        if not user:
            continue
        # Vérifier si une annonce similaire existe
        existing = PartnershipAd.query.filter_by(
            user_id=user.id, tender_title=tender_title
        ).first()
        if existing:
            continue
        p = PartnershipAd(
            user_id=user.id, tender_title=tender_title,
            looking_for=looking_for, sector_wanted=sector_wanted,
            commune_wanted=commune_wanted, message=message,
            contact_phone=user.phone, is_open=True,
        )
        db.session.add(p)
        created += 1
    db.session.commit()
    return created


def create_professionals():
    created = 0
    for (email, business_name, category, description, services, commune, years, phone) in PROFESSIONALS:
        user = User.query.filter_by(email=email).first()
        if not user:
            continue
        if Professional.query.filter_by(user_id=user.id).first():
            continue
        now = datetime.utcnow()
        p = Professional(
            user_id=user.id,
            business_name=business_name,
            category=category,
            description=description,
            services=services,
            phone=phone,
            whatsapp=phone,
            email_public=email,
            commune=commune,
            years_experience=years,
            price_dzd=3000,
            duration_days=180,
            payment_status="paid",
            payment_method="manual",
            is_approved=True,
            is_active=True,
            starts_at=now - timedelta(days=10),
            ends_at=now + timedelta(days=170),
            views=5 + (hash(business_name) % 50),
            phone_clicks=hash(business_name) % 15,
        )
        db.session.add(p)
        created += 1
    db.session.commit()
    return created

def create_past_tenders():
    """Crée des marchés avec deadlines dans le passé (pour permettre gagné/perdu)."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    past_data = [
        ("Réhabilitation 5 km route Sidi Ali Boussidi", "Direction des Travaux Publics",
         -45, "travaux", "Sidi Ali Boussidi", 22000000),
        ("Fourniture matériel informatique - Lycée Telagh", "Direction de l'Éducation",
         -30, "fournitures", "Telagh", 5500000),
        ("Nettoyage annuel de 3 hôpitaux", "Direction de la Santé",
         -60, "services", "Sidi Bel Abbes", 9800000),
        ("Construction 4 salles de classe - APC Telagh", "APC de Telagh",
         -20, "travaux", "Telagh", 15000000),
        ("Étude hydraulique barrage de Tessala", "ANBT",
         -15, "etudes", "Tessala", 7200000),
    ]
    created = 0
    for (title, agency, offset, sector, commune, budget) in past_data:
        if Tender.query.filter_by(title=title).first():
            continue
        deadline = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
        db.session.add(Tender(
            title=title, agency=agency, deadline=deadline,
            sector=sector, commune=commune, budget_dzd=budget,
            created_at=datetime.utcnow() + timedelta(days=offset - 30),
        ))
        created += 1
    db.session.commit()
    return created
def create_favorites_and_follows():
       
    """Ajoute des favoris et des suivis LOGIQUES (statuts cohérents avec les dates)."""
    fav_count = 0
    follow_count = 0
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # S'assurer qu'il existe des marchés passés
    past_tender = Tender.query.filter(
        Tender.deadline < today.strftime("%Y-%m-%d")
    ).first()

    tenders_all = Tender.query.all()
    if not tenders_all:
        return 0, 0

    # Trier : passé d'abord, futur ensuite
    past = [t for t in tenders_all if t.deadline < today.strftime("%Y-%m-%d")]
    future = [t for t in tenders_all if t.deadline >= today.strftime("%Y-%m-%d")]

    users = User.query.limit(10).all()
    statuses_notes = {
        "gagne": "🏆 Marché remporté",
        "perdu": "❌ Offre non retenue",
        "depose": "📤 Dossier déposé",
        "dossier_en_cours": "📝 Dossier en cours",
        "a_etudier": "🔍 À étudier",
    }

    for i, user in enumerate(users):
        # Favoris (indépendant du statut)
        for j in range(2 + (i % 3)):
            t = tenders_all[(i + j) % len(tenders_all)]
            if not Favorite.query.filter_by(user_id=user.id, tender_id=t.id).first():
                db.session.add(Favorite(user_id=user.id, tender_id=t.id))
                fav_count += 1

        # Suivis LOGIQUES
        # 1. Si marchés passés existent → possibilité de gagné/perdu
        if past and i % 2 == 0:
            t = past[i % len(past)]
            status = "gagne" if i % 4 == 0 else "perdu"
            if not TenderFollow.query.filter_by(user_id=user.id, tender_id=t.id).first():
                db.session.add(TenderFollow(
                    user_id=user.id, tender_id=t.id,
                    status=status, notes=statuses_notes[status],
                ))
                follow_count += 1

        # 2. Marchés futurs → a_etudier ou dossier_en_cours
        if future:
            for k in range(1 + (i % 2)):
                t = future[(i + k) % len(future)]
                if TenderFollow.query.filter_by(user_id=user.id, tender_id=t.id).first():
                    continue
                status = "a_etudier" if k == 0 else "dossier_en_cours"
                db.session.add(TenderFollow(
                    user_id=user.id, tender_id=t.id,
                    status=status, notes=statuses_notes[status],
                ))
                follow_count += 1

    db.session.commit()
    return fav_count, follow_count

def create_alerts():
    """Crée des alertes pour les users Premium."""
    created = 0
    premium_users = User.query.filter_by(plan="premium").all()
    alerts_config = [
        ("btp", "Sidi Bel Abbes", "route, construction, école"),
        ("services", "Telagh", "nettoyage, gardiennage"),
        ("informatique", "Sidi Bel Abbes", "réseau, logiciel"),
        ("hydraulique", "Tessala", "forage, eau"),
        ("energie", "", "électricité, éclairage"),
    ]
    for i, user in enumerate(premium_users):
        cfg = alerts_config[i % len(alerts_config)]
        existing = SavedAlert.query.filter_by(user_id=user.id).first()
        if existing:
            continue
        db.session.add(SavedAlert(
            user_id=user.id,
            sector=cfg[0] or None,
            commune=cfg[1] or None,
            keywords=cfg[2],
            email_notifications=True,
            sms_notifications=True,
        ))
        created += 1
    db.session.commit()
    return created


def create_checklists():
    """Coche quelques pièces dans les checklists des suivis."""
    created = 0
    items = ["declaration_souscrire", "registre_commerce", "cnas_casnos", "offre_technique"]
    follows = TenderFollow.query.limit(15).all()
    for i, f in enumerate(follows):
        for j in range(i % 5):
            key = items[j % len(items)]
            if not ChecklistItem.query.filter_by(
                user_id=f.user_id, tender_id=f.tender_id, item_key=key
            ).first():
                db.session.add(ChecklistItem(
                    user_id=f.user_id, tender_id=f.tender_id, item_key=key
                ))
                created += 1
    db.session.commit()
    return created


def main():
    print("\n" + "=" * 60)
    print("🌱 Remplissage de la base de données Safqa Belabbès")
    print("=" * 60 + "\n")

    with app.app_context():
        print("👥 Création des utilisateurs...")
        n_users = create_users()
        print(f"   ✅ {n_users} utilisateur(s) créé(s)")

        print("\n🤝 Création des annonces de groupement...")
        n_part = create_partnerships()
        print(f"   ✅ {n_part} annonce(s) créée(s)")

        print("\n📇 Création des professionnels (annuaire)...")
        n_prof = create_professionals()
        print(f"   ✅ {n_prof} profil(s) professionnel(s) créé(s)")
        print("📋 Création des marchés passés...")
        n_past = create_past_tenders()
        print(f"   ✅ {n_past} marché(s) passé(s) créé(s)")

        print("\n⭐ Création des favoris et suivis...")
        n_fav, n_follow = create_favorites_and_follows()
        print(f"   ✅ {n_fav} favori(s) + {n_follow} suivi(s)")
        print("\n🔔 Création des alertes...")
        n_alerts = create_alerts()
        print(f"   ✅ {n_alerts} alerte(s) créée(s)")

        print("\n📋 Remplissage des checklists...")
        n_check = create_checklists()
        print(f"   ✅ {n_check} pièce(s) cochée(s)")

        # Résumé final
        print("\n" + "=" * 60)
        print("📊 ÉTAT FINAL DE LA BASE")
        print("=" * 60)
        print(f"👥 Utilisateurs    : {User.query.count()}")
        print(f"  ⭐ Premium       : {User.query.filter_by(plan='premium').count()}")
        print(f"  🆓 Gratuits      : {User.query.filter_by(plan='free').count()}")
        print(f"📋 Marchés         : {Tender.query.count()}")
        print(f"🤝 Groupements     : {PartnershipAd.query.count()}")
        print(f"📇 Professionnels  : {Professional.query.count()}")
        print(f"⭐ Favoris         : {Favorite.query.count()}")
        print(f"📊 Suivis          : {TenderFollow.query.count()}")
        print(f"🔔 Alertes         : {SavedAlert.query.count()}")
        print(f"📋 Checklists      : {ChecklistItem.query.count()}")
        print("=" * 60)
        print("\n✅ Base remplie avec succès !")
        print("\n🔐 Identifiants de test :")
        print("   Email    : karim.bouzid@gmail.com")
        print("   Password : password123")
        print("\n💡 Pour tester l'annuaire :")
        print("   Allez sur /directory et cliquez sur une catégorie")
        print("\n💡 Pour tester les groupements :")
        print("   Connectez-vous et allez sur /partnerships")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()