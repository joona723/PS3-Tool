"""Reading real controllers through SDL (via pygame).

SDL already understands hundreds of controllers (PS3 via DsHidMini, PS4, PS5,
Switch Pro, 8BitDo, generic USB pads...). Two kinds of source:

  StandardSource - SDL knows the controller's layout, so it works with zero setup.
  ProfileSource  - uses a mapping you recorded with the "map" wizard. Works with
                   ANY controller, and overrides the standard layout if present.
"""
import os

# These must be set before SDL starts.
# Keep reading the controller while a game window (not us) has focus.
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
# Let SDL talk to PS3 controllers directly (needed with DsHidMini's SXS mode).
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS3", "1")

import pygame
from pygame._sdl2 import controller as sdl_controller

from .profiles import load_profile
from .state import BUTTONS, STICKS, TRIGGERS, PadState, clamp

_started = False


def start_sdl():
    global _started
    if not _started:
        pygame.init()
        pygame.joystick.init()
        sdl_controller.init()
        # We poll controller state directly and only need plug/unplug events. Queued input
        # events from a controller that was re-enumerated make pygame.event.get() crash
        # (KeyError on an unknown instance id), so don't queue them at all.
        pygame.event.set_blocked([
            pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYHATMOTION,
            pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP,
            pygame.CONTROLLERAXISMOTION, pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP,
            pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED, pygame.CONTROLLERDEVICEREMAPPED,
        ])
        _started = True
    pygame.event.pump()


def poll_device_changes():
    """Returns (added, removed): whether any controller was plugged in, and the instance
    ids that were unplugged. All other queued events are dropped.

    pygame crashes converting a removal for a controller it never opened (SDL re-enumerates
    some pads at startup, e.g. a PS4 pad over USB). That batch is lost, so in that case
    `removed` is every instance id that is no longer present."""
    added = bool(pygame.event.get(eventtype=pygame.JOYDEVICEADDED))
    try:
        removed = {e.instance_id for e in pygame.event.get(eventtype=pygame.JOYDEVICEREMOVED)}
    except SystemError:
        present = {pygame.joystick.Joystick(i).get_instance_id() for i in range(pygame.joystick.get_count())}
        removed = _AllExcept(present)
    pygame.event.clear()
    return added, removed


class _AllExcept:
    def __init__(self, present):
        self.present = present

    def __contains__(self, instance_id):
        return instance_id not in self.present


def is_virtual_xbox(name):
    """Our own output pad shows up as an input device too; never read from it."""
    return "xbox 360" in name.lower() or "xinput" in name.lower()


class DeviceInfo:
    def __init__(self, index):
        js = pygame.joystick.Joystick(index)
        self.index = index
        self.instance_id = js.get_instance_id()
        self.name = js.get_name()
        self.guid = js.get_guid()
        self.is_standard = sdl_controller.is_controller(index)
        self.has_profile = load_profile(self.guid) is not None
        self.axes, self.buttons, self.hats = js.get_numaxes(), js.get_numbuttons(), js.get_numhats()

    @property
    def ready(self):
        return self.has_profile or self.is_standard

    def describe(self):
        if self.has_profile:
            how = "custom mapping"
        elif self.is_standard:
            how = "known layout, works out of the box"
        else:
            how = "unknown layout - run 'map' once"
        return f"[{self.index}] {self.name}  ({how})"


def list_devices():
    start_sdl()
    return [DeviceInfo(i) for i in range(pygame.joystick.get_count())]


def open_source(info):
    if info.has_profile:
        return ProfileSource(info)
    if info.is_standard:
        return StandardSource(info)
    raise LookupError(
        f"'{info.name}' has an unknown button layout. Run the mapping wizard first (menu option 4).")


class _Source:
    kind = "?"

    def __init__(self, info):
        self.info = info

    @property
    def instance_id(self):
        return self.info.instance_id

    def read(self) -> PadState:
        raise NotImplementedError

    def rumble(self, low, high):
        """low = big/heavy motor, high = small/buzzy motor, each 0..1."""
        try:
            if low <= 0 and high <= 0:
                self._rumbler().stop_rumble()
            else:
                self._rumbler().rumble(low, high, 0)
        except pygame.error:
            pass  # This controller doesn't support rumble through SDL.

    def _rumbler(self):
        raise NotImplementedError

    def close(self):
        pass


class StandardSource(_Source):
    kind = "standard layout"

    _BUTTONS = {
        "a": pygame.CONTROLLER_BUTTON_A, "b": pygame.CONTROLLER_BUTTON_B,
        "x": pygame.CONTROLLER_BUTTON_X, "y": pygame.CONTROLLER_BUTTON_Y,
        "lb": pygame.CONTROLLER_BUTTON_LEFTSHOULDER, "rb": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
        "back": pygame.CONTROLLER_BUTTON_BACK, "start": pygame.CONTROLLER_BUTTON_START,
        "guide": pygame.CONTROLLER_BUTTON_GUIDE,
        "ls": pygame.CONTROLLER_BUTTON_LEFTSTICK, "rs": pygame.CONTROLLER_BUTTON_RIGHTSTICK,
        "up": pygame.CONTROLLER_BUTTON_DPAD_UP, "down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        "left": pygame.CONTROLLER_BUTTON_DPAD_LEFT, "right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
    }

    def __init__(self, info):
        super().__init__(info)
        self.pad = sdl_controller.Controller(info.index)

    def _axis(self, axis):
        return clamp(self.pad.get_axis(axis) / 32767.0, -1.0, 1.0)

    def read(self):
        s = PadState()
        for name, btn in self._BUTTONS.items():
            s.buttons[name] = bool(self.pad.get_button(btn))
        s.sticks["lx"] = self._axis(pygame.CONTROLLER_AXIS_LEFTX)
        s.sticks["ly"] = -self._axis(pygame.CONTROLLER_AXIS_LEFTY)   # SDL: down is +
        s.sticks["rx"] = self._axis(pygame.CONTROLLER_AXIS_RIGHTX)
        s.sticks["ry"] = -self._axis(pygame.CONTROLLER_AXIS_RIGHTY)
        s.triggers["lt"] = max(0.0, self._axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT))
        s.triggers["rt"] = max(0.0, self._axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT))
        return s

    def _rumbler(self):
        return self.pad

    def close(self):
        self.pad.quit()


_HAT_DIRS = {"up": (1, 1), "down": (1, -1), "left": (0, -1), "right": (0, 1)}


def read_binding(js, b):
    """Value of one binding: -1..1 for "axis", 0..1 for everything else."""
    t = b["type"]
    if t == "button":
        return float(js.get_button(b["index"]))
    if t == "hat":
        component, wanted = _HAT_DIRS[b["dir"]]
        return 1.0 if js.get_hat(b["index"])[component] == wanted else 0.0
    if t == "axis":
        v = js.get_axis(b["index"])
        return -v if b.get("invert") else v
    if t == "half":
        rest, sign = b["rest"], b["sign"]
        span = (1.0 - rest) if sign > 0 else (rest + 1.0)
        return clamp((js.get_axis(b["index"]) - rest) * sign / (span or 1.0), 0.0, 1.0)
    raise ValueError(f"Unknown binding type {t!r}")


class ProfileSource(_Source):
    kind = "custom mapping"

    def __init__(self, info):
        super().__init__(info)
        self.js = pygame.joystick.Joystick(info.index)
        self.bindings = load_profile(info.guid)["bindings"]

    def _get(self, name, default=0.0):
        b = self.bindings.get(name)
        return read_binding(self.js, b) if b else default

    def read(self):
        s = PadState()
        for name in BUTTONS:
            s.buttons[name] = self._get(name) > 0.5
        for name in STICKS:
            s.sticks[name] = clamp(self._get(name), -1.0, 1.0)
        for name in TRIGGERS:
            s.triggers[name] = self._get(name)
        return s

    def _rumbler(self):
        return self.js
