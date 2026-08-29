# USB Key 2FA for Windows

Turns a specific USB pendrive into a second factor for logging into a
Windows laptop.

**Flow:** Windows password (factor 1) -> a fullscreen prompt asks for
your pendrive password (factor 2), which only appears once that exact
pendrive is detected by its hardware serial number -> unplug the
pendrive at any point and the workstation instantly locks, requiring
both factors again to get back in.

## Requirements
1. **Python** must be installed. If it isn't:
   - Go to https://www.python.org/downloads/
   - Download and run the installer
   - **Important:** on the first install screen, check the box
     "Add python.exe to PATH" before clicking Install
2. Open a terminal and install the two required packages:
   ```
   py -m pip install pywin32 wmi
   ```

## Files
- `setup_usbkey.py` - run once to register your pendrive and install the scheduled tasks
- `verify_2fa.py` - the fullscreen password prompt (auto-run by the scheduled task, don't run manually except for testing)
- `watch_removal.py` - the background watcher that locks on removal (auto-run by the scheduled task)
- `uninstall_usbkey.py` - removes everything cleanly

## Install
1. Copy this whole folder to the laptop.
2. Plug in the pendrive to use as the key.
3. Open a terminal **as Administrator**.
4. `cd` into this folder.
5. Run:
   ```
   py setup_usbkey.py
   ```
6. Pick the pendrive from the numbered list, then set a pendrive password.

This creates two scheduled tasks, `USBKeyAuthPy-Verify` and
`USBKeyAuthPy-Monitor`, which run automatically from the next
logon/unlock onward.

## Testing before trusting it automatically
- Test manually first, with a visible console (`py`, not `pythonw`), so
  any error is visible instead of hidden:
  ```
  py verify_2fa.py
  py watch_removal.py
  ```
- Only enable/trust the scheduled tasks after confirming both behave
  correctly when run manually a few times.
- **If you edit any of these scripts after setup:** copying the updated
  file into `C:\USBKeyAuthPy` is not enough on its own - the scheduled
  task needs to be restarted (or the laptop signed out/in) to pick up
  the change:
  ```
  Stop-ScheduledTask -TaskName "USBKeyAuthPy-Verify"
  Start-ScheduledTask -TaskName "USBKeyAuthPy-Verify"
  ```

## Design notes / honest limitations
- `verify_2fa.py` runs as a fullscreen, always-on-top window with the
  close button and Alt+F4 disabled, by deliberate choice, so it cannot
  be casually dismissed. **There is intentionally no in-app override
  key.** If it ever hangs, the documented recovery path is
  `Ctrl+Shift+Esc` (Task Manager, no admin rights needed) -> end the
  "Python" process. This does not require Administrator rights and does
  not require restarting the laptop.
- **Do not force-shutdown by holding the power button** to escape a
  stuck screen - on this laptop that has previously triggered a
  BitLocker recovery lock, which requires a separate 48-digit recovery
  key to resolve. Task Manager -> End Task is always the safer route.
- This is an app-level lock, not a Windows Credential Provider, so it
  is not equivalent to full-disk encryption or a hardware security key.
  It is a learning project and a practical deterrent, not a replacement
  for BitLocker if strong protection against a stolen laptop is the
  goal.
- Matching is done by the pendrive's hardware serial number (not its
  drive letter, which can change), so it recognizes the correct
  physical pendrive even if Windows assigns it a different letter.

## Uninstalling / disabling
- Full removal: run `py uninstall_usbkey.py` as Administrator.
- Quick disable without removing anything:
  ```
  Disable-ScheduledTask -TaskName "USBKeyAuthPy-Verify"
  Disable-ScheduledTask -TaskName "USBKeyAuthPy-Monitor"
  ```
- Re-enable later with `Enable-ScheduledTask` using the same task names.
