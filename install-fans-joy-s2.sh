#!/usr/bin/env bash
#
# Fansjoy FJ-S2 driver installer.
#
# Usage:
#   sudo ./install-fans-joy-s2.sh                    # interactive choice
#   sudo ./install-fans-joy-s2.sh direct             # recommended: raw driver + verified full mapping
#   sudo ./install-fans-joy-s2.sh libinput [matrix]  # driver + optional custom libinput rotation
#   sudo ./install-fans-joy-s2.sh uninstall          # unload and remove files
#
# The script uses the directory containing this script as its source
# directory, so you can copy these files to another machine:
#   fans_joy_s2.c
#   Makefile
#   99-fans-joy-s2-calibration.rules
#   install-fans-joy-s2.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_NAME="fans_joy_s2"
MODULE_FILE="${SCRIPT_DIR}/${MODULE_NAME}.ko"
KVER="$(uname -r)"
MODULE_DEST="/lib/modules/${KVER}/extra/${MODULE_NAME}.ko"
MODULES_LOAD_CONF="/etc/modules-load.d/fans-joy-s2.conf"
UDEV_RULES_DEST="/etc/udev/rules.d/99-fans-joy-s2-calibration.rules"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi

print_usage() {
    cat >&2 <<EOF
Usage:
  sudo $0 direct             # recommended: raw driver + full-area identity mapping
  sudo $0 libinput [matrix]  # driver + optional custom libinput calibration matrix
  sudo $0 uninstall          # unload and remove installed files

Libinput matrix examples:
  identity:     1 0 0 0 1 0
  90 deg CCW:   0 1 0 -1 0 1
  90 deg CW:    0 -1 1 1 0 0
  180 deg:      -1 0 1 0 -1 1
EOF
}

choose_mode() {
    local answer
    if [[ ! -t 0 ]]; then
        echo "direct"
        return
    fi

    echo "Choose install mode:"
    echo "  1) Direct install driver with verified full mapping (recommended)"
    echo "  2) Install driver + custom libinput calibration"
    read -rp "Choice [1]: " answer || true
    case "${answer:-1}" in
        2) echo "libinput" ;;
        *) echo "direct" ;;
    esac
}

matrix_to_kwin() {
    local -a v=(${1:-1 0 0 0 1 0})
    printf '%s,%s,%s,0,%s,%s,%s,0,0,0,1,0,0,0,0,1' \
        "${v[0]}" "${v[1]}" "${v[2]}" "${v[3]}" "${v[4]}" "${v[5]}"
}

install_libinput_rule() {
    local matrix="${1:-1 0 0 0 1 0}"

    echo "==> Installing libinput calibration rule: ${matrix}"
    mkdir -p "$(dirname "${UDEV_RULES_DEST}")"
    cat > "${UDEV_RULES_DEST}" <<EOF
# Fansjoy FJ-S2 libinput calibration matrix.
ACTION=="add|change", SUBSYSTEM=="input", ATTRS{idVendor}=="2d80", ATTRS{idProduct}=="3013", ENV{ID_INPUT_TABLET}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="${matrix}"
EOF
    udevadm control --reload-rules
    udevadm trigger
}

configure_kde_tablet_defaults() {
    local matrix="${1:-1 0 0 0 1 0}"
    local kwin_matrix
    local config_user="${SUDO_USER:-}"

    if [[ -z "${config_user}" ]]; then
        echo "Warning: cannot determine desktop user; skipping KDE orientation default." >&2
        return
    fi

    kwin_matrix="$(matrix_to_kwin "${matrix}")"

    echo "==> Setting KDE tablet defaults (orientation=0, full area, matrix=${matrix})"
    sudo -H -u "${config_user}" -- kwriteconfig6 \
        --file kcminputrc \
        --group Libinput \
        --group 11648 \
        --group 12307 \
        --group 'Fansjoy FJ-S2' \
        --key Orientation \
        0

    sudo -H -u "${config_user}" -- kwriteconfig6 \
        --file kcminputrc \
        --group Libinput \
        --group 11648 \
        --group 12307 \
        --group 'Fansjoy FJ-S2' \
        --key OutputArea \
        '0,0,1,1'

    sudo -H -u "${config_user}" -- kwriteconfig6 \
        --file kcminputrc \
        --group Libinput \
        --group 11648 \
        --group 12307 \
        --group 'Fansjoy FJ-S2' \
        --key MapToWorkspace \
        --type bool \
        false

    sudo -H -u "${config_user}" -- kwriteconfig6 \
        --file kcminputrc \
        --group Libinput \
        --group 11648 \
        --group 12307 \
        --group 'Fansjoy FJ-S2' \
        --key CalibrationMatrix \
        "${kwin_matrix}"
}

do_install() {
    local mode="${1:-direct}"
    local matrix="${2:-}"

    if [[ -z "${matrix}" ]]; then
        matrix="1 0 0 0 1 0"
    fi

    echo "==> Unloading any previously loaded ${MODULE_NAME}"
    rmmod "${MODULE_NAME}" 2>/dev/null || true

    echo "==> Installing build dependencies and kernel headers for ${KVER}"
    apt-get update
    apt-get install -y build-essential python3-usb
    if ! apt-get install -y "linux-headers-${KVER}"; then
        echo "Warning: exact linux-headers-${KVER} package was not found." >&2
        echo "Trying linux-headers-generic as a fallback." >&2
        apt-get install -y linux-headers-generic
    fi

    if [[ ! -f "${SCRIPT_DIR}/fans_joy_s2.c" || ! -f "${SCRIPT_DIR}/Makefile" ]]; then
        echo "Missing fans_joy_s2.c or Makefile in ${SCRIPT_DIR}" >&2
        exit 1
    fi

    echo "==> Building ${MODULE_NAME}.ko"
    cd "${SCRIPT_DIR}"
    make clean || true
    make

    echo "==> Installing module to ${MODULE_DEST}"
    install -D -m 0644 "${MODULE_FILE}" "${MODULE_DEST}"
    depmod -a

    install_libinput_rule "${matrix}"
    configure_kde_tablet_defaults "${matrix}"

    echo "==> Enabling automatic load at boot"
    printf '%s\n' "${MODULE_NAME}" > "${MODULES_LOAD_CONF}"

    echo "==> Loading module now"
    modprobe "${MODULE_NAME}"

    echo
    echo "Installation complete."
    echo "Boot loader config: ${MODULES_LOAD_CONF}"
    echo "Module file:        ${MODULE_DEST}"
    echo "Libinput rule:      ${UDEV_RULES_DEST}"
    echo "Calibration matrix: ${matrix}"
    echo
    echo "Verify with:"
    echo "  lsmod | grep ${MODULE_NAME}"
    echo "  modinfo ${MODULE_NAME}"
    echo "  dmesg | grep fans-joy"
}

do_uninstall() {
    echo "==> Unloading module"
    rmmod "${MODULE_NAME}" 2>/dev/null || true

    echo "==> Removing installed files"
    rm -f "${MODULES_LOAD_CONF}"
    rm -f "${UDEV_RULES_DEST}"
    rm -f "${MODULE_DEST}"
    depmod -a

    echo "==> Reloading udev rules"
    udevadm control --reload-rules
    udevadm trigger

    echo "Uninstall complete. Replug the tablet or reboot to restore hid-generic."
}

mode="${1:-}"
if [[ -z "${mode}" ]]; then
    mode="$(choose_mode)"
fi

case "${mode}" in
    direct|install)
        do_install direct
        ;;
    libinput|calibration)
        matrix="${2:-}"
        if [[ -z "${matrix}" && -t 0 ]]; then
            read -rp "Libinput matrix [1 0 0 0 1 0]: " matrix || true
        fi
        matrix="${matrix:-1 0 0 0 1 0}"
        do_install libinput "${matrix}"
        ;;
    uninstall)
        do_uninstall
        ;;
    *)
        print_usage
        exit 2
        ;;
esac
