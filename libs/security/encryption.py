"""Encryption and hashing utilities."""

import base64
import hashlib
import hmac
import secrets
from typing import Dict, Any, Optional, Union
import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt", "argon2"],
    deprecated="auto",
    bcrypt__rounds=12,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
    argon2__time_cost=3
)


class EncryptionManager:
    """Encryption manager for sensitive data."""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or self._generate_master_key()
        self.fernet = self._create_fernet()
    
    def _generate_master_key(self) -> str:
        """Generate master encryption key."""
        return Fernet.generate_key().decode()
    
    def _create_fernet(self) -> Fernet:
        """Create Fernet encryption instance."""
        return Fernet(self.master_key.encode())
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """Encrypt data."""
        if isinstance(data, str):
            data = data.encode()
        
        encrypted_data = self.fernet.encrypt(data)
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Encrypt dictionary values."""
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                encrypted[key] = self.encrypt(str(value))
            else:
                encrypted[key] = str(value)
        return encrypted
    
    def decrypt_dict(self, encrypted_data: Dict[str, str]) -> Dict[str, Any]:
        """Decrypt dictionary values."""
        decrypted = {}
        for key, value in encrypted_data.items():
            try:
                decrypted[key] = self.decrypt(value)
            except ValueError:
                # If decryption fails, keep original value
                decrypted[key] = value
        return decrypted


class HashManager:
    """Hash management for passwords and data integrity."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def hash_data(data: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash data with salt."""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Use PBKDF2 for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        key = base64.b64encode(kdf.derive(data.encode()))
        
        return key.decode(), salt
    
    @staticmethod
    def verify_hash(data: str, hashed_data: str, salt: str) -> bool:
        """Verify data against hash."""
        try:
            computed_hash, _ = HashManager.hash_data(data, salt)
            return hmac.compare_digest(computed_hash, hashed_data)
        except Exception:
            return False
    
    @staticmethod
    def generate_hmac(data: str, secret: str) -> str:
        """Generate HMAC for data integrity."""
        return hmac.new(
            secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_hmac(data: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature."""
        expected_signature = HashManager.generate_hmac(data, secret)
        return hmac.compare_digest(signature, expected_signature)


class TokenManager:
    """Token generation and validation."""
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate session token."""
        return secrets.token_urlsafe(48)
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate password reset token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generate email verification token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()


class DataMasking:
    """Data masking utilities for sensitive information."""
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address."""
        if "@" not in email:
            return email
        
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone number."""
        if len(phone) <= 4:
            return "*" * len(phone)
        
        return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]
    
    @staticmethod
    def mask_credit_card(card_number: str) -> str:
        """Mask credit card number."""
        if len(card_number) <= 4:
            return "*" * len(card_number)
        
        return "*" * (len(card_number) - 4) + card_number[-4:]
    
    @staticmethod
    def mask_ssn(ssn: str) -> str:
        """Mask Social Security Number."""
        if len(ssn) != 9:
            return "*" * len(ssn)
        
        return "***-**-" + ssn[-4:]


# Global instances
encryption_manager = EncryptionManager()
hash_manager = HashManager()
token_manager = TokenManager()
data_masking = DataMasking()


# Convenience functions
def encrypt_sensitive_data(data: Union[str, bytes]) -> str:
    """Encrypt sensitive data."""
    return encryption_manager.encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return encryption_manager.decrypt(encrypted_data)


def hash_password(password: str) -> str:
    """Hash password."""
    return hash_manager.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password."""
    return hash_manager.verify_password(plain_password, hashed_password)
