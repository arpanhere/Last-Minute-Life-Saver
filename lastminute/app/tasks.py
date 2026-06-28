from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import ai_engine
from .models import CATEGORIES, Task, db

tasks_bp = Blueprint("tasks", __name__)


def _user_tasks():
    return Task.query.filter_by(user_id=current_user.id).all()


@tasks_bp.route("/dashboard")
@login_required
def dashboard():
    tasks = _user_tasks()
    if ai_engine.sync_missed(tasks):
        db.session.commit()

    active = [t for t in tasks if t.status in ("pending", "in_progress")]
    ranked = ai_engine.rank_tasks(active)
    top = ranked[0] if ranked else None
    upcoming = ranked[1:6]
    tips = ai_engine.personalized_recommendations(tasks)

    stats = {
        "pending": len(active),
        "done": len([t for t in tasks if t.status == "done"]),
        "missed": len([t for t in tasks if t.status == "missed"]),
    }

    return render_template(
        "dashboard.html",
        top=top,
        upcoming=upcoming,
        tips=tips,
        stats=stats,
        now=datetime.utcnow(),
    )


@tasks_bp.route("/tasks")
@login_required
def task_list():
    status_filter = request.args.get("status", "active")
    tasks = _user_tasks()
    if ai_engine.sync_missed(tasks):
        db.session.commit()

    if status_filter == "active":
        tasks = [t for t in tasks if t.status in ("pending", "in_progress")]
    elif status_filter != "all":
        tasks = [t for t in tasks if t.status == status_filter]

    ranked = ai_engine.rank_tasks(tasks) if status_filter == "active" else [
        {"task": t, "score": None, "risk": None, "reason": None} for t in
        sorted(tasks, key=lambda x: x.deadline)
    ]
    return render_template("tasks.html", ranked=ranked, status_filter=status_filter)


@tasks_bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def new_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        deadline_raw = request.form.get("deadline", "")
        if not title or not deadline_raw:
            flash("A title and deadline are required.", "error")
            return render_template("task_form.html", categories=CATEGORIES, task=None)

        try:
            deadline = datetime.fromisoformat(deadline_raw)
        except ValueError:
            flash("That deadline doesn't look right.", "error")
            return render_template("task_form.html", categories=CATEGORIES, task=None)

        task = Task(
            user_id=current_user.id,
            title=title,
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "general"),
            deadline=deadline,
            estimated_minutes=int(request.form.get("estimated_minutes") or 30),
            importance=int(request.form.get("importance") or 3),
        )
        db.session.add(task)
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("tasks.task_detail", task_id=task.id))

    return render_template("task_form.html", categories=CATEGORIES, task=None)


@tasks_bp.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    score, risk, reason = ai_engine.compute_priority(task)
    return render_template("task_detail.html", task=task, score=score, risk=risk, reason=reason)


@tasks_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        task.title = request.form.get("title", task.title).strip()
        task.description = request.form.get("description", "").strip()
        task.category = request.form.get("category", task.category)
        deadline_raw = request.form.get("deadline")
        if deadline_raw:
            try:
                task.deadline = datetime.fromisoformat(deadline_raw)
            except ValueError:
                flash("That deadline doesn't look right.", "error")
                return render_template("task_form.html", categories=CATEGORIES, task=task)
        task.estimated_minutes = int(request.form.get("estimated_minutes") or task.estimated_minutes)
        task.importance = int(request.form.get("importance") or task.importance)
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("tasks.task_detail", task_id=task.id))

    return render_template("task_form.html", categories=CATEGORIES, task=task)


@tasks_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Nice work -- \"{task.title}\" is done.", "success")
    return redirect(request.referrer or url_for("tasks.dashboard"))


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/breakdown", methods=["POST"])
@login_required
def breakdown_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    steps, source = ai_engine.breakdown_task(task)
    task.set_steps(steps, source)
    db.session.commit()
    return redirect(url_for("tasks.task_detail", task_id=task.id))


@tasks_bp.route("/calendar")
@login_required
def calendar():
    tasks = _user_tasks()
    if ai_engine.sync_missed(tasks):
        db.session.commit()

    scheduled = [t for t in tasks if t.scheduled_start and t.status in ("pending", "in_progress")]
    scheduled.sort(key=lambda t: t.scheduled_start)

    by_day = {}
    for t in scheduled:
        day = t.scheduled_start.strftime("%A, %d %b")
        by_day.setdefault(day, []).append(t)

    unscheduled = [t for t in tasks if not t.scheduled_start and t.status in ("pending", "in_progress")]
    return render_template("calendar.html", by_day=by_day, unscheduled=unscheduled)


@tasks_bp.route("/calendar/auto-schedule", methods=["POST"])
@login_required
def auto_schedule():
    tasks = _user_tasks()
    plan = ai_engine.auto_schedule(tasks)
    for item in plan:
        item["task"].scheduled_start = item["start"]
        item["task"].scheduled_end = item["end"]
    db.session.commit()
    flash(f"Auto-scheduled {len(plan)} task(s) into your day.", "success")
    return redirect(url_for("tasks.calendar"))
