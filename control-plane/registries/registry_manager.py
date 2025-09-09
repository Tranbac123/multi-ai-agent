"""Registry manager for signed manifests."""

import hashlib
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from uuid import UUID, uuid4
import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

logger = structlog.get_logger(__name__)


class Manifest:
    """Signed manifest for registry items."""
    
    def __init__(
        self,
        name: str,
        version: str,
        checksum_sha256: str,
        created_at: datetime,
        owner: str,
        changelog: str,
        deprecated: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        signature: Optional[str] = None
    ):
        self.name = name
        self.version = version
        self.checksum_sha256 = checksum_sha256
        self.created_at = created_at
        self.owner = owner
        self.changelog = changelog
        self.deprecated = deprecated
        self.metadata = metadata or {}
        self.signature = signature
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "checksum_sha256": self.checksum_sha256,
            "created_at": self.created_at.isoformat(),
            "owner": self.owner,
            "changelog": self.changelog,
            "deprecated": self.deprecated,
            "metadata": self.metadata,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            version=data["version"],
            checksum_sha256=data["checksum_sha256"],
            created_at=datetime.fromisoformat(data["created_at"]),
            owner=data["owner"],
            changelog=data["changelog"],
            deprecated=data.get("deprecated", False),
            metadata=data.get("metadata", {}),
            signature=data.get("signature")
        )


class RegistryManager:
    """Manages signed manifests for agents, tools, prompts, and models."""
    
    def __init__(self, registry_path: Path, private_key_path: Optional[Path] = None):
        self.registry_path = registry_path
        self.private_key_path = private_key_path
        self.private_key = None
        self.public_key = None
        
        if private_key_path and private_key_path.exists():
            self._load_keys()
    
    def _load_keys(self):
        """Load private and public keys."""
        try:
            with open(self.private_key_path, "rb") as f:
                self.private_key = load_pem_private_key(f.read(), password=None)
            
            # Extract public key
            self.public_key = self.private_key.public_key()
            logger.info("Keys loaded successfully")
        except Exception as e:
            logger.error("Failed to load keys", error=str(e))
    
    def generate_keys(self, key_path: Path):
        """Generate new RSA key pair."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Save private key
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Save public key
        public_key_path = key_path.with_suffix('.pub')
        with open(public_key_path, "wb") as f:
            f.write(private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
        
        logger.info("Keys generated", private_key_path=str(key_path), public_key_path=str(public_key_path))
    
    def calculate_checksum(self, content: Union[str, bytes]) -> str:
        """Calculate SHA256 checksum of content."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha256(content).hexdigest()
    
    def sign_manifest(self, manifest: Manifest) -> str:
        """Sign manifest with private key."""
        if not self.private_key:
            raise ValueError("Private key not loaded")
        
        # Create signature data (exclude signature field)
        manifest_dict = manifest.to_dict()
        del manifest_dict["signature"]
        signature_data = json.dumps(manifest_dict, sort_keys=True).encode('utf-8')
        
        # Sign data
        signature = self.private_key.sign(
            signature_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature.hex()
    
    def verify_manifest(self, manifest: Manifest) -> bool:
        """Verify manifest signature."""
        if not self.public_key or not manifest.signature:
            return False
        
        try:
            # Recreate signature data
            manifest_dict = manifest.to_dict()
            del manifest_dict["signature"]
            signature_data = json.dumps(manifest_dict, sort_keys=True).encode('utf-8')
            
            # Verify signature
            signature_bytes = bytes.fromhex(manifest.signature)
            self.public_key.verify(
                signature_bytes,
                signature_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.warning("Manifest verification failed", error=str(e))
            return False
    
    def create_manifest(
        self,
        name: str,
        version: str,
        content: Union[str, bytes],
        owner: str,
        changelog: str,
        deprecated: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Manifest:
        """Create and sign a new manifest."""
        checksum = self.calculate_checksum(content)
        
        manifest = Manifest(
            name=name,
            version=version,
            checksum_sha256=checksum,
            created_at=datetime.utcnow(),
            owner=owner,
            changelog=changelog,
            deprecated=deprecated,
            metadata=metadata or {}
        )
        
        if self.private_key:
            manifest.signature = self.sign_manifest(manifest)
        
        return manifest
    
    def save_manifest(self, manifest: Manifest, registry_type: str) -> bool:
        """Save manifest to registry."""
        try:
            registry_dir = self.registry_path / registry_type
            registry_dir.mkdir(parents=True, exist_ok=True)
            
            manifest_file = registry_dir / f"{manifest.name}_{manifest.version}.yaml"
            
            with open(manifest_file, 'w') as f:
                yaml.dump(manifest.to_dict(), f, default_flow_style=False)
            
            logger.info("Manifest saved", 
                       name=manifest.name, 
                       version=manifest.version,
                       registry_type=registry_type)
            return True
            
        except Exception as e:
            logger.error("Failed to save manifest", error=str(e))
            return False
    
    def load_manifest(self, registry_type: str, name: str, version: str) -> Optional[Manifest]:
        """Load manifest from registry."""
        try:
            manifest_file = self.registry_path / registry_type / f"{name}_{version}.yaml"
            
            if not manifest_file.exists():
                return None
            
            with open(manifest_file, 'r') as f:
                data = yaml.safe_load(f)
            
            return Manifest.from_dict(data)
            
        except Exception as e:
            logger.error("Failed to load manifest", error=str(e))
            return None
    
    def list_manifests(self, registry_type: str) -> List[Manifest]:
        """List all manifests in registry type."""
        manifests = []
        registry_dir = self.registry_path / registry_type
        
        if not registry_dir.exists():
            return manifests
        
        for manifest_file in registry_dir.glob("*.yaml"):
            try:
                with open(manifest_file, 'r') as f:
                    data = yaml.safe_load(f)
                manifests.append(Manifest.from_dict(data))
            except Exception as e:
                logger.warning("Failed to load manifest file", 
                              file=str(manifest_file), 
                              error=str(e))
        
        return manifests
    
    def validate_content(self, manifest: Manifest, content: Union[str, bytes]) -> bool:
        """Validate content against manifest checksum."""
        expected_checksum = manifest.checksum_sha256
        actual_checksum = self.calculate_checksum(content)
        return expected_checksum == actual_checksum
