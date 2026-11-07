obj-m += panasonic-hbtn.o

KVER ?= $(shell uname -r)
KDIR ?= /usr/src/kernels/$(KVER)

.PHONY: all clean
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
