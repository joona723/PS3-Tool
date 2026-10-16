"""Command line + simple menu (the menu shows when you double-click start.bat)."""
import argparse
import sys

from .xbox import BridgeError

MENU = """
==============================
   PadBridge - controller to PC
==============================
  0. Set up this PC (new PC? start here - installs everything)
  1. Check setup
  2. Start (controller -> Xbox controller for games)
  3. Test controller (see button presses live)
  4. Map controller buttons (for unknown controllers)
  5. Reset a controller's mapping
  6. Run in the system tray (background, waits for USB or Bluetooth)
  7. Bluetooth check (wireless not connecting?)
  8. Quit
"""


def _reset_mapping():
    from .bridge import pick_device
    from .profiles import delete_profile
    d = pick_device()
    print("Mapping removed." if delete_profile(d.guid) else "That controller had no custom mapping.")


def _map(index=None):
    from .bridge import pick_device
    from .mapper import run_wizard
    run_wizard(pick_device(index, prefer_unmapped=True))


def _start_tray():
    import subprocess
    from .tray import LAUNCHER, _pythonw
    subprocess.Popen([str(_pythonw()), str(LAUNCHER)], cwd=LAUNCHER.parent)
    print("PadBridge is now running in the system tray (by the clock). You can close this window.")


def menu():
    from .bridge import run_bridge, run_test
    from .doctor import run_doctor
    from .btcheck import run_bt_check
    from .installer import run_setup
    actions = {"7": run_bt_check, "0": run_setup, "1": run_doctor, "2": run_bridge, "3": run_test, "4": _map, "5": _reset_mapping}
    while True:
        print(MENU)
        choice = input("Choose 0-8: ").strip()
        if choice in ("8", "q", ""):
            return
        if choice == "6":
            _start_tray()
            return
        action = actions.get(choice)
        if not action:
            continue
        try:
            action()
        except (BridgeError, LookupError) as e:
            print(f"\n{e}\n")
        except KeyboardInterrupt:
            print()
        input("Press Enter to go back to the menu...")


def main(argv=None):
    p = argparse.ArgumentParser(prog="padbridge",
                                description="Use a PS3 (or other) controller as an Xbox controller on PC.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("setup", help="install drivers and set everything up (new PC)")
    sub.add_parser("doctor", help="check drivers and controllers")
    sub.add_parser("bt", help="find out why Bluetooth won't connect")
    sub.add_parser("list", help="list controllers")
    run = sub.add_parser("run", help="start the bridge")
    run.add_argument("-c", "--controller", type=int, help="controller number from 'list'")
    run.add_argument("--deadzone", type=float, default=0.08, help="stick deadzone 0..0.5 (default 0.08)")
    run.add_argument("--quiet", action="store_true", help="don't print live input")
    test = sub.add_parser("test", help="show live input")
    test.add_argument("-c", "--controller", type=int)
    tray = sub.add_parser("tray", help="run in the system tray")
    tray.add_argument("--deadzone", type=float, default=0.08)
    mp = sub.add_parser("map", help="record a button mapping")
    mp.add_argument("-c", "--controller", type=int)
    args = p.parse_args(argv)

    try:
        if args.cmd is None:
            menu()
        elif args.cmd == "setup":
            from .installer import run_setup
            run_setup()
        elif args.cmd == "bt":
            from .btcheck import run_bt_check
            return 0 if run_bt_check() else 1
        elif args.cmd == "doctor":
            from .doctor import run_doctor
            return 0 if run_doctor() else 1
        elif args.cmd == "list":
            from .sources import is_virtual_xbox, list_devices
            devices = [d for d in list_devices() if not is_virtual_xbox(d.name)]
            for d in devices:
                print(d.describe())
            if not devices:
                print("No controllers found.")
        elif args.cmd == "run":
            from .bridge import run_bridge
            run_bridge(args.controller, deadzone=args.deadzone, show=not args.quiet)
        elif args.cmd == "tray":
            from .tray import main as tray_main
            return tray_main(args.deadzone)
        elif args.cmd == "test":
            from .bridge import run_test
            run_test(args.controller)
        elif args.cmd == "map":
            _map(args.controller)
    except (BridgeError, LookupError) as e:
        print(f"\n{e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
