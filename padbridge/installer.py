"""One-click setup for a new PC: installs the drivers, configures the PS3 driver for
PadBridge, and makes PadBridge start with Windows in the tray.

Driver installers are downloaded from their official GitHub releases. Windows asks for
permission (UAC) once per installer.
"""
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from .doctor import _installed_drivers, _run, _service_running

DSHM_CONFIG = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "DsHidMini" / "DsHidMini.json"
# SXS is the DsHidMini mode SDL (and so PadBridge) understands with zero setup.
WANTED_MODE = "SXS"

DRIVERS = [
    # (name, GitHub repo, file extension, why)
    ("ViGEmBus", "nefarius/ViGEmBus", ".exe", "virtual Xbox controller for games"),
    ("DsHidMini", "nefarius/DsHidMini", ".msi", "lets Windows read the PS3 controller"),
    ("BthPS3", "nefarius/BthPS3", ".msi", "PS3 controller over Bluetooth"),
]


def missing_drivers():
    drivers = _installed_drivers()
    missing = []
    if not _service_running("ViGEmBus"):
        missing.append("ViGEmBus")
    if "dshidmini" not in drivers:
        missing.append("DsHidMini")
    if "bthps3" not in drivers and has_bluetooth():
        missing.append("BthPS3")
    return missing


def has_bluetooth():
    out = _run(["powershell", "-NoProfile", "-Command",
                "@(Get-PnpDevice -Class Bluetooth -PresentOnly -Status OK -ErrorAction SilentlyContinue).Count"])
    return out.strip().isdigit() and int(out.strip()) > 0


def _download_latest(repo, ext):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"User-Agent": "PadBridge"})
    with urllib.request.urlopen(req, timeout=30) as r:
        release = json.load(r)
    asset = next((a for a in release["assets"]
                  if a["name"].lower().endswith(ext) and "x64" in a["name"].lower()), None)
    if asset is None:
        raise RuntimeError(f"no {ext} installer in the latest {repo} release")
    path = Path(tempfile.gettempdir()) / asset["name"]
    print(f"     downloading {asset['name']}...")
    req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "PadBridge"})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def _run_elevated(path):
    """Runs an installer as administrator (Windows shows a UAC prompt) and waits for it."""
    if path.suffix == ".msi":
        exe, args = "msiexec.exe", f'/i "{path}" /passive /norestart'
    else:
        exe, args = str(path), ""
    ps = (f"$p = Start-Process -FilePath '{exe}' -Verb RunAs -Wait -PassThru"
          + (f" -ArgumentList '{args}'" if args else "") + "; exit $p.ExitCode")
    code = subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode
    # 0 = done, 3010 = done but needs a restart, 1638 = already installed
    return code in (0, 3010, 1638), code == 3010


def dshidmini_mode():
    """The PS3 driver's configured mode, or None if it has no config file yet."""
    try:
        return json.loads(DSHM_CONFIG.read_text(encoding="utf-8")).get("Global", {}).get("HidDeviceMode")
    except (OSError, ValueError):
        return None


def set_dshidmini_mode(mode=WANTED_MODE):
    """Puts DsHidMini in `mode` for every controller, with Bluetooth auto-pairing on.
    The driver reloads the file by itself and restarts the controller in the new mode."""
    try:
        config = json.loads(DSHM_CONFIG.read_text(encoding="utf-8"))
        backup = DSHM_CONFIG.with_suffix(".json.padbridge-backup")
        if not backup.exists():
            backup.write_text(DSHM_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    except (OSError, ValueError):
        config = {}
    g = config.setdefault("Global", {})
    g["HidDeviceMode"] = mode
    g["DevicePairingMode"] = "Auto"  # plugging in over USB pairs it to this PC's Bluetooth
    g["AutoRestartOnHidModeMismatch"] = True
    for dev in config.get("Devices", {}).values():  # per-controller overrides win, so fix those too
        dev["HidDeviceMode"] = mode
    DSHM_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    DSHM_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")


def run_setup():
    print("\n=== Setting up this PC for PadBridge ===\n")
    restart = False

    missing = missing_drivers()
    if not has_bluetooth():
        print("  [ -- ] No Bluetooth adapter found - skipping Bluetooth (USB cable will work)")
    if missing:
        print(f"  Installing: {', '.join(missing)}. Click 'Yes' when Windows asks for permission.\n")
    for name, repo, ext, why in DRIVERS:
        if name not in missing:
            print(f"  [ OK ] {name} already installed")
            continue
        print(f"  [ .. ] {name} ({why})")
        try:
            ok, needs_restart = _run_elevated(_download_latest(repo, ext))
        except Exception as e:
            ok, needs_restart = False, False
            print(f"     failed: {e}")
        restart |= needs_restart
        print(f"  [{' OK ' if ok else ' !! '}] {name} {'installed' if ok else 'was NOT installed'}")

    try:
        set_dshidmini_mode()
        print(f"  [ OK ] PS3 driver set to {WANTED_MODE} mode with Bluetooth auto-pairing")
    except OSError as e:
        print(f"  [ !! ] Couldn't configure the PS3 driver ({e}). "
              f"Open the DsHidMini app (DSHMC) and pick {WANTED_MODE} mode.")

    from .tray import LAUNCHER, _pythonw, set_autostart
    set_autostart(True)
    print("  [ OK ] PadBridge will start with Windows (tray icon by the clock)")
    subprocess.Popen([str(_pythonw()), str(LAUNCHER)], cwd=LAUNCHER.parent)

    print("\n=== Done! ===")
    if restart:
        print("  Restart the PC once to finish installing the drivers.")
    print("  1. Plug the PS3 controller in with the USB cable and press the PS button.")
    print("     The tray icon turns green, and the controller is paired for Bluetooth.")
    print("  2. For wireless: unplug the cable and press the PS button again.")
    print()
