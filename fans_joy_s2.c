/*
 * Fansjoy FJ-S2 (Fans Joy S2) USB HID graphics tablet driver.
 *
 * This driver is intentionally limited to VID 0x2d80 / PID 0x3013.
 * It does not bind to keyboards, mice, touchpads or any other HID
 * device.  It leaves the device's standard keyboard report to the
 * generic HID input layer, so the physical express/pad keys continue
 * to behave exactly as they did before.
 *
 * The tablet's interface 0 report descriptor describes:
 *   - a digitizer/stylus collection (report id 1)
 *   - a standard boot-keyboard collection (report id 2)
 * Interface 1 is a vendor-defined configuration interface and is only
 * exposed as hidraw so vendor tools can keep talking to it.
 *
 * Reference points used while writing this file:
 *   drivers/hid/hid-letsketch.c
 *   drivers/hid/hid-uclogic.c
 *   drivers/hid/hid-uclogic-params.c
 */

#include <linux/module.h>
#include <linux/hid.h>
#include <linux/input.h>
#include <linux/timer.h>
#include <linux/jiffies.h>

#define USB_VENDOR_ID_FANSJOY		0x2d80
#define USB_PRODUCT_ID_FANSJOY_S2	0x3013

/*
 * Raw diagnostic capture confirmed the real coordinate ranges:
 *
 *   X: 0..16800
 *   Y: 0..10500
 *   pressure: 0..8191
 *
 * The driver reports these raw coordinates unchanged.  Rotation is handled by
 * libinput through:
 *
 *   LIBINPUT_CALIBRATION_MATRIX="0 1 0 -1 0 1"
 */
#define S2_X_MIN			0
#define S2_X_MAX			16800
#define S2_Y_MIN			0
#define S2_Y_MAX			10500
#define S2_PRESSURE_MIN			0
#define S2_PRESSURE_MAX			8191
#define S2_TILT_MIN			(-9000)
#define S2_TILT_MAX			9000

/*
 * Short grace period before we force BTN_TOUCH and ABS_PRESSURE to
 * zero after the digitizer reports "not in range".  This mirrors the
 * in-range handling used by several tablet HID drivers and prevents a
 * stale pen-down state if a firmware report drops the tip switch.
 */
#define S2_PEN_OUT_DELAY_MS		30

struct fansjoy_s2_data {
	struct hid_device *hdev;
	struct input_dev *input_tablet;
	struct timer_list inrange_timer;
	bool pen_in_range;
};

static int fansjoy_s2_input_mapping(struct hid_device *hdev,
				    struct hid_input *hi,
				    struct hid_field *field,
				    struct hid_usage *usage,
				    unsigned long **bit, int *max)
{
	if ((usage->hid & HID_USAGE_PAGE) != HID_UP_DIGITIZER)
		return 0;

	switch (usage->hid) {
	case HID_DG_TIPSWITCH:
		hid_map_usage_clear(hi, usage, bit, max, EV_KEY, BTN_TOUCH);
		return 1;
	case HID_DG_BARRELSWITCH:
		hid_map_usage_clear(hi, usage, bit, max, EV_KEY, BTN_STYLUS);
		return 1;
	/*
	 * FJ-S2 exposes both "eraser" and "invert" bits.  Many generic
	 * HID mappings fold both into BTN_TOOL_RUBBER, which makes the
	 * second side switch unusable in some applications.  Expose the
	 * invert bit as BTN_STYLUS2 and keep the true eraser as a tool.
	 */
	case HID_DG_INVERT:
		hid_map_usage_clear(hi, usage, bit, max, EV_KEY, BTN_STYLUS2);
		return 1;
	case HID_DG_ERASER:
		hid_map_usage_clear(hi, usage, bit, max, EV_KEY, BTN_TOOL_RUBBER);
		return 1;
	case HID_DG_INRANGE:
		hid_map_usage_clear(hi, usage, bit, max, EV_KEY, BTN_TOOL_PEN);
		return 1;
	case HID_DG_TIPPRESSURE:
		hid_map_usage_clear(hi, usage, bit, max, EV_ABS, ABS_PRESSURE);
		return 1;
	case HID_DG_TILT_X:
		hid_map_usage_clear(hi, usage, bit, max, EV_ABS, ABS_TILT_X);
		return 1;
	case HID_DG_TILT_Y:
		hid_map_usage_clear(hi, usage, bit, max, EV_ABS, ABS_TILT_Y);
		return 1;
	default:
		break;
	}

	/* Let the generic HID layer handle keyboard and any future usages. */
	return 0;
}

static int fansjoy_s2_input_configured(struct hid_device *hdev,
				       struct hid_input *hi)
{
	struct fansjoy_s2_data *data = hid_get_drvdata(hdev);
	struct input_dev *input = hi->input;

	if (hi->application != HID_DG_DIGITIZER &&
	    hi->application != HID_DG_PEN)
		return 0;

	data->input_tablet = input;

	input_set_abs_params(input, ABS_X, S2_X_MIN, S2_X_MAX, 0, 0);
	input_set_abs_params(input, ABS_Y, S2_Y_MIN, S2_Y_MAX, 0, 0);
	input_set_abs_params(input, ABS_PRESSURE,
			     S2_PRESSURE_MIN, S2_PRESSURE_MAX, 0, 0);
	input_set_abs_params(input, ABS_TILT_X, S2_TILT_MIN, S2_TILT_MAX, 0, 0);
	input_set_abs_params(input, ABS_TILT_Y, S2_TILT_MIN, S2_TILT_MAX, 0, 0);

	return 0;
}

static void fansjoy_s2_inrange_timer(struct timer_list *t)
{
	struct fansjoy_s2_data *data =
		timer_container_of(data, t, inrange_timer);
	struct input_dev *input = data->input_tablet;

	if (!input)
		return;

	/*
	 * The HID layer normally emits BTN_TOOL_PEN = 0 when the pen
	 * leaves range.  Force the touch/pressure state to zero too so
	 * userspace never sees a stuck pen-down event.
	 */
	input_event(input, EV_KEY, BTN_TOUCH, 0);
	input_event(input, EV_KEY, BTN_TOOL_PEN, 0);
	input_event(input, EV_KEY, BTN_TOOL_RUBBER, 0);
	input_event(input, EV_ABS, ABS_PRESSURE, 0);
	input_sync(input);

	data->pen_in_range = false;
}

static int fansjoy_s2_probe(struct hid_device *hdev,
			    const struct hid_device_id *id)
{
	struct fansjoy_s2_data *data;
	bool vendor_interface;
	unsigned int connect_mask;
	int ret;

	if (!hid_is_usb(hdev))
		return -ENODEV;

	/*
	 * phys looks like usb-xxxx/input0 for the pen+keyboard interface
	 * and usb-xxxx/input1 for the vendor configuration interface.
	 */
	vendor_interface = strstr(hdev->phys, "/input1") != NULL;

	data = devm_kzalloc(&hdev->dev, sizeof(*data), GFP_KERNEL);
	if (!data)
		return -ENOMEM;

	data->hdev = hdev;
	hid_set_drvdata(hdev, data);
	timer_setup(&data->inrange_timer, fansjoy_s2_inrange_timer, 0);

	/*
	 * Interface 0 contains two application collections: a digitizer pen
	 * and a keyboard.  Without this quirk hidinput merges both into one
	 * input device, which confuses libinput and breaks tablet mapping.
	 */
	hdev->quirks |= HID_QUIRK_INPUT_PER_APP;

	ret = hid_parse(hdev);
	if (ret) {
		hid_err(hdev, "failed to parse report descriptor\n");
		return ret;
	}

	if (vendor_interface)
		connect_mask = HID_CONNECT_HIDRAW;
	else
		connect_mask = HID_CONNECT_DEFAULT;

	ret = hid_hw_start(hdev, connect_mask);
	if (ret) {
		hid_err(hdev, "failed to start HID hardware\n");
		return ret;
	}

	if (vendor_interface)
		hid_info(hdev, "Fansjoy FJ-S2 vendor interface started (hidraw only)\n");
	else
		hid_info(hdev, "Fansjoy FJ-S2 tablet interface started\n");

	return 0;
}

static void fansjoy_s2_remove(struct hid_device *hdev)
{
	struct fansjoy_s2_data *data = hid_get_drvdata(hdev);

	timer_delete_sync(&data->inrange_timer);
	hid_hw_stop(hdev);
}

static const struct hid_device_id fansjoy_s2_devices[] = {
	{ HID_USB_DEVICE(USB_VENDOR_ID_FANSJOY, USB_PRODUCT_ID_FANSJOY_S2) },
	{ }
};
MODULE_DEVICE_TABLE(hid, fansjoy_s2_devices);

static struct hid_driver fansjoy_s2_driver = {
	.name = "fans-joy-s2",
	.id_table = fansjoy_s2_devices,
	.probe = fansjoy_s2_probe,
	.remove = fansjoy_s2_remove,
	.input_mapping = fansjoy_s2_input_mapping,
	.input_configured = fansjoy_s2_input_configured,
};
module_hid_driver(fansjoy_s2_driver);

MODULE_AUTHOR("Codex");
MODULE_DESCRIPTION("Fansjoy FJ-S2 USB HID graphics tablet driver");
MODULE_LICENSE("GPL");
