# -*- coding: utf-8 -*-
"""Nettoie les données de test de la base."""
from app import create_app, db, Tender, TenderFollow, Notification, Favorite

app = create_app()

with app.app_context():
    # Trouver tous les marchés de test
    test_tenders = Tender.query.filter(
        Tender.title.like("TEST%")
    ).all()

    if not test_tenders:
        print("✅ Aucun marché de test trouvé")
    else:
        print(f"\n🗑️ Suppression de {len(test_tenders)} marché(s) de test :")
        for t in test_tenders:
            print(f"   - [{t.id}] {t.title}")

            # Supprimer les dépendances
            Notification.query.filter_by(tender_id=t.id).delete()
            Favorite.query.filter_by(tender_id=t.id).delete()
            TenderFollow.query.filter_by(tender_id=t.id).delete()

            db.session.delete(t)
        db.session.commit()
        print(f"\n✅ {len(test_tenders)} marché(s) supprimé(s)")

    # Afficher les marchés restants
    print("\n" + "=" * 60)
    print("📊 ÉTAT DES MARCHÉS")
    print("=" * 60)

    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")

    past = Tender.query.filter(Tender.deadline < today).all()
    future = Tender.query.filter(Tender.deadline >= today).all()

    print(f"\n📁 Marchés PASSÉS ({len(past)}) — utilisés pour les statuts 'gagné/perdu' :")
    for t in past:
        print(f"   • [{t.id}] {t.deadline} | {t.title[:55]}")

    print(f"\n🔵 Marchés FUTURS ({len(future)}) — affichés sur l'accueil :")
    for t in future:
        print(f"   • [{t.id}] {t.deadline} | {t.title[:55]}")

    print("\n" + "=" * 60 + "\n")