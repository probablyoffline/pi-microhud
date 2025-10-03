#!/bin/bash
# Script to create and enable Pi HUD Kismet systemd service

SERVICE_NAME="pihud-kismet.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "Creating $SERVICE_NAME..."

sudo bash -c "cat > $SERVICE_PATH" <<'EOF'
[Unit]
Description=PiHUD Kismet Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/pihud
ExecStartPre=/bin/sleep 10
ExecStart=/bin/bash -c "source /opt/pihud/env/bin/activate && exec python3 /opt/pihud/pihud-kismet.py"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target

EOF

echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Enabling $SERVICE_NAME to start on boot..."
sudo systemctl enable "$SERVICE_NAME"

echo "Starting $SERVICE_NAME..."
sudo systemctl start "$SERVICE_NAME"

echo "Checking status..."
sudo systemctl status "$SERVICE_NAME" --no-pager
