"""Smoke test: hits every major route with the Flask test client."""
import sys
from datetime import datetime, timedelta

from app import create_app
from app.models import db, User

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False

failures = []


def check(name, resp, expect=(200, 302)):
    ok = resp.status_code in expect
    print(f"{'OK ' if ok else 'FAIL'} {name} -> {resp.status_code}")
    if not ok:
        failures.append(name)
        print(resp.data[:600])
    return resp


with app.app_context():
    db.create_all()
    User.query.filter_by(username="smoketest").delete()
    db.session.commit()

client = app.test_client()

check("register", client.post("/register", data={
    "username": "smoketest", "email": "smoketest@example.com", "password": "pw12345"
}))

check("logout", client.get("/logout"))

check("login", client.post("/login", data={"identifier": "smoketest", "password": "pw12345"}))

check("dashboard (empty)", client.get("/dashboard"))

deadline = (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M")
resp = check("new task POST", client.post("/tasks/new", data={
    "title": "Smoke test task",
    "description": "desc",
    "category": "assignment",
    "deadline": deadline,
    "estimated_minutes": "45",
    "importance": "4",
}))

with app.app_context():
    from app.models import Task
    task = Task.query.filter_by(title="Smoke test task").first()
    assert task is not None, "task was not created"
    task_id = task.id

check("dashboard (with task)", client.get("/dashboard"))
check("task list active", client.get("/tasks?status=active"))
check("task list all", client.get("/tasks?status=all"))
check("task detail", client.get(f"/tasks/{task_id}"))
check("edit task GET", client.get(f"/tasks/{task_id}/edit"))
check("breakdown (form route)", client.post(f"/tasks/{task_id}/breakdown"))
check("breakdown (api/json route)", client.post(f"/api/tasks/{task_id}/breakdown"))
check("whats-next api", client.get("/api/whats-next"))
check("complete task", client.post(f"/tasks/{task_id}/complete"))

deadline2 = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
client.post("/tasks/new", data={
    "title": "Second task", "description": "", "category": "bill",
    "deadline": deadline2, "estimated_minutes": "20", "importance": "3",
})

check("calendar", client.get("/calendar"))
check("auto-schedule", client.post("/calendar/auto-schedule"))
check("calendar after schedule", client.get("/calendar"))

import json
check("voice-task api", client.post("/api/voice-task",
      data=json.dumps({"transcript": "remind me to submit the report tomorrow at 5pm"}),
      content_type="application/json"))

check("habits list", client.get("/habits"))
check("new habit", client.post("/habits/new", data={"name": "Read 10 pages", "frequency": "daily"}))

with app.app_context():
    from app.models import Habit
    habit = Habit.query.filter_by(name="Read 10 pages").first()
    habit_id = habit.id

check("habit checkin", client.post(f"/habits/{habit_id}/checkin"))
check("habit checkin again (should no-op)", client.post(f"/habits/{habit_id}/checkin"))
check("habit delete", client.post(f"/habits/{habit_id}/delete"))

check("delete task", client.post(f"/tasks/{task_id}/delete"))

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
else:
    print("ALL ROUTES OK")
