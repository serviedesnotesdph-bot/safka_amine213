# -*- coding: utf-8 -*-
from datetime import datetime
from app import create_app, db, Tender, TenderFollow, User

app = create_app()

with app.app_context():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n📅 Date du jour : {today}\n")

    # Afficher chaque suivi et vérifier la cohérence
    print(f"{'User':<25} {'Marché':<45} {'Statut':<20} {'Deadline':<12} {'Cohérent'}")
    print("-" * 110)

    issues = 0
    for f in TenderFollow.query.all():
        t = db.session.get(Tender, f.tender_id)
        u = db.session.get(User, f.user_id)
        if not t or not u:
            continue
        days = (datetime.strptime(t.deadline, "%Y-%m-%d") - datetime.strptime(today, "%Y-%m-%d")).days
        coherent = "✅"
        if f.status in ("gagne", "perdu") and days >= 0:
            coherent = f"❌ (deadline dans {days}j)"
            issues += 1
        elif f.status == "depose" and days > 7:
            coherent = f"❌ (deadline dans {days}j)"
            issues += 1
        print(f"{u.full_name[:24]:<25} {t.title[:44]:<45} {f.status:<20} {t.deadline:<12} {coherent}")

    print(f"\n{'✅ Aucune incohérence' if issues == 0 else f'❌ {issues} incohérence(s)'}\n")