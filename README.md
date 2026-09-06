# USB Key 2FA - Linux version (Debian-based and Arch-based)

A specific USB pendrive (matched by its hardware serial number) becomes
a second factor for your session. Works on any systemd-based distro -
Debian, Ubuntu, Arch, Manjaro, Fedora, etc. - since it only relies on
standard tools already present on virtually all mainstream distros:
`lsblk`, `udevadm`, and `systemd --user` services. No distro-specific
package manager commands are used in the scripts themselves.

## Requirements

Install Python's Tk GUI library (not bundled with Python by default on Linux):

**Debian / Ubuntu:**
```
sudo apt install python3-tk
```

**Arch / Manjaro:**
```
sudo pacman -S tk
```

`lsblk` and `udevadm` are part of `util-linux`/`systemd`, already
installed by default on both. No `pip install` packages are needed -
this version only uses Python's standard library plus these command-line
tools.

## Files
- `setup_usbkey.py` - run once to register your pendrive and install the systemd services
- `verify_2fa.py` - the fullscreen password prompt
- `watch_removal.py` - the background watcher that locks the session on removal
- `uninstall_usbkey.py` - removes everything cleanly

## Install
1. Plug in and mount your pendrive (open it in your file manager once so it auto-mounts).
2. `cd` into this folder.
3. Run:
   ```
   python3 setup_usbkey.py
   ```
4. Pick your pendrive from the numbered list, set a pendrive password.

This creates two systemd `--user` services (`usbkeyauth-verify` and
`usbkeyauth-monitor`), enabled to start at your next graphical login.
**No root/sudo is needed anywhere in this setup** - `systemd --user`
services run entirely under your own account.

## Testing before trusting it automatically
Test manually first:
```
python3 verify_2fa.py
python3 watch_removal.py    # Ctrl+C to stop your manual test copy
```

If you edit a script after setup, copy it into `~/.local/share/usbkeyauth/`
and restart the service to pick up the change:
```
systemctl --user restart usbkeyauth-verify.service
systemctl --user restart usbkeyauth-monitor.service
```

Check logs anytime with:
```
journalctl --user -u usbkeyauth-verify.service -f
journalctl --user -u usbkeyauth-monitor.service -f
```
or read the plain log files directly:
```
~/.config/usbkeyauth/verify-log.txt
~/.config/usbkeyauth/watch-log.txt
```

## Features

- **Fullscreen, always-on-top** - deliberate lockdown so the prompt
  can't be casually bypassed.
- **Re-prompts for the pendrive password on every unlock**, not just at
  login. This works by watching systemd-logind's `LockedHint` property
  for your session (via `loginctl show-session`) - when it flips from
  locked to unlocked, the watcher re-launches the prompt automatically.

**One honest caveat:** this depends on your desktop environment properly
telling systemd-logind when the screen locks/unlocks. GNOME and KDE do
this correctly (covering most Debian/Arch desktop installs). If you're
using a minimal window manager that doesn't integrate with logind's
session locking, the unlock re-prompt may not fire - the pendrive
removal-lock will still work regardless, since that doesn't depend on
this. Check `~/.config/usbkeyauth/watch-log.txt` for a line saying
"Monitoring session ID: ..." shortly after login to confirm it's working;
if it instead says "Could not determine session ID", that's the sign
this specific feature isn't supported on the current setup.

## Design notes
- Fullscreen, always-on-top, and deliberately no in-app override, per
  project design. If it ever hangs: any desktop environment's own task
  manager, or from a different TTY (Ctrl+Alt+F3, log in, then
  `pkill -f verify_2fa.py`), closes it without needing root.
- Matching is by hardware serial number (via `lsblk`), not mount path,
  so it's independent of exactly where a given distro/DE happens to
  auto-mount removable drives.

## Troubleshooting: service doesn't start automatically at login

Linux desktop environments vary in exactly *when* a `systemd --user`
session becomes fully active. This project uses `WantedBy=default.target`,
which works on most modern setups (GNOME, KDE, XFCE with systemd
integration), but if the services don't start automatically:

1. Check their status:
   ```
   systemctl --user status usbkeyauth-verify.service
   systemctl --user status usbkeyauth-monitor.service
   ```
2. Try starting manually to confirm the scripts themselves work:
   ```
   systemctl --user start usbkeyauth-monitor.service
   ```
3. If `default.target` isn't triggering them, try switching to
   `graphical-session.target` instead - this is more specifically tied to
   a graphical login but requires the desktop environment to properly
   export it (most do, some minimal window managers don't):
   ```
   sed -i 's/WantedBy=default.target/WantedBy=graphical-session.target/' \
     ~/.config/systemd/user/usbkeyauth-verify.service \
     ~/.config/systemd/user/usbkeyauth-monitor.service
   systemctl --user daemon-reload
   systemctl --user enable usbkeyauth-verify.service usbkeyauth-monitor.service
   ```
4. As a last resort on any setup, adding the two `ExecStart` commands
   from the service files to your desktop environment's own "Startup
   Applications" tool (present in GNOME, KDE, XFCE, and most others)
   will always work, since it bypasses systemd targets entirely.

This variability is a genuine, known rough edge of Linux service
auto-start across different desktop environments - not a bug in the
scripts themselves.

## Uninstalling / disabling
```
python3 uninstall_usbkey.py
```
or manually:
```
systemctl --user disable --now usbkeyauth-verify.service
systemctl --user disable --now usbkeyauth-monitor.service
```
