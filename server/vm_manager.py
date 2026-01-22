#!/usr/bin/env python3
"""
Firecracker VM Manager - Manages microVM lifecycle
"""

import os
import json
import socket
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


class FirecrackerVM:
    """Manages a single Firecracker microVM instance."""
    
    def __init__(
        self,
        vm_id: str,
        socket_path: str,
        kernel_path: str,
        rootfs_path: str,
        vcpu_count: int = 1,
        mem_size_mib: int = 512
    ):
        self.vm_id = vm_id
        self.socket_path = socket_path
        self.kernel_path = kernel_path
        self.rootfs_path = rootfs_path
        self.vcpu_count = vcpu_count
        self.mem_size_mib = mem_size_mib
        self.process: Optional[subprocess.Popen] = None
        
    def _api_call(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API call to Firecracker over Unix socket."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        
        body = json.dumps(data) if data else ""
        request = (
            f"{method} {endpoint} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )
        
        sock.sendall(request.encode())
        response = sock.recv(65536).decode()
        sock.close()
        
        # Parse response
        parts = response.split("\r\n\r\n", 1)
        if len(parts) > 1 and parts[1]:
            return json.loads(parts[1])
        return {}
    
    def start(self) -> bool:
        """Start the Firecracker VM."""
        # Clean up old socket if exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        # Start Firecracker process
        self.process = subprocess.Popen(
            ["firecracker", "--api-sock", self.socket_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for socket to be ready
        for _ in range(50):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.1)
        else:
            return False
        
        # Configure boot source
        self._api_call("PUT", "/boot-source", {
            "kernel_image_path": self.kernel_path,
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
        })
        
        # Configure rootfs
        self._api_call("PUT", "/drives/rootfs", {
            "drive_id": "rootfs",
            "path_on_host": self.rootfs_path,
            "is_root_device": True,
            "is_read_only": False
        })
        
        # Configure machine
        self._api_call("PUT", "/machine-config", {
            "vcpu_count": self.vcpu_count,
            "mem_size_mib": self.mem_size_mib
        })
        
        # Start the VM
        self._api_call("PUT", "/actions", {"action_type": "InstanceStart"})
        
        return True
    
    def stop(self):
        """Stop the Firecracker VM."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
        
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
    
    def is_running(self) -> bool:
        """Check if VM is running."""
        return self.process is not None and self.process.poll() is None


class VMManager:
    """Manages multiple Firecracker VMs with S3 persistence."""
    
    def __init__(
        self,
        firecracker_bin: str = "/usr/bin/firecracker",
        kernel_path: str = "/opt/firecracker/vmlinux",
        base_rootfs_path: str = "/opt/firecracker/rootfs.ext4",
        vm_dir: str = "/tmp/firecracker-vms",
        s3_bucket: Optional[str] = None,
        aws_region: str = "us-east-1"
    ):
        self.firecracker_bin = firecracker_bin
        self.kernel_path = kernel_path
        self.base_rootfs_path = base_rootfs_path
        self.vm_dir = Path(vm_dir)
        self.vm_dir.mkdir(parents=True, exist_ok=True)
        
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3', region_name=aws_region) if s3_bucket else None
        
        self.vms: Dict[str, FirecrackerVM] = {}
    
    def _get_user_rootfs_path(self, user_id: str) -> Path:
        """Get path to user's rootfs image."""
        return self.vm_dir / f"{user_id}_rootfs.ext4"
    
    def _get_socket_path(self, user_id: str) -> str:
        """Get path to user's VM socket."""
        return str(self.vm_dir / f"{user_id}.sock")
    
    def restore_from_s3(self, user_id: str) -> bool:
        """Restore user's rootfs from S3."""
        if not self.s3_client:
            return False
        
        rootfs_path = self._get_user_rootfs_path(user_id)
        s3_key = f"users/{user_id}/rootfs.ext4"
        
        try:
            self.s3_client.download_file(self.s3_bucket, s3_key, str(rootfs_path))
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def save_to_s3(self, user_id: str) -> bool:
        """Save user's rootfs to S3."""
        if not self.s3_client:
            return False
        
        rootfs_path = self._get_user_rootfs_path(user_id)
        if not rootfs_path.exists():
            return False
        
        s3_key = f"users/{user_id}/rootfs.ext4"
        self.s3_client.upload_file(str(rootfs_path), self.s3_bucket, s3_key)
        return True
    
    def create_vm(self, user_id: str) -> FirecrackerVM:
        """Create or restore a VM for user."""
        if user_id in self.vms and self.vms[user_id].is_running():
            return self.vms[user_id]
        
        rootfs_path = self._get_user_rootfs_path(user_id)
        
        # Try to restore from S3
        if not rootfs_path.exists():
            if not self.restore_from_s3(user_id):
                # Copy base rootfs for new user
                shutil.copy(self.base_rootfs_path, rootfs_path)
        
        vm = FirecrackerVM(
            vm_id=user_id,
            socket_path=self._get_socket_path(user_id),
            kernel_path=self.kernel_path,
            rootfs_path=str(rootfs_path)
        )
        
        vm.start()
        self.vms[user_id] = vm
        return vm
    
    def stop_vm(self, user_id: str, save: bool = True):
        """Stop a user's VM, optionally saving to S3."""
        if user_id not in self.vms:
            return
        
        vm = self.vms[user_id]
        vm.stop()
        
        if save:
            self.save_to_s3(user_id)
        
        del self.vms[user_id]
    
    def get_vm(self, user_id: str) -> Optional[FirecrackerVM]:
        """Get user's VM if running."""
        return self.vms.get(user_id)
