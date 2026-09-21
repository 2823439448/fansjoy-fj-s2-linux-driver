#!/usr/bin/env python3
"""
Capture raw interrupt HID reports from a Fansjoy FJ-S2 tablet.

The script is intentionally self-contained.  It requires pyusb:

    sudo apt install python3-usb

Typical usage:

    sudo python3 probe_tablet.py --outfile raw_tablet.log --mark

While it is running, move the pen as requested in the prompt and press
Enter to write a marker (tl, tr, br, bl).  Press Ctrl-C to stop.
The kernel driver is detached from the selected interface only while
the script runs and is re-attached on exit.
"""

import argparse
import os
import select
import struct
import sys
import time

try:
    import usb.core
    import usb.util
except ImportError:
    sys.stderr.write(
        "pyusb is not installed.  Install it with:\n"
        "    sudo apt install python3-usb\n"
    )
    sys.exit(2)


MARKERS = ["tl", "tr", "br", "bl"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vid", default="2d80")
    p.add_argument("--pid", default="3013")
    p.add_argument("--interface", type=int, default=0,
                   help="USB interface number (0 = pen + keyboard)")
    p.add_argument("--endpoint", type=int, default=0,
                   help="endpoint address as an integer, e.g. 0x81")
    p.add_argument("--outfile", default="raw_tablet.log")
    p.add_argument("--timeout-ms", type=int, default=500)
    p.add_argument("--no-detach", action="store_true",
                   help="do not detach the kernel HID driver")
    p.add_argument("--mark", action="store_true",
                   help="write corner markers on Enter")
    return p.parse_args()


def find_device(vid, pid):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        sys.stderr.write(f"device {vid:04x}:{pid:04x} not found\n")
        sys.exit(1)
    return dev


def select_interrupt_in(dev, interface, endpoint_addr):
    cfg = dev.get_active_configuration()
    intf = cfg[(interface, 0)]
    for ep in intf:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN and \
           usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR:
            if endpoint_addr and ep.bEndpointAddress != endpoint_addr:
                continue
            return intf, ep
    raise RuntimeError("no matching interrupt IN endpoint found")


def read_stdin_marker(mark_index):
    if not select.select([sys.stdin], [], [], 0)[0]:
        return mark_index
    line = sys.stdin.readline()
    if not line:
        return mark_index
    if mark_index >= len(MARKERS):
        return mark_index
    label = MARKERS[mark_index]
    sys.stdout.write(f"# MARK {label}\n")
    sys.stdout.flush()
    return mark_index + 1


def maybe_print_marker_prompt(mark_index, printed):
    if mark_index >= len(MARKERS) or mark_index in printed:
        return printed
    label = MARKERS[mark_index].upper()
    sys.stderr.write(
        f"\n>>> Place the pen at {label} and hold still, then press Enter.\n"
    )
    sys.stderr.flush()
    printed.add(mark_index)
    return printed


def main():
    args = parse_args()
    vid = int(args.vid, 16)
    pid = int(args.pid, 16)
    endpoint_addr = args.endpoint

    dev = find_device(vid, pid)
    intf, ep = select_interrupt_in(dev, args.interface, endpoint_addr)

    if dev.is_kernel_driver_active(intf.bInterfaceNumber) and not args.no_detach:
        dev.detach_kernel_driver(intf.bInterfaceNumber)

    try:
        usb.util.claim_interface(dev, intf.bInterfaceNumber)

        out = open(args.outfile, "w", encoding="ascii")
        out.write("# fans-joy-s2 raw HID report log v1\n")
        out.write(f"# vid={vid:04x} pid={pid:04x} interface={intf.bInterfaceNumber}\n")
        out.write(f"# endpoint=0x{ep.bEndpointAddress:02x} packet={ep.wMaxPacketSize}\n")
        out.flush()

        mark_index = 0
        printed = set()
        if args.mark:
            sys.stderr.write(
                "Marker order: TL (top-left), TR (top-right), "
                "BR (bottom-right), BL (bottom-left).\n"
            )
        while True:
            if args.mark:
                printed = maybe_print_marker_prompt(mark_index, printed)
                mark_index = read_stdin_marker(mark_index)

            try:
                data = bytes(dev.read(ep.bEndpointAddress,
                                      ep.wMaxPacketSize,
                                      timeout=args.timeout_ms))
            except usb.core.USBError as exc:
                if exc.errno == 110 or exc.backend_error_code == -7:
                    continue
                sys.stderr.write(f"USB read error: {exc}\n")
                time.sleep(0.05)
                continue

            if not data:
                continue

            ts = time.time()
            hexstr = " ".join(f"{b:02x}" for b in data)
            line = f"{ts:.6f} {hexstr}\n"
            out.write(line)
            sys.stdout.write(line)
            out.flush()
            sys.stdout.flush()
    finally:
        try:
            usb.util.release_interface(dev, intf.bInterfaceNumber)
        except Exception:
            pass
        try:
            if not args.no_detach:
                dev.attach_kernel_driver(intf.bInterfaceNumber)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
