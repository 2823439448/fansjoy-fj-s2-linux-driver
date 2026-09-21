# Fansjoy FJ-S2 verification record

This file records what has actually been verified on this machine and what
still requires root-level live testing.

## Verified without loading the module

- Device is present on USB: `Bus 003 Device 006: ID 2d80:3013 Fansjoy FJ-S2`
- Two HID interfaces exist:
  - `0003:2D80:3013.0005` at `usb-.../input0`, currently `hid-generic`
  - `0003:2D80:3013.0006` at `usb-.../input1`, currently `hid-generic`
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
  - vermagic: `7.0.0-30-generic SMP preempt mod_unload modversions`

## Still requires `sudo` on the live device

- Four-corner raw capture with `probe_tablet.py --mark`
- Direction confirmation and final calibration matrix with
  `analyze_tablet.py`
- Load test with `insmod`/`modprobe`
- `evtest` verification of `ABS_X`, `ABS_Y`, `ABS_PRESSURE`,
  `BTN_STYLUS`, `BTN_STYLUS2` and pad keys
- Reboot test to confirm automatic loading

## Expected result after live testing

- `lsmod | grep fans_joy_s2` shows the module
- `dmesg | grep fans-joy` shows the tablet interface started
- Pen and cursor positions correspond, with any minor correction done by the
  libinput calibration matrix rather than hard-coded rotation in the driver
- Mouse, keyboard and touchpad are unaffected
