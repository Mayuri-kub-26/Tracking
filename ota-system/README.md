# Level-3 OTA System - Build and Deployment Guide

## Prerequisites

- Raspberry Pi running Ubuntu Linux
- Root access
- Internet connectivity
- GitHub repository for hosting releases

## Directory Structure

```
ota-system/
├── ota-update.sh                    # Main OTA script
├── systemd/
│   ├── video-app.service           # Application service
│   ├── ota-update.service          # OTA service
│   └── ota-update.timer            # OTA timer
├── debian-packages/
│   ├── v1/
│   │   ├── DEBIAN/
│   │   │   ├── control
│   │   │   └── postinst
│   │   └── opt/app/v1/bin/
│   │       └── video_app
│   └── v2/
│       ├── DEBIAN/
│       │   ├── control
│       │   └── postinst
│       └── opt/app/v2/bin/
│           └── video_app
└── README.md                        # This file
```

## Step 1: Prepare Your Application

Replace the placeholder `video_app` scripts with your actual application:

```bash
# For v1 (normal video)
cp /path/to/your/app debian-packages/v1/opt/app/v1/bin/video_app

# For v2 (black-and-white video)
cp /path/to/your/modified/app debian-packages/v2/opt/app/v2/bin/video_app
```

Make sure both are executable:
```bash
chmod +x debian-packages/v1/opt/app/v1/bin/video_app
chmod +x debian-packages/v2/opt/app/v2/bin/video_app
```

## Step 2: Build Debian Packages

```bash
# Build v1 package
chmod +x debian-packages/v1/DEBIAN/postinst
dpkg-deb --build debian-packages/v1 video-app-v1.0.0.deb

# Build v2 package
chmod +x debian-packages/v2/DEBIAN/postinst
dpkg-deb --build debian-packages/v2 video-app-v2.0.0.deb
```

## Step 3: Upload to GitHub Releases

1. Create a new release on GitHub (e.g., v1.0.0)
2. Upload `video-app-v1.0.0.deb` as a release asset
3. Later, create v2.0.0 release with `video-app-v2.0.0.deb`

## Step 4: Configure OTA Script

Edit `ota-update.sh` and update the GitHub repository:

```bash
GITHUB_REPO="your-username/your-repo"  # Line 18
```

## Step 5: Install on Raspberry Pi

### Initial Installation (v1)

```bash
# Install the first version manually
sudo dpkg -i video-app-v1.0.0.deb

# Copy OTA script
sudo cp ota-update.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/ota-update.sh

# Install systemd units
sudo cp systemd/video-app.service /etc/systemd/system/
sudo cp systemd/ota-update.service /etc/systemd/system/
sudo cp systemd/ota-update.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the application
sudo systemctl enable video-app.service
sudo systemctl start video-app.service

# Enable and start the OTA timer
sudo systemctl enable ota-update.timer
sudo systemctl start ota-update.timer
```

### Verify Installation

```bash
# Check application status
sudo systemctl status video-app.service

# Check current version
cat /opt/app/current/VERSION
readlink /opt/app/current

# Check OTA timer
sudo systemctl status ota-update.timer
sudo systemctl list-timers ota-update.timer
```

## Step 6: Test OTA Update

### Manual OTA Test

```bash
# Trigger OTA update manually
sudo /usr/local/bin/ota-update.sh

# Watch logs
sudo journalctl -u ota-update.service -f
```

### Automatic OTA Test

1. Upload v2.0.0 to GitHub Releases
2. Wait for the timer to trigger 
3. Monitor the update:

```bash
# Watch OTA logs
tail -f /var/cache/ota/logs/ota-update.log

# Watch service status
watch -n 1 'systemctl status video-app.service'
```

## Step 7: Verify Update Success

```bash
# Check new version
cat /opt/app/current/VERSION  # Should show 2.0.0

# Check active slot
cat /opt/app/metadata/active_slot  # Should show v2

# Verify symlink
readlink /opt/app/current  # Should point to /opt/app/v2

# Check application is running
sudo systemctl status video-app.service
```

## Rollback Testing

### Simulate Failure

```bash
# Stop the service during health check to trigger rollback
sudo systemctl stop video-app.service
# Wait for health check to fail and rollback to occur
```

### Manual Rollback

```bash
# If needed, you can manually rollback
sudo ln -sfn /opt/app/v1 /opt/app/current.tmp
sudo mv -T /opt/app/current.tmp /opt/app/current
sudo systemctl restart video-app.service
```

## Monitoring and Logs

### View OTA Logs
```bash
# OTA update logs
tail -f /var/cache/ota/logs/ota-update.log

# Systemd journal
sudo journalctl -u ota-update.service -f
sudo journalctl -u video-app.service -f
```

### Check Update Status
```bash
# Current state
cat /opt/app/metadata/update_state

# Active slot
cat /opt/app/metadata/active_slot

# Last known good version
cat /opt/app/metadata/last_known_good
```

## Troubleshooting

### OTA Update Not Running

```bash
# Check timer status
sudo systemctl status ota-update.timer

# Check if timer is enabled
sudo systemctl is-enabled ota-update.timer

# Manually trigger
sudo systemctl start ota-update.service
```

### Application Not Starting

```bash
# Check service logs
sudo journalctl -u video-app.service -n 50

# Check if symlink is correct
ls -la /opt/app/current

# Verify permissions
ls -la /opt/app/current/bin/video_app
```

### Update Stuck

```bash
# Check current state
cat /opt/app/metadata/update_state

# If stuck, reset state
echo "IDLE" | sudo tee /opt/app/metadata/update_state

# Retry update
sudo /usr/local/bin/ota-update.sh
```

## Customization

### Change Update Frequency

Edit `/etc/systemd/system/ota-update.timer`:

```ini
# Check every 30 minutes instead of 1 hour
OnUnitActiveSec=30min
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ota-update.timer
```

### Add Custom Health Checks

Edit `/usr/local/bin/ota-update.sh` in the `health_check()` function:

```bash
# Add application-specific checks
if ! curl -f http://localhost:8080/health &> /dev/null; then
    log_error "Application health endpoint failed"
    return 1
fi
```

## Production Considerations

1. **Disk Space**: Ensure sufficient space for two complete installations
2. **Network**: Consider bandwidth for downloading packages
3. **GitHub API Limits**: Use authentication token for higher rate limits
4. **Backup**: Keep backups of working configurations
5. **Testing**: Always test updates in a staging environment first
6. **Monitoring**: Set up alerts for failed updates
7. **Rollback Window**: Adjust health check duration based on your application

## Security Notes

- The OTA script runs as root - ensure it's properly secured
- Verify package signatures in production (add GPG verification)
- Use HTTPS for all downloads
- Consider implementing checksum verification
- Restrict access to `/opt/app` and `/var/cache/ota`
