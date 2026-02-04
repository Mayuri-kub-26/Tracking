#!/bin/bash
################################################################################
# Raspberry Pi 5 - Tracker Quick Setup Script
# This script automates the installation and configuration process
################################################################################

set -e  # Exit on error

echo "=========================================="
echo "Tracker Quick Setup for Raspberry Pi 5"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}ERROR: Do not run this script as root (without sudo)${NC}"
   echo "Run as: ./setup_pi.sh"
   exit 1
fi

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
sudo apt update
sudo apt upgrade -y

echo ""
echo -e "${GREEN}Step 2: Installing system dependencies...${NC}"
sudo apt install -y \
    python3-pip \
    python3-opencv \
    python3-yaml \
    python3-numpy \
    git \
    curl \
    libopencv-dev \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

echo ""
echo -e "${GREEN}Step 3: Installing Python packages...${NC}"
pip3 install --upgrade pip
pip3 install opencv-python opencv-contrib-python
pip3 install numpy pyyaml
pip3 install fastapi uvicorn
pip3 install pyserial

echo ""
echo -e "${GREEN}Step 4: Installing Hailo software...${NC}"
# Check if Hailo is already installed
if command -v hailortcli &> /dev/null; then
    echo -e "${YELLOW}Hailo already installed, skipping...${NC}"
else
    echo "Adding Hailo repository..."
    wget -qO - https://hailo.ai/hailo-apt-repo/hailo.gpg.key | sudo apt-key add -
    echo "deb https://hailo.ai/hailo-apt-repo stable main" | sudo tee /etc/apt/sources.list.d/hailo.list
    sudo apt update
    sudo apt install -y hailo-all
    
    echo "Installing Hailo Python package..."
    pip3 install hailort
fi

echo ""
echo -e "${GREEN}Step 5: Configuring UART for gimbal...${NC}"
# Enable UART in config.txt
if ! grep -q "enable_uart=1" /boot/firmware/config.txt; then
    echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt
    echo "dtoverlay=uart0" | sudo tee -a /boot/firmware/config.txt
    echo -e "${YELLOW}UART configuration added${NC}"
else
    echo -e "${YELLOW}UART already configured${NC}"
fi

# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER

echo ""
echo -e "${GREEN}Step 6: Setting up project directory...${NC}"
cd ~
if [ -d "Tracker" ]; then
    echo -e "${YELLOW}Tracker directory already exists${NC}"
    cd Tracker
    echo "Pulling latest changes..."
    git pull
else
    echo "Cloning Tracker repository..."
    git clone https://github.com/Flying-Wedge-Defence-AI/Tracker.git
    cd Tracker
fi

# Create models directory
mkdir -p models

echo ""
echo -e "${GREEN}Step 7: Creating systemd service...${NC}"
sudo tee /etc/systemd/system/tracker.service > /dev/null <<EOF
[Unit]
Description=Video Tracking Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/Tracker
ExecStart=/usr/bin/python3 /home/$USER/Tracker/src/main.py --mode production
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next Steps:"
echo ""
echo "1. Place your Hailo model (.hef) in ~/Tracker/models/"
echo "   Example: ~/Tracker/models/yolov10s.hef"
echo ""
echo "2. Edit configuration:"
echo "   nano ~/Tracker/src/config.yaml"
echo ""
echo "3. Test the tracker:"
echo "   cd ~/Tracker"
echo "   python3 src/main.py --mode debug"
echo ""
echo "4. Enable auto-start service:"
echo "   sudo systemctl enable tracker.service"
echo "   sudo systemctl start tracker.service"
echo ""
echo "5. Check service status:"
echo "   sudo systemctl status tracker.service"
echo ""
echo "6. View logs:"
echo "   sudo journalctl -u tracker.service -f"
echo ""
echo -e "${YELLOW}IMPORTANT: Reboot required for UART changes to take effect${NC}"
echo "   sudo reboot"
echo ""
echo "Your Raspberry Pi IP address:"
hostname -I
echo ""
echo "Access from Windows PC:"
echo "  Video: http://$(hostname -I | awk '{print $1}'):8000/video1"
echo "  API:   http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
