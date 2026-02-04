# Raspberry Pi 5 Setup Guide - Complete Step-by-Step

Complete guide to deploy the drone tracking system on Raspberry Pi 5 with Hailo-8L AI HAT and SIYI gimbal camera.

---

## 📦 What You Need

### Hardware
- ✅ **Raspberry Pi 5** (4GB or 8GB RAM)
- ✅ **Hailo-8L AI HAT** (AI accelerator)
- ✅ **SIYI ZT30 or A8 Mini Gimbal Camera**
- ✅ **MicroSD Card** (32GB+ recommended, Class 10)
- ✅ **USB-C Power Supply** (5V/5A, 27W official Pi 5 adapter)
- ✅ **Ethernet Cable** or WiFi connection
- ✅ **UART Cable** (for gimbal connection - usually comes with SIYI)
- ✅ **Monitor + HDMI Cable** (for initial setup)
- ✅ **USB Keyboard + Mouse** (for initial setup)

### Optional
- 🔌 **Cooling Fan/Heatsink** (recommended for continuous operation)
- 🔌 **Case** (with Hailo HAT compatibility)
- 🔌 **Power Bank** (for field testing)

---

## 🔌 Hardware Connections

### Step 1: Physical Assembly

#### 1.1 Install Hailo-8L HAT on Raspberry Pi

```
1. Power OFF Raspberry Pi (if already running)
2. Align Hailo-8L HAT with GPIO pins (40-pin header)
3. Gently press down until fully seated
4. Secure with standoffs/screws if provided
```

**Visual:**
```
     ┌─────────────────┐
     │   Hailo-8L HAT  │  ← AI Accelerator
     │    (Top)        │
     └────────┬────────┘
              │ GPIO Pins (40-pin)
     ┌────────▼────────┐
     │ Raspberry Pi 5  │
     │                 │
     └─────────────────┘
```

#### 1.2 Connect SIYI Gimbal to Raspberry Pi (UART)

**GPIO Pin Connections:**

```
SIYI Gimbal Cable          Raspberry Pi 5 GPIO
──────────────────         ───────────────────
TX (Yellow/White)    ───>  GPIO 15 (Pin 10) - RXD
RX (Green/Blue)      <───  GPIO 14 (Pin 8)  - TXD  
GND (Black)          ───>  GND (Pin 6 or 14)
VCC (Red)            ───>  DO NOT CONNECT (gimbal has own power)
```

**Pin Layout Reference:**
```
Raspberry Pi 5 GPIO Header (Top View)
┌─────────────────────────────────┐
│ 3V3  [1] [2]  5V                │
│ GPIO2[3] [4]  5V                │
│ GPIO3[5] [6]  GND  ← Connect GND│
│ GPIO4[7] [8]  GPIO14 ← TX (TXD) │
│ GND  [9] [10] GPIO15 ← RX (RXD) │
│ ...                             │
└─────────────────────────────────┘
```

**Important Notes:**
- ⚠️ **DO NOT** connect gimbal VCC to Pi - gimbal uses its own battery/power
- ⚠️ Double-check TX/RX crossover (Pi TX → Gimbal RX, Pi RX → Gimbal TX)
- ⚠️ Ensure common ground connection

#### 1.3 Power Connections

```
1. Connect USB-C power supply to Raspberry Pi 5
2. Power gimbal separately (battery or 12V adapter)
3. DO NOT power on yet
```

#### 1.4 Network Connection

**Option A: Ethernet (Recommended for setup)**
```
Raspberry Pi [Ethernet Port] ──Cable──> Router/Switch
```

**Option B: WiFi**
- Will configure during OS setup

#### 1.5 Display Connection (Initial Setup Only)

```
Raspberry Pi [Micro HDMI Port 0] ──Cable──> Monitor
```

---

## 💿 Software Installation

### Step 2: Install Raspberry Pi OS

#### 2.1 Prepare SD Card (On Your Windows PC)

1. **Download Raspberry Pi Imager:**
   - Visit: https://www.raspberrypi.com/software/
   - Download and install for Windows

2. **Flash OS to SD Card:**
   ```
   1. Insert SD card into Windows PC
   2. Open Raspberry Pi Imager
   3. Choose Device: Raspberry Pi 5
   4. Choose OS: Raspberry Pi OS (64-bit) - Full version recommended
   5. Choose Storage: Your SD card
   6. Click "Next"
   ```

3. **Configure OS Settings (IMPORTANT):**
   ```
   Click "Edit Settings" when prompted:
   
   GENERAL Tab:
   ✓ Set hostname: raspberrypi (or your choice)
   ✓ Set username: pi
   ✓ Set password: [your secure password]
   ✓ Configure WiFi (if not using Ethernet):
       SSID: [your WiFi name]
       Password: [your WiFi password]
       Country: IN (India)
   ✓ Set locale:
       Timezone: Asia/Kolkata
       Keyboard: us
   
   SERVICES Tab:
   ✓ Enable SSH (Use password authentication)
   ```

4. **Write to SD Card:**
   ```
   Click "Yes" to apply settings
   Click "Yes" to erase SD card
   Wait for write and verify to complete
   ```

5. **Insert SD Card into Raspberry Pi**

#### 2.2 First Boot

1. **Power on Raspberry Pi:**
   - Connect all cables (HDMI, keyboard, mouse, ethernet, power)
   - Plug in USB-C power
   - Wait for boot (1-2 minutes)

2. **Initial Setup Wizard:**
   - Follow on-screen prompts if any
   - Skip if you configured everything in Imager

3. **Find IP Address:**
   ```bash
   hostname -I
   ```
   Example output: `192.168.1.100`
   
   **Write this down! You'll need it to connect from Windows.**

---

### Step 3: Connect via SSH (From Your Windows PC)

Now you can disconnect monitor/keyboard and work remotely!

#### 3.1 SSH from Windows

**Option A: PowerShell (Built-in)**
```powershell
ssh pi@192.168.1.100
# Enter password when prompted
```

**Option B: PuTTY**
1. Download PuTTY: https://www.putty.org/
2. Host: `192.168.1.100`
3. Port: `22`
4. Click "Open"
5. Login as: `pi`
6. Password: [your password]

#### 3.2 Update System

```bash
# Update package lists
sudo apt update

# Upgrade all packages (this may take 10-15 minutes)
sudo apt upgrade -y

# Reboot
sudo reboot
```

Wait 1 minute, then reconnect via SSH.

---

### Step 4: Install Hailo Software

#### 4.1 Install Hailo TAPPAS

```bash
# Add Hailo repository
wget -qO - https://hailo.ai/hailo-apt-repo/hailo.gpg.key | sudo apt-key add -
echo "deb https://hailo.ai/hailo-apt-repo stable main" | sudo tee /etc/apt/sources.list.d/hailo.list

# Update and install
sudo apt update
sudo apt install -y hailo-all

# Verify installation
hailortcli fw-control identify
```

**Expected output:**
```
Identifying board
Control Protocol Version: 2
Firmware Version: 4.17.0
Board Name: Hailo-8L
Device Architecture: HAILO8L
```

#### 4.2 Install Python Hailo Libraries

```bash
# Install Hailo Python package
pip3 install hailort

# Verify
python3 -c "import hailo_platform; print('Hailo OK')"
```

---

### Step 5: Install Project Dependencies

#### 5.1 Install System Packages

```bash
# Install OpenCV dependencies
sudo apt install -y python3-opencv
sudo apt install -y libopencv-dev

# Install other dependencies
sudo apt install -y python3-pip python3-yaml python3-numpy
sudo apt install -y git curl

# Install GStreamer (for video streaming)
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

#### 5.2 Install Python Packages

```bash
# Install pip packages
pip3 install --upgrade pip
pip3 install opencv-python opencv-contrib-python
pip3 install numpy pyyaml
pip3 install fastapi uvicorn
pip3 install pyserial  # For SIYI gimbal communication
```

---

### Step 6: Clone and Setup Project

#### 6.1 Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone the project
git clone https://github.com/Flying-Wedge-Defence-AI/Tracker.git
cd Tracker

# Check contents
ls -la
```

#### 6.2 Download Model Files

```bash
# Create models directory if not exists
mkdir -p models

# Download YOLOv10 model (example - adjust URL as needed)
cd models
# You'll need to get the actual .hef model file
# Either download from Hailo Model Zoo or use your custom model
# Example:
# wget https://hailo-model-zoo.s3.amazonaws.com/ModelZoo/Compiled/v2.11.0/hailo8l/yolov10s.hef

cd ..
```

---

### Step 7: Configure UART for Gimbal

#### 7.1 Enable UART

```bash
# Edit config file
sudo nano /boot/firmware/config.txt
```

**Add these lines at the end:**
```ini
# Enable UART for SIYI Gimbal
enable_uart=1
dtoverlay=uart0
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

#### 7.2 Disable Serial Console

```bash
# Disable serial console
sudo raspi-config
```

Navigate:
```
3 Interface Options
  → I6 Serial Port
    → "Would you like a login shell accessible over serial?" → No
    → "Would you like the serial port hardware to be enabled?" → Yes
  → Finish
  → Reboot? → Yes
```

#### 7.3 Verify UART

After reboot, check:
```bash
ls -l /dev/serial*
```

Expected output:
```
/dev/serial0 -> ttyAMA0
```

---

### Step 8: Configure the Tracker

#### 8.1 Edit Configuration

```bash
cd ~/Tracker
nano src/config.yaml
```

**Example configuration:**
```yaml
detection:
  model_path: "models/yolov10s.hef"
  target_classes: ["person", "car", "truck"]
  confidence_threshold: 0.5

hardware:
  camera:
    type: "siyi"  # or "picam" for Raspberry Pi Camera
    device: "/dev/video0"
  
  gimbal:
    enabled: true
    port: "/dev/serial0"
    baudrate: 115200
    model: "ZT30"  # or "A8mini"

stream:
  type: "web"  # "web" for MJPEG or "rtsp" for MediaMTX
  web_port: 8000
  rtsp_url: "rtsp://127.0.0.1:8554/video1"

pid:
  kp: 0.5
  ki: 0.01
  kd: 0.1
```

**Save:** `Ctrl+X`, `Y`, `Enter`

---

### Step 9: Test the System

#### 9.1 Test Gimbal Connection

```bash
cd ~/Tracker

# Test gimbal communication
python3 -c "
import serial
ser = serial.Serial('/dev/serial0', 115200, timeout=1)
print('Serial port opened:', ser.name)
ser.close()
print('Test passed!')
"
```

#### 9.2 Test Camera

```bash
# Test camera capture
python3 -c "
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    print(f'Camera OK: {frame.shape}')
else:
    print('Camera FAILED')
cap.release()
"
```

#### 9.3 Test Hailo Detection

```bash
# Run Hailo test
python3 -c "
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams
print('Hailo import successful!')
"
```

---

### Step 10: Run the Tracker

#### 10.1 Debug Mode (With Display)

If you have monitor connected:

```bash
cd ~/Tracker
python3 src/main.py --mode debug
```

**Controls:**
- `s`: Stop and select manual ROI
- `c` or Right Click: Cancel tracking
- `q`: Quit
- Left Click: Track detected object

#### 10.2 Production Mode (Headless)

For deployment without monitor:

```bash
cd ~/Tracker
python3 src/main.py --mode production
```

**Access from Windows PC:**
- Video Stream: `http://192.168.1.100:8000/video1`
- API Docs: `http://192.168.1.100:8000/docs`

---

### Step 11: Setup as System Service (Auto-start)

#### 11.1 Create Service File

```bash
sudo nano /etc/systemd/system/tracker.service
```

**Paste this content:**
```ini
[Unit]
Description=Video Tracking Application
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Tracker
ExecStart=/usr/bin/python3 /home/pi/Tracker/src/main.py --mode production
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Save:** `Ctrl+X`, `Y`, `Enter`

#### 11.2 Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable tracker.service

# Start service now
sudo systemctl start tracker.service

# Check status
sudo systemctl status tracker.service
```

#### 11.3 View Logs

```bash
# View live logs
sudo journalctl -u tracker.service -f

# View last 50 lines
sudo journalctl -u tracker.service -n 50
```

---

## 🔍 Verification Checklist

After setup, verify everything works:

### Hardware Checks
- [ ] Hailo HAT detected: `hailortcli fw-control identify`
- [ ] UART available: `ls -l /dev/serial0`
- [ ] Camera working: `vcgencmd get_camera` or test with OpenCV
- [ ] Gimbal responding: Check serial communication

### Software Checks
- [ ] Python packages installed: `pip3 list | grep opencv`
- [ ] Hailo library: `python3 -c "import hailo_platform"`
- [ ] Project files present: `ls ~/Tracker`
- [ ] Config file valid: `cat ~/Tracker/src/config.yaml`

### Network Checks
- [ ] Pi has IP address: `hostname -I`
- [ ] Can ping from Windows: `ping 192.168.1.100`
- [ ] Web stream accessible: Open browser to `http://192.168.1.100:8000/video1`
- [ ] API accessible: `http://192.168.1.100:8000/docs`

### Service Checks
- [ ] Service running: `sudo systemctl status tracker.service`
- [ ] No errors in logs: `sudo journalctl -u tracker.service -n 20`
- [ ] Auto-starts on reboot: `sudo reboot` then check status

---

## 🛠️ Troubleshooting

### Issue: Hailo Not Detected

```bash
# Check if HAT is seated properly
lsusb | grep Hailo

# Reinstall drivers
sudo apt install --reinstall hailo-all

# Check kernel messages
dmesg | grep -i hailo
```

### Issue: UART Not Working

```bash
# Check UART config
cat /boot/firmware/config.txt | grep uart

# Check permissions
sudo usermod -a -G dialout pi
# Logout and login again

# Test with minicom
sudo apt install minicom
sudo minicom -D /dev/serial0 -b 115200
```

### Issue: Camera Not Found

```bash
# List video devices
ls -l /dev/video*

# Check camera detection
v4l2-ctl --list-devices

# For Pi Camera
vcgencmd get_camera
```

### Issue: Cannot Access Web Stream

```bash
# Check if service is running
sudo systemctl status tracker.service

# Check firewall
sudo ufw status
sudo ufw allow 8000

# Check if port is listening
sudo netstat -tulpn | grep 8000
```

### Issue: Gimbal Not Responding

```bash
# Check serial connection
sudo minicom -D /dev/serial0 -b 115200

# Check wiring (TX/RX might be swapped)
# Try swapping GPIO 14 and GPIO 15

# Check gimbal power
# Ensure gimbal is powered separately
```

---

## 📊 Performance Optimization

### CPU Governor (Max Performance)

```bash
# Set CPU to performance mode
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Increase GPU Memory

```bash
sudo nano /boot/firmware/config.txt
```

Add:
```ini
gpu_mem=256
```

### Disable Unnecessary Services

```bash
# Disable Bluetooth if not needed
sudo systemctl disable bluetooth

# Disable WiFi if using Ethernet
sudo rfkill block wifi
```

---

## 🚀 Quick Reference Commands

```bash
# Start tracker manually
cd ~/Tracker && python3 src/main.py --mode production

# Check service status
sudo systemctl status tracker.service

# Restart service
sudo systemctl restart tracker.service

# View logs
sudo journalctl -u tracker.service -f

# Check IP address
hostname -I

# Test camera
raspistill -o test.jpg  # For Pi Camera
# OR
fswebcam test.jpg  # For USB camera

# Check Hailo
hailortcli fw-control identify

# Reboot
sudo reboot

# Shutdown
sudo shutdown -h now
```

---

## 📞 Next Steps

1. ✅ **Complete hardware setup** - Connect all cables
2. ✅ **Install OS and software** - Follow steps 1-6
3. ✅ **Configure UART and camera** - Steps 7-8
4. ✅ **Test components** - Step 9
5. ✅ **Run tracker** - Step 10
6. ✅ **Setup auto-start** - Step 11
7. ✅ **Access from Windows** - Open browser to Pi's IP

---

## 🎯 Accessing from Your Windows PC

Once everything is running:

1. **Find Pi IP:** `192.168.1.100` (example)

2. **View Video Stream:**
   - Browser: `http://192.168.1.100:8000/video1`
   - VLC: `rtsp://192.168.1.100:8554/video1`

3. **Control via API:**
   - API Docs: `http://192.168.1.100:8000/docs`
   - Track point: POST to `/track_point`
   - Status: GET `/status`

4. **SSH Access:**
   ```powershell
   ssh pi@192.168.1.100
   ```

5. **Display on MSI Monitor:**
   - Open browser in fullscreen (F11)
   - Or use VLC in fullscreen mode

---

## 📝 Support

If you encounter issues:
1. Check hardware connections are secure
2. Verify all services are running
3. Check logs: `sudo journalctl -u tracker.service -n 50`
4. Test components individually (camera, gimbal, Hailo)
5. Ensure network connectivity between Pi and Windows PC
