"""
Optional: populate the database with a demo account and a spread of
tasks across risk levels, so judges can see the prioritization engine
working immediately without typing in data first.

Run with:  python seed.py
Login with: demo / demo1234
"""
from datetime import datetime, timedelta

from app import create_app
from app.models import Habit, Task, User, db

app = create_app()

with app.app_context():
    user = User.query.filter_by(username="demo").first()
    if not user:
        user = User(username="demo", email="demo@example.com")
        user.set_password("demo1234")
        db.session.add(user)
        db.session.commit()

    if not Task.query.filter_by(user_id=user.id).first():
        now = datetime.utcnow()
        demo_tasks = [
            dict(title="Submit DBMS normalization assignment", category="assignment",
                 deadline=now + timedelta(hours=3), estimated_minutes=90, importance=5),
            dict(title="Pay hostel WiFi bill", category="bill",
                 deadline=now + timedelta(hours=20), estimated_minutes=10, importance=4),
            dict(title="Mock interview prep for TA role", category="interview",
                 deadline=now + timedelta(days=2), estimated_minutes=60, importance=4),
            dict(title="Revise MAD1 Flask blueprints for quiz", category="exam",
                 deadline=now + timedelta(days=4), estimated_minutes=120, importance=3),
            dict(title="Team sync on project API contract", category="meeting",
                 deadline=now + timedelta(hours=6), estimated_minutes=30, importance=3),
            dict(title="Reorganize LED project parts box", category="general",
                 deadline=now + timedelta(days=6), estimated_minutes=20, importance=1),
        ]
        for d in demo_tasks:
            db.session.add(Task(user_id=user.id, **d))

        db.session.add(Habit(user_id=user.id, name="Revise for 20 minutes", frequency="daily"))
        db.session.commit()

    print("Demo account ready -> username: demo / password: demo1234")
