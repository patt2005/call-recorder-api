"""
Daily push notification background job.

Fires once per day at TARGET_HOUR_ET (Eastern Time). For every user who has
an FCM token but is either not registered in the tweb backend or has zero
revenue and no trial, it sends a randomly chosen promotional push notification.
"""

import threading
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests as _requests

from database.database import db
from models.user import User
from services.notification_copy_data import pick_random_coherent
from services.push_notification_service import push_notification_service

import logging

logger = logging.getLogger(__name__)

# ── configuration ────────────────────────────────────────────────────────────

EASTERN = ZoneInfo("Asia/Seoul")
TARGET_HOUR_ET = 14          # 2 PM Korea Standard Time
POLL_INTERVAL_SECONDS = 30  # check every 30 minutes

TWEB_BASE_URL = "https://twebbackend-production.up.railway.app"
TWEB_TIMEOUT_SECONDS = 10


# ── tweb client ───────────────────────────────────────────────────────────────

def _get_tweb_app_user(user_id: str) -> dict | None:
    """
    Call GET /api/appuser?userId={user_id} on the tweb backend.
    Returns the parsed JSON dict, or None if the user is not found or the
    request fails.
    """
    try:
        resp = _requests.get(
            f"{TWEB_BASE_URL}/api/appuser",
            params={"userId": user_id},
            timeout=TWEB_TIMEOUT_SECONDS,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("tweb lookup failed for user %s: %s", user_id, exc)
        return None


def _is_paying(app_user: dict | None) -> bool:
    """Return True if the user has revenue > 0 or an active trial."""
    if app_user is None:
        return False
    total_revenue = app_user.get("totalRevenue") or 0
    has_trial = bool(app_user.get("hasTrial"))
    return float(total_revenue) > 0.0 or has_trial


# ── runner ────────────────────────────────────────────────────────────────────

class NotificationRunStats:
    def __init__(self):
        self.run_at: datetime = datetime.now(tz=timezone.utc)
        self.checked: int = 0
        self.eligible: int = 0
        self.sent: int = 0
        self.failed: int = 0

    def __str__(self):
        return (
            f"checked={self.checked} eligible={self.eligible} "
            f"sent={self.sent} failed={self.failed}"
        )


def run_no_revenue_notifications(app_context) -> NotificationRunStats:
    """
    Query users, check tweb, and send promotional notifications to users
    who are not paying and have no active trial.

    Must be called inside a Flask application context.
    """
    import random
    stats = NotificationRunStats()
    rng = random.Random()

    users = (
        db.session.query(User.id, User.fcm_token)
        .filter(User.fcm_token.isnot(None), User.fcm_token != "")
        .all()
    )

    for user_id, fcm_token in users:
        stats.checked += 1

        app_user = _get_tweb_app_user(str(user_id))
        if _is_paying(app_user):
            continue

        stats.eligible += 1
        title, body = pick_random_coherent(rng)

        ok = push_notification_service.send_notification(fcm_token, title, body)
        if ok:
            stats.sent += 1
        else:
            stats.failed += 1

    return stats


# ── scheduler ─────────────────────────────────────────────────────────────────

class NotificationScheduler:
    """
    Background thread that fires the notification runner once per day at
    TARGET_HOUR_ET Eastern Time.
    """

    def __init__(self, flask_app):
        self._app = flask_app
        self._last_sent_date: datetime.date | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.start()

    def start(self):
        print("NotificationScheduler starting...")
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="notification-scheduler",
            daemon=True,
        )
        self._thread.start()

        print("NotificationScheduler started — fires daily at 03:00 ET")
        logger.info(
            "NotificationScheduler started — fires daily at %02d:00 ET",
            TARGET_HOUR_ET,
        )

    def stop(self):
        self._stop_event.set()

    def _run(self):
        self._stop_event.wait(30)

        while not self._stop_event.is_set():
            try:
                self._check_and_run()
            except Exception as exc:
                logger.error("NotificationScheduler iteration failed: %s", exc, exc_info=True)

            self._stop_event.wait(POLL_INTERVAL_SECONDS)

    def _check_and_run(self):
        now_et = datetime.now(tz=EASTERN)
        today_et = now_et.date()

        if now_et.hour != TARGET_HOUR_ET:
            logger.info(
                "NotificationScheduler is not time to run"
            )
            return

        if self._last_sent_date == today_et:
            return

        logger.info(
            "NotificationScheduler firing for %s (ET %02d:%02d)",
            today_et, now_et.hour, now_et.minute,
        )

        with self._app.app_context():
            stats = run_no_revenue_notifications(self._app)

        self._last_sent_date = today_et

        logger.info("NotificationScheduler completed — %s", stats)
