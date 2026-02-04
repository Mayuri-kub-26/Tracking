#!/bin/bash

# Target IPs to check
TARGET_IP1="192.168.145.25"
TARGET_IP2="192.168.144.60"

# Function to ping a host
check_ping() {
  ping -c 1 -W 1 "$1" > /dev/null 2>&1
  return $?
}

echo "Waiting for network connectivity to $TARGET_IP1 and $TARGET_IP2..."

# Loop until both IPs are reachable
while true; do
  if check_ping "$TARGET_IP1" && check_ping "$TARGET_IP2"; then
    echo "Both targets are reachable. Starting service..."
    break
  else
    echo "Waiting for targets to act up..."
    sleep 2
  fi
done

# Execute the python application
# Using exec to replace the shell process with the python process
exec /usr/bin/python3 src/main.py --mode production
