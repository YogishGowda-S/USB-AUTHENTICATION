"""
verify_2fa.py
Runs automatically at logon and at unlock (via Task Scheduler).
Shows a normal, closable window asking for your pendrive password once
the correct pendrive (matched by hardware serial) is detected.

SAFETY DESIGN CHANGE: earlier versions used a fullscreen, always-on-top,
close-button-disabled window. That caused a genuine lockout situation
when it froze and nothing (not even Escape) could close it. This version
is deliberately a normal window - closable with the X button, Alt+F4, or
Escape, just like any other app. It is easier to defeat, which is an
acceptable and intentional tradeoff: you should never be trapped by a
window on your own computer.
"""

import datetime
import hashlib
import json
import os
import sys
import tkinter as tk

CONFIG_DIR = os.path.join(os.environ["ProgramData"], "USBKeyAuthPy")
LOG_FILE = os.path.join(CONFIG_DIR, "verify-log.txt")
os.makedirs(CONFIG_DIR, exist_ok=True)

# If there's a real console (we were run with 'py', not 'pythonw'), keep
# printing to it AND to the log file. If there's no console (pythonw.exe,
# the real scheduled-task situation), only the log file is used - this is
# what prevents the original crash-on-crash freeze bug.
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
    log(f"Expecting serial: {EXPECTED_SERIAL}")
except Exception as e:
    log(f"FATAL: could not read config: {e}")
    sys.exit(1)


def get_key_drive():
    try:
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive(InterfaceType="USB"):
            if (disk.SerialNumber or "").strip() == EXPECTED_SERIAL:
                for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                    for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                        return logical_disk.DeviceID
        return None
    except Exception as e:
        log(f"get_key_drive error: {e}")
        return None


def check_password(drive_letter, entered_password):
    try:
        auth_path = os.path.join(drive_letter + "\\", ".usbkey", "auth.dat")
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
root.geometry("500x300+400+200")
root.configure(bg="#141419")
# Deliberately NOT fullscreen, NOT topmost, and the X button and Alt+F4
# work normally. Safety comes first - this window can always be closed
# like any other window, no exceptions, no special key needed.
root.lift()
root.attributes("-topmost", True)
root.after(1500, lambda: root.attributes("-topmost", False))
root.focus_force()

log("A SEPARATE small window titled 'USB Key 2FA' should now be visible on your screen (not this console). Look for it in your taskbar if you don't see it.")


def emergency_exit(event=None):
    log("Window closed by user.")
    root.destroy()


root.bind_all("<Escape>", emergency_exit)

label = tk.Label(
    root, text="Insert your USB key...", fg="white", bg="#141419",
    font=("Segoe UI", 14), wraplength=440
)
label.place(relx=0.5, rely=0.25, anchor="center")

password_var = tk.StringVar()
entry = tk.Entry(
    root, textvariable=password_var, show="*", font=("Segoe UI", 14),
    justify="center", width=24, bd=0, relief="flat",
    bg="#2a2a33", fg="white", insertbackground="white"
)

status_label = tk.Label(root, text="", fg="#ff5533", bg="#141419", font=("Segoe UI", 11))

drive_shown = {"visible": False}


def on_enter(event=None):
    global authenticated
    try:
        drive_letter = get_key_drive()
        if not drive_letter:
            status_label.config(text="Key removed. Re-insert it.")
            status_label.place(relx=0.5, rely=0.75, anchor="center")
            return
        if check_password(drive_letter, password_var.get()):
            authenticated = True
            log("Password correct - closing prompt.")
            root.destroy()
        else:
            status_label.config(text="Incorrect password.")
            status_label.place(relx=0.5, rely=0.75, anchor="center")
            password_var.set("")
    except Exception as e:
        log(f"on_enter error: {e}")


entry.bind("<Return>", on_enter)


def poll():
    try:
        drive_letter = get_key_drive()
        if drive_letter and not drive_shown["visible"]:
            label.config(text="USB key detected. Enter pendrive password:")
            entry.place(relx=0.5, rely=0.5, anchor="center", height=40)
            entry.focus_set()
            drive_shown["visible"] = True
        elif not drive_letter and drive_shown["visible"]:
            label.config(text="Insert your USB key...")
            entry.place_forget()
            status_label.place_forget()
            drive_shown["visible"] = False
    except Exception as e:
        log(f"poll error: {e}")
    finally:
        # This ALWAYS runs, even if something above threw an error -
        # this is what guarantees polling never silently dies again.
        root.after(800, poll)


root.after(800, poll)

try:
    root.mainloop()
except Exception as e:
    log(f"mainloop crashed: {e}")

log("verify_2fa exiting.")
_log_fh.close()