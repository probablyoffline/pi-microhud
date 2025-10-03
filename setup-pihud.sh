#!/bin/bash
set -euo pipefail

PI_USER="$(whoami)"
INSTALL_DIR="/opt/pihud"

echo "Using PI_USER=${PI_USER}"

# copy files into /opt (needs sudo)
sudo rm -rf "${INSTALL_DIR}"
sudo cp -r pihud "${INSTALL_DIR}"
sudo chown -R "${PI_USER}:${PI_USER}" "${INSTALL_DIR}"

# install system packages (needs sudo)
sudo apt update -y
sudo apt install -y python3-pip python3-venv git i2c-tools python3-smbus python-dotenv

# enable i2c (needs sudo)
sudo bash -lc '
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_i2c 0
else
  sed -i -E "/^dtparam=i2c_arm=/d" /boot/config.txt
  echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi
modprobe i2c-dev || true
'

# create venv as the normal user
python3 -m venv "${INSTALL_DIR}/env"

# upgrade pip/setuptools/wheel inside venv
"${INSTALL_DIR}/env/bin/python" -m pip install --upgrade pip setuptools wheel

# install required Python packages into venv
"${INSTALL_DIR}/env/bin/python" -m pip install adafruit-circuitpython-ssd1306 smbus2

# create service manually
#bash create-pihudservice.sh
