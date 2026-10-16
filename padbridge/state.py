"""The controller-independent "pad state" that every input source produces.

Everything is expressed in Xbox 360 terms, because that's what we output:
  buttons  -> True/False
  sticks   -> -1.0 .. 1.0  (up and right are positive)
  triggers ->  0.0 .. 1.0
"""
from dataclasses import dataclass, field

BUTTONS = ("a", "b", "x", "y", "lb", "rb", "back", "start", "guide",
           "ls", "rs", "up", "down", "left", "right")
STICKS = ("lx", "ly", "rx", "ry")
TRIGGERS = ("lt", "rt")
CONTROLS = BUTTONS + TRIGGERS + STICKS

# Friendly names, so people with a PlayStation pad see familiar labels.
PS_NAMES = {
    "a": "Cross (X)", "b": "Circle (O)", "x": "Square", "y": "Triangle",
    "lb": "L1", "rb": "R1", "lt": "L2", "rt": "R2",
    "back": "Select", "start": "Start", "guide": "PS button",
    "ls": "L3 (press left stick)", "rs": "R3 (press right stick)",
    "up": "D-pad Up", "down": "D-pad Down", "left": "D-pad Left", "right": "D-pad Right",
    "lx": "Left stick", "ly": "Left stick", "rx": "Right stick", "ry": "Right stick",
}

# Short labels for the live input display.
SHORT_PS = {
    "a": "X", "b": "O", "x": "SQ", "y": "TRI", "lb": "L1", "rb": "R1",
    "back": "SEL", "start": "START", "guide": "PS", "ls": "L3", "rs": "R3",
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
}


@dataclass
class PadState:
    buttons: dict = field(default_factory=lambda: {b: False for b in BUTTONS})
    sticks: dict = field(default_factory=lambda: {s: 0.0 for s in STICKS})
    triggers: dict = field(default_factory=lambda: {t: 0.0 for t in TRIGGERS})


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def apply_deadzone(x, y, deadzone):
    """Radial deadzone: ignores tiny stick drift, rescales the rest to stay smooth."""
    mag = (x * x + y * y) ** 0.5
    if mag <= deadzone:
        return 0.0, 0.0
    scale = (mag - deadzone) / (1.0 - deadzone) / mag
    return clamp(x * scale, -1.0, 1.0), clamp(y * scale, -1.0, 1.0)
