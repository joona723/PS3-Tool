"""The main loop: real controller in -> virtual Xbox 360 controller out."""
import time

import pygame

from .sources import (DeviceInfo, is_virtual_xbox, list_devices, open_source, poll_device_changes,
                      start_sdl)
from .state import BUTTONS, SHORT_PS, PadState
from .xbox import BridgeError, VirtualXbox


def pick_device(index=None, prefer_unmapped=False):
    devices = [d for d in list_devices() if not is_virtual_xbox(d.name)]
    if index is not None:
        for d in devices:
            if d.index == index:
                return d
        raise BridgeError(f"No controller with number {index}.")
    if not devices:
        raise BridgeError("No controller found. Plug it in, then run the setup check (option 1).")
    unmapped = [d for d in devices if not d.ready]
    if prefer_unmapped and len(unmapped) == 1:
        return unmapped[0]
    ready = [d for d in devices if d.ready]
    if len(devices) == 1 or len(ready) == 1:
        return (ready or devices)[0]
    print("Which controller?")
    for d in devices:
        print(f"  {d.describe()}")
    choice = input("Number: ").strip()
    return pick_device(int(choice)) if choice.isdigit() else devices[0]


def _status_line(state):
    pressed = [SHORT_PS[b] for b in BUTTONS if state.buttons[b]]
    s, t = state.sticks, state.triggers
    return (f"L({s['lx']:+.2f},{s['ly']:+.2f}) R({s['rx']:+.2f},{s['ry']:+.2f}) "
            f"L2 {t['lt']:.2f} R2 {t['rt']:.2f}  {' '.join(pressed) or '-'}")


def _find_ready(prefer=None):
    """The controller to use: the previous one if it's back, else any usable one.
    A controller can come back with a different GUID (e.g. USB cable -> Bluetooth),
    so one with the same name counts as "the previous one" too."""
    devices = [d for d in list_devices() if not is_virtual_xbox(d.name) and d.ready]
    if prefer is not None:
        for d in devices:
            if d.guid == prefer.guid or d.name == prefer.name:
                return d
    return devices[0] if devices else None


def _wait_for_reconnect(previous):
    print("\nController disconnected - waiting for it to come back (Ctrl+C to stop)...")
    while True:
        added, _ = poll_device_changes()
        if added:
            d = _find_ready(previous)
            if d and (d.guid == previous.guid or d.name == previous.name):
                print("Reconnected!")
                return d
        time.sleep(0.2)


def run_bridge(index=None, deadzone=0.08, rate=250, show=True):
    info = pick_device(index)
    source = open_source(info)
    pad = VirtualXbox()
    print(f"\nRunning: {info.name} ({source.kind})  ->  virtual Xbox 360 controller")
    print("Start your game now. Keep this window open. Ctrl+C to stop.\n")

    clock = pygame.time.Clock()
    last_print = 0.0
    try:
        while True:
            _, removed = poll_device_changes()
            if source.instance_id in removed:
                pad.send(PadState())  # release everything
                source.close()
                info = _wait_for_reconnect(info)
                source = open_source(info)
            state = source.read()
            pad.send(state, deadzone)
            rumble = pad.take_rumble()
            if rumble is not None:
                source.rumble(*rumble)
            if show and time.time() - last_print > 0.1:
                print("\r" + _status_line(state).ljust(78), end="", flush=True)
                last_print = time.time()
            clock.tick(rate)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        source.rumble(0, 0)
        source.close()
        pad.close()


def serve(stop, on_status=None, deadzone=0.08, rate=250):
    """Background mode (used by the tray icon): no prompts, no printing.

    Waits for any usable controller (USB or Bluetooth), bridges it, and goes back to
    waiting when it disconnects, until `stop` (a threading.Event) is set.
    on_status(kind, detail) is called with kind "waiting", "connected" or "unmapped".
    """
    status = on_status or (lambda kind, detail: None)
    start_sdl()
    pad = VirtualXbox()  # raises BridgeError if ViGEmBus is missing
    previous = None
    try:
        while not stop.is_set():
            status("waiting", None)
            info, rescan, warned, next_rescan = None, True, set(), 0.0
            while info is None and not stop.is_set():
                if rescan:
                    rescan = False
                    info = _find_ready(previous)
                    unmapped = [d.name for d in list_devices()
                                if not is_virtual_xbox(d.name) and not d.ready and d.name not in warned]
                    if info is None and unmapped:
                        warned.update(unmapped)
                        status("unmapped", unmapped[0])
                stop.wait(0.25)
                added, _ = poll_device_changes()
                # While an unknown controller waits to be mapped, keep checking for its new mapping.
                rescan = added or (warned and time.monotonic() > next_rescan)
                if rescan:
                    next_rescan = time.monotonic() + 2
            if info is None:
                break

            source = open_source(info)
            previous = info
            status("connected", info.name)
            clock = pygame.time.Clock()
            try:
                while not stop.is_set():
                    if source.instance_id in poll_device_changes()[1]:
                        break
                    pad.send(source.read(), deadzone)
                    rumble = pad.take_rumble()
                    if rumble is not None:
                        source.rumble(*rumble)
                    clock.tick(rate)
            finally:
                pad.send(PadState())  # release everything
                source.rumble(0, 0)
                source.close()
    finally:
        pad.close()


def run_test(index=None):
    """Show live input without creating a virtual controller (no ViGEmBus needed)."""
    info = pick_device(index)
    source = open_source(info)
    print(f"\nTesting {info.name} ({source.kind}). Press buttons, move sticks. Ctrl+C to stop.\n")
    clock = pygame.time.Clock()
    try:
        while True:
            pygame.event.pump()
            print("\r" + _status_line(source.read()).ljust(78), end="", flush=True)
            clock.tick(30)
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        source.close()


__all__ = ["run_bridge", "run_test", "serve", "pick_device", "DeviceInfo"]
