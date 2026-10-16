"""Interactive wizard: press each button when asked, and we record where it lives.

This is what makes the tool work with controllers SDL has never heard of.
"""
import time

import pygame

from .profiles import save_profile
from .sources import DeviceInfo
from .state import BUTTONS, PS_NAMES, TRIGGERS

try:
    import msvcrt  # Windows: lets Enter/Esc work while we watch the controller
except ImportError:
    msvcrt = None

AXIS_THRESHOLD = 0.6

STICK_STEPS = [
    ("lx", "Push the LEFT stick all the way RIGHT"),
    ("ly", "Push the LEFT stick all the way UP"),
    ("rx", "Push the RIGHT stick all the way RIGHT"),
    ("ry", "Push the RIGHT stick all the way UP"),
]


class Cancelled(Exception):
    pass


def _key():
    if msvcrt and msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch == "\x1b":
            raise Cancelled()
        if ch in ("\r", "\n"):
            return "skip"
    return None


def _rest_of(v):
    return -1.0 if v < -0.5 else 1.0 if v > 0.5 else 0.0


def _snapshot(js):
    pygame.event.pump()
    return {
        "buttons": [js.get_button(i) for i in range(js.get_numbuttons())],
        "hats": [js.get_hat(i) for i in range(js.get_numhats())],
        "axes": [js.get_axis(i) for i in range(js.get_numaxes())],
    }


def _moved_axis(snap, baseline):
    best = None
    for i, v in enumerate(snap["axes"]):
        delta = v - baseline[i]
        if abs(delta) > AXIS_THRESHOLD and (best is None or abs(delta) > abs(best[1])):
            best = (i, delta)
    return best


def _detect(snap, baseline, want_axis_only=False):
    """Find what the user is pressing. Buttons and hats win over axes, because some
    controllers (like the PS3's pressure-sensitive buttons) move an axis AND a button."""
    if not want_axis_only:
        for i, pressed in enumerate(snap["buttons"]):
            if pressed:
                return {"type": "button", "index": i}
        for i, (x, y) in enumerate(snap["hats"]):
            if (x, y) != (0, 0):
                d = "up" if y == 1 else "down" if y == -1 else "left" if x == -1 else "right"
                return {"type": "hat", "index": i, "dir": d}
    hit = _moved_axis(snap, baseline)
    if hit:
        i, delta = hit
        if want_axis_only:
            return {"type": "axis", "index": i, "invert": delta < 0}
        return {"type": "half", "index": i, "rest": _rest_of(baseline[i]), "sign": 1 if delta > 0 else -1}
    return None


def _capture(js, baseline, stick=False, trigger=False):
    while True:
        if _key() == "skip":
            return None
        found = _detect(_snapshot(js), baseline, want_axis_only=stick)
        if found:
            if trigger and found["type"] != "half":
                # Triggers are often a digital button AND an analog axis. Give the
                # analog side a moment to show up, and prefer it - it's smoother.
                end = time.time() + 0.5
                while time.time() < end:
                    hit = _moved_axis(_snapshot(js), baseline)
                    if hit:
                        i, delta = hit
                        return {"type": "half", "index": i, "rest": _rest_of(baseline[i]),
                                "sign": 1 if delta > 0 else -1}
                    time.sleep(0.01)
            return found
        time.sleep(0.01)


def _wait_release(js, baseline, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        s = _snapshot(js)
        if (not any(s["buttons"]) and all(h == (0, 0) for h in s["hats"])
                and all(abs(v - baseline[i]) < 0.3 for i, v in enumerate(s["axes"]))):
            return
        time.sleep(0.01)


def _describe(b):
    if b is None:
        return "skipped"
    if b["type"] == "button":
        return f"button {b['index']}"
    if b["type"] == "hat":
        return f"hat {b['index']} {b['dir']}"
    return f"axis {b['index']}" + (" (inverted)" if b.get("invert") or b.get("sign") == -1 else "")


def run_wizard(info: DeviceInfo):
    js = pygame.joystick.Joystick(info.index)
    print(f"\nMapping: {info.name}")
    print("For each prompt, press that button on the controller.")
    print("  Enter = skip (controller doesn't have it)    Esc = cancel\n")
    input("Put the controller down - don't touch anything - and press Enter...")
    time.sleep(0.3)
    baseline = _snapshot(js)["axes"]

    bindings = {}
    try:
        for name in BUTTONS + TRIGGERS:
            print(f"  Press {PS_NAMES[name]:<24}", end="", flush=True)
            b = _capture(js, baseline, trigger=name in TRIGGERS)
            print(f"-> {_describe(b)}")
            if b:
                bindings[name] = b
                _wait_release(js, baseline)
        for name, prompt in STICK_STEPS:
            print(f"  {prompt:<40}", end="", flush=True)
            b = _capture(js, baseline, stick=True)
            print(f"-> {_describe(b)}")
            if b:
                bindings[name] = b
                _wait_release(js, baseline)
    except Cancelled:
        print("\nCancelled - nothing was saved.")
        return None

    path = save_profile(info.guid, info.name, bindings)
    print(f"\nSaved! ({path.name}) This controller will use your mapping from now on.")
    return path
