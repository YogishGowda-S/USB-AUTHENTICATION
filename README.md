# USB Key 2FA for Windows (Python version)

Same idea as the PowerShell version, rewritten in Python:
Windows password (factor 1) -> fullscreen prompt for your pendrive
password (factor 2, only shows once the correct pendrive is detected
by its hardware serial) -> unplug the pendrive at any point and the
workstation instantly locks.

## Requirements
1. **Python must be installed** on the laptop. If it isn't:
   - Go to https://www.python.org/downloads/
   - Download and run the installer
   - **Important:** on the first install screen, check the box
     "Add python.exe to PATH" before clicking Install
2. Open PowerShell/Terminal **as Administrator** and install two packages:
   ```
   pip install pywin32 wmi
   ```

## Files
- `setup_usbkey.py` - run once to register your pendrive and install the tasks
- `verify_2fa.py` - the fullscreen prompt (auto-installed, don't run manually)
- `watch_removal.py` - the background watcher (auto-installed, don't run manually)
- `uninstall_usbkey.py` - removes everything cleanly

## Install
1. Copy this whole folder to your laptop.
2. Plug in the pendrive you want to use as your key.
3. Open PowerShell/Terminal **as Administrator**.
4. `cd` into this folder.
5. Run:
   ```
   python setup_usbkey.py
   ```
6. Pick your pendrive from the numbered list, then set a pendrive password.

The two scheduled tasks (`USBKeyAuthPy-Verify` and `USBKeyAuthPy-Monitor`)
are now active from your next logon/unlock onward.

## Testing safely (important)
- Stay logged into your current session while testing.
- Test manually first: run `python verify_2fa.py` directly so you can
  see any errors printed in the console, before trusting the automatic
  scheduled task.
- Same for the watcher: `python watch_removal.py` (this one runs forever
  in a loop - press Ctrl+C to stop your manual test copy once you're
  done, so it doesn't linger and confuse you about whether the
  *automatic* task is really the one working).

## Debugging
`watch_removal.py` writes a log file every time it runs:
```
C:\ProgramData\USBKeyAuthPy\watch-log.txt
```
If the automatic removal-lock ever stops working, open this file first -
it logs when the script starts, what serial it's watching for, and any
errors it hits.

## Uninstalling / disabling
- Full removal: run `python uninstall_usbkey.py` as Administrator.
- Quick disable: open Task Scheduler (`taskschd.msc`) -> find
  `USBKeyAuthPy-Verify` and `USBKeyAuthPy-Monitor` -> Disable.
- Emergency exit: boot into **Safe Mode** (hold Shift while clicking
  Restart -> Troubleshoot -> Advanced options -> Startup Settings ->
  Safe Mode). Scheduled tasks don't run there.

## Honest limitations
Same as the PowerShell version - this is an app-level lock, not a
Windows Credential Provider, so it can theoretically be killed via Task
Manager by someone with physical access. It's a solid learning project
and deterrent, not a replacement for BitLocker/disk encryption.
