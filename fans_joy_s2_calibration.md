# Fansjoy FJ-S2 calibration

> Status note: values below that are marked **verified** were read from the
> live device's sysfs report descriptor / udev data and confirmed by live
> testing with `fans_joy_s2.ko`.  The X range is `0..16800`, the Y range is
> `0..10500`, and the final orientation mapping is the identity.  If the device
> is ever re-captured, `analyze_tablet.py` can regenerate this file.

## Device identification

- Brand: Fansjoy (凡画)
- Model: S2 / FJ-S2
- VID: **0x2d80** (verified)
- PID: **0x3013** (verified)
- USB interface 0: pen + keyboard, interrupt IN endpoint **0x81** (verified)
- USB interface 1: vendor-defined configuration, endpoints **0x82 IN / 0x02 OUT** (verified)
- Kernel HID name: **Fansjoy FJ-S2** (verified)
- Serial: FJSMD000000000 (verified)
- Current handler before custom driver: `hid-generic` (verified)

## Coordinate mapping

- X descriptor range: **0..16800** (verified from report descriptor)
- X captured raw range: **0..16800** (observed from diagnose_raw.log)
- Y logical range: **0..10500** (verified from report descriptor)
- X direction: left-to-right increasing (observed)
- Y direction: top-to-bottom increasing (observed)
- Physical size: **430 x 269 mm** (verified from udev `ID_INPUT_WIDTH_MM`/`ID_INPUT_HEIGHT_MM`)
- Natural orientation: landscape (native long axis = X, native short axis = Y)
- Screen: **2560x1440** (verified from connected eDP mode)
- Mapping area: full screen (verified by corner-to-corner pen movement)
- Rotation needed: **none (identity)**
- Rotation location: **libinput calibration matrix**
- Libinput calibration matrix: `1 0 0 0 1 0`
- KDE/libinput 4x4 form: `1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1`

## Pressure and buttons

- Pressure range: **0..8191** (verified from report descriptor)
- Pressure offset: **0** (provisional)
- Tip switch -> **BTN_TOUCH**
- Barrel switch -> **BTN_STYLUS**
- Invert -> **BTN_STYLUS2**
- Eraser -> **BTN_TOOL_RUBBER**
- In-range -> **BTN_TOOL_PEN**
- Tilt X -> **ABS_TILT_X** (-9000..9000)
- Tilt Y -> **ABS_TILT_Y** (-9000..9000)
- Pad/physical keys: exposed as a standard boot-keyboard report (report ID 2) on interface 0; left to the generic HID keyboard input so existing express keys continue to work (verified from descriptor)

## Raw HID report format (interface 0)

- Pen report ID: **0x01**, length **12 bytes**
- Byte 0: report ID 0x01
- Byte 1: bit field
  - bit 0: tip switch
  - bit 1: barrel switch
  - bit 2: eraser
  - bit 3: invert
  - bit 5: in-range
- Bytes 2..3: X, little-endian
- Bytes 4..5: Y, little-endian
- Bytes 6..7: pressure, little-endian
- Bytes 8..9: tilt X, signed little-endian
- Bytes 10..11: tilt Y, signed little-endian
- Keyboard report ID: **0x02**, length **13 bytes**
  - byte 1: 8 modifier bits
  - bytes 2..13: 12-byte keyboard key array

## Direction and screen mapping

The tablet's raw axes already match the landscape screen, so libinput applies
the identity matrix:

```text
1 0 0
0 1 0
0 0 1
```

The six-value form for udev/libinput is:

```text
1 0 0 0 1 0
```
