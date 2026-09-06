#!/usr/bin/env python3
"""
watch_removal.py (Linux version)
Runs continuously via a systemd --user service. Does two things:

1. Polls every 2 seconds for the registered pendrive's hardware serial
   (via lsblk). If it was present and disappears, locks the session
   using `loginctl lock-sessions`.

2. Polls the session's LockedHint (via `loginctl show-session`) to
   detect lock -> unlock transitions, and re-spawns verify_2fa.py each
   time, matching the Windows version's "re-prompt on every unlock"
   behavior. This depends on the desktop environment correctly telling
   systemd-logind when the screen is locked/unlocked - true for GNOME
   and KDE (covering most Debian/Arch desktop setups), but not
   guaranteed on every minimal window manager. If LockedHint isn't
   available, this script logs that clearly and the removal-lock
   feature still works normally either way.
"""

import datetime
import json
import os
import subprocess
import sys
import time

CONFIG_DIR = os.path.expanduser("~/.config/usbkeyauth")
LOG_FILE = os.path.join(CONFIG_DIR, "watch-log.txt")
os.makedirs(CONFIG_DIR, exist_ok=True)

_log_fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
sys.stdout = _log_fh
sys.stderr = _log_fh


def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")


log("watch_removal started.")

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
if not os.path.exists(CONFIG_FILE):
    log("Config file not found - exiting.")
    sys.exit(0)

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    EXPECTED_SERIAL = config["expected_serial"]
    log(f"Watching for serial: {EXPECTED_SERIAL}")
except Exception as e:
    log(f"FATAL: could not read config: {e}")
    sys.exit(1)

INSTALL_DIR = os.path.expanduser("~/.local/share/usbkeyauth")
VERIFY_SCRIPT = os.path.join(INSTALL_DIR, "verify_2fa.py")


def get_session_id():
    """Find this user's active graphical session ID via loginctl."""
    sid = os.environ.get("XDG_SESSION_ID")
    if sid:
        return sid
    try:
        result = subprocess.run(["loginctl", "list-sessions", "--no-legend"],
                                 capture_output=True, text=True)
        user = os.environ.get("USER", "")
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == user:
                return parts[0]
    except Exception as e:
        log(f"get_session_id error: {e}")
    return None


def is_session_locked(session_id):
    """Checks systemd-logind's LockedHint for this session. Depends on the
    desktop environment correctly reporting lock state to logind - true
    for GNOME and KDE, which covers most Debian/Arch desktop setups, but
    not guaranteed on every minimal window manager."""
    try:
        result = subprocess.run(
            ["loginctl", "show-session", session_id, "-p", "LockedHint", "--value"],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "yes"
    except Exception as e:
        log(f"is_session_locked error: {e}")
        return None  # unknown - caller should not act on this


def spawn_verify_prompt():
    try:
        subprocess.Popen(
            [sys.executable, VERIFY_SCRIPT],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log("Spawned verify_2fa.py after unlock.")
    except Exception as e:
        log(f"spawn_verify_prompt error: {e}")


def key_present():
    result = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,SERIAL,TRAN"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)

    def walk(devices):
        for dev in devices:
            if (dev.get("serial") or "").strip() == EXPECTED_SERIAL:
                return True
            if walk(dev.get("children", [])):
                return True
        return False

    return walk(data.get("blockdevices", []))


def lock_session():
    subprocess.run(["loginctl", "lock-sessions"])


try:
    was_present = key_present()
    log(f"Initial drive present state: {was_present}")
except Exception as e:
    log(f"Initial check failed, assuming present to be safe: {e}")
    was_present = True

session_id = get_session_id()
if session_id:
    log(f"Monitoring session ID: {session_id}")
else:
    log("Could not determine session ID - unlock re-prompt will not work, only removal-lock will.")

was_locked = is_session_locked(session_id) if session_id else None

consecutive_errors = 0

while True:
    time.sleep(2)
    try:
        is_present = key_present()
        consecutive_errors = 0

        if was_present and not is_present:
            log("Drive removed - locking session.")
            lock_session()

        was_present = is_present

        # Re-prompt for the pendrive password every time the session
        # transitions from locked to unlocked - this is what matches the
        # Windows version's "on unlock" trigger.
        if session_id:
            now_locked = is_session_locked(session_id)
            if now_locked is not None:
                if was_locked and not now_locked:
                    log("Session unlocked - re-prompting for pendrive password.")
                    spawn_verify_prompt()
                was_locked = now_locked

    except Exception as e:
        consecutive_errors += 1
        log(f"Loop error (#{consecutive_errors}): {e}")
        if consecutive_errors >= 10:
            log("10 consecutive errors - lsblk may be failing. Still retrying, not giving up.")
