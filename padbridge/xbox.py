"""The virtual Xbox 360 controller that games see (needs the ViGEmBus driver)."""
import threading
import time

from .state import BUTTONS, PadState, apply_deadzone

VIGEM_HELP = (
    "Couldn't create the virtual Xbox controller.\n"
    "The ViGEmBus driver is probably not installed. Get it here, install it, then try again:\n"
    "  https://github.com/nefarius/ViGEmBus/releases  (ViGEmBus_x64.exe / .msi)"
)


class BridgeError(Exception):
    pass


class VirtualXbox:
    def __init__(self):
        try:
            import vgamepad as vg
            self.pad = vg.VX360Gamepad()
        except Exception as e:  # vgamepad raises various types when the driver is missing
            raise BridgeError(f"{VIGEM_HELP}\n(details: {type(e).__name__}: {e})") from e

        B = vg.XUSB_BUTTON
        self._bits = {
            "a": B.XUSB_GAMEPAD_A, "b": B.XUSB_GAMEPAD_B, "x": B.XUSB_GAMEPAD_X, "y": B.XUSB_GAMEPAD_Y,
            "lb": B.XUSB_GAMEPAD_LEFT_SHOULDER, "rb": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "back": B.XUSB_GAMEPAD_BACK, "start": B.XUSB_GAMEPAD_START, "guide": B.XUSB_GAMEPAD_GUIDE,
            "ls": B.XUSB_GAMEPAD_LEFT_THUMB, "rs": B.XUSB_GAMEPAD_RIGHT_THUMB,
            "up": B.XUSB_GAMEPAD_DPAD_UP, "down": B.XUSB_GAMEPAD_DPAD_DOWN,
            "left": B.XUSB_GAMEPAD_DPAD_LEFT, "right": B.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        self._last = None
        # Rumble requests arrive on a driver thread; the main loop picks them up.
        self._rumble_lock = threading.Lock()
        self._rumble = (0.0, 0.0)
        self._rumble_dirty = False
        self.pad.register_notification(self._on_notification)

    def _on_notification(self, client, target, large_motor, small_motor, led_number, user_data):
        with self._rumble_lock:
            self._rumble = (large_motor / 255.0, small_motor / 255.0)
            self._rumble_dirty = True

    def take_rumble(self):
        """Returns (low, high) if a game changed rumble since last call, else None."""
        with self._rumble_lock:
            if not self._rumble_dirty:
                return None
            self._rumble_dirty = False
            return self._rumble

    def send(self, s: PadState, deadzone=0.0):
        lx, ly = apply_deadzone(s.sticks["lx"], s.sticks["ly"], deadzone)
        rx, ry = apply_deadzone(s.sticks["rx"], s.sticks["ry"], deadzone)
        mask = 0
        for name in BUTTONS:
            if s.buttons[name]:
                mask |= self._bits[name]
        report = (mask, _stick(lx), _stick(ly), _stick(rx), _stick(ry),
                  round(s.triggers["lt"] * 255), round(s.triggers["rt"] * 255))
        if report == self._last:
            return  # nothing changed, don't spam the driver
        self._last = report
        self.pad.report.wButtons = mask
        self.pad.left_joystick(report[1], report[2])
        self.pad.right_joystick(report[3], report[4])
        self.pad.left_trigger(report[5])
        self.pad.right_trigger(report[6])
        self.pad.update()

    def close(self):
        try:
            self.pad.reset()
            self.pad.update()
            self.pad.unregister_notification()
        except Exception:
            pass
        del self.pad


def _stick(v):
    return max(-32768, min(32767, round(v * 32767)))
