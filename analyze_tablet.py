#!/usr/bin/env python3
"""
Analyze raw FJ-S2 report logs captured by probe_tablet.py.

It extracts pen report id 1, determines X/Y ranges, pressure range,
coordinate direction from four marked corners, and emits a calibration
Markdown file plus a libinput calibration matrix suggestion.

Run it after probe_tablet.py has written a log:

    python3 analyze_tablet.py --log raw_tablet.log
"""

import argparse
import re
import struct
import sys


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", default="raw_tablet.log")
    p.add_argument("--output-md", default="fans_joy_s2_calibration.md")
    p.add_argument("--screen", default="2560x1440",
                   help="screen size, WxH")
    p.add_argument("--mapping-area", default="full",
                   help="full or partial mapping area")
    return p.parse_args()


def signed16(b):
    v = struct.unpack("<h", b)[0]
    return v


def parse_pen_report(hex_bytes):
    """
    Report id 1 layout confirmed from the device report descriptor:
      byte 0: report id (0x01)
      byte 1: bits
              bit0 tip switch
              bit1 barrel switch
              bit2 eraser
              bit3 invert
              bit5 in-range
      bytes 2..3: X (LE)
      bytes 4..5: Y (LE)
      bytes 6..7: pressure (LE)
      bytes 8..9: tilt X (signed LE)
      bytes 10..11: tilt Y (signed LE)
    """
    if len(hex_bytes) < 12 or hex_bytes[0] != 1:
        return None
    b1 = hex_bytes[1]
    return {
        "tip": bool(b1 & 0x01),
        "barrel": bool(b1 & 0x02),
        "eraser": bool(b1 & 0x04),
        "invert": bool(b1 & 0x08),
        "in_range": bool(b1 & 0x20),
        "x": struct.unpack("<H", bytes(hex_bytes[2:4]))[0],
        "y": struct.unpack("<H", bytes(hex_bytes[4:6]))[0],
        "pressure": struct.unpack("<H", bytes(hex_bytes[6:8]))[0],
        "tilt_x": signed16(bytes(hex_bytes[8:10])),
        "tilt_y": signed16(bytes(hex_bytes[10:12])),
    }


def iter_reports(log):
    samples = []
    current_marker = None
    marker_samples = {}
    pending = None

    for line in log:
        m = re.match(r"\s*#\s*MARK\s+(\S+)", line, re.I)
        if m:
            if current_marker is not None and pending is not None:
                marker_samples[current_marker] = pending
            current_marker = m.group(1).lower()
            pending = None
            continue

        hexes = re.findall(r"\b[0-9a-fA-F]{2}\b", line)
        if not hexes:
            continue
        parsed = parse_pen_report([int(x, 16) for x in hexes])
        if parsed is None:
            continue
        samples.append(parsed)

        # Prefer the first in-range report immediately after a marker.
        # Holding the pen still for two seconds before pressing Enter makes
        # this sample a reliable corner measurement.
        if current_marker is not None and pending is None and parsed["in_range"]:
            pending = parsed

    if current_marker is not None and pending is not None:
        marker_samples[current_marker] = pending

    return samples, marker_samples


def calibration_matrix(corners):
    if not all(k in corners for k in ("tl", "tr", "bl", "br")):
        return None
    tl = corners["tl"]
    tr = corners["tr"]
    bl = corners["bl"]
    br = corners["br"]

    top_dx = tr["x"] - tl["x"]
    top_dy = tr["y"] - tl["y"]
    left_dx = bl["x"] - tl["x"]
    left_dy = bl["y"] - tl["y"]

    # If the X axis is horizontal, the top row changes mostly in X and the
    # left column changes mostly in Y.
    landscape = abs(top_dx) >= abs(top_dy) and abs(left_dy) >= abs(left_dx)
    x_right = top_dx > 0
    y_down = left_dy > 0

    if landscape:
        if x_right and y_down:
            return "1 0 0 0 1 0 0 0 1"
        if x_right and not y_down:
            return "1 0 0 0 -1 1 0 0 1"
        if not x_right and y_down:
            return "-1 0 1 0 1 0 0 0 1"
        return "-1 0 1 0 -1 1 0 0 1"

    # Portrait: X and Y are swapped relative to the screen.
    if top_dy < 0 and left_dx > 0:
        return "0 -1 1 1 0 0 0 0 1"
    if top_dy > 0 and left_dx < 0:
        return "0 1 0 -1 0 1 0 0 1"
    if top_dy > 0 and left_dx > 0:
        return "0 1 0 1 0 0 0 0 1"
    return "0 -1 1 -1 0 1 0 0 1"


def write_md(path, corners, samples, matrix, screen, mapping_area):
    if samples:
        xs = [s["x"] for s in samples]
        ys = [s["y"] for s in samples]
        ps = [s["pressure"] for s in samples]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        p_min, p_max = min(ps), max(ps)
    else:
        x_min = x_max = y_min = y_max = p_min = p_max = 0

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Fansjoy FJ-S2 calibration\n\n")
        f.write("## Device identification\n\n")
        f.write("- Brand: Fansjoy (凡画)\n")
        f.write("- Model: S2 / FJ-S2\n")
        f.write("- VID: 2d80\n")
        f.write("- PID: 3013\n")
        f.write("- USB interface 0: pen + keyboard, interrupt IN endpoint 0x81\n")
        f.write("- USB interface 1: vendor-defined configuration, endpoints 0x82 IN / 0x02 OUT\n")
        f.write("- Kernel HID name: Fansjoy FJ-S2\n\n")
        f.write("## Coordinate mapping\n\n")
        f.write(f"- X observed range: {x_min}..{x_max}\n")
        f.write(f"- Y observed range: {y_min}..{y_max}\n")
        f.write("- X descriptor range: 0..16800\n")
        f.write("- Y descriptor range: 0..10500\n")
        if corners:
            for label in ("tl", "tr", "bl", "br"):
                c = corners[label]
                f.write(f"- {label.upper()}: X={c['x']} Y={c['y']}\n")
        f.write(f"- Screen: {screen}\n")
        f.write(f"- Mapping area: {mapping_area}\n")
        f.write(f"- Libinput calibration matrix: {matrix if matrix else 'not enough corner data'}\n\n")
        f.write("## Pressure and buttons\n\n")
        f.write(f"- Pressure observed range: {p_min}..{p_max}\n")
        f.write("- Pressure descriptor range: 0..8191\n")
        f.write("- Tip switch -> BTN_TOUCH\n")
        f.write("- Barrel switch -> BTN_STYLUS\n")
        f.write("- Invert -> BTN_STYLUS2\n")
        f.write("- Eraser -> BTN_TOOL_RUBBER\n")
        f.write("- In-range -> BTN_TOOL_PEN\n")
        f.write("- Tilt X -> ABS_TILT_X (-9000..9000)\n")
        f.write("- Tilt Y -> ABS_TILT_Y (-9000..9000)\n\n")
        f.write("## Raw HID report format (interface 0)\n\n")
        f.write("- Pen report ID: 0x01, length 12 bytes\n")
        f.write("- Byte 0: report ID 0x01\n")
        f.write("- Byte 1: tip/barrel/eraser/invert/in-range bit field\n")
        f.write("- Bytes 2..3: X little-endian\n")
        f.write("- Bytes 4..5: Y little-endian\n")
        f.write("- Bytes 6..7: pressure little-endian\n")
        f.write("- Bytes 8..9: tilt X signed little-endian\n")
        f.write("- Bytes 10..11: tilt Y signed little-endian\n")
        f.write("- Keyboard report ID: 0x02, length 13 bytes\n\n")
        f.write("## Direction and screen mapping\n\n")
        if matrix:
            f.write(f"- Calibration matrix: {matrix}\n")
        else:
            f.write("- Direction could not be determined; collect four corner markers.\n")


def main():
    args = parse_args()
    try:
        logfile = open(args.log, "r", encoding="ascii", errors="replace")
    except FileNotFoundError:
        print(
            f"error: {args.log} does not exist.\n"
            "Run the probe first:\n"
            "  sudo python3 probe_tablet.py --outfile raw_tablet.log --mark",
            file=sys.stderr,
        )
        sys.exit(2)

    with logfile:
        samples, corners = iter_reports(logfile)

    matrix = calibration_matrix(corners)
    write_md(args.output_md, corners, samples, matrix,
             args.screen, args.mapping_area)

    print(f"parsed {len(samples)} pen reports")
    print(f"corners: {sorted(corners) if corners else 'missing'}")
    print(f"matrix: {matrix}")
    print(f"wrote {args.output_md}")

    if samples:
        xs = [s["x"] for s in samples]
        ys = [s["y"] for s in samples]
        ps = [s["pressure"] for s in samples]
        print("\nSuggested driver constants (copy into fans_joy_s2.c):")
        print(f"#define S2_X_MIN {min(xs)}")
        print(f"#define S2_X_MAX {max(xs)}")
        print(f"#define S2_Y_MIN {min(ys)}")
        print(f"#define S2_Y_MAX {max(ys)}")
        print(f"#define S2_PRESSURE_MIN {min(ps)}")
        print(f"#define S2_PRESSURE_MAX {max(ps)}")


if __name__ == "__main__":
    main()
