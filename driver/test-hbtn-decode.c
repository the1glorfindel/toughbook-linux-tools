// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include "hbtn-decode.h"

int main(void)
{
	static const unsigned long long scans[] = { 0x34, 0x36, 0x38, 0x3a };
	unsigned int i;
	hbtn_u8 scan;
	hbtn_bool pressed;

	for (i = 0; i < sizeof(scans) / sizeof(scans[0]); i++) {
		assert(hbtn_decode(scans[i], &scan, &pressed) == 0);
		assert(scan == scans[i] && pressed);
		assert(hbtn_decode(scans[i] | 1, &scan, &pressed) == 0);
		assert(scan == scans[i] && !pressed);
	}
	assert(hbtn_decode(0x02, &scan, &pressed) == -EINVAL);
	assert(hbtn_decode(0x0f, &scan, &pressed) == -EINVAL);
	assert(hbtn_decode(0x14, &scan, &pressed) == -EINVAL);
	assert(hbtn_decode(0x74, &scan, &pressed) == -EINVAL);
	assert(hbtn_decode(0x04, &scan, &pressed) == -EINVAL);
	assert(hbtn_decode(0x80, &scan, &pressed) == -EINVAL);
	return 0;
}
