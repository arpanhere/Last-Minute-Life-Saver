# The Last-Minute Life Saver

An AI-powered productivity companion that doesn't just remind you about
deadlines — it tells you, every time you open it, the *one thing* you
should be doing right now, why, and how to actually get it done.

Built for the challenge: *"Students, professionals, and entrepreneurs
frequently miss deadlines... existing tools rely on passive reminders
that are easy to ignore."* This is the opposite of a passive reminder.

---

## The core idea

Most to-do apps hand you a flat list and let you decide what matters.
This app makes that decision for you, continuously, using a transparent
scoring engine — and then helps you act, instead of just notifying you.

The home screen is built around one question: **"What should I actually
do right now?"** Everything else (the task list, the calendar, the
habits) supports that one answer.

---

## Features, mapped to the brief

| Brief asked for | What's implemented |
|---|---|
| Intelligent task prioritization | `ai_engine.compute_priority()` scores every task from urgency (time left vs. time needed) + importance, and labels it overdue / critical / at-risk / watch / safe |
| AI-powered scheduling assistance | "Auto-schedule my day" greedily slots pending tasks into working hours, highest priority first, skipping lunch, across days if needed |
| Personalized productivity recommendations | `personalized_recommendations()` mines the user's own completed/missed history (on-time rate, most-missed category, how long tasks sit before being started) into 2–4 concrete tips |
| Context-aware reminders | The "Right now" card's tone and the live countdown change with risk level — a task due in 5 days reads completely differently from one due in 40 minutes |
| Calendar integration | A day-by-day agenda view of auto-scheduled tasks |
| Goal and habit tracking | Daily/weekly habits with streak counting and longest-streak tracking |
| Voice-enabled assistance | Tap the mic, say "remind me to pay the hostel bill by Friday 6pm" — it's parsed into a real task and confirmed back out loud |
| Autonomous task planning and execution | "Break it down" turns one vague task into 3–5 concrete ordered steps, using Claude when available |

---

## Honest AI, with a real fallback

Two features call the Anthropic API when `ANTHROPIC_API_KEY` is set:
**task breakdown** and **voice parsing**. Both are also fully implemented
as deterministic, inspectable Python (rule-based step templates per
category; a small regex-based date/time parser) so the app **never
breaks and never fakes a result** if no key is configured — it just
quietly uses the simpler engine instead. The navbar shows which mode is
active ("● AI live" vs "○ Heuristic mode") so this is never hidden.

The prioritization engine, scheduler, and recommendation engine are
intentionally rule-based rather than LLM calls — they need to run
instantly, deterministically, and for free every time the dashboard
loads, and a transparent formula is something a stressed user can
actually trust and reason about ("why is this task on top?").

---

## Quick start

```bash
cd lastminute
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# optional: enables real Claude-powered breakdown & voice parsing
cp .env.example .env             # then fill in ANTHROPIC_API_KEY

python seed.py                  # creates a demo account with sample tasks
python run.py
```

Open **http://127.0.0.1:5000** and log in with `demo` / `demo1234`, or
register your own account.

`smoke_test.py` exercises every route end-to-end with Flask's test
client (`python smoke_test.py`) — useful if you change anything.

---

## A 90-second demo script

1. **Log in as `demo`.** The dashboard immediately shows a "Right now"
   card with a live countdown and a plain-English reason, plus a
   ranked queue underneath it.
2. Open the top task and click **Break it down** — watch a vague task
   turn into an ordered checklist.
3. Go to **Calendar → Auto-schedule my day** — every pending task gets
   a real time slot, most urgent first.
4. Tap the **mic** in the corner and say *"remind me to call the bank
   tomorrow at 11am"* — it's parsed, saved, and read back to you.
5. Add a habit on the **Habits** page and check in to start a streak.

---

## Architecture

```
app/
  __init__.py      Flask app factory, blueprint + extension wiring
  models.py        User, Task, Habit (SQLAlchemy)
  ai_engine.py     The "brain": prioritization, breakdown, scheduling,
                    recommendations, voice parsing (AI + heuristic fallback)
  auth.py          Register / login / logout
  tasks.py         Dashboard, task CRUD, breakdown, calendar, auto-schedule
  habits.py        Habit CRUD + streak check-in
  api.py           JSON endpoints: voice capture, whats-next, breakdown
  templates/       Server-rendered Jinja2 views
  static/          CSS ("mission control" design system) + vanilla JS
                    (live countdowns, Web Speech API voice capture)
run.py             Entry point
seed.py            Demo data
```

Plain Flask + SQLAlchemy + Flask-Login, server-rendered with a little
vanilla JS for the parts that benefit from it (countdown ticking, voice
capture, AJAX breakdown). No build step, no JS framework — anyone can
clone this and have it running in under a minute.

---

## What's next (beyond a hackathon prototype)

- Real calendar sync (Google Calendar / Outlook) instead of an in-app agenda
- Push notifications / SMS / WhatsApp nudges as deadlines approach, not just in-app
- A phone-call "wake-up call" mode for truly last-minute deadlines
- Smarter scheduling that reads existing calendar events as busy time
- Per-step completion tracking (not just per-task) in the breakdown checklist
- A mobile app shell so the voice capture works one-handed, anywhere
