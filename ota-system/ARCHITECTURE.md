# Level-3 OTA A/B Deployment - Architecture Deep Dive

## Executive Summary

This document provides a comprehensive architectural explanation of the production-grade Level-3 OTA (Over-The-Air) update system using A/B (Blue-Green) deployment strategy for Raspberry Pi running Ubuntu Linux.

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Raspberry Pi System                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Application Layer                          │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────┐             │    │
│  │  │   video-app.service                  │             │    │
│  │  │   (systemd managed)                  │             │    │
│  │  │                                       │             │    │
│  │  │   ExecStart=/opt/app/current/bin/... │             │    │
│  │  └──────────────┬───────────────────────┘             │    │
│  │                 │                                       │    │
│  │                 ▼                                       │    │
│  │  ┌──────────────────────────────────────┐             │    │
│  │  │   /opt/app/current (symlink)         │             │    │
│  │  └──────────────┬───────────────────────┘             │    │
│  │                 │                                       │    │
│  │         ┌───────┴────────┐                            │    │
│  │         ▼                ▼                            │    │
│  │  ┌────────────┐   ┌────────────┐                     │    │
│  │  │ /opt/app/v1│   │ /opt/app/v2│                     │    │
│  │  │  (Slot A)  │   │  (Slot B)  │                     │    │
│  │  │            │   │            │                     │    │
│  │  │ Version 1  │   │ Version 2  │                     │    │
│  │  │ Normal     │   │ B&W Video  │                     │    │
│  │  └────────────┘   └────────────┘                     │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              OTA Update Layer                           │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────┐             │    │
│  │  │   ota-update.timer                   │             │    │
│  │  │   (triggers every 1 hour)            │             │    │
│  │  └──────────────┬───────────────────────┘             │    │
│  │                 │                                       │    │
│  │                 ▼                                       │    │
│  │  ┌──────────────────────────────────────┐             │    │
│  │  │   ota-update.service                 │             │    │
│  │  │   (one-shot execution)               │             │    │
│  │  └──────────────┬───────────────────────┘             │    │
│  │                 │                                       │    │
│  │                 ▼                                       │    │
│  │  ┌──────────────────────────────────────┐             │    │
│  │  │   /usr/local/bin/ota-update.sh       │             │    │
│  │  │   (main OTA logic)                   │             │    │
│  │  └──────────────────────────────────────┘             │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│                         ▲                                        │
│                         │                                        │
│                         │ HTTPS                                 │
│                         │                                        │
└─────────────────────────┼────────────────────────────────────────┘
                          │
                          ▼
                ┌──────────────────┐
                │  GitHub Releases │
                │                  │
                │  - v1.0.0.deb    │
                │  - v2.0.0.deb    │
                └──────────────────┘
```

## Core Components

### 1. A/B Slot Architecture

**Concept:**
- Two independent installation directories (slots)
- Only one slot is active at any time
- Updates install to the inactive slot
- Atomic switching between slots

**Implementation:**
```
/opt/app/
├── v1/          ← Slot A
├── v2/          ← Slot B
└── current →    ← Symlink (points to active slot)
```

**Benefits:**
- **Zero downtime**: New version installed while old version runs
- **Instant rollback**: Just switch symlink back
- **Disk space trade-off**: Requires 2x application space
- **Safe updates**: Old version untouched during update

### 2. Atomic Symlink Switching

**The Problem:**
Traditional file replacement is not atomic. During replacement, there's a moment where the file doesn't exist or is partially written.

**The Solution:**
Linux's `mv` command performs atomic rename operations on the same filesystem.

**Implementation:**
```bash
# Step 1: Create new symlink with temporary name
ln -sfn /opt/app/v2 /opt/app/current.tmp

# Step 2: Atomically replace old symlink with new one
mv -T /opt/app/current.tmp /opt/app/current
```

**Why This Works:**
1. `ln -sfn` creates a new symlink (doesn't touch the old one)
2. `mv -T` performs an atomic rename
3. At the filesystem level, this is a single inode operation
4. Either the old symlink exists OR the new one exists
5. No intermediate broken state

**Visual Timeline:**
```
Time 0: /opt/app/current → /opt/app/v1
        /opt/app/current.tmp doesn't exist

Time 1: /opt/app/current → /opt/app/v1
        /opt/app/current.tmp → /opt/app/v2

Time 2: /opt/app/current → /opt/app/v2
        /opt/app/current.tmp doesn't exist
```

**Critical Property:**
Running processes that have already opened files from `/opt/app/v1` continue using those files (Linux keeps the inode alive). New processes immediately see `/opt/app/v2`.

### 3. State Machine

The OTA system operates as a state machine to ensure crash safety:

```
┌──────┐
│ IDLE │ ←─────────────────────────┐
└───┬──┘                            │
    │                               │
    │ Update Available              │
    ▼                               │
┌──────────────┐                    │
│ DOWNLOADING  │                    │
└───┬──────────┘                    │
    │                               │
    │ Download Complete             │
    ▼                               │
┌──────────────┐                    │
│ INSTALLING   │                    │
└───┬──────────┘                    │
    │                               │
    │ Installation Complete         │
    ▼                               │
┌──────────────┐                    │
│ SWITCHING    │                    │
└───┬──────────┘                    │
    │                               │
    │ Symlink Switched              │
    ▼                               │
┌──────────────┐    Health Check    │
│ HEALTH_CHECK │────Failed──────────┤
└───┬──────────┘                    │
    │                               │
    │ Health Check Passed           │
    └───────────────────────────────┘
```

**State Persistence:**
Each state is written to `/opt/app/metadata/update_state` before entering that state.

**Recovery Logic:**
On boot or script restart, the system checks the state:
- `DOWNLOADING`: Clean up partial downloads, retry
- `INSTALLING`: Clean up partial installation, retry
- `SWITCHING`: Complete the switch (idempotent)
- `HEALTH_CHECK`: Perform health check or rollback
- `IDLE`: Normal operation

## Detailed OTA Flow

### Phase 1: Preparation

```bash
# 1. Internet Check
ping -c 1 8.8.8.8
ping -c 1 github.com

# 2. Read Current Version
current_version=$(cat /opt/app/current/VERSION)

# 3. Query GitHub API
latest_version=$(curl -s https://api.github.com/repos/USER/REPO/releases/latest \
                 | grep tag_name)
```

### Phase 2: Download

```bash
# 4. Get Download URL
download_url=$(curl -s https://api.github.com/repos/USER/REPO/releases/latest \
               | grep browser_download_url | grep .deb)

# 5. Download with Resume Support
curl -L -C - -o /var/cache/ota/downloads/app-v2.deb "$download_url"

# 6. Verify Package
file app-v2.deb | grep "Debian binary package"
```

### Phase 3: Installation

```bash
# 7. Determine Inactive Slot
active_slot=$(cat /opt/app/metadata/active_slot)
if [ "$active_slot" = "v1" ]; then
    inactive_slot="v2"
else
    inactive_slot="v1"
fi

# 8. Clean Inactive Slot
rm -rf /opt/app/$inactive_slot

# 9. Extract Package
dpkg-deb -x app-v2.deb /opt/app/$inactive_slot
```

### Phase 4: Switching

```bash
# 10. Atomic Switch
ln -sfn /opt/app/$inactive_slot /opt/app/current.tmp
mv -T /opt/app/current.tmp /opt/app/current

# 11. Update Metadata
echo "$inactive_slot" > /opt/app/metadata/active_slot

# 12. Restart Service
systemctl restart video-app.service
```

### Phase 5: Verification

```bash
# 13. Health Check Loop (30 seconds)
for i in {1..15}; do
    if ! systemctl is-active video-app.service; then
        # ROLLBACK!
        exit 1
    fi
    sleep 2
done

# 14. Mark as Last Known Good
echo "$inactive_slot" > /opt/app/metadata/last_known_good
```

## Rollback Mechanism

### Automatic Rollback Triggers

1. **Service Crash During Health Check**
   - Health check monitors service for 30 seconds
   - If service becomes inactive → immediate rollback

2. **Failed Service Restart**
   - If `systemctl restart` fails → immediate rollback

3. **Boot Failure** (future enhancement)
   - Track successful boots
   - If system fails to boot after update → rollback on next boot

### Rollback Process

```bash
rollback() {
    # 1. Read last known good version
    last_good=$(cat /opt/app/metadata/last_known_good)
    
    # 2. Switch symlink back
    ln -sfn /opt/app/$last_good /opt/app/current.tmp
    mv -T /opt/app/current.tmp /opt/app/current
    
    # 3. Update metadata
    echo "$last_good" > /opt/app/metadata/active_slot
    
    # 4. Restart service
    systemctl restart video-app.service
    
    # 5. Log rollback
    echo "$(date): Rolled back to $last_good" >> /var/cache/ota/logs/rollback.log
}
```

**Rollback Safety:**
- Uses the same atomic switching mechanism
- Last known good version is never deleted
- Rollback can be performed multiple times (idempotent)

## Crash Safety

### Scenario 1: Power Loss During Download

**State:** `DOWNLOADING`

**Recovery:**
```bash
# On next boot/run
if [ "$(cat update_state)" = "DOWNLOADING" ]; then
    # Clean up partial download
    rm -f /var/cache/ota/downloads/*.deb
    # Reset state
    echo "IDLE" > update_state
    # Retry update
fi
```

### Scenario 2: Power Loss During Installation

**State:** `INSTALLING`

**Recovery:**
```bash
# On next boot/run
if [ "$(cat update_state)" = "INSTALLING" ]; then
    # Clean up partial installation
    inactive_slot=$(get_inactive_slot)
    rm -rf /opt/app/$inactive_slot
    # Reset state
    echo "IDLE" > update_state
    # Retry update
fi
```

### Scenario 3: Power Loss During Switching

**State:** `SWITCHING`

**Recovery:**
```bash
# On next boot/run
if [ "$(cat update_state)" = "SWITCHING" ]; then
    # The switch might be complete or incomplete
    # Re-run the switch (idempotent)
    ln -sfn /opt/app/$new_slot /opt/app/current.tmp
    mv -T /opt/app/current.tmp /opt/app/current
    # Continue to health check
fi
```

### Scenario 4: Power Loss During Health Check

**State:** `HEALTH_CHECK`

**Recovery:**
```bash
# On next boot/run
if [ "$(cat update_state)" = "HEALTH_CHECK" ]; then
    # Assume health check failed
    rollback
fi
```

## Debian Package Structure

### Why .deb Format?

1. **Standard Linux packaging**: Native to Debian/Ubuntu
2. **Metadata support**: Version, dependencies, maintainer info
3. **Pre/post install scripts**: Setup automation
4. **Verification**: Built-in integrity checks
5. **Tooling**: `dpkg`, `apt` ecosystem

### Package Layout

```
video-app-v1.0.0.deb
├── DEBIAN/
│   ├── control          # Package metadata
│   └── postinst         # Post-installation script
└── opt/app/v1/
    ├── bin/
    │   └── video_app    # Application binary
    ├── lib/             # Dependencies (if any)
    └── VERSION          # Version file
```

### Control File

```
Package: video-app
Version: 1.0.0
Section: video
Priority: optional
Architecture: arm64
Maintainer: Your Name <email@example.com>
Description: Video Streaming Application
```

### Post-Install Script

```bash
#!/bin/bash
# Set permissions
chmod +x /opt/app/v1/bin/video_app

# Create VERSION file
echo "1.0.0" > /opt/app/v1/VERSION

# First-time setup
if [ ! -L /opt/app/current ]; then
    ln -sfn /opt/app/v1 /opt/app/current
fi
```

## Systemd Integration

### Service File (video-app.service)

```ini
[Unit]
Description=Video Streaming Application
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/app/current/bin/video_app
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Key Points:**
- `ExecStart` uses symlink path `/opt/app/current`
- `Restart=on-failure` ensures resilience
- Service doesn't know about A/B slots

### Timer File (ota-update.timer)

```ini
[Unit]
Description=OTA Update Timer

[Timer]
OnBootSec=5min           # First check 5 min after boot
OnUnitActiveSec=1h       # Then every hour
Persistent=true          # Catch up missed runs

[Install]
WantedBy=timers.target
```

**Benefits:**
- Automatic periodic checks
- Survives reboots
- No cron dependency
- Systemd logging integration

## Security Considerations

### 1. Download Verification

**Current:**
- File type verification (is it a .deb?)
- Size check (non-empty)

**Production Enhancement:**
```bash
# GPG signature verification
curl -L -o package.deb.sig "$url.sig"
gpg --verify package.deb.sig package.deb

# SHA256 checksum
expected_sha=$(curl -s "$url.sha256")
actual_sha=$(sha256sum package.deb | cut -d' ' -f1)
[ "$expected_sha" = "$actual_sha" ]
```

### 2. GitHub API Rate Limiting

**Problem:** Unauthenticated API calls limited to 60/hour

**Solution:**
```bash
# Use personal access token
GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
curl -H "Authorization: token $GITHUB_TOKEN" "$GITHUB_API"
```

### 3. Filesystem Permissions

```bash
# Restrict access to OTA directories
chmod 700 /opt/app
chmod 700 /var/cache/ota

# OTA script runs as root (required for systemctl)
# Ensure script is not world-writable
chmod 755 /usr/local/bin/ota-update.sh
```

## Performance Characteristics

### Disk Space

- **Active slot**: ~100MB (example)
- **Inactive slot**: ~100MB
- **Total**: ~200MB + overhead
- **Downloads cache**: ~100MB (temporary)

### Network Bandwidth

- **Package size**: ~100MB (example)
- **Download time** (10 Mbps): ~80 seconds
- **API calls**: Minimal (<1KB per check)

### Update Duration

1. Download: 1-5 minutes (depends on package size and network)
2. Installation: 5-10 seconds (extract .deb)
3. Switching: <1 second (atomic)
4. Service restart: 2-5 seconds
5. Health check: 30 seconds
6. **Total**: ~2-7 minutes

### Downtime

- **Application downtime**: 2-5 seconds (service restart only)
- **Stream interruption**: Existing connections may drop, new connections use new version immediately

## Testing Strategy

### Unit Tests

1. **Internet check**: Simulate network down
2. **Version comparison**: Test various version formats
3. **Download**: Test resume, failure, corruption
4. **Atomic switch**: Verify symlink correctness
5. **Rollback**: Simulate health check failure

### Integration Tests

1. **Full update flow**: v1 → v2
2. **Rollback flow**: v2 fails → v1
3. **Crash recovery**: Kill script at each state
4. **Power loss simulation**: Force reboot during update

### Production Validation

1. **Staging environment**: Test updates before production
2. **Canary deployment**: Update one device first
3. **Monitoring**: Track update success rate
4. **Alerting**: Notify on failed updates

## Monitoring and Observability

### Logs

```bash
# OTA update logs
/var/cache/ota/logs/ota-update.log

# Systemd journal
journalctl -u ota-update.service
journalctl -u video-app.service
```

### Metrics to Track

1. **Update success rate**: % of successful updates
2. **Rollback rate**: % of updates that rolled back
3. **Download failures**: Network issues
4. **Health check failures**: Application crashes
5. **Update duration**: Time to complete update

### Health Checks

**Current:**
- Service active check (`systemctl is-active`)

**Enhanced:**
```bash
# Application-specific health endpoint
curl -f http://localhost:8080/health

# Video stream check
ffprobe rtsp://localhost:8554/stream

# Resource usage check
check_cpu_usage
check_memory_usage
```

## Future Enhancements

1. **Delta updates**: Download only changed files
2. **Compression**: Reduce package size
3. **Parallel downloads**: Multiple chunks
4. **Update scheduling**: Maintenance windows
5. **Multi-device orchestration**: Fleet management
6. **Telemetry**: Report update status to server
7. **A/B/C slots**: Support for more than 2 versions
8. **Incremental rollout**: Percentage-based deployment

## Conclusion

This Level-3 OTA system provides:
- ✅ Production-grade reliability
- ✅ Atomic updates with zero-downtime
- ✅ Automatic rollback on failure
- ✅ Crash-safe state management
- ✅ No application code changes required
- ✅ External version management
- ✅ Automated periodic updates
- ✅ Comprehensive logging and monitoring

The A/B deployment strategy ensures that updates are safe, reversible, and transparent to the running application.
