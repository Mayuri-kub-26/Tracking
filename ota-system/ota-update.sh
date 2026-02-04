#!/bin/bash

################################################################################
# Production-Grade OTA Update Script for A/B Deployment
# Supports atomic switching, health checks, and automatic rollback
################################################################################

set -euo pipefail

# Configuration
APP_BASE="/opt/app"
SLOT_A="${APP_BASE}/v1"
SLOT_B="${APP_BASE}/v2"
CURRENT_SYMLINK="${APP_BASE}/current"
METADATA_DIR="${APP_BASE}/metadata"
CACHE_DIR="/var/cache/ota"
DOWNLOAD_DIR="${CACHE_DIR}/downloads"
LOG_DIR="${CACHE_DIR}/logs"
LOG_FILE="${LOG_DIR}/ota-update.log"

# GitHub Configuration
GITHUB_REPO="your-username/your-repo"  # TODO: Replace with actual repo
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"

# Service Configuration
SERVICE_NAME="video-app.service"
HEALTH_CHECK_DURATION=30  # seconds
HEALTH_CHECK_INTERVAL=2   # seconds

# State file paths
STATE_FILE="${METADATA_DIR}/update_state"
ACTIVE_SLOT_FILE="${METADATA_DIR}/active_slot"
LAST_KNOWN_GOOD_FILE="${METADATA_DIR}/last_known_good"

################################################################################
# Logging Functions
################################################################################

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${LOG_FILE}" >&2
}

################################################################################
# State Management
################################################################################

set_state() {
    local state="$1"
    echo "${state}" > "${STATE_FILE}"
    log "State changed to: ${state}"
}

get_state() {
    if [[ -f "${STATE_FILE}" ]]; then
        cat "${STATE_FILE}"
    else
        echo "IDLE"
    fi
}

################################################################################
# Setup and Initialization
################################################################################

initialize() {
    log "Initializing OTA update system..."
    
    # Create necessary directories
    mkdir -p "${METADATA_DIR}" "${DOWNLOAD_DIR}" "${LOG_DIR}"
    
    # Initialize state files if they don't exist
    if [[ ! -f "${STATE_FILE}" ]]; then
        set_state "IDLE"
    fi
    
    if [[ ! -f "${ACTIVE_SLOT_FILE}" ]]; then
        # Determine active slot from symlink
        if [[ -L "${CURRENT_SYMLINK}" ]]; then
            local target
            target=$(readlink "${CURRENT_SYMLINK}")
            echo "$(basename "${target}")" > "${ACTIVE_SLOT_FILE}"
        else
            echo "v1" > "${ACTIVE_SLOT_FILE}"
        fi
    fi
    
    if [[ ! -f "${LAST_KNOWN_GOOD_FILE}" ]]; then
        cat "${ACTIVE_SLOT_FILE}" > "${LAST_KNOWN_GOOD_FILE}"
    fi
}

################################################################################
# Internet Connectivity Check
################################################################################

check_internet() {
    log "Checking internet connectivity..."
    
    # Try multiple reliable hosts
    local hosts=("8.8.8.8" "1.1.1.1" "github.com")
    
    for host in "${hosts[@]}"; do
        if ping -c 1 -W 2 "${host}" &> /dev/null; then
            log "Internet connectivity confirmed (${host})"
            return 0
        fi
    done
    
    log_error "No internet connectivity detected"
    return 1
}

################################################################################
# Version Management
################################################################################

get_current_version() {
    local active_slot
    active_slot=$(cat "${ACTIVE_SLOT_FILE}")
    local version_file="${APP_BASE}/${active_slot}/VERSION"
    
    if [[ -f "${version_file}" ]]; then
        cat "${version_file}"
    else
        echo "unknown"
    fi
}

get_latest_version_from_github() {
    log "Querying GitHub for latest release..."
    
    local response
    response=$(curl -s -f "${GITHUB_API}" 2>&1) || {
        log_error "Failed to query GitHub API"
        return 1
    }
    
    # Extract version tag (assumes tag format: v1.0.0 or 1.0.0)
    local version
    version=$(echo "${response}" | grep -oP '"tag_name":\s*"\K[^"]+' | head -1)
    
    if [[ -z "${version}" ]]; then
        log_error "Could not parse version from GitHub response"
        return 1
    fi
    
    echo "${version}"
}

get_download_url_from_github() {
    local version="$1"
    log "Getting download URL for version ${version}..."
    
    local response
    response=$(curl -s -f "${GITHUB_API}" 2>&1) || {
        log_error "Failed to query GitHub API"
        return 1
    }
    
    # Extract .deb download URL
    local url
    url=$(echo "${response}" | grep -oP '"browser_download_url":\s*"\K[^"]+\.deb' | head -1)
    
    if [[ -z "${url}" ]]; then
        log_error "Could not find .deb download URL"
        return 1
    fi
    
    echo "${url}"
}

################################################################################
# Download and Verification
################################################################################

download_package() {
    local url="$1"
    local output_file="$2"
    
    log "Downloading package from ${url}..."
    set_state "DOWNLOADING"
    
    # Download with resume support and progress
    if curl -L -f -C - -o "${output_file}" "${url}"; then
        log "Download completed: ${output_file}"
        return 0
    else
        log_error "Download failed"
        return 1
    fi
}

verify_package() {
    local package_file="$1"
    
    log "Verifying package integrity..."
    
    # Check if file exists and is not empty
    if [[ ! -f "${package_file}" ]] || [[ ! -s "${package_file}" ]]; then
        log_error "Package file is missing or empty"
        return 1
    fi
    
    # Verify it's a valid .deb file
    if ! file "${package_file}" | grep -q "Debian binary package"; then
        log_error "File is not a valid Debian package"
        return 1
    fi
    
    # Optional: Verify checksum if provided by GitHub
    # TODO: Implement checksum verification if available
    
    log "Package verification successful"
    return 0
}

################################################################################
# Installation
################################################################################

get_inactive_slot() {
    local active_slot
    active_slot=$(cat "${ACTIVE_SLOT_FILE}")
    
    if [[ "${active_slot}" == "v1" ]]; then
        echo "v2"
    else
        echo "v1"
    fi
}

install_to_slot() {
    local package_file="$1"
    local slot="$2"
    
    log "Installing package to slot ${slot}..."
    set_state "INSTALLING"
    
    local slot_path="${APP_BASE}/${slot}"
    
    # Clean the inactive slot first
    if [[ -d "${slot_path}" ]]; then
        log "Cleaning existing installation in ${slot}..."
        rm -rf "${slot_path}"
    fi
    
    # Extract .deb to the slot
    # Note: We use dpkg-deb to extract, not install, to maintain A/B structure
    mkdir -p "${slot_path}"
    
    if dpkg-deb -x "${package_file}" "${slot_path}"; then
        log "Package extracted to ${slot_path}"
        
        # Verify VERSION file exists
        if [[ ! -f "${slot_path}/VERSION" ]]; then
            log_error "VERSION file not found in package"
            return 1
        fi
        
        return 0
    else
        log_error "Failed to extract package"
        return 1
    fi
}

################################################################################
# Atomic Switching
################################################################################

switch_to_slot() {
    local new_slot="$1"
    
    log "Performing atomic switch to ${new_slot}..."
    set_state "SWITCHING"
    
    local new_target="${APP_BASE}/${new_slot}"
    local temp_symlink="${CURRENT_SYMLINK}.tmp"
    
    # Create temporary symlink
    ln -sfn "${new_target}" "${temp_symlink}"
    
    # Atomic rename (this is the critical atomic operation)
    if mv -T "${temp_symlink}" "${CURRENT_SYMLINK}"; then
        log "Symlink switched atomically to ${new_slot}"
        echo "${new_slot}" > "${ACTIVE_SLOT_FILE}"
        return 0
    else
        log_error "Failed to switch symlink"
        rm -f "${temp_symlink}"
        return 1
    fi
}

################################################################################
# Service Management
################################################################################

restart_service() {
    log "Restarting ${SERVICE_NAME}..."
    
    if systemctl restart "${SERVICE_NAME}"; then
        log "Service restarted successfully"
        return 0
    else
        log_error "Failed to restart service"
        return 1
    fi
}

################################################################################
# Health Check
################################################################################

health_check() {
    log "Starting health check (${HEALTH_CHECK_DURATION}s)..."
    set_state "HEALTH_CHECK"
    
    local elapsed=0
    
    while [[ ${elapsed} -lt ${HEALTH_CHECK_DURATION} ]]; do
        # Check if service is active
        if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
            log_error "Service is not active during health check"
            return 1
        fi
        
        # Optional: Add application-specific health check
        # For example, check if video stream is accessible
        # if ! curl -f http://localhost:8080/health &> /dev/null; then
        #     log_error "Application health endpoint failed"
        #     return 1
        # fi
        
        sleep ${HEALTH_CHECK_INTERVAL}
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
    done
    
    log "Health check passed"
    return 0
}

################################################################################
# Rollback
################################################################################

rollback() {
    log "Initiating rollback..."
    
    local last_good
    last_good=$(cat "${LAST_KNOWN_GOOD_FILE}")
    
    log "Rolling back to last known good version: ${last_good}"
    
    # Switch back to last known good
    if switch_to_slot "${last_good}"; then
        if restart_service; then
            log "Rollback successful"
            set_state "IDLE"
            return 0
        fi
    fi
    
    log_error "Rollback failed - manual intervention required!"
    return 1
}

################################################################################
# Main Update Flow
################################################################################

perform_update() {
    log "========================================="
    log "Starting OTA update check..."
    log "========================================="
    
    # 1. Check internet connectivity
    if ! check_internet; then
        log "No internet connection. Will retry later."
        return 0
    fi
    
    # 2. Get current version
    local current_version
    current_version=$(get_current_version)
    log "Current version: ${current_version}"
    
    # 3. Get latest version from GitHub
    local latest_version
    if ! latest_version=$(get_latest_version_from_github); then
        log_error "Failed to get latest version from GitHub"
        return 1
    fi
    log "Latest version: ${latest_version}"
    
    # 4. Compare versions
    if [[ "${current_version}" == "${latest_version}" ]]; then
        log "Already running latest version. No update needed."
        return 0
    fi
    
    log "New version available: ${latest_version}"
    
    # 5. Get download URL
    local download_url
    if ! download_url=$(get_download_url_from_github "${latest_version}"); then
        log_error "Failed to get download URL"
        return 1
    fi
    
    # 6. Download package
    local package_file="${DOWNLOAD_DIR}/video-app-${latest_version}.deb"
    if ! download_package "${download_url}" "${package_file}"; then
        log_error "Failed to download package"
        return 1
    fi
    
    # 7. Verify package
    if ! verify_package "${package_file}"; then
        log_error "Package verification failed"
        rm -f "${package_file}"
        return 1
    fi
    
    # 8. Determine inactive slot
    local inactive_slot
    inactive_slot=$(get_inactive_slot)
    log "Installing to inactive slot: ${inactive_slot}"
    
    # 9. Install to inactive slot
    if ! install_to_slot "${package_file}" "${inactive_slot}"; then
        log_error "Installation failed"
        return 1
    fi
    
    # 10. Switch to new version
    if ! switch_to_slot "${inactive_slot}"; then
        log_error "Failed to switch slots"
        return 1
    fi
    
    # 11. Restart service
    if ! restart_service; then
        log_error "Failed to restart service"
        rollback
        return 1
    fi
    
    # 12. Health check
    if ! health_check; then
        log_error "Health check failed"
        rollback
        return 1
    fi
    
    # 13. Update last known good
    echo "${inactive_slot}" > "${LAST_KNOWN_GOOD_FILE}"
    log "Update completed successfully!"
    log "New version ${latest_version} is now active in slot ${inactive_slot}"
    
    set_state "IDLE"
    
    # Clean up old download
    rm -f "${package_file}"
    
    return 0
}

################################################################################
# Recovery from Interrupted Updates
################################################################################

recover_from_interrupted_update() {
    local state
    state=$(get_state)
    
    log "Checking for interrupted update (state: ${state})..."
    
    case "${state}" in
        DOWNLOADING|INSTALLING)
            log "Cleaning up interrupted download/installation..."
            rm -f "${DOWNLOAD_DIR}"/*.deb
            set_state "IDLE"
            ;;
        SWITCHING)
            log "Completing interrupted switch..."
            # The switch should have completed, just verify
            set_state "IDLE"
            ;;
        HEALTH_CHECK)
            log "Interrupted during health check, performing rollback..."
            rollback
            ;;
        IDLE)
            log "No recovery needed"
            ;;
        *)
            log "Unknown state: ${state}, resetting to IDLE"
            set_state "IDLE"
            ;;
    esac
}

################################################################################
# Main Entry Point
################################################################################

main() {
    # Initialize system
    initialize
    
    # Recover from any interrupted updates
    recover_from_interrupted_update
    
    # Perform update
    if perform_update; then
        log "OTA update process completed successfully"
        exit 0
    else
        log_error "OTA update process failed"
        exit 1
    fi
}

# Run main function
main "$@"
