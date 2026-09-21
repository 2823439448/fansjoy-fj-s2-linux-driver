# Fansjoy FJ-S2 Linux HID Kernel Driver

为 **凡画 / Fansjoy FJ-S2** 数位板编写的 Linux HID 内核驱动。目标是在
Kubuntu / Ubuntu 上开机自动加载，让数位板插上即可使用，并保持鼠标、键盘、
触摸板等其他输入设备不受影响。

This repository provides a Linux HID kernel driver for the Fansjoy FJ-S2
graphics tablet / pen tablet with USB vendor and product IDs `2d80:3013`.
It is intended for Ubuntu and Kubuntu users who find that the stock
`hid-generic` and `usbhid` drivers detect the tablet but fail to map the pen
position, pressure, tilt, or orientation correctly on a landscape screen.

The driver fixes the Fansjoy FJ-S2 tablet coordinate mapping problem on
Ubuntu 26.04 and Kubuntu 26.04, supports automatic module loading at boot,
and does not take over the keyboard, mouse, touchpad, or other unrelated USB
HID input devices.

## 设备信息

- 品牌：Fansjoy / 凡画
- 型号：FJ-S2 / S2
- USB VID：`2d80`
- USB PID：`3013`
- USB 接口 0：数位板笔 + 标准键盘报告
- USB 接口 1：厂商自定义配置接口
- 内核识别名：`Fansjoy FJ-S2`

## 实测坐标范围

```text
X：0..16800
Y：0..10500
pressure：0..8191
tilt X：-9000..9000
tilt Y：-9000..9000
```

数位板原始坐标轴与横屏方向存在 90 度旋转关系，因此本方案由 **libinput
校准矩阵**完成方向映射：

```text
0 1 0 -1 0 1
```

内核驱动本身只负责正确解析该设备的 HID 报告并上报标准输入事件。

## 包含文件

- `fans_joy_s2.c` — HID 内核驱动源码
- `Makefile` — 编译脚本
- `install-fans-joy-s2.sh` — 一键编译、安装、开机自启脚本
- `99-fans-joy-s2-calibration.rules` — libinput 旋转校准 udev 规则
- `fans_joy_s2_calibration.md` — 设备校准记录
- `probe_tablet.py` — pyusb 原始 HID 报告采集脚本
- `analyze_tablet.py` — 原始坐标分析和校准矩阵生成脚本
- `diagnose_tablet.py` — 实测 X/Y/pressure 范围诊断脚本
- `INSTALL.md` — 详细安装说明

## 快速安装

需要 Ubuntu / Kubuntu，并已连接 FJ-S2。

### 从 GitHub 拉取到本地再安装

```bash
git clone https://github.com/2823439448/fansjoy-fj-s2-linux-driver.git
cd fansjoy-fj-s2-linux-driver
sudo ./install-fans-joy-s2.sh libinput "0 1 0 -1 0 1"
```

如果你已经有本地仓库，可以更新后再安装：

```bash
cd fansjoy-fj-s2-linux-driver
git pull
sudo ./install-fans-joy-s2.sh libinput "0 1 0 -1 0 1"
```

### 直接在源码目录安装

```bash
cd /path/to/repo
sudo ./install-fans-joy-s2.sh libinput "0 1 0 -1 0 1"
```

脚本会：

1. 安装 `build-essential` 和当前内核头文件
2. 编译 `fans_joy_s2.ko`
3. 安装到 `/lib/modules/$(uname -r)/extra/`
4. 写入开机自动加载配置 `/etc/modules-load.d/fans-joy-s2.conf`
5. 写入 libinput 校准规则 `/etc/udev/rules.d/99-fans-joy-s2-calibration.rules`
6. 立即加载模块

也可以手动编译：

```bash
make
sudo make install
sudo modprobe fans_joy_s2
```

## 为什么写这个驱动

该设备能被内核识别，但默认 `hid-generic` / `usbhid` 不能正确处理它的坐标
映射和方向。具体遇到的问题记录如下：

### 问题 1：坐标范围容易被误判

设备报告描述符中 X 逻辑最大值写的是 `16800`，但一次不完整的抓包曾把 X
最大值误判为 `4704`，导致数位板只有一半区域可用。

最终通过 `diagnose_tablet.py` 绕数位板完整移动采集，确认真实范围是：

```text
X：0..16800
Y：0..10500
```

### 问题 2：方向旋转不要硬编码进 raw_event

曾尝试在 `raw_event()` 中直接交换/翻转 X、Y，但 HID 通用层仍会按原始报告
描述符钳制坐标，导致屏幕只能覆盖一半。标准且稳定的做法是：

```text
内核驱动上报原始坐标 + libinput calibration matrix 做旋转
```

## 搜索关键词

`Fansjoy FJ-S2 Linux driver`, `凡画 S2 Linux 驱动`, `2d80:3013`,
`FJ-S2 hid driver`, `Fansjoy tablet Ubuntu`, `凡画数位板 Kubuntu`

## English search keywords and descriptions

This project is a `Fansjoy FJ-S2 Linux kernel driver`, also useful as a
`Fansjoy FJ-S2 Ubuntu driver` and `Fansjoy FJ-S2 Kubuntu driver`.

It solves the `Fansjoy FJ-S2 tablet coordinate mapping issue`, the
`Fansjoy FJ-S2 pressure not working on Linux` problem, and the
`Fansjoy FJ-S2 pen tilt orientation problem`.

The device is identified by `USB ID 2d80:3013` and is also written as
`2d80:3013 Fansjoy FJ-S2`, `FJ-S2 2d80:3013`, `Fansjoy S2 USB HID tablet`,
`Fansjoy S2 graphics tablet Linux driver`, `Fansjoy S2 drawing tablet Ubuntu`,
`Fansjoy S2 pen tablet Kubuntu`, and `Fansjoy S2 HID digitizer driver`.

This repository explains how to compile and install a custom Linux HID driver
for the Fansjoy FJ-S2 tablet, how to load it automatically at boot with
`/etc/modules-load.d/`, and how to use a libinput calibration matrix to rotate
the tablet coordinate system on Ubuntu or Kubuntu.
