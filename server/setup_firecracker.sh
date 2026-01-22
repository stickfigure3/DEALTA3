#!/bin/bash
# Setup script for Firecracker infrastructure
# Run this on an EC2 instance with KVM support (e.g., .metal or nitro instances)

set -e

echo "=== DELTA3 Firecracker Setup ==="

# Check for KVM
if [ ! -e /dev/kvm ]; then
    echo "❌ KVM not available. Use a bare metal or .metal EC2 instance."
    exit 1
fi
echo "✅ KVM available"

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y curl jq

# Create directories
sudo mkdir -p /opt/firecracker
cd /opt/firecracker

# Download Firecracker
FIRECRACKER_VERSION="v1.6.0"
echo "Downloading Firecracker ${FIRECRACKER_VERSION}..."
curl -L -o firecracker.tgz \
    "https://github.com/firecracker-microvm/firecracker/releases/download/${FIRECRACKER_VERSION}/firecracker-${FIRECRACKER_VERSION}-x86_64.tgz"

tar -xzf firecracker.tgz
sudo mv release-${FIRECRACKER_VERSION}-x86_64/firecracker-${FIRECRACKER_VERSION}-x86_64 /usr/bin/firecracker
sudo chmod +x /usr/bin/firecracker
rm -rf firecracker.tgz release-*

echo "✅ Firecracker installed: $(firecracker --version)"

# Download kernel
echo "Downloading kernel..."
KERNEL_URL="https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/x86_64/kernels/vmlinux.bin"
sudo curl -L -o vmlinux "${KERNEL_URL}"
echo "✅ Kernel downloaded"

# Create base rootfs
echo "Creating base rootfs..."
ROOTFS_URL="https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/x86_64/rootfs/bionic.rootfs.ext4"
sudo curl -L -o rootfs.ext4 "${ROOTFS_URL}"

# Customize rootfs (add Python, etc.)
echo "Customizing rootfs (this takes a few minutes)..."
mkdir -p /tmp/rootfs_mount
sudo mount rootfs.ext4 /tmp/rootfs_mount

# Add Python and common tools
sudo chroot /tmp/rootfs_mount /bin/bash -c "
    apt-get update
    apt-get install -y python3 python3-pip curl wget git
    pip3 install requests
    
    # Create user directory
    mkdir -p /home/user
    chown 1000:1000 /home/user
    
    # Set up SSH (optional)
    apt-get install -y openssh-server
    mkdir -p /var/run/sshd
"

sudo umount /tmp/rootfs_mount
echo "✅ Rootfs customized"

# Set permissions
sudo chmod 644 vmlinux rootfs.ext4

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Files created:"
echo "  /usr/bin/firecracker - Firecracker binary"
echo "  /opt/firecracker/vmlinux - Linux kernel"
echo "  /opt/firecracker/rootfs.ext4 - Base root filesystem"
echo ""
echo "Next steps:"
echo "  1. Configure S3 bucket for persistence"
echo "  2. Set up environment variables in .env"
echo "  3. Run the API server: cd server && python api.py"
