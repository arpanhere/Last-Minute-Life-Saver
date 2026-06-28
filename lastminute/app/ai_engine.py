"""
ai_engine.py
------------
The "brain" of The Last-Minute Life Saver.

Everything here is plain, inspectable Python so it always works offline.
Wherever a real LLM call genuinely adds value (turning a messy task into
concrete steps, or turning a spoken sentence into structured data), the
engine tries Anthropic's API first and falls back to a deterministic
heuristic if no ANTHROPIC_API_KEY is configured or the call fails.
That fallback is not a stub -- it is a fully working rule-based engine,
so the app is honest about what is "real AI" vs. "smart defaults".
"""
import json
import os
import re
from datetime import datetime, timedelta

try:
    import anthropic
    _ANTHROPIC_IMPORTED = True
except ImportError:
    _ANTHROPIC_IMPORTED = False

MODEL_NAME = "claude-sonnet-4-6"


def _get_client():
    """Return an Anthropic client if an API key is configured, else None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not _ANTHROPIC_IMPORTED:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


def ai_is_configured():
    return _get_client() is not None


# ---------------------------------------------------------------------------
# 1. Intelligent task prioritization
# ---------------------------------------------------------------------------

def hours_remaining(deadline, now=None):
    now = now or datetime.utcnow()
    return (deadline - now).total_seconds() / 3600.0


def compute_priority(task, now=None):
    """Score a single task. Higher score = act on this sooner.

    Returns (score, risk, reason).
    risk is one of: overdue, critical, at_risk, watch, safe
    """
    now = now or datetime.utcnow()
    hrs = hours_remaining(task.deadline, now)
    importance = task.importance or 3
    needed_hours = max((task.estimated_minutes or 30) / 60.0, 0.25)

    if hrs <= 0:
        urgency, risk = 100, "overdue"
    else:
        ratio = hrs / needed_hours
        if ratio <= 1:
            urgency, risk = 95, "critical"
        elif ratio <= 3:
            urgency, risk = 75, "at_risk"
        elif ratio <= 8:
            urgency, risk = 50, "watch"
        else:
            urgency, risk = max(5, 30 - min(hrs / 24, 25)), "safe"

    score = round(urgency * 0.65 + importance * 7, 1)
    reason = _explain(task, hrs, risk)
    return score, risk, reason


def _explain(task, hrs, risk):
    needed_h = round((task.estimated_minutes or 30) / 60.0, 1)
    if risk == "overdue":
        return "This passed its deadline. Either do it right now or reschedule it deliberately."
    if risk == "critical":
        return f"Needs about {needed_h}h and you only have {round(hrs, 1)}h left. Start this now."
    if risk == "at_risk":
        return f"Due in {round(hrs, 1)}h. Start soon so you're not cutting it close."
    if risk == "watch":
        return f"Due in {round(hrs, 1)}h. No rush yet, but block time for it today."
    return f"Due in about {round(hrs / 24, 1)} days. Comfortable for now."


def sync_missed(tasks):
    """Flip overdue pending/in_progress tasks to 'missed'. Returns count changed."""
    now = datetime.utcnow()
    changed = 0
    for t in tasks:
        if t.status in ("pending", "in_progress") and t.deadline < now:
            t.status = "missed"
            changed += 1
    return changed


def rank_tasks(tasks, now=None):
    now = now or datetime.utcnow()
    scored = [
        {"task": t, "score": s, "risk": r, "reason": reason}
        for t in tasks
        for s, r, reason in [compute_priority(t, now)]
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def whats_next(tasks, now=None):
    """The single most important thing to do right now, or None."""
    pending = [t for t in tasks if t.status in ("pending", "in_progress")]
    if not pending:
        return None
    return rank_tasks(pending, now)[0]


# ---------------------------------------------------------------------------
# 2. Autonomous task planning: break a task into concrete steps
# ---------------------------------------------------------------------------

_STEP_TEMPLATES = {
    "bill": [
        "Confirm the exact amount and the due date",
        "Make sure funds or your payment method are ready",
        "Make the payment",
        "Save the receipt or confirmation number",
    ],
    "interview": [
        "Research the company and the role",
        "Prepare answers to likely questions",
        "Sort logistics: route, video link, or outfit",
        "Do one mock run-through out loud",
        "Attend the interview",
    ],
    "exam": [
        "List the topics or chapters to cover",
        "Build a short revision timetable",
        "Active-recall practice: past papers or flashcards",
        "Light final review the day before",
    ],
    "assignment": [
        "Re-read the brief and note every requirement",
        "Draft an outline or skeleton",
        "Write or build the core content",
        "Review against the rubric, then submit",
    ],
    "meeting": [
        "Confirm time, link or location, and attendees",
        "Prepare an agenda or talking points",
        "Gather any files or numbers you'll need",
        "Send a short follow-up afterwards",
    ],
    "general": [
        "Clarify exactly what 'done' looks like",
        "Break the work into one sittable chunk",
        "Do the work",
        "Double-check it and close it out",
    ],
}


def _guess_template_key(category, title):
    text = f"{category or ''} {title or ''}".lower()
    for key in _STEP_TEMPLATES:
        if key in text:
            return key
    return "general"


def breakdown_task(task):
    """Return (steps: list[str], source: 'ai' | 'heuristic')."""
    client = _get_client()
    if client is not None:
        try:
            prompt = (
                "Break this task into 3 to 5 short, concrete, sequential action "
                "steps a person can actually follow. Reply with ONLY a JSON array "
                "of plain strings -- no markdown, no preamble, no extra keys.\n\n"
                f"Title: {task.title}\n"
                f"Category: {task.category}\n"
                f"Description: {task.description or '(none)'}\n"
                f"Deadline: {task.deadline.isoformat()}\n"
                f"Estimated minutes needed: {task.estimated_minutes}"
            )
            resp = client.messages.create(
                model=MODEL_NAME,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            ).strip()
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
            steps = json.loads(text)
            steps = [str(s).strip() for s in steps if str(s).strip()]
            if steps:
                return steps[:6], "ai"
        except Exception:
            pass  # fall through to heuristic

    key = _guess_template_key(task.category, task.title)
    return list(_STEP_TEMPLATES[key]), "heuristic"


# ---------------------------------------------------------------------------
# 3. AI-powered scheduling assistance
# ---------------------------------------------------------------------------

def auto_schedule(tasks, now=None, day_start=9, day_end=21, lunch_hour=13):
    """Greedily slot pending tasks into a working day, highest priority first.

    Returns a list of dicts: {task, start, end, risk}. Does not write to DB;
    caller decides whether to persist scheduled_start/scheduled_end.
    """
    now = now or datetime.utcnow()
    pending = [t for t in tasks if t.status in ("pending", "in_progress")]
    ranked = rank_tasks(pending, now)

    cursor = now.replace(second=0, microsecond=0)
    cursor += timedelta(minutes=(15 - cursor.minute % 15) % 15)  # round up to next 15 min
    if cursor.hour < day_start:
        cursor = cursor.replace(hour=day_start, minute=0)
    elif cursor.hour >= day_end:
        cursor = (cursor + timedelta(days=1)).replace(hour=day_start, minute=0)

    plan = []
    for item in ranked:
        t = item["task"]
        duration = timedelta(minutes=t.estimated_minutes or 30)

        if cursor.hour == lunch_hour:
            cursor = cursor.replace(hour=lunch_hour + 1, minute=0)
        if cursor.hour >= day_end:
            cursor = (cursor + timedelta(days=1)).replace(hour=day_start, minute=0)

        start = cursor
        end = start + duration
        plan.append({"task": t, "start": start, "end": end, "risk": item["risk"]})
        cursor = end

    return plan


# ---------------------------------------------------------------------------
# 4. Personalized productivity recommendations
# ---------------------------------------------------------------------------

def personalized_recommendations(tasks):
    """Rule-based insights mined from the user's own task history."""
    if not tasks:
        return ["Add a few tasks and I'll start spotting patterns in how you work."]

    tips = []
    completed = [t for t in tasks if t.status == "done" and t.completed_at]
    missed = [t for t in tasks if t.status == "missed"]

    if completed:
        on_time = [t for t in completed if t.completed_at <= t.deadline]
        rate = round(len(on_time) / len(completed) * 100)
        if rate >= 80:
            tips.append(f"You finish {rate}% of tasks before the deadline -- that's a strong track record.")
        elif rate >= 50:
            tips.append(f"You finish {rate}% of tasks on time. Starting your top-ranked task a little earlier could push this higher.")
        else:
            tips.append(f"Only {rate}% of completed tasks beat their deadline. Try using 'Right now' as soon as you sit down to work.")

    if missed:
        counts = {}
        for t in missed:
            counts[t.category] = counts.get(t.category, 0) + 1
        worst = max(counts, key=counts.get)
        tips.append(f"Most of your missed deadlines are '{worst}' tasks -- consider defaulting those to start a day earlier.")

    lags = [
        (t.completed_at - t.created_at).total_seconds() / 3600
        for t in completed
        if t.created_at and t.completed_at
    ]
    if lags and (sum(lags) / len(lags)) > 48:
        tips.append("You tend to let tasks sit for a couple of days before starting. The 'Right now' card is built to short-circuit exactly that.")

    big_and_late = [
        t for t in completed
        if (t.estimated_minutes or 0) >= 90 and t.completed_at > t.deadline
    ]
    if big_and_late:
        tips.append("Tasks over 90 minutes are the ones most likely to run late -- use 'Break it down' to chunk them as soon as you add them.")

    if not tips:
        tips.append("Not enough history yet to spot a pattern -- keep going and check back here.")
    return tips[:4]


# ---------------------------------------------------------------------------
# 5. Voice-enabled assistance: turn a spoken sentence into a task
# ---------------------------------------------------------------------------

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_FILLERS = ["remind me to", "remember to", "i need to", "i have to", "i've got to", "please", "by", "due", "at", "on"]


def _regex_parse_voice(text, now=None):
    """Dependency-free fallback parser for short spoken task commands."""
    now = now or datetime.now()
    t = " " + text.lower().strip() + " "
    hour, minute, day_offset = None, 0, None

    m = re.search(r"\bin (\d+)\s*(minute|hour|day)s?\b", t)
    deadline = None
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {
            "minute": timedelta(minutes=n),
            "hour": timedelta(hours=n),
            "day": timedelta(days=n),
        }[unit]
        deadline = now + delta
        t = t[: m.start()] + " " + t[m.end():]

    tm = re.search(r"\b(\d{1,2})(:(\d{2}))?\s*(am|pm)?\b(?!\s*(minute|hour|day))", t)
    if deadline is None and tm:
        hour = int(tm.group(1))
        minute = int(tm.group(3) or 0)
        ampm = tm.group(4)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            t = t[: tm.start()] + " " + t[tm.end():]
        else:
            hour = None

    if deadline is None:
        if " tomorrow " in t:
            day_offset = 1
            t = t.replace(" tomorrow ", " ")
        elif " tonight " in t:
            day_offset = 0
            hour = hour if hour is not None else 21
            t = t.replace(" tonight ", " ")
        elif " today " in t:
            day_offset = 0
            t = t.replace(" today ", " ")
        else:
            for i, wd in enumerate(_WEEKDAYS):
                if f" {wd} " in t:
                    diff = (i - now.weekday()) % 7
                    day_offset = diff or 7
                    t = t.replace(f" {wd} ", " ")
                    break

        base_day = now + timedelta(days=day_offset if day_offset is not None else 1)
        if hour is not None:
            deadline = base_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            deadline = base_day.replace(hour=21, minute=0, second=0, microsecond=0)

    t = " " + re.sub(r"\s+", " ", t).strip() + " "
    for filler in _FILLERS:
        t = t.replace(f" {filler} ", " ")
    title = re.sub(r"\s+", " ", t).strip()
    title = (title[0].upper() + title[1:]) if title else "New task"

    return {"title": title, "deadline": deadline, "category": "general", "importance": 3}


def parse_voice_command(text, now=None):
    """Turn a spoken sentence into {title, deadline, category, importance}.

    Tries the LLM for robust extraction; falls back to a deterministic
    regex parser so voice capture always works, even with no API key.
    """
    now = now or datetime.now()
    client = _get_client()
    if client is not None:
        try:
            prompt = (
                "Extract a task from this spoken sentence. Reply with ONLY a JSON "
                "object with keys: title (short string), deadline_iso (ISO 8601 "
                "datetime, infer a sensible one if not stated, relative to the "
                f"current moment {now.isoformat()}), category (one of assignment, "
                "exam, bill, interview, meeting, general), importance (integer 1-5). "
                f"Sentence: \"{text}\""
            )
            resp = client.messages.create(
                model=MODEL_NAME,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            out = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            ).strip().strip("`")
            if out.lower().startswith("json"):
                out = out[4:].strip()
            data = json.loads(out)
            deadline = datetime.fromisoformat(data["deadline_iso"])
            return {
                "title": str(data.get("title") or "New task").strip(),
                "deadline": deadline,
                "category": data.get("category") or "general",
                "importance": int(data.get("importance") or 3),
            }
        except Exception:
            pass  # fall through to regex parser

    return _regex_parse_voice(text, now)
