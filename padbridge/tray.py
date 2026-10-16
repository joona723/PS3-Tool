"""System tray mode: PadBridge runs quietly in the background with an icon by the clock.

The icon is grey while waiting for a controller, green while one is connected and
red if something is wrong. It waits for a controller to show up (USB or Bluetooth),
so you can start it once - or with Windows - and just turn your controller on.
"""
import ctypes
import logging
import subprocess
import sys
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .bridge import serve
from .xbox import BridgeError

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "PadBridge.pyw"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "PadBridge"
COLORS = {"waiting": "#8a8f98", "connected": "#2fb344", "error": "#d63939", "unmapped": "#f59f00"}

log = logging.getLogger("padbridge")


def _icon_image(color):
    """A little gamepad drawn in the status colour."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 22, 26, 58), fill=color)    # left grip
    d.ellipse((38, 22, 62, 58), fill=color)   # right grip
    d.rounded_rectangle((6, 14, 58, 44), radius=12, fill=color)
    d.ellipse((14, 22, 24, 32), fill="white")  # sticks
    d.ellipse((40, 22, 50, 32), fill="white")
    return img


# ---- Start with Windows (a per-user "Run" registry entry, no admin needed) ----

def _pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{_pythonw()}" "{LAUNCHER}"')
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except OSError:
                pass


def _already_running():
    """Only one tray icon at a time (e.g. started with Windows AND double-clicked)."""
    _already_running.handle = ctypes.windll.kernel32.CreateMutexW(None, False, "PadBridgeTrayMutex")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


class TrayApp:
    def __init__(self, deadzone=0.08):
        self.deadzone = deadzone
        self.stop = threading.Event()
        self.status_text = "Starting..."
        self.icon = pystray.Icon("PadBridge", _icon_image(COLORS["waiting"]), "PadBridge", self._menu())

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda _: self.status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Setup / map buttons...", self._open_console),
            pystray.MenuItem("Start with Windows", self._toggle_autostart,
                             checked=lambda _: autostart_enabled()),
            pystray.MenuItem("Quit", self._quit),
        )

    def _set(self, kind, text, notify=None):
        self.status_text = text
        self.icon.icon = _icon_image(COLORS[kind])
        self.icon.title = f"PadBridge - {text}"
        self.icon.update_menu()
        if notify:
            try:
                self.icon.notify(notify, "PadBridge")
            except Exception:
                pass
        log.info(text)

    def _on_status(self, kind, detail):
        if kind == "waiting":
            was_connected = self.status_text.startswith("Connected")
            self._set("waiting", "Waiting for a controller",
                      notify="Controller disconnected - waiting for it to come back" if was_connected else None)
        elif kind == "connected":
            self._set("connected", f"Connected: {detail}", notify=f"{detail} connected")
        elif kind == "unmapped":
            # First time we see this controller: open the mapping wizard for it right away.
            self._set("unmapped", f"'{detail}' needs mapping",
                      notify=f"New controller '{detail}': press each button the window asks for.")
            self._open_console(None, None, "map")

    def _worker(self):
        try:
            serve(self.stop, self._on_status, deadzone=self.deadzone)
        except BridgeError as e:
            log.error("%s", e)
            self._set("error", "Error - see Setup", notify=str(e).splitlines()[0])
        except Exception:
            log.exception("PadBridge stopped unexpectedly")
            self._set("error", "Stopped unexpectedly - see padbridge.log",
                      notify="PadBridge stopped unexpectedly. Details are in padbridge.log.")

    def _open_console(self, icon, item, *args):
        subprocess.Popen(["cmd", "/c", "start", "PadBridge", str(ROOT / "start.bat"), *args], cwd=ROOT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def _toggle_autostart(self, icon, item):
        set_autostart(not autostart_enabled())

    def _quit(self, icon, item):
        self.stop.set()
        self.thread.join(timeout=3)
        icon.stop()

    def run(self):
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.icon.run()


def main(deadzone=0.08):
    logging.basicConfig(filename=ROOT / "padbridge.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if _already_running():
        return 0
    if autostart_enabled():
        set_autostart(True)  # keep the entry pointing here if the folder was moved
    TrayApp(deadzone).run()
    return 0
