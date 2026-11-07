// SPDX-License-Identifier: GPL-2.0-only
/*
 * Panasonic CF-19 Tablet Button driver.
 *
 * Modernized from the Panasonic CF-18/19 Tablet Button driver by Heiher
 * <admin@heiher.info>, Copyright (C) 2012. The original driver is derived
 * from panasonic-laptop.c, Copyright (C) 2002-2004 John Belmonte.
 *
 * The HINF decoding and scan-code/key map below retain that driver's
 * documented behavior. The ACPI match is intentionally restricted to
 * MAT001F, the CF-19 tablet-button device.
 */
#include <linux/acpi.h>
#include <linux/dmi.h>
#include <linux/input.h>
#include <linux/module.h>
#include <linux/pm.h>
#include <linux/slab.h>
#include <linux/string.h>

#include "hbtn-decode.h"

#define DRIVER_NAME "panasonic-hbtn"
#define HBTN_NOTIFY 0x80
#define HBTN_HINF "HINF"

struct hbtn_key {
	u8 scan;
	u16 keycode;
};

static const struct hbtn_key hbtn_keymap[] = {
	{ 0x34, KEY_F16 },	/* key button */
	{ 0x36, KEY_F15 },	/* rotate button */
	{ 0x3a, KEY_F13 },	/* keyboard button; Mk6 physical trace */
	{ 0x38, KEY_F14 },	/* circle button; Mk6 physical trace */
};

struct hbtn_data {
	struct input_dev *input;
};

static void hbtn_notify(struct acpi_device *adev, u32 event)
{
	struct hbtn_data *data = acpi_driver_data(adev);
	unsigned long long result;
	u8 scan;
	unsigned int i;
	bool pressed;
	acpi_status status;

	if (event != HBTN_NOTIFY) {
		dev_warn_ratelimited(&adev->dev, "unknown ACPI notify %#x\n", event);
		return;
	}

	status = acpi_evaluate_integer(adev->handle, HBTN_HINF, NULL, &result);
	if (ACPI_FAILURE(status)) {
		dev_err(&adev->dev, "failed to evaluate HINF\n");
		return;
	}

	/* Mk6 retains the upstream transition bit; bit 0 is release. */
	if (hbtn_decode(result, &scan, &pressed)) {
		dev_warn_ratelimited(&adev->dev, "invalid HINF result %#llx\n", result);
		return;
	}
	for (i = 0; i < ARRAY_SIZE(hbtn_keymap); i++) {
		if (hbtn_keymap[i].scan == scan) {
			input_event(data->input, EV_MSC, MSC_SCAN, scan);
			input_report_key(data->input, hbtn_keymap[i].keycode,
					 pressed);
			input_sync(data->input);
			return;
		}
	}

	dev_warn_ratelimited(&adev->dev, "unknown HINF scan code %#x (result %#llx)\n",
		scan, result);
}

static int hbtn_add(struct acpi_device *adev)
{
	struct hbtn_data *data;
	struct input_dev *input;
	unsigned int i;
	int error;
	const char *vendor = dmi_get_system_info(DMI_SYS_VENDOR);
	const char *product = dmi_get_system_info(DMI_PRODUCT_NAME);
	const char *board = dmi_get_system_info(DMI_BOARD_NAME);

	if (!vendor || strcmp(vendor, "Panasonic Corporation") ||
	    !product || strncmp(product, "CF-19", 5) ||
	    !board || strcmp(board, "CF19-6"))
		return -ENODEV;

	data = devm_kzalloc(&adev->dev, sizeof(*data), GFP_KERNEL);
	if (!data)
		return -ENOMEM;
	input = devm_input_allocate_device(&adev->dev);
	if (!input)
		return -ENOMEM;

	input->dev.parent = &adev->dev;
	input->name = "Panasonic CF-19 Tablet Buttons";
	input->phys = "panasonic/hbtn0";
	input->id.bustype = BUS_HOST;
	input_set_capability(input, EV_MSC, MSC_SCAN);
	for (i = 0; i < ARRAY_SIZE(hbtn_keymap); i++)
		input_set_capability(input, EV_KEY, hbtn_keymap[i].keycode);
	data->input = input;
	adev->driver_data = data;

	error = input_register_device(input);
	if (error)
		return error;
	dev_info(&adev->dev, "registered Panasonic CF-19 tablet buttons\n");
	return 0;
}

/* Release stale transitions around suspend, where firmware may lose key-up. */
static int hbtn_clear_keys(struct device *dev)
{
    struct hbtn_data *data = acpi_driver_data(to_acpi_device(dev));
    unsigned int i;

    for (i = 0; i < ARRAY_SIZE(hbtn_keymap); i++)
        input_report_key(data->input, hbtn_keymap[i].keycode, 0);
    input_sync(data->input);
    return 0;
}
static DEFINE_SIMPLE_DEV_PM_OPS(hbtn_pm, hbtn_clear_keys, hbtn_clear_keys);

static const struct acpi_device_id hbtn_ids[] = {
	{ "MAT001F", 0 },
	{ }
};
MODULE_DEVICE_TABLE(acpi, hbtn_ids);

static struct acpi_driver hbtn_driver = {
	.name = DRIVER_NAME,
	.class = "hotkey",
	.ids = hbtn_ids,
	.ops = { .add = hbtn_add, .notify = hbtn_notify },
	.drv.pm = pm_sleep_ptr(&hbtn_pm),
};
module_acpi_driver(hbtn_driver);

MODULE_AUTHOR("Heiher <admin@heiher.info> (original driver)");
MODULE_AUTHOR("Toughbook Fedora Tools contributors (modernization)");
MODULE_DESCRIPTION("Panasonic CF-19 Tablet Buttons");
MODULE_LICENSE("GPL v2");
