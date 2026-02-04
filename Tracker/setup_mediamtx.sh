#!/bin/bash
set -e

# Version to install
VERSION="v1.15.6"
ARCH="arm64" # For x86_64

echo "Downloading MediaMTX ${VERSION} for ${ARCH}..."
URL="https://github.com/bluenviron/mediamtx/releases/download/${VERSION}/mediamtx_${VERSION}_linux_${ARCH}.tar.gz"

wget -q --show-progress $URL -O mediamtx.tar.gz

echo "Extracting..."
tar -xzf mediamtx.tar.gz

echo "Installing binary to /usr/local/bin/..."
sudo mv mediamtx /usr/local/bin/
sudo chmod +x /usr/local/bin/mediamtx

echo "Installing config to /usr/local/etc/..."
if [ -f /usr/local/etc/mediamtx.yml ]; then
    echo "Config already exists at /usr/local/etc/mediamtx.yml. Backing up..."
    sudo mv /usr/local/etc/mediamtx.yml /usr/local/etc/mediamtx.yml.bak
fi
sudo mv mediamtx.yml /usr/local/etc/

echo "Cleaning up..."
rm mediamtx.tar.gz LICENSE

echo "MediaMTX installed successfully."
echo "Binary: /usr/local/bin/mediamtx"
echo "Config: /usr/local/etc/mediamtx.yml"
