"""
Code execution environment for the AI agent.
Handles Python and shell command execution with optional S3 persistence.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class PersistentCodeExecutor:
    """
    Executes code with optional S3-backed persistent storage.
    
    In AWS Lambda: Files are synced to/from S3 for persistence.
    In local mode: Files are stored in a local directory.
    """
    
    def __init__(
        self, 
        user_id: str, 
        workspace_base: str = "/tmp",
        s3_bucket: Optional[str] = None,
        local_mode: bool = False
    ):
        self.user_id = user_id
        self.local_mode = local_mode
        
        # Sanitize user_id for filesystem
        safe_user_id = user_id.replace('@', '_').replace('.', '_')
        self.workspace = os.path.join(workspace_base, f"workspace_{safe_user_id}")
        
        # S3 configuration
        self.s3_bucket = s3_bucket or os.environ.get("FILES_BUCKET", "delta3-files")
        self.s3_prefix = f"users/{user_id}/workspace/"
        
        if HAS_BOTO3 and not local_mode:
            self.s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        else:
            self.s3 = None
        
        self._setup_workspace()
    
    def _setup_workspace(self):
        """Setup workspace by optionally restoring files from S3."""
        # Clean and create workspace
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)
        os.makedirs(self.workspace, exist_ok=True)
        
        # Restore files from S3 if available
        if self.s3 and not self.local_mode:
            self._restore_from_s3()
    
    def _restore_from_s3(self):
        """Restore files from S3."""
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    relative_path = key.replace(self.s3_prefix, '')
                    if relative_path:
                        local_path = os.path.join(self.workspace, relative_path)
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        self.s3.download_file(self.s3_bucket, key, local_path)
        except Exception:
            pass  # No files yet, that's okay
    
    def _sync_to_s3(self, path: str, content: str = None):
        """Sync a file to S3."""
        if not self.s3 or self.local_mode:
            return
        
        # Normalize path
        if path.startswith("/"):
            path = path[1:]
        if path.startswith("tmp/workspace"):
            path = path.split("/", 3)[-1] if len(path.split("/")) > 3 else ""
        
        s3_key = f"{self.s3_prefix}{path}"
        
        try:
            if content is not None:
                self.s3.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=content.encode('utf-8'),
                    ContentType='text/plain'
                )
            else:
                local_path = os.path.join(self.workspace, path)
                if os.path.exists(local_path):
                    self.s3.upload_file(local_path, self.s3_bucket, s3_key)
        except Exception as e:
            print(f"S3 sync error: {e}")
    
    def _delete_from_s3(self, path: str):
        """Delete a file from S3."""
        if not self.s3 or self.local_mode:
            return
        
        if path.startswith("/"):
            path = path[1:]
        
        s3_key = f"{self.s3_prefix}{path}"
        
        try:
            self.s3.delete_object(Bucket=self.s3_bucket, Key=s3_key)
        except Exception:
            pass
    
    def execute_python(self, code: str) -> Dict[str, Any]:
        """Execute Python code."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", 
                suffix=".py", 
                dir=self.workspace,
                delete=False
            ) as f:
                f.write(code)
                script_path = f.name
            
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.workspace,
                env={**os.environ, "PYTHONPATH": self.workspace}
            )
            
            os.unlink(script_path)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out (60s limit)", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
    
    def execute_shell(self, command: str) -> Dict[str, Any]:
        """Execute shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.workspace
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Command timed out (60s limit)", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file to workspace and sync to S3."""
        try:
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            dir_path = os.path.dirname(full_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(content)
            
            self._sync_to_s3(clean_path, content)
            
            return {"success": True, "path": clean_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file from workspace."""
        try:
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            
            with open(full_path, "r") as f:
                content = f.read()
            
            return {"success": True, "content": content}
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_files(self, path: str = "") -> Dict[str, Any]:
        """List files in directory."""
        try:
            clean_path = path.lstrip("/") if path else ""
            full_path = os.path.join(self.workspace, clean_path) if clean_path else self.workspace
            
            if not os.path.exists(full_path):
                return {"success": True, "files": []}
            
            files = []
            for name in os.listdir(full_path):
                # Skip temp files
                if name.startswith("tmp") and name.endswith(".py"):
                    continue
                    
                item_path = os.path.join(full_path, name)
                files.append({
                    "name": name,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                })
            
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file from workspace and S3."""
        try:
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            
            if os.path.exists(full_path):
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.unlink(full_path)
            
            self._delete_from_s3(clean_path)
            
            return {"success": True, "path": clean_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
