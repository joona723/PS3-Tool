# PadBridge

Use a **PS3 controller** (or almost any other controller) in PC games.
PadBridge reads your controller and turns it into a **virtual Xbox 360 controller**,
which nearly every PC game supports.

## New PC? One click

1. Copy this whole folder to the PC (anywhere, e.g. the Desktop).
2. Double-click **`Setup.bat`**. It installs Python if needed, downloads the drivers
   (ViGEmBus, DsHidMini, and BthPS3 if the PC has Bluetooth), switches the PS3 driver to SXS mode,
   and starts PadBridge in the tray, from now on together with Windows.
   Click **Yes** whenever Windows asks for permission. If it says so, restart the PC once.
3. Plug the PS3 controller in with the USB cable and press the **PS button**. The tray icon turns
   green, and the controller is now also paired with the PC's Bluetooth.
4. Unplug the cable and press the PS button to play wirelessly.

If a controller's layout isn't recognised, PadBridge opens the button-mapping window by itself.
Press each button it asks for, once.

## Quick start

1. **Double-click `start.bat`** (it installs what it needs the first time).
2. Choose **1. Check setup**. It tells you exactly what's missing.
3. When the check says everything is good, choose **2. Start** and launch your game.
   Keep the PadBridge window open while you play.

## One-time setup for a PS3 controller

Windows can't read a PS3 controller without a driver, so a program alone can't fix that.
You need these two free, open-source drivers:

| What | Why | Download |
|---|---|---|
| **DsHidMini** | lets Windows read the PS3 controller | https://github.com/nefarius/DsHidMini/releases |
| **ViGEmBus** | creates the virtual Xbox controller (already installed on this PC) | https://github.com/nefarius/ViGEmBus/releases |
| BthPS3 *(optional)* | only if you want to play **wireless** over Bluetooth | https://github.com/nefarius/BthPS3/releases |
| HidHide *(optional)* | hides the real controller so games don't see it twice | https://github.com/nefarius/HidHide/releases |

After installing DsHidMini, plug the controller in with a **USB cable** and press the **PS button**.

**Which DsHidMini mode?** DsHidMini comes with a settings app (DSHMC) where you choose a mode:
- **SXS**: recommended for PadBridge. Its button layout is recognised automatically.
- **XInput**: DsHidMini turns the controller into an Xbox controller by itself. If that's all
  you want, you don't need PadBridge running. PadBridge is still useful for custom button
  mapping and for other controllers.
- Any other mode: works too. Just use **4. Map controller buttons** once.

## Run it in the background (system tray)

Double-click **`PadBridge.pyw`** (or choose **6** in the menu). A small gamepad icon appears by the clock:

- **grey**: waiting for a controller. Just plug it in or turn it on (USB or Bluetooth).
- **green**: connected and working. Hover the icon to see which controller is connected.
- **orange**: this controller needs its buttons mapped once (right-click > *Setup / map buttons*, option 4).
- **red**: something is wrong (usually a missing driver). Right-click > *Setup / map buttons* > option 1.

Right-click the icon for **Start with Windows** (so you never have to start it yourself) and **Quit**.
It shows a notification when a controller connects or disconnects, and reconnects automatically,
even when you switch from the USB cable to Bluetooth. Problems are written to `padbridge.log`.

## Going wireless (Bluetooth) later

1. Install **BthPS3** (link above). Your PC needs a Bluetooth adapter.
2. Plug the PS3 controller in with the USB cable **once**. DsHidMini pairs it to your PC automatically.
   Don't pair it in Windows' Bluetooth settings, because that doesn't work for PS3 controllers.
3. Unplug the cable and press the **PS button**. It connects wirelessly, and the tray icon turns green.

Nothing in PadBridge needs to change. Note: a *custom* button mapping (option 4) is saved per connection
type, so if you made one over USB, map once more over Bluetooth. In SXS mode you don't need a mapping at all.

## Other controllers

- **Known controllers** (PS4, PS5, Switch Pro, 8BitDo, most popular pads): they work right away.
- **Anything else**: choose **4. Map controller buttons** and press each button when it asks.
  Your mapping is saved in the `profiles/` folder and used automatically from then on.

## Menu options

| Option | What it does |
|---|---|
| 0. Set up this PC | Same as `Setup.bat`: installs drivers, configures them, starts the tray icon |
| 1. Check setup | Checks drivers and lists the controllers PadBridge can see |
| 2. Start | Real controller → virtual Xbox controller. Rumble is passed through when supported. Reconnects automatically if the controller is unplugged. |
| 3. Test controller | Shows your button presses live (no game needed) |
| 4. Map controller buttons | Records a custom layout |
| 5. Reset mapping | Deletes a custom layout |
| 6. Run in the system tray | Same as Start, but in the background with a tray icon (see above) |

Command line, for advanced users: `python -m padbridge [setup|doctor|list|run|test|tray|map]`.
For example, `python -m padbridge run --deadzone 0.12` adds extra stick deadzone for a drifting stick.

## How it's built (for adding features later)

```
padbridge/
  sources.py   reads real controllers (SDL via pygame); add new input types here
  profiles.py  saves and loads custom button mappings (JSON)
  mapper.py    the "press each button" mapping wizard
  xbox.py      the virtual Xbox 360 controller (ViGEmBus via vgamepad)
  bridge.py    main loop: read -> deadzone -> send, plus rumble and reconnect
  tray.py      system tray icon, notifications, start with Windows
  doctor.py    setup checker
  installer.py one-click setup for a new PC (drivers, DsHidMini mode, autostart)
  state.py     controller-independent button/stick/trigger state
```
