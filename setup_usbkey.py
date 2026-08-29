"""
setup_usbkey.py
Run this ONCE, as Administrator, with your pendrive plugged in.
Requires: pip install pywin32 wmi
"""

import ctypes
import getpass
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys

try:
    import wmi
    import win32com.client
except ImportError:
    print("Missing packages. Run this first:")
    print("    pip install pywin32 wmi")
    sys.exit(1)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


if not is_admin():
    print("Please run this script as Administrator (right-click PowerShell/Terminal -> Run as administrator).")
    sys.exit(1)

INSTALL_DIR = r"C:\USBKeyAuthPy"
CONFIG_DIR = os.path.join(os.environ["ProgramData"], "USBKeyAuthPy")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

os.makedirs(INSTALL_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

# Copy the sibling scripts into the install dir so scheduled tasks have a stable path
script_dir = os.path.dirname(os.path.abspath(__file__))
shutil.copy(os.path.join(script_dir, "verify_2fa.py"), os.path.join(INSTALL_DIR, "verify_2fa.py"))
shutil.copy(os.path.join(script_dir, "watch_removal.py"), os.path.join(INSTALL_DIR, "watch_removal.py"))


def get_usb_disks():
    c = wmi.WMI()
    results = []
    for disk in c.Win32_DiskDrive(InterfaceType="USB"):
        for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
            for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                results.append({
                    "model": disk.Model,
                    "serial": (disk.SerialNumber or "").strip(),
                    "drive_letter": logical_disk.DeviceID,
                })
    return results


print("Scanning for connected USB drives...")
drives = get_usb_disks()

if not drives:
    print("No USB drives with an assigned drive letter were found. Plug in your pendrive and re-run this script.")
    sys.exit(1)

print("\nFound the following USB drives:\n")
for i, d in enumerate(drives):
    print(f"[{i}] {d['drive_letter']}  {d['model']}  (Serial: {d['serial']})")

choice = input("\nEnter the number of the drive to use as your security key: ")
try:
    selected = drives[int(choice)]
except (ValueError, IndexError):
    print("Invalid selection.")
    sys.exit(1)

print(f"\nSelected: {selected['drive_letter']} (Serial: {selected['serial']})")

pw1 = getpass.getpass("Set a password for this pendrive key: ")
pw2 = getpass.getpass("Confirm password: ")

if pw1 != pw2:
    print("Passwords did not match. Re-run the script.")
    sys.exit(1)

salt = secrets.token_hex(16)
password_hash = hashlib.sha256((salt + pw1).encode("utf-8")).hexdigest()

key_folder = os.path.join(selected["drive_letter"] + "\\", ".usbkey")
os.makedirs(key_folder, exist_ok=True)
auth_path = os.path.join(key_folder, "auth.dat")
with open(auth_path, "w", encoding="utf-8") as f:
    json.dump({"salt": salt, "hash": password_hash}, f)

# Hide the folder on the pendrive
subprocess.run(["attrib", "+h", "+s", key_folder], shell=True)

with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump({"expected_serial": selected["serial"]}, f)

print("\nPendrive key registered.")

# --- Register scheduled tasks via the Task Scheduler COM API ---
pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(pythonw):
    pythonw = sys.executable  # fallback, will show a console window

service = win32com.client.Dispatch("Schedule.Service")
service.Connect()
root_folder = service.GetFolder("\\")
user_id = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"

TASK_TRIGGER_LOGON = 9
TASK_TRIGGER_SESSION_STATE_CHANGE = 11
TASK_SESSION_UNLOCK = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_INTERACTIVE_TOKEN = 3
TASK_CREATE_OR_UPDATE = 6

# Task 1: verify_2fa - runs at logon AND at unlock
task_def = service.NewTask(0)
task_def.RegistrationInfo.Description = "USB Key 2FA prompt (Python)"
task_def.Settings.Enabled = True
task_def.Settings.StopIfGoingOnBatteries = False
task_def.Settings.DisallowStartIfOnBatteries = False
task_def.Settings.ExecutionTimeLimit = "PT0S"

logon_trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)
logon_trigger.UserId = user_id
logon_trigger.Enabled = True

unlock_trigger = task_def.Triggers.Create(TASK_TRIGGER_SESSION_STATE_CHANGE)
unlock_trigger.StateChange = TASK_SESSION_UNLOCK
unlock_trigger.UserId = user_id
unlock_trigger.Enabled = True

action = task_def.Actions.Create(TASK_ACTION_EXEC)
action.Path = pythonw
action.Arguments = f'"{os.path.join(INSTALL_DIR, "verify_2fa.py")}"'

root_folder.RegisterTaskDefinition(
    "USBKeyAuthPy-Verify", task_def, TASK_CREATE_OR_UPDATE, None, None, TASK_LOGON_INTERACTIVE_TOKEN
)

# Task 2: watch_removal - runs at logon, hidden, loops forever
task_def2 = service.NewTask(0)
task_def2.RegistrationInfo.Description = "USB Key removal watcher (Python)"
task_def2.Settings.Enabled = True
task_def2.Settings.StopIfGoingOnBatteries = False
task_def2.Settings.DisallowStartIfOnBatteries = False
task_def2.Settings.ExecutionTimeLimit = "PT0S"

logon_trigger2 = task_def2.Triggers.Create(TASK_TRIGGER_LOGON)
logon_trigger2.UserId = user_id
logon_trigger2.Enabled = True

action2 = task_def2.Actions.Create(TASK_ACTION_EXEC)
action2.Path = pythonw
action2.Arguments = f'"{os.path.join(INSTALL_DIR, "watch_removal.py")}"'

root_folder.RegisterTaskDefinition(
    "USBKeyAuthPy-Monitor", task_def2, TASK_CREATE_OR_UPDATE, None, None, TASK_LOGON_INTERACTIVE_TOKEN
)

print("\nSetup complete.")
print("Two scheduled tasks were created: 'USBKeyAuthPy-Verify' and 'USBKeyAuthPy-Monitor'.")
print("They will start next time you log on or unlock.")
print("\nIMPORTANT: Test this while you still have another way to get in (e.g. stay logged in on this session).")
print("To remove everything, run uninstall_usbkey.py as Administrator.")
