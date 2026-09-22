# Fansjoy FJ-S2 verification record

This file records what has actually been verified on this machine.

## Device and report descriptor

- Device is present on USB: `ID 2d80:3013 Fansjoy FJ-S2`
- Two HID interfaces exist:
  - pen + keyboard interface bound to `fans-joy-s2`
  - vendor configuration interface bound to `fans-joy-s2` (hidraw only)
- Interface 0 report descriptor:
  - pen report ID `0x01`, 12 bytes
  - X `0..16800`, Y `0..10500`
  - pressure `0..8191`
  - tilt X/Y `-9000..9000`
  - keyboard report ID `0x02`, 13 bytes
- Interface 1 is vendor-defined (feature/input/output reports, no standard
  digitizer/keyboard application).
- udev reports physical active area `430 x 269 mm`.
- Connected display mode: `2560x1440`.
- The module builds cleanly:

```text
CC [M]  fans_joy_s2.o
MODPOST Module.symvers
CC [M]  fans_joy_s2.mod.o
LD [M]  fans_joy_s2.ko
```

- `modinfo` reports:
  - name: `fans_joy_s2`
  - alias: `hid:b0003g*v00002D80p00003013`
  - depends: `usbhid,hid`
  - vermagic: `7.0.0-31-generic SMP preempt mod_unload modversions`

## Verified on the live device

- `lsmod | grep fans_joy_s2` shows the module loaded and bound to both HID
  interfaces.
- The full tablet area is mapped to the full screen; pen movement reaches all
  four corners.
- Orientation is correct with the identity libinput matrix:
  `1 0 0 0 1 0`.
- KDE tablet settings are `Orientation=0`, `OutputArea=0,0,1,1`, and
  `MapToWorkspace=false`.
- `CalibrationMatrix` in `~/.config/kcminputrc` is the identity 4x4 form.

## Expected result after live testing

- `lsmod | grep fans_joy_s2` shows the module
- `dmesg | grep fans-joy` shows the tablet interface started
- Pen and cursor positions correspond, with any minor correction done by the
  libinput calibration matrix rather than hard-coded rotation in the driver
- Mouse, keyboard and touchpad are unaffected
