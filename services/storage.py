import os
import logging
import hashlib
from typing import Optional, Union
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class StorageError(Exception):
    """Base exception for storage operations"""
    pass

class StorageService:
    """Unified storage service supporting local filesystem and S3-compatible backends"""
    
    def __init__(self):
        self.backend_type = "local"  # Default to local
        self.base_path = None
        self.s3_client = None
        self.s3_bucket = None
        
        # Check for S3 configuration
        s3_endpoint = os.getenv("S3_ENDPOINT")
        s3_bucket = os.getenv("S3_BUCKET")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")
        
        if all([s3_endpoint, s3_bucket, s3_access_key, s3_secret_key]):
            self._init_s3_backend(s3_endpoint, s3_bucket, s3_access_key, s3_secret_key)
        else:
            self._init_local_backend()
        
        logger.info(f"🚀 Storage service initialized with {self.backend_type} backend")
        if self.backend_type == "local":
            logger.info(f"   📁 Local storage root: {self.base_path}")
        else:
            logger.info(f"   ☁️ S3-compatible storage: {s3_endpoint}/{s3_bucket}")
    
    def _init_s3_backend(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
        """Initialize S3-compatible backend"""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name='us-east-1'  # Default region
            )
            
            # Test connection
            self.s3_client.head_bucket(Bucket=bucket)
            
            self.s3_bucket = bucket
            self.backend_type = "s3"
            logger.info("✅ S3 backend connection successful")
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"❌ S3 backend initialization failed: {e}")
            logger.warning("⚠️ Falling back to local storage")
            self._init_local_backend()
    
    def _init_local_backend(self):
        """Initialize local filesystem backend"""
        self.base_path = Path(os.getenv("FILE_STORAGE_ROOT", "/mnt/data/generated"))
        
        # Ensure directory exists
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Local storage directory ready: {self.base_path}")
        except Exception as e:
            logger.error(f"❌ Failed to create local storage directory: {e}")
            # Fallback to system temp directory
            import tempfile
            self.base_path = Path(tempfile.gettempdir()) / "reqagent_storage"
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.warning(f"⚠️ Using fallback temp directory: {self.base_path}")
    
    def _validate_path(self, path: str) -> str:
        """Validate and sanitize file path to prevent path traversal attacks"""
        # Remove any path traversal attempts
        clean_path = os.path.normpath(path).replace('..', '').replace('//', '/')
        
        # Ensure path doesn't start with absolute paths or drive letters
        if clean_path.startswith('/') or ':' in clean_path:
            clean_path = clean_path.lstrip('/').split(':', 1)[-1]
        
        # Remove any remaining dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            clean_path = clean_path.replace(char, '_')
        
        return clean_path
    
    def _get_full_path(self, path: str) -> Union[Path, str]:
        """Get full storage path based on backend type"""
        clean_path = self._validate_path(path)
        
        if self.backend_type == "local":
            return self.base_path / clean_path
        else:
            return clean_path
    
    def save_bytes(self, path: str, data: bytes) -> str:
        """Save bytes to storage and return canonical path/URI"""
        try:
            clean_path = self._validate_path(path)
            
            if self.backend_type == "local":
                full_path = self.base_path / clean_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_path, 'wb') as f:
                    f.write(data)
                
                logger.info(f"💾 Saved {len(data)} bytes to local path: {full_path}")
                return str(full_path)
                
            else:  # S3
                try:
                    self.s3_client.put_object(
                        Bucket=self.s3_bucket,
                        Key=clean_path,
                        Body=data,
                        ServerSideEncryption='AES256' if self._supports_encryption() else None
                    )
                    
                    # Return S3 URI
                    s3_uri = f"s3://{self.s3_bucket}/{clean_path}"
                    logger.info(f"💾 Saved {len(data)} bytes to S3: {s3_uri}")
                    return s3_uri
                    
                except ClientError as e:
                    logger.error(f"❌ S3 upload failed: {e}")
                    raise StorageError(f"S3 upload failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage save failed: {e}")
            raise StorageError(f"Failed to save data: {e}")
    
    def open(self, path: str) -> bytes:
        """Read bytes from storage"""
        try:
            clean_path = self._validate_path(path)
            
            if self.backend_type == "local":
                full_path = self.base_path / clean_path
                if not full_path.exists():
                    raise FileNotFoundError(f"File not found: {full_path}")
                
                with open(full_path, 'rb') as f:
                    data = f.read()
                
                logger.info(f"📖 Read {len(data)} bytes from local path: {full_path}")
                return data
                
            else:  # S3
                try:
                    response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=clean_path)
                    data = response['Body'].read()
                    
                    logger.info(f"📖 Read {len(data)} bytes from S3: {clean_path}")
                    return data
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        raise FileNotFoundError(f"File not found in S3: {clean_path}")
                    raise StorageError(f"S3 read failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage read failed: {e}")
            raise StorageError(f"Failed to read data: {e}")
    
    def exists(self, path: str) -> bool:
        """Check if file exists in storage"""
        try:
            clean_path = self._validate_path(path)
            
            if self.backend_type == "local":
                full_path = self.base_path / clean_path
                return full_path.exists()
                
            else:  # S3
                try:
                    self.s3_client.head_object(Bucket=self.s3_bucket, Key=clean_path)
                    return True
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        return False
                    raise StorageError(f"S3 existence check failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage existence check failed: {e}")
            return False
    
    def delete(self, path: str) -> None:
        """Delete file from storage"""
        try:
            clean_path = self._validate_path(path)
            
            if self.backend_type == "local":
                full_path = self.base_path / clean_path
                if full_path.exists():
                    full_path.unlink()
                    logger.info(f"🗑️ Deleted local file: {full_path}")
                
            else:  # S3
                try:
                    self.s3_client.delete_object(Bucket=self.s3_bucket, Key=clean_path)
                    logger.info(f"🗑️ Deleted S3 file: {clean_path}")
                except ClientError as e:
                    logger.error(f"❌ S3 delete failed: {e}")
                    raise StorageError(f"S3 delete failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage delete failed: {e}")
            raise StorageError(f"Failed to delete file: {e}")
    
    def _supports_encryption(self) -> bool:
        """Check if S3 backend supports server-side encryption"""
        try:
            if self.s3_client:
                # Try to get bucket encryption configuration
                self.s3_client.get_bucket_encryption(Bucket=self.s3_bucket)
                return True
        except:
            pass
        return False
    
    def get_file_size(self, path: str) -> int:
        """Get file size in bytes"""
        try:
            clean_path = self._validate_path(path)
            
            if self.backend_type == "local":
                full_path = self.base_path / clean_path
                if full_path.exists():
                    return full_path.stat().st_size
                return 0
                
            else:  # S3
                try:
                    response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=clean_path)
                    return response['ContentLength']
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        return 0
                    raise StorageError(f"S3 size check failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage size check failed: {e}")
            return 0
    
    def list_files(self, prefix: str = "") -> list:
        """List files with given prefix"""
        try:
            clean_prefix = self._validate_path(prefix)
            
            if self.backend_type == "local":
                full_prefix = self.base_path / clean_prefix
                if not full_prefix.exists():
                    return []
                
                files = []
                for item in full_prefix.rglob("*"):
                    if item.is_file():
                        files.append(str(item.relative_to(self.base_path)))
                return files
                
            else:  # S3
                try:
                    response = self.s3_client.list_objects_v2(
                        Bucket=self.s3_bucket,
                        Prefix=clean_prefix
                    )
                    
                    if 'Contents' in response:
                        return [obj['Key'] for obj in response['Contents']]
                    return []
                    
                except ClientError as e:
                    logger.error(f"❌ S3 list failed: {e}")
                    raise StorageError(f"S3 list failed: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Storage list failed: {e}")
            return []

# Global storage service instance
storage_service = StorageService()

