"""Bluetooth checker: works out why a PS3 controller won't connect wirelessly.

Plug the controller in with USB while this runs - the PS3 driver (DsHidMini) records
on the USB device whether pairing it to this PC's Bluetooth worked.
"""
import json

from .doctor import _installed_drivers, _run, _service_running, bad, info, ok

DSHM_STATUS = "{3fecf510-cc94-4fbe-8839-738201f84d59}"
PROPS = {  # DsHidMini device properties (include/DsHidMini/dshmguid.h)
    "pairing": f"{DSHM_STATUS} 5",        # LastHostRequestStatus (NTSTATUS)
    "pairing_old": f"{DSHM_STATUS} 3",    # LastPairingStatus (older drivers)
    "fake_address": f"{DSHM_STATUS} 7",   # DeviceAddressSynthesized: controller didn't report its address
    "clone": f"{DSHM_STATUS} 11",         # IdentificationCloneHeuristic
}

_PS = r"""
$out = @{}
$out.adapters = @(Get-PnpDevice -Class Bluetooth -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -match '^(USB|PCI)\\' } | ForEach-Object {
        $params = "HKLM:\SYSTEM\CurrentControlSet\Enum\$($_.InstanceId)\Device Parameters"
        $patch = (Get-ItemProperty -Path $params -Name BthPS3PSMPatchEnabled -ErrorAction SilentlyContinue).BthPS3PSMPatchEnabled
        @{ Name = $_.FriendlyName; Status = "$($_.Status)"; Id = $_.InstanceId; Patch = $patch }
    })
$out.pads = @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.Service -eq 'dshidmini' } | ForEach-Object {
        $dev = $_; $p = @{}
        foreach ($k in @(KEYS)) {
            $v = (Get-PnpDeviceProperty -InstanceId $dev.InstanceId -KeyName $k.Value -ErrorAction SilentlyContinue).Data
            $p[$k.Name] = $v
        }
        @{ Name = $dev.FriendlyName; Status = "$($dev.Status)"; Id = $dev.InstanceId; Props = $p }
    })
$out.windows_paired = @(Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -match 'PLAYSTATION|PS3' } | ForEach-Object { $_.FriendlyName })
$out | ConvertTo-Json -Depth 5
"""


def _ntstatus(v):
    if v is None:
        return None
    return int(v) & 0xFFFFFFFF


def _gather():
    keys = ",".join(f"@{{Name='{n}';Value='{k}'}}" for n, k in PROPS.items())
    out = _run(["powershell", "-NoProfile", "-Command", _PS.replace("@(KEYS)", f"@({keys})")]).strip()
    try:
        return json.loads(out)
    except ValueError:
        return {"adapters": [], "pads": [], "windows_paired": []}


def run_bt_check():
    print("\n=== Bluetooth check ===\n")
    todo = []
    data = _gather()

    adapters = data.get("adapters") or []
    working = [a for a in adapters if a.get("Status") == "OK"]
    if working:
        for a in working:
            ok(f"Bluetooth adapter: {a['Name']}")
    elif adapters:
        bad("Bluetooth adapter found but it isn't working / is turned off")
        todo.append("Turn Bluetooth on (Settings > Bluetooth & devices), then run this again.")
    else:
        bad("No Bluetooth adapter found")
        todo.append("This PC has no Bluetooth. Plug in a USB Bluetooth dongle (Bluetooth 4.0 or newer).")

    if "bthps3" in _installed_drivers():
        ok("BthPS3 driver is installed")
        if not _service_running("BthPS3"):
            info("BthPS3 isn't active right now (normal until a PS3 controller connects over Bluetooth)")
    else:
        bad("BthPS3 is NOT installed - this is what lets a PS3 controller connect over Bluetooth")
        todo.append("Run Setup.bat again (with Bluetooth turned on), or install BthPS3 from "
                    "https://github.com/nefarius/BthPS3/releases - then restart the PC.")

    for a in working:
        patch = a.get("Patch")
        if patch == 1:
            ok("BthPS3 is allowed to accept PS3 controllers on this adapter")
        elif patch is not None:
            bad("BthPS3 is installed but NOT accepting PS3 controllers on this adapter")
            todo.append("Restart the PC. If that doesn't help, re-run the BthPS3 installer and choose 'Repair'.")

    for name in data.get("windows_paired") or []:
        bad(f"Windows has '{name}' in its Bluetooth list - that blocks the PS3 driver")
        todo.append(f"Settings > Bluetooth & devices: remove '{name}', then plug the controller in by USB again.")

    pads = data.get("pads") or []
    usb = [p for p in pads if str(p.get("Id", "")).upper().startswith("USB\\")]
    wireless = [p for p in pads if not str(p.get("Id", "")).upper().startswith("USB\\")]
    if wireless:
        ok("A PS3 controller is connected over Bluetooth right now!")
    if not usb:
        info("Plug the PS3 controller in with the USB cable and run this again to check its pairing.")
    for p in usb:
        props = p.get("Props") or {}
        status = _ntstatus(props.get("pairing"))
        if status is None:
            status = _ntstatus(props.get("pairing_old"))
        if status == 0:
            ok("The controller is paired to this PC's Bluetooth")
        elif status is not None:
            bad(f"Pairing the controller to this PC's Bluetooth FAILED (code 0x{status:08X})")
            todo.append("Unplug the controller, wait 5 seconds, plug it back in and run this again.")
        else:
            info("The PS3 driver hasn't reported a pairing result for this controller")
        if props.get("fake_address") or props.get("clone"):
            bad("This looks like a clone (non-Sony) PS3 controller")
            todo.append("Many clone PS3 controllers can't connect over Bluetooth to a PC at all - "
                        "if everything else here is OK, the cable is the only option for this pad.")

    print()
    if todo:
        print("=== What to do next ===")
        for i, t in enumerate(dict.fromkeys(todo), 1):
            print(f"  {i}. {t}")
    elif wireless:
        print("Bluetooth is working.")
    else:
        print("Everything looks right. Unplug the cable and press the PS button.")
        print("If it still doesn't connect, copy everything above and send it.")
    print()
    print("Details:", json.dumps(data, default=str))
    return not todo
