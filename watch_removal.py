"""
watch_removal.py
Runs hidden in the background from logon onward.
Polls every 2 seconds for the registered pendrive's hardware serial.
If it was present and disappears, locks the workstation immediately.

FIX: previously the whole while-loop was wrapped in ONE try/except, so
a single transient error anywhere (e.g. a momentary WMI hiccup) would
break out of the loop and end the script permanently - silently, with
no visible error, which is why it looked like "nothing happens" on
removal even though the task technically ran and "completed successfully".

Now each loop iteration has its own try/except, so one bad iteration
just gets logged and skipped - the watcher keeps running no matter what.
"""

import ctypes
import datetime
import json
import os
import sys
import time

CONFIG_DIR = os.path.join(os.environ["ProgramData"], "USBKeyAuthPy")
LOG_FILE = os.path.join(CONFIG_DIR, "watch-log.txt")
os.makedirs(CONFIG_DIR, exist_ok=True)

_log_fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
sys.stdout = _log_fh
sys.stderr = _log_fh


def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")


log("watch_removal started.")

try:
    import wmi
except ImportError as e:
    log(f"FATAL: could not import wmi module: {e}")
    sys.exit(1)

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


def key_present():
    c = wmi.WMI()
    for disk in c.Win32_DiskDrive(InterfaceType="USB"):
        if (disk.SerialNumber or "").strip() == EXPECTED_SERIAL:
            return True
    return False


try:
    was_present = key_present()
    log(f"Initial drive present state: {was_present}")
except Exception as e:
    log(f"Initial check failed, assuming present to be safe: {e}")
    was_present = True

consecutive_errors = 0

while True:
    time.sleep(2)
    try:
        is_present = key_present()
        consecutive_errors = 0

        if was_present and not is_present:
            log("Drive removed - locking workstation.")
            ctypes.windll.user32.LockWorkStation()

        was_present = is_present
    except Exception as e:
        consecutive_errors += 1
        log(f"Loop error (#{consecutive_errors}): {e}")
        # A single bad check doesn't mean the drive was removed - skip
        # this cycle rather than assuming anything. If WMI is genuinely
        # broken repeatedly, log it clearly so it's visible in the file.
        if consecutive_errors >= 10:
            log("10 consecutive errors - WMI may be broken. Still retrying, not giving up.")