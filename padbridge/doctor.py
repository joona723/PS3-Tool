"""Setup checker: tells you exactly what's missing for your controller to work."""
import json
import subprocess
import sys

from .sources import is_virtual_xbox, list_devices

DS3_ID = "VID_054C&PID_0268"
LINKS = {
    "vigem": "https://github.com/nefarius/ViGEmBus/releases",
    "dshidmini": "https://github.com/nefarius/DsHidMini/releases",
    "hidhide": "https://github.com/nefarius/HidHide/releases",
}


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return ""


def _service_running(name):
    return "RUNNING" in _run(["sc", "query", name])


def _installed_drivers():
    return _run(["pnputil", "/enum-drivers"]).lower()


def _sony_devices():
    ps = (
        "Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -match '054C&PID_0268' "
        "-or $_.DeviceID -match 'BTHPS3' -or $_.Service -match 'dshidmini' } | "
        "Select-Object Name,DeviceID,Service,Status | ConvertTo-Json"
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps]).strip()
    if not out:
        return []
    data = json.loads(out)
    return data if isinstance(data, list) else [data]


def ok(msg):
    print(f"  [ OK ] {msg}")


def bad(msg):
    print(f"  [ !! ] {msg}")


def info(msg):
    print(f"  [ -- ] {msg}")


def run_doctor():
    todo = []
    print("\n=== Setup check ===\n")

    ok(f"Python {sys.version.split()[0]}")

    # 1. ViGEmBus: required for the virtual Xbox controller.
    if _service_running("ViGEmBus"):
        ok("ViGEmBus driver is installed (virtual Xbox controller)")
    else:
        bad("ViGEmBus driver is NOT installed - games can't see a virtual Xbox controller")
        todo.append(f"Install ViGEmBus: {LINKS['vigem']}  (download the x64 installer, run it)")

    # 2. PS3 controller driver.
    drivers = _installed_drivers()
    has_dshidmini = "dshidmini" in drivers
    if has_dshidmini:
        ok("DsHidMini driver is installed (PS3 controller support)")
    else:
        bad("DsHidMini is NOT installed - Windows can't read a PS3 controller without it")
        todo.append(f"Install DsHidMini (PS3 controller driver): {LINKS['dshidmini']}")
    if has_dshidmini:
        from .installer import WANTED_MODE, dshidmini_mode
        mode = dshidmini_mode()
        if mode == WANTED_MODE:
            ok(f"PS3 driver is in {WANTED_MODE} mode (works with PadBridge without mapping)")
        else:
            info(f"PS3 driver mode is {mode or 'the default (DS4Windows)'}; {WANTED_MODE} is recommended. "
                 "'Set up this PC' (option 0) switches it.")
    if "bthps3" in drivers:
        ok("BthPS3 is installed (PS3 controller over Bluetooth)")
    else:
        info("BthPS3 not installed - only needed for wireless/Bluetooth (USB cable works without it)")

    sony = _sony_devices()
    if sony:
        for d in sony:
            svc = (d.get("Service") or "none").lower()
            line = f"PS3 controller found: {d.get('Name')}  (driver: {svc}, status: {d.get('Status')})"
            if "dshidmini" in svc:
                ok(line)
            else:
                bad(line)
                if has_dshidmini:
                    todo.append("Your PS3 controller isn't using DsHidMini yet: unplug it and plug it back in. "
                                "If it still doesn't work, re-run the DsHidMini installer.")
    else:
        info("No PS3 controller detected right now (plug it in with the USB cable)")

    # 3. Optional: HidHide prevents "double input".
    if _service_running("HidHide"):
        ok("HidHide is installed (can hide the real controller so games only see the Xbox one)")
    else:
        info(f"Optional: HidHide stops games seeing the controller twice: {LINKS['hidhide']}")

    # 4. What our tool can actually read.
    devices = [d for d in list_devices() if not is_virtual_xbox(d.name)]
    print()
    if devices:
        print("  Controllers this tool can see:")
        for d in devices:
            print(f"     {d.describe()}")
            if not d.ready:
                todo.append(f"Map the buttons of '{d.name}' once (menu option 4).")
    else:
        bad("This tool can't see any controller yet")
        if not todo:
            todo.append("Plug the controller in (USB), wait a few seconds, and run this check again.")

    print()
    if todo:
        print("=== What to do next ===")
        for i, t in enumerate(todo, 1):
            print(f"  {i}. {t}")
    else:
        print("Everything looks good! Choose 'Start' to play.")
    print()
    return not todo
