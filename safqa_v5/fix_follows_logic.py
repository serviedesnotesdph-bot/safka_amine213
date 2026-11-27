# -*- coding: utf-8 -*-
"""
Corrige les incohérences logiques dans les suivis de marchés.
- Ajoute des marchés passés (deadline en 2025-2026)
- Corrige les statuts "gagné/perdu" sur marchés futurs
- Crée des suivis réalistes et temporellement cohérents
Usage : python3 fix_follows_logic.py
"""
from datetime import datetime, timedelta
from app import (create_app, db, User, Tender, TenderFollow,
                 ChecklistItem, Favorite)


app = create_app()


def main():
    print("\n" + "=" * 60)
    print("🔧 Correction des incohérences dans les suivis")
    print("=" * 60 + "\n")

    with app.app_context():
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # ============================================================
        # 1. CRÉER DES MARCHÉS PASSÉS (deadline en 2025-2026)
        # ============================================================
        print("📋 Création de marchés passés pour la cohérence...")

        past_tenders_data = [
            ("Réhabilitation 5 km route Sidi Ali Boussidi",
             "Direction des Travaux Publics de la wilaya",
             -45, "travaux", "Sidi Ali Boussidi", 22000000, "travaux"),
            ("Fourniture de matériel informatique - Lycée Telagh",
             "Direction de l'Éducation",
             -30, "fournitures", "Telagh", 5500000, "fournitures"),
            ("Nettoyage annuel de 3 établissements hospitaliers",
             "Direction de la Santé",
             -60, "services", "Sidi Bel Abbes", 9800000, "services"),
            ("Construction de 4 salles de classe - APC Telagh",
             "APC de Telagh",
             -20, "travaux", "Telagh", 15000000, "travaux"),
            ("Étude hydraulique du barrage de Tessala",
             "ANBT - Agence Nationale des Barrages",
             -15, "etudes", "Tessala", 7200000, "etudes"),
            ("Achat de 20 véhicules utilitaires",
             "Direction des Transports",
             -10, "fournitures", "Sidi Bel Abbes", 35000000, "fournitures"),
        ]

        created_tenders = []
        for (title, agency, offset_days, sector, commune, budget, _) in past_tenders_data:
            existing = Tender.query.filter_by(title=title).first()
            if existing:
                created_tenders.append(existing)
                continue
            deadline_str = (today + timedelta(days=offset_days)).strftime("%Y-%m-%d")
            t = Tender(
                title=title,
                agency=agency,
                deadline=deadline_str,
                sector=sector,
                commune=commune,
                budget_dzd=budget,
                created_at=datetime.utcnow() + timedelta(days=offset_days - 30),
            )
            db.session.add(t)
            db.session.flush()
            created_tenders.append(t)

        db.session.commit()
        print(f"   ✅ {len(created_tenders)} marchés passés prêts\n")

        # ============================================================
        # 2. CORRIGER LES SUIVIS ILLOGIQUES
        # ============================================================
        print("🔍 Correction des suivis incohérents...")

        all_follows = TenderFollow.query.all()
        fixed_won_lost = 0
        fixed_depose = 0
        deleted_follows = 0

        for f in all_follows:
            tender = db.session.get(Tender, f.tender_id)
            if not tender:
                db.session.delete(f)
                deleted_follows += 1
                continue

            try:
                deadline_dt = datetime.strptime(tender.deadline.strip(), "%Y-%m-%d")
            except (ValueError, AttributeError):
                db.session.delete(f)
                deleted_follows += 1
                continue

            days_to_deadline = (deadline_dt - today).days

            # Règle 1 : "gagné" ou "perdu" SEULEMENT si deadline passée
            if f.status in ("gagne", "perdu") and days_to_deadline >= 0:
                f.status = "a_etudier"
                f.notes = "Suivi à réévaluer — marché encore ouvert"
                fixed_won_lost += 1

            # Règle 2 : "déposé" seulement si deadline passée ou dans moins de 7 jours
            elif f.status == "depose" and days_to_deadline > 7:
                f.status = "dossier_en_cours"
                f.notes = "Préparation du dossier en cours"
                fixed_depose += 1

        db.session.commit()
        print(f"   ✅ {fixed_won_lost} suivis 'gagné/perdu' corrigés")
        print(f"   ✅ {fixed_depose} suivis 'déposé' corrigés")
        if deleted_follows:
            print(f"   ✅ {deleted_follows} suivis orphelins supprimés")
        print()

        # ============================================================
        # 3. CRÉER DES SUIVIS RÉALISTES ET COHÉRENTS
        # ============================================================
        print("🎯 Création de suivis réalistes...")

        statuses_notes = {
            "gagne": "🏆 Marché remporté — contrat signé, exécution en cours",
            "perdu": "❌ Offre non retenue — écart de prix trop important",
            "depose": "📤 Dossier déposé — en attente d'ouverture des plis",
            "dossier_en_cours": "📝 Préparation des pièces en cours",
            "a_etudier": "🔍 À examiner cette semaine",
        }

        users = User.query.filter(User.role != "admin").all()
        new_follows = 0

        for user in users:
            # A. Associer 1-2 marchés passés (gagné/perdu) — uniquement si secteur compatible
            for i, t in enumerate(created_tenders):
                # Vérifier compatibilité secteur
                sector_match = (
                    user.sector_activity and
                    (user.sector_activity == t.sector or
                     (user.sector_activity in ["electricien", "plombier", "macon", "peintre", "menuisier", "architecte"] and t.sector in ["travaux", "btp"]))
                )
                # Ou forcer pour certains users pour avoir de la variété
                if not sector_match and i > 0:
                    continue

                # Seulement 1 user sur 2 pour éviter le sur-remplissage
                if hash(user.email + str(t.id)) % 2 != 0:
                    continue

                existing = TenderFollow.query.filter_by(
                    user_id=user.id, tender_id=t.id
                ).first()
                if existing:
                    continue

                # Alterner gagné/perdu
                status = "gagne" if hash(user.email + str(t.id) + "won") % 2 == 0 else "perdu"
                db.session.add(TenderFollow(
                    user_id=user.id, tender_id=t.id,
                    status=status,
                    notes=statuses_notes[status],
                    created_at=datetime.utcnow() - timedelta(days=60),
                    updated_at=datetime.utcnow() - timedelta(days=30),
                ))
                new_follows += 1

        db.session.commit()
        print(f"   ✅ {new_follows} suivis 'gagné/perdu' créés sur marchés passés\n")

        # ============================================================
        # 4. VÉRIFICATION FINALE
        # ============================================================
        print("=" * 60)
        print("📊 ÉTAT APRÈS CORRECTION")
        print("=" * 60)

        # Compter par statut avec vérification temporelle
        follows_by_status = {}
        incoherent_count = 0

        for f in TenderFollow.query.all():
            t = db.session.get(Tender, f.tender_id)
            if not t:
                continue
            try:
                deadline_dt = datetime.strptime(t.deadline.strip(), "%Y-%m-%d")
                days = (deadline_dt - today).days
            except (ValueError, AttributeError):
                continue

            follows_by_status[f.status] = follows_by_status.get(f.status, 0) + 1

            # Vérifier cohérence
            if f.status in ("gagne", "perdu") and days >= 0:
                incoherent_count += 1
                print(f"   ⚠️ INCOHÉRENT : {f.status} sur marché futur (deadline {t.deadline})")

        print(f"\n📊 Total suivis : {TenderFollow.query.count()}")
        for status, label in [("a_etudier", "À étudier"),
                              ("dossier_en_cours", "Dossier en cours"),
                              ("depose", "Déposé"),
                              ("gagne", "Gagné"),
                              ("perdu", "Perdu")]:
            count = follows_by_status.get(status, 0)
            print(f"   • {label:20s} : {count}")

        print(f"\n📋 Marchés passés : {sum(1 for t in created_tenders if t.deadline < today.strftime('%Y-%m-%d'))}")

        if incoherent_count == 0:
            print(f"\n✅ COHÉRENCE VALIDÉE : aucune incohérence détectée")
        else:
            print(f"\n⚠️ {incoherent_count} incohérence(s) restante(s)")

        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()