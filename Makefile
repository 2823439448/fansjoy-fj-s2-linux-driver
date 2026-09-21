obj-m += fans_joy_s2.o

KDIR := /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

install:
	sudo mkdir -p /lib/modules/$(shell uname -r)/extra
	sudo cp fans_joy_s2.ko /lib/modules/$(shell uname -r)/extra/
	sudo depmod -a

load:
	sudo modprobe fans_joy_s2

unload:
	sudo rmmod fans_joy_s2

.PHONY: all clean install load unload
