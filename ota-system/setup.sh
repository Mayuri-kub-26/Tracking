#!/bin/bash
# Quick setup script for OTA system on Raspberry Pi

set -e

echo "========================================="
echo "OTA System Setup Script"
echo "========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Install v1 package
echo "Installing video-app v1.0.0..."
if [[ -f "video-app-v1.0.0.deb" ]]; then
    dpkg -i video-app-v1.0.0.deb
else
    echo "ERROR: video-app-v1.0.0.deb not found!"
    exit 1
fi

# Install OTA script
echo "Installing OTA update script..."
cp ota-update.sh /usr/local/bin/
chmod +x /usr/local/bin/ota-update.sh

# Install systemd units
echo "Installing systemd units..."
cp systemd/video-app.service /etc/systemd/system/
cp systemd/ota-update.service /etc/systemd/system/
cp systemd/ota-update.timer /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start services
echo "Enabling and starting services..."
systemctl enable video-app.service
systemctl start video-app.service

systemctl enable ota-update.timer
systemctl start ota-update.timer

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Status:"
systemctl status video-app.service --no-pager
echo ""
echo "Current version:"
cat /opt/app/current/VERSION
echo ""
echo "Active slot:"
readlink /opt/app/current
echo ""
echo "OTA timer status:"
systemctl list-timers ota-update.timer --no-pager
echo ""
echo "To manually trigger OTA update:"
echo "  sudo /usr/local/bin/ota-update.sh"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u video-app.service -f"
echo "  sudo tail -f /var/cache/ota/logs/ota-update.log"
