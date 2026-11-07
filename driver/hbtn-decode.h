/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PANASONIC_HBTN_DECODE_H
#define PANASONIC_HBTN_DECODE_H

#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/types.h>
typedef u8 hbtn_u8;
typedef bool hbtn_bool;
#else
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
typedef uint8_t hbtn_u8;
typedef bool hbtn_bool;
#endif

/* CF-19 Mk6 physical trace: 0x34/35, 36/37, 38/39, 3a/3b.
 * Never mask unknown upper bits into a supported button. */
static inline int hbtn_decode(unsigned long long result, hbtn_u8 *scan,
			      hbtn_bool *pressed)
{
	if (result & ~0x3fULL)
		return -EINVAL;

	*scan = result & 0x3e;
	if (*scan != 0x34 && *scan != 0x36 && *scan != 0x38 && *scan != 0x3a)
		return -EINVAL;
	*pressed = !(result & 0x01);
	return 0;
}

#endif
