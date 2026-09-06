#!/usr/bin/env python3
"""
verify_2fa.py (Linux version)
Runs at graphical login via a systemd --user service.
Shows a fullscreen prompt for the pendrive password once the correct
pendrive (matched by hardware serial via lsblk) is detected and mounted.

Same design choice as the Windows version, made deliberately after real
testing: fullscreen, always-on-top, no close button - and intentionally
no in-app override, at the project owner's request. If it ever hangs,
use your desktop environment's own task manager (or `pkill -f verify_2fa`
from another terminal/TTY) to close it - this does not need root.
"""

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tkinter as tk

CONFIG_DIR = os.path.expanduser("~/.config/usbkeyauth")
LOG_FILE = os.path.join(CONFIG_DIR, "verify-log.txt")
os.makedirs(CONFIG_DIR, exist_ok=True)

_console_stdout = sys.stdout
_log_fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)


def log(msg):
    line = f"[{datetime.datetime.now()}] {msg}"
    _log_fh.write(line + "\n")
    _log_fh.flush()
    if _console_stdout is not None:
        try:
            _console_stdout.write(line + "\n")
            _console_stdout.flush()
        except Exception:
            pass


sys.stdout = _log_fh
sys.stderr = _log_fh

log("verify_2fa started.")

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
if not os.path.exists(CONFIG_FILE):
    log("Config file not found - exiting.")
    sys.exit(0)

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    EXPECTED_SERIAL = config["expected_serial"]
    log(f"Expecting serial: {EXPECTED_SERIAL}")
except Exception as e:
    log(f"FATAL: could not read config: {e}")
    sys.exit(1)


def get_key_mountpoint():
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SERIAL,MOUNTPOINT,TRAN"],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout)

        def walk(devices):
            for dev in devices:
                if (dev.get("serial") or "").strip() == EXPECTED_SERIAL:
                    if dev.get("mountpoint"):
                        return dev["mountpoint"]
                    for child in dev.get("children", []):
                        if child.get("mountpoint"):
                            return child["mountpoint"]
                found = walk(dev.get("children", []))
                if found:
                    return found
            return None

        return walk(data.get("blockdevices", []))
    except Exception as e:
        log(f"get_key_mountpoint error: {e}")
        return None


def check_password(mountpoint, entered_password):
    try:
        auth_path = os.path.join(mountpoint, ".usbkey", "auth.dat")
        if not os.path.exists(auth_path):
            return False
        with open(auth_path, "r", encoding="utf-8") as f:
            auth = json.load(f)
        computed = hashlib.sha256((auth["salt"] + entered_password).encode("utf-8")).hexdigest()
        return computed == auth["hash"]
    except Exception as e:
        log(f"check_password error: {e}")
        return False


authenticated = False

root = tk.Tk()
root.title("USB Key 2FA")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.configure(bg="#141419")
root.protocol("WM_DELETE_WINDOW", lambda: None)
root.bind("<Alt-F4>", lambda e: "break")  # block Alt+F4, matching Windows lockdown
root.lift()
root.focus_force()

log("Fullscreen prompt shown.")

label = tk.Label(
    root, text="Insert your USB key...", fg="white", bg="#141419",
    font=("Sans", 22)
)
label.place(relx=0.5, rely=0.4, anchor="center")

password_var = tk.StringVar()
entry = tk.Entry(
    root, textvariable=password_var, show="*", font=("Sans", 18),
    justify="center", width=28, bd=0, relief="flat",
    bg="#2a2a33", fg="white", insertbackground="white"
)

status_label = tk.Label(root, text="", fg="#ff5533", bg="#141419", font=("Sans", 13))

drive_shown = {"visible": False}


def on_enter(event=None):
    global authenticated
    try:
        mountpoint = get_key_mountpoint()
        if not mountpoint:
            status_label.config(text="Key removed. Re-insert it.")
            status_label.place(relx=0.5, rely=0.56, anchor="center")
            return
        if check_password(mountpoint, password_var.get()):
            authenticated = True
            log("Password correct - closing prompt.")
            root.destroy()
        else:
            status_label.config(text="Incorrect password.")
            status_label.place(relx=0.5, rely=0.56, anchor="center")
            password_var.set("")
    except Exception as e:
        log(f"on_enter error: {e}")


entry.bind("<Return>", on_enter)


def poll():
    try:
        mountpoint = get_key_mountpoint()
        if mountpoint and not drive_shown["visible"]:
            label.config(text="USB key detected. Enter pendrive password:")
            entry.place(relx=0.5, rely=0.47, anchor="center", height=44)
            entry.focus_set()
            drive_shown["visible"] = True
        elif not mountpoint and drive_shown["visible"]:
            label.config(text="Insert your USB key...")
            entry.place_forget()
            status_label.place_forget()
            drive_shown["visible"] = False
    except Exception as e:
        log(f"poll error: {e}")
    finally:
        root.after(800, poll)


root.after(800, poll)

try:
    root.mainloop()
except Exception as e:
    log(f"mainloop crashed: {e}")

log("verify_2fa exiting.")
_log_fh.close()
