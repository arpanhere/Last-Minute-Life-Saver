from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from . import ai_engine
from .models import Task, db

api_bp = Blueprint("api", __name__)


@api_bp.route("/voice-task", methods=["POST"])
@login_required
def voice_task():
    data = request.get_json(silent=True) or {}
    transcript = (data.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"ok": False, "error": "No speech captured."}), 400

    parsed = ai_engine.parse_voice_command(transcript)

    task = Task(
        user_id=current_user.id,
        title=parsed["title"],
        category=parsed.get("category", "general"),
        deadline=parsed["deadline"],
        importance=parsed.get("importance", 3),
        estimated_minutes=30,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({
        "ok": True,
        "task": task.to_dict(),
        "spoken_confirmation": f"Added {task.title}, due {task.deadline.strftime('%A %I:%M %p')}.",
    })


@api_bp.route("/whats-next")
@login_required
def whats_next():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    ai_engine.sync_missed(tasks)
    db.session.commit()

    item = ai_engine.whats_next(tasks)
    if not item:
        return jsonify({"ok": True, "task": None})

    t = item["task"]
    return jsonify({
        "ok": True,
        "task": t.to_dict(),
        "score": item["score"],
        "risk": item["risk"],
        "reason": item["reason"],
    })


@api_bp.route("/tasks/<int:task_id>/breakdown", methods=["POST"])
@login_required
def breakdown(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    steps, source = ai_engine.breakdown_task(task)
    task.set_steps(steps, source)
    db.session.commit()
    return jsonify({"ok": True, "steps": steps, "source": source})
