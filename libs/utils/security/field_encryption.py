"""Field-Level Encryption Manager for sensitive data protection."""

import json
import base64
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = structlog.get_logger(__name__)


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    FERNET = "fernet"


class KeyRotationStatus(Enum):
    """Key rotation status."""
    ACTIVE = "active"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class EncryptionKey:
    """Encryption key metadata."""
    key_id: str
    algorithm: EncryptionAlgorithm
    key_version: int
    created_at: datetime
    status: KeyRotationStatus
    tenant_id: str
    field_name: Optional[str] = None


@dataclass
class EncryptedField:
    """Encrypted field data."""
    encrypted_data: str
    key_id: str
    algorithm: EncryptionAlgorithm
    key_version: int
    created_at: datetime
    metadata: Dict[str, Any]


class FieldEncryptionManager:
    """Manages field-level encryption for sensitive data."""
    
    def __init__(self, kms_client=None):
        self.kms_client = kms_client
        self.key_cache: Dict[str, EncryptionKey] = {}
        self.encryption_cache: Dict[str, Fernet] = {}
        self.key_rotation_interval = 90  # days
        self.algorithm = EncryptionAlgorithm.FERNET
    
    async def encrypt_field(self, value: Any, tenant_id: str, field_name: str, 
                          key_id: Optional[str] = None) -> EncryptedField:
        """Encrypt a field value."""
        try:
            # Get or create encryption key
            if not key_id:
                key_id = await self._get_or_create_key(tenant_id, field_name)
            
            # Get encryption cipher
            cipher = await self._get_cipher(key_id)
            
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, ensure_ascii=False)
            else:
                serialized_value = str(value)
            
            # Encrypt the value
            encrypted_bytes = cipher.encrypt(serialized_value.encode('utf-8'))
            encrypted_data = base64.b64encode(encrypted_bytes).decode('utf-8')
            
            # Create encrypted field
            encrypted_field = EncryptedField(
                encrypted_data=encrypted_data,
                key_id=key_id,
                algorithm=self.algorithm,
                key_version=self.key_cache[key_id].key_version,
                created_at=datetime.now(timezone.utc),
                metadata={
                    "field_name": field_name,
                    "tenant_id": tenant_id,
                    "original_type": type(value).__name__
                }
            )
            
            logger.info("Field encrypted successfully",
                       tenant_id=tenant_id,
                       field_name=field_name,
                       key_id=key_id)
            
            return encrypted_field
            
        except Exception as e:
            logger.error("Failed to encrypt field",
                        tenant_id=tenant_id,
                        field_name=field_name,
                        error=str(e))
            raise
    
    async def decrypt_field(self, encrypted_field: EncryptedField) -> Any:
        """Decrypt a field value."""
        try:
            # Get encryption cipher
            cipher = await self._get_cipher(encrypted_field.key_id)
            
            # Decode and decrypt
            encrypted_bytes = base64.b64decode(encrypted_field.encrypted_data.encode('utf-8'))
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            decrypted_value = decrypted_bytes.decode('utf-8')
            
            # Deserialize if needed
            original_type = encrypted_field.metadata.get("original_type", "str")
            if original_type in ["dict", "list"]:
                try:
                    return json.loads(decrypted_value)
                except json.JSONDecodeError:
                    return decrypted_value
            elif original_type == "int":
                return int(decrypted_value)
            elif original_type == "float":
                return float(decrypted_value)
            elif original_type == "bool":
                return decrypted_value.lower() == "true"
            else:
                return decrypted_value
            
        except Exception as e:
            logger.error("Failed to decrypt field",
                        key_id=encrypted_field.key_id,
                        error=str(e))
            raise
    
    async def _get_or_create_key(self, tenant_id: str, field_name: str) -> str:
        """Get or create encryption key for tenant and field."""
        try:
            key_id = f"{tenant_id}:{field_name}"
            
            # Check cache first
            if key_id in self.key_cache:
                key = self.key_cache[key_id]
                if key.status == KeyRotationStatus.ACTIVE:
                    return key_id
            
            # Create new key if not exists or needs rotation
            key = await self._create_encryption_key(tenant_id, field_name)
            self.key_cache[key_id] = key
            
            return key_id
            
        except Exception as e:
            logger.error("Failed to get or create key",
                        tenant_id=tenant_id,
                        field_name=field_name,
                        error=str(e))
            raise
    
    async def _create_encryption_key(self, tenant_id: str, field_name: str) -> EncryptionKey:
        """Create a new encryption key."""
        try:
            key_id = f"{tenant_id}:{field_name}"
            
            # Generate encryption key
            if self.kms_client:
                # Use KMS to generate key
                key_material = await self._generate_key_via_kms(key_id)
            else:
                # Generate key locally (for development/testing)
                key_material = Fernet.generate_key()
            
            # Create encryption key metadata
            encryption_key = EncryptionKey(
                key_id=key_id,
                algorithm=self.algorithm,
                key_version=1,
                created_at=datetime.now(timezone.utc),
                status=KeyRotationStatus.ACTIVE,
                tenant_id=tenant_id,
                field_name=field_name
            )
            
            # Store cipher in cache
            self.encryption_cache[key_id] = Fernet(key_material)
            
            # Store key metadata (in production, this would be in secure storage)
            await self._store_key_metadata(encryption_key)
            
            logger.info("Encryption key created",
                       key_id=key_id,
                       algorithm=self.algorithm.value)
            
            return encryption_key
            
        except Exception as e:
            logger.error("Failed to create encryption key",
                        tenant_id=tenant_id,
                        field_name=field_name,
                        error=str(e))
            raise
    
    async def _generate_key_via_kms(self, key_id: str) -> bytes:
        """Generate encryption key via KMS."""
        try:
            if not self.kms_client:
                raise ValueError("KMS client not configured")
            
            # Generate data encryption key (DEK)
            dek_response = await self.kms_client.generate_data_key(
                KeyId=f"alias/{key_id}",
                KeySpec="AES_256"
            )
            
            return dek_response['Plaintext']
            
        except Exception as e:
            logger.error("Failed to generate key via KMS", key_id=key_id, error=str(e))
            raise
    
    async def _get_cipher(self, key_id: str) -> Fernet:
        """Get encryption cipher for key."""
        try:
            if key_id in self.encryption_cache:
                return self.encryption_cache[key_id]
            
            # Load key from storage
            key_material = await self._load_key_material(key_id)
            cipher = Fernet(key_material)
            
            # Cache the cipher
            self.encryption_cache[key_id] = cipher
            
            return cipher
            
        except Exception as e:
            logger.error("Failed to get cipher", key_id=key_id, error=str(e))
            raise
    
    async def _load_key_material(self, key_id: str) -> bytes:
        """Load key material from secure storage."""
        try:
            if self.kms_client:
                # Decrypt key material using KMS
                response = await self.kms_client.decrypt(
                    CiphertextBlob=await self._get_encrypted_key_material(key_id)
                )
                return response['Plaintext']
            else:
                # For development/testing - generate new key
                return Fernet.generate_key()
                
        except Exception as e:
            logger.error("Failed to load key material", key_id=key_id, error=str(e))
            raise
    
    async def _get_encrypted_key_material(self, key_id: str) -> bytes:
        """Get encrypted key material from storage."""
        # In production, this would retrieve from secure key storage
        # For now, return empty bytes (will generate new key)
        return b""
    
    async def _store_key_metadata(self, key: EncryptionKey):
        """Store key metadata in secure storage."""
        try:
            # In production, this would store in secure key management system
            # For now, just log the key creation
            logger.info("Key metadata stored",
                       key_id=key.key_id,
                       algorithm=key.algorithm.value,
                       version=key.key_version)
            
        except Exception as e:
            logger.error("Failed to store key metadata", key_id=key.key_id, error=str(e))
    
    async def rotate_key(self, tenant_id: str, field_name: str) -> str:
        """Rotate encryption key for a field."""
        try:
            old_key_id = f"{tenant_id}:{field_name}"
            
            # Mark old key as rotating
            if old_key_id in self.key_cache:
                self.key_cache[old_key_id].status = KeyRotationStatus.ROTATING
            
            # Create new key
            new_key = await self._create_encryption_key(tenant_id, field_name)
            new_key_id = new_key.key_id
            
            # Update cache
            self.key_cache[new_key_id] = new_key
            
            logger.info("Key rotation initiated",
                       tenant_id=tenant_id,
                       field_name=field_name,
                       old_key_id=old_key_id,
                       new_key_id=new_key_id)
            
            return new_key_id
            
        except Exception as e:
            logger.error("Failed to rotate key",
                        tenant_id=tenant_id,
                        field_name=field_name,
                        error=str(e))
            raise
    
    async def reencrypt_with_new_key(self, encrypted_field: EncryptedField, 
                                   new_key_id: str) -> EncryptedField:
        """Re-encrypt field with new key."""
        try:
            # Decrypt with old key
            decrypted_value = await self.decrypt_field(encrypted_field)
            
            # Encrypt with new key
            new_encrypted_field = await self.encrypt_field(
                decrypted_value,
                encrypted_field.metadata["tenant_id"],
                encrypted_field.metadata["field_name"],
                new_key_id
            )
            
            logger.info("Field re-encrypted with new key",
                       old_key_id=encrypted_field.key_id,
                       new_key_id=new_key_id)
            
            return new_encrypted_field
            
        except Exception as e:
            logger.error("Failed to re-encrypt field",
                        old_key_id=encrypted_field.key_id,
                        new_key_id=new_key_id,
                        error=str(e))
            raise
    
    async def get_key_rotation_status(self, tenant_id: str, field_name: str) -> Dict[str, Any]:
        """Get key rotation status for a field."""
        try:
            key_id = f"{tenant_id}:{field_name}"
            
            if key_id not in self.key_cache:
                return {"status": "not_found"}
            
            key = self.key_cache[key_id]
            
            return {
                "key_id": key_id,
                "algorithm": key.algorithm.value,
                "version": key.key_version,
                "status": key.status.value,
                "created_at": key.created_at.isoformat(),
                "needs_rotation": self._needs_rotation(key)
            }
            
        except Exception as e:
            logger.error("Failed to get key rotation status",
                        tenant_id=tenant_id,
                        field_name=field_name,
                        error=str(e))
            return {"status": "error", "error": str(e)}
    
    def _needs_rotation(self, key: EncryptionKey) -> bool:
        """Check if key needs rotation."""
        try:
            days_since_creation = (datetime.now(timezone.utc) - key.created_at).days
            return days_since_creation >= self.key_rotation_interval
            
        except Exception as e:
            logger.error("Failed to check rotation need", key_id=key.key_id, error=str(e))
            return False
    
    async def get_encryption_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get encryption summary for tenant."""
        try:
            tenant_keys = [
                key for key in self.key_cache.values() 
                if key.tenant_id == tenant_id
            ]
            
            summary = {
                "tenant_id": tenant_id,
                "total_fields_encrypted": len(tenant_keys),
                "keys_by_status": {},
                "keys_needing_rotation": [],
                "algorithms_used": set()
            }
            
            # Count by status
            for status in KeyRotationStatus:
                count = sum(1 for key in tenant_keys if key.status == status)
                summary["keys_by_status"][status.value] = count
            
            # Find keys needing rotation
            for key in tenant_keys:
                if self._needs_rotation(key):
                    summary["keys_needing_rotation"].append({
                        "key_id": key.key_id,
                        "field_name": key.field_name,
                        "created_at": key.created_at.isoformat(),
                        "days_since_creation": (datetime.now(timezone.utc) - key.created_at).days
                    })
                
                summary["algorithms_used"].add(key.algorithm.value)
            
            summary["algorithms_used"] = list(summary["algorithms_used"])
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get encryption summary", tenant_id=tenant_id, error=str(e))
            return {"tenant_id": tenant_id, "error": str(e)}
    
    async def cleanup_deprecated_keys(self, tenant_id: str) -> int:
        """Clean up deprecated encryption keys."""
        try:
            deprecated_keys = [
                key_id for key_id, key in self.key_cache.items()
                if key.tenant_id == tenant_id and key.status == KeyRotationStatus.DEPRECATED
            ]
            
            # Remove from cache
            for key_id in deprecated_keys:
                if key_id in self.key_cache:
                    del self.key_cache[key_id]
                if key_id in self.encryption_cache:
                    del self.encryption_cache[key_id]
            
            logger.info("Deprecated keys cleaned up",
                       tenant_id=tenant_id,
                       keys_removed=len(deprecated_keys))
            
            return len(deprecated_keys)
            
        except Exception as e:
            logger.error("Failed to cleanup deprecated keys", tenant_id=tenant_id, error=str(e))
            return 0
