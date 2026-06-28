"""
Database models for The Last-Minute Life Saver.
"""
import json
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

CATEGORIES = ["assignment", "exam", "bill", "interview", "meeting", "general"]
STATUSES = ["pending", "in_progress", "done", "missed"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship(
        "Task", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    habits = db.relationship(
        "Habit", backref="owner", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(50), default="general")
    deadline = db.Column(db.DateTime, nullable=False)
    estimated_minutes = db.Column(db.Integer, default=30)
    importance = db.Column(db.Integer, default=3)  # 1 (low) - 5 (high)
    status = db.Column(db.String(20), default="pending")

    ai_steps = db.Column(db.Text)        # JSON-encoded list of strings
    ai_source = db.Column(db.String(20))  # "ai" or "heuristic"

    scheduled_start = db.Column(db.DateTime)
    scheduled_end = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    def steps_list(self):
        if not self.ai_steps:
            return []
        try:
            return json.loads(self.ai_steps)
        except (ValueError, TypeError):
            return []

    def set_steps(self, steps, source):
        self.ai_steps = json.dumps(steps)
        self.ai_source = source

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "estimated_minutes": self.estimated_minutes,
            "importance": self.importance,
            "status": self.status,
        }


class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    frequency = db.Column(db.String(10), default="daily")  # daily / weekly
    streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_checkin = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
