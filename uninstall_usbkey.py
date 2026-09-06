#!/usr/bin/env python3
"""
uninstall_usbkey.py (Linux version)
Removes the systemd --user services and all related files. No root needed.
"""

import os
import shutil
import subprocess

SYSTEMD_USER_DIR = os.path.expanduser("~/.config/systemd/user")
CONFIG_DIR = os.path.expanduser("~/.config/usbkeyauth")
INSTALL_DIR = os.path.expanduser("~/.local/share/usbkeyauth")

for service in ["usbkeyauth-verify.service", "usbkeyauth-monitor.service"]:
    subprocess.run(["systemctl", "--user", "disable", "--now", service], capture_output=True)
    path = os.path.join(SYSTEMD_USER_DIR, service)
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed {service}")

subprocess.run(["systemctl", "--user", "daemon-reload"])

shutil.rmtree(CONFIG_DIR, ignore_errors=True)
shutil.rmtree(INSTALL_DIR, ignore_errors=True)

print("\nUninstall complete. Note: the .usbkey folder on the pendrive itself")
print("was left in place (harmless) - delete it manually if you want it fully gone.")
