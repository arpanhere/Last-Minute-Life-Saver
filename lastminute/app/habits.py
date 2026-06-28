from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .models import Habit, db

habits_bp = Blueprint("habits", __name__)


@habits_bp.route("/habits")
@login_required
def habit_list():
    habits = Habit.query.filter_by(user_id=current_user.id).order_by(Habit.created_at).all()
    today = date.today()
    return render_template("habits.html", habits=habits, today=today)


@habits_bp.route("/habits/new", methods=["POST"])
@login_required
def new_habit():
    name = request.form.get("name", "").strip()
    frequency = request.form.get("frequency", "daily")
    if not name:
        flash("Give your habit a name.", "error")
        return redirect(url_for("habits.habit_list"))

    habit = Habit(user_id=current_user.id, name=name, frequency=frequency)
    db.session.add(habit)
    db.session.commit()
    flash(f"Tracking \"{name}\" now.", "success")
    return redirect(url_for("habits.habit_list"))


@habits_bp.route("/habits/<int:habit_id>/checkin", methods=["POST"])
@login_required
def checkin(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    today = date.today()

    if habit.last_checkin == today:
        flash("Already checked in for today.", "info")
        return redirect(url_for("habits.habit_list"))

    if habit.last_checkin == today - timedelta(days=1):
        habit.streak += 1
    else:
        habit.streak = 1

    habit.longest_streak = max(habit.longest_streak, habit.streak)
    habit.last_checkin = today
    db.session.commit()
    flash(f"\"{habit.name}\" streak: {habit.streak} day(s).", "success")
    return redirect(url_for("habits.habit_list"))


@habits_bp.route("/habits/<int:habit_id>/delete", methods=["POST"])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.filter_by(id=habit_id, user_id=current_user.id).first_or_404()
    db.session.delete(habit)
    db.session.commit()
    return redirect(url_for("habits.habit_list"))
