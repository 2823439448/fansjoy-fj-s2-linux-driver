#!/usr/bin/env python3
"""
Diagnose the real coordinate range of the Fansjoy FJ-S2 tablet.

This script reads the raw interrupt HID reports directly from USB, so it
bypasses the kernel driver and shows exactly what the hardware reports.

Usage:
    sudo python3 diagnose_tablet.py

While it is running, move the pen over the whole usable area and touch all
four corners.  Press Ctrl-C when done.  The script prints the observed
minimum/maximum raw X, Y and pressure values and writes the raw log to
diagnose_raw.log.
"""

import argparse
import struct
import sys
import time

try:
    import usb.core
    import usb.util
except ImportError:
    sys.stderr.write("pyusb is not installed: sudo apt install python3-usb\n")
    sys.exit(2)


VID = 0x2D80
PID = 0x3013
INTERFACE = 0
ENDPOINT = 0x81


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeout-ms", type=int, default=100)
    p.add_argument("--outfile", default="diagnose_raw.log")
    return p.parse_args()


def find_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.stderr.write(f"device {VID:04x}:{PID:04x} not found\n")
        sys.exit(1)
    return dev


def find_endpoint(dev):
    cfg = dev.get_active_configuration()
    intf = cfg[(INTERFACE, 0)]
    for ep in intf:
        if (usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN and
                usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR and
                ep.bEndpointAddress == ENDPOINT):
            return intf, ep
    raise RuntimeError(f"endpoint 0x{ENDPOINT:02x} not found")


def main():
    args = parse_args()
    dev = find_device()
    intf, ep = find_endpoint(dev)

    if dev.is_kernel_driver_active(intf.bInterfaceNumber):
        dev.detach_kernel_driver(intf.bInterfaceNumber)

    x_min = y_min = p_min = None
    x_max = y_max = p_max = None
    samples = 0
    last_print = 0.0

    try:
        usb.util.claim_interface(dev, intf.bInterfaceNumber)
        with open(args.outfile, "w", encoding="ascii") as out:
            out.write("# fans-joy-s2 raw diagnostic log\n")
            out.write(f"# vid={VID:04x} pid={PID:04x}\n")
            print("Move the pen over the full tablet and touch all corners.")
            print("Press Ctrl-C when done.\n")

            while True:
                try:
                    data = bytes(dev.read(ep.bEndpointAddress,
                                          ep.wMaxPacketSize,
                                          timeout=args.timeout_ms))
                except usb.core.USBError as exc:
                    if exc.errno in (110, -7) or exc.backend_error_code == -7:
                        continue
                    sys.stderr.write(f"USB read error: {exc}\n")
                    time.sleep(0.05)
                    continue

                if not data:
                    continue

                out.write(" ".join(f"{b:02x}" for b in data) + "\n")
                out.flush()

                if len(data) < 12 or data[0] != 0x01:
                    continue

                x = struct.unpack("<H", bytes(data[2:4]))[0]
                y = struct.unpack("<H", bytes(data[4:6]))[0]
                pressure = struct.unpack("<H", bytes(data[6:8]))[0]
                in_range = bool(data[1] & 0x20)

                if not in_range:
                    continue

                samples += 1
                x_min = x if x_min is None else min(x_min, x)
                x_max = x if x_max is None else max(x_max, x)
                y_min = y if y_min is None else min(y_min, y)
                y_max = y if y_max is None else max(y_max, y)
                p_min = pressure if p_min is None else min(p_min, pressure)
                p_max = pressure if p_max is None else max(p_max, pressure)

                now = time.time()
                if now - last_print >= 0.5:
                    print(f"X={x:<6} Y={y:<6} P={pressure:<5} "
                          f"range X[{x_min},{x_max}] Y[{y_min},{y_max}]",
                          flush=True)
                    last_print = now
    finally:
        try:
            usb.util.release_interface(dev, intf.bInterfaceNumber)
        except Exception:
            pass
        try:
            dev.attach_kernel_driver(intf.bInterfaceNumber)
        except Exception:
            pass

    print("\n=== RESULT ===")
    if samples == 0:
        print("No in-range pen samples captured.")
    else:
        print(f"samples: {samples}")
        print(f"X min/max: {x_min} / {x_max}")
        print(f"Y min/max: {y_min} / {y_max}")
        print(f"pressure min/max: {p_min} / {p_max}")
    print(f"raw log: {args.outfile}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
