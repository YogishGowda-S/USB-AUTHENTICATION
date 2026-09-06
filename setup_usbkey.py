#!/usr/bin/env python3
"""
setup_usbkey.py (Linux version)
Run this ONCE, with your pendrive plugged in and mounted.
Works on any systemd-based distro (Debian/Ubuntu, Arch, Fedora, etc.)
since it only relies on standard tools: lsblk, udevadm, systemd --user.

Dependencies (install first):
  Debian/Ubuntu: sudo apt install python3-tk lsblk udev
  Arch:          sudo pacman -S tk util-linux systemd
  (lsblk and udevadm are part of util-linux/systemd and are already
  present on virtually all mainstream distros by default.)
"""

import getpass
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys

CONFIG_DIR = os.path.expanduser("~/.config/usbkeyauth")
SYSTEMD_USER_DIR = os.path.expanduser("~/.config/systemd/user")
INSTALL_DIR = os.path.expanduser("~/.local/share/usbkeyauth")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(SYSTEMD_USER_DIR, exist_ok=True)
os.makedirs(INSTALL_DIR, exist_ok=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
shutil.copy(os.path.join(script_dir, "verify_2fa.py"), os.path.join(INSTALL_DIR, "verify_2fa.py"))
shutil.copy(os.path.join(script_dir, "watch_removal.py"), os.path.join(INSTALL_DIR, "watch_removal.py"))


def get_usb_disks():
    """Uses lsblk (present on every mainstream distro) to list USB disks
    with their serial number and mountpoint, as JSON."""
    result = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,SERIAL,MOUNTPOINT,TRAN,MODEL"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Error running lsblk:", result.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)
    disks = []

    def walk(devices):
        for dev in devices:
            if dev.get("tran") == "usb" and dev.get("serial"):
                mountpoint = dev.get("mountpoint")
                # If the disk itself has no mountpoint, check its children (partitions)
                if not mountpoint and "children" in dev:
                    for child in dev["children"]:
                        if child.get("mountpoint"):
                            mountpoint = child["mountpoint"]
                            break
                disks.append({
                    "name": dev.get("name"),
                    "serial": dev.get("serial", "").strip(),
                    "model": dev.get("model", "").strip(),
                    "mountpoint": mountpoint,
                })
            if "children" in dev:
                walk(dev["children"])

    walk(data.get("blockdevices", []))
    return disks


print("Scanning for connected USB drives...")
drives = [d for d in get_usb_disks() if d["mountpoint"]]

if not drives:
    print("No mounted USB drives found. Plug in and mount your pendrive first,")
    print("then re-run this script. (Most file managers auto-mount when you")
    print("open the drive - make sure a file manager window for it is open.)")
    sys.exit(1)

print("\nFound the following USB drives:\n")
for i, d in enumerate(drives):
    print(f"[{i}] {d['mountpoint']}  {d['model']}  (Serial: {d['serial']})")

choice = input("\nEnter the number of the drive to use as your security key: ")
try:
    selected = drives[int(choice)]
except (ValueError, IndexError):
    print("Invalid selection.")
    sys.exit(1)

print(f"\nSelected: {selected['mountpoint']} (Serial: {selected['serial']})")

pw1 = getpass.getpass("Set a password for this pendrive key: ")
pw2 = getpass.getpass("Confirm password: ")

if pw1 != pw2:
    print("Passwords did not match. Re-run the script.")
    sys.exit(1)

salt = secrets.token_hex(16)
password_hash = hashlib.sha256((salt + pw1).encode("utf-8")).hexdigest()

key_folder = os.path.join(selected["mountpoint"], ".usbkey")
os.makedirs(key_folder, exist_ok=True)
with open(os.path.join(key_folder, "auth.dat"), "w", encoding="utf-8") as f:
    json.dump({"salt": salt, "hash": password_hash}, f)

with open(os.path.join(CONFIG_DIR, "config.json"), "w", encoding="utf-8") as f:
    json.dump({"expected_serial": selected["serial"]}, f)

print("\nPendrive key registered.")

# --- Create systemd --user service files ---
python_path = sys.executable

verify_service = f"""[Unit]
Description=USB Key 2FA prompt

[Service]
Type=oneshot
ExecStart={python_path} {INSTALL_DIR}/verify_2fa.py

[Install]
WantedBy=default.target
"""

monitor_service = f"""[Unit]
Description=USB Key removal watcher

[Service]
Type=simple
ExecStart={python_path} {INSTALL_DIR}/watch_removal.py
Restart=on-failure

[Install]
WantedBy=default.target
"""

with open(os.path.join(SYSTEMD_USER_DIR, "usbkeyauth-verify.service"), "w") as f:
    f.write(verify_service)
with open(os.path.join(SYSTEMD_USER_DIR, "usbkeyauth-monitor.service"), "w") as f:
    f.write(monitor_service)

subprocess.run(["systemctl", "--user", "daemon-reload"])
subprocess.run(["systemctl", "--user", "enable", "usbkeyauth-verify.service"])
subprocess.run(["systemctl", "--user", "enable", "usbkeyauth-monitor.service"])

print("\nSetup complete.")
print("Two systemd user services were created: 'usbkeyauth-verify' and 'usbkeyauth-monitor'.")
print("They are enabled and will start at your next graphical login.")
print("\nIMPORTANT: test manually first (see README) before trusting this automatically.")
print("To remove everything, run uninstall_usbkey.py")
