"""
uninstall_usbkey.py
Run as Administrator to fully remove the USB 2FA (Python) setup.
"""

import ctypes
import shutil
import subprocess
import sys
import os


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


if not is_admin():
    print("Please run this script as Administrator.")
    sys.exit(1)

for task in ["USBKeyAuthPy-Verify", "USBKeyAuthPy-Monitor"]:
    result = subprocess.run(["schtasks", "/delete", "/tn", task, "/f"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Removed scheduled task: {task}")
    else:
        print(f"Task {task} not found (already removed?)")

shutil.rmtree(r"C:\USBKeyAuthPy", ignore_errors=True)
shutil.rmtree(os.path.join(os.environ["ProgramData"], "USBKeyAuthPy"), ignore_errors=True)

print("\nUninstall complete. Note: the .usbkey folder on the pendrive itself was left in place (harmless) - delete it manually if you want it fully gone.")
