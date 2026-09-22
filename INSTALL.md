# Build, install and verify Fansjoy FJ-S2

All work is done in `/home/dlc/work`.

## Quick automatic install

```bash
cd /home/dlc/work
sudo ./install-fans-joy-s2.sh
```

This installs the build toolchain and kernel headers, builds the module,
installs it under `/lib/modules/$(uname -r)/extra/`, enables loading at boot
through `/etc/modules-load.d/fans-joy-s2.conf`, and installs the libinput
identity rule plus KDE defaults needed to map the raw tablet axes to the full
landscape screen without rotation.

To install the driver with a custom libinput rotation:

```bash
sudo ./install-fans-joy-s2.sh libinput "0 1 0 -1 0 1"
```

To remove it:

```bash
sudo ./install-fans-joy-s2.sh uninstall
```

## 1. Install the build toolchain (one time)

```bash
sudo apt update
sudo apt install build-essential linux-headers-$(uname -r) git python3-usb
```

Confirm the kernel build directory exists:

```bash
ls -ld /lib/modules/$(uname -r)/build
```

## 2. Capture raw reports before finalizing the calibration

```bash
cd /home/dlc/work
sudo python3 probe_tablet.py --outfile raw_tablet.log --mark
```

Move the pen to the four corners and press Enter after each hold:

1. top-left, Enter
2. top-right, Enter
3. bottom-right, Enter
4. bottom-left, Enter
5. Ctrl-C

Then generate/update calibration data:

```bash
python3 analyze_tablet.py --log raw_tablet.log
```

Read `fans_joy_s2_calibration.md`.  If direction is confirmed as identity,
the driver constants already match the descriptor.

## 3. libinput calibration (default: no rotation)

The driver reports raw coordinates and does not rotate them.  The shipped udev
rule installs an identity matrix by default, so the tablet maps one-to-one to
a landscape screen:

```bash
sudo cp /home/dlc/work/99-fans-joy-s2-calibration.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The default matrix is:

```text
1 0 0 0 1 0
```

If you later want to rotate or mirror the tablet further, edit
`/etc/udev/rules.d/99-fans-joy-s2-calibration.rules` and reload the rules.

## 4. Build the module

```bash
cd /home/dlc/work
make
```

This creates `fans_joy_s2.ko`.

## 5. Test-load without touching boot configuration

First verify the matching VID/PID:

```bash
lsusb | grep -i fansjoy
```

During testing, the tablet interface can be freed from the generic driver:

```bash
sudo rmmod hid-generic
sudo rmmod usbhid
sudo insmod /home/dlc/work/fans_joy_s2.ko
sudo dmesg | tail -30
```

> `rmmod hid-generic` can affect other HID devices.  If you are concerned,
> keep an SSH session open or use a text console.  The final install below is
> safer because the custom driver's id_table only matches `2d80:3013`.

Verify input devices:

```bash
ls /dev/input/event*
sudo evtest
```

Check that:

- pen movement changes `ABS_X` and `ABS_Y`
- pressure changes `ABS_PRESSURE`
- side switches produce `BTN_STYLUS` / `BTN_STYLUS2`
- the keyboard/pad input still reports its keys
- mouse, keyboard and touchpad are unaffected

Unload the test module and restore the generic stack:

```bash
sudo rmmod fans_joy_s2
sudo modprobe usbhid
sudo modprobe hid-generic
```

## 6. Install and enable automatic loading

```bash
cd /home/dlc/work
sudo make install
sudo modprobe fans_joy_s2
```

Enable load at boot:

```bash
echo "fans_joy_s2" | sudo tee /etc/modules-load.d/fans-joy-s2.conf
```

If you are installing on an already-booted system and the tablet is currently
bound to `hid-generic`, the new driver is not automatically forced onto the
existing device.  Either unplug/replug the tablet after running
`sudo modprobe fans_joy_s2`, or use the test sequence in section 4 to unbind
and rebind the HID stack.

Verify:

```bash
lsmod | grep fans_joy_s2
modinfo fans_joy_s2
dmesg | grep fans-joy
```

`modinfo` must report the module at:

```text
/lib/modules/$(uname -r)/extra/fans_joy_s2.ko
```

## 7. After a kernel upgrade

Because DKMS is not used, the module must be reinstalled after every kernel
update:

```bash
cd /home/dlc/work
make clean
make
sudo make install
```
