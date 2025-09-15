"""Image Signing Manager for container security and supply-chain integrity."""

import json
import hashlib
import subprocess
import asyncio
import tempfile
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone
from pathlib import Path

logger = structlog.get_logger(__name__)


class SigningAlgorithm(Enum):
    """Signing algorithms."""
    RSA = "rsa"
    ECDSA = "ecdsa"
    ED25519 = "ed25519"


class SignatureFormat(Enum):
    """Signature formats."""
    COSIGN = "cosign"
    DOCKER_CONTENT_TRUST = "dct"
    NOTARY = "notary"


class SignatureStatus(Enum):
    """Signature status."""
    SIGNED = "signed"
    UNSIGNED = "unsigned"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class SigningKey:
    """Signing key definition."""
    key_id: str
    algorithm: SigningAlgorithm
    public_key: str
    private_key_path: Optional[str] = None
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None


@dataclass
class ImageSignature:
    """Image signature data."""
    image_name: str
    image_digest: str
    signature: str
    signing_key_id: str
    signature_format: SignatureFormat
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None


@dataclass
class ImageManifest:
    """Image manifest data."""
    image_name: str
    image_digest: str
    manifest_digest: str
    layers: List[str]
    created_at: datetime
    size_bytes: int
    metadata: Dict[str, Any] = None


class ImageSigningManager:
    """Manages container image signing for supply-chain security."""
    
    def __init__(self):
        self.signing_keys: Dict[str, SigningKey] = {}
        self.image_signatures: Dict[str, ImageSignature] = {}
        self.image_manifests: Dict[str, ImageManifest] = {}
        self.cosign_path = "cosign"
        self.notary_path = "notary"
    
    async def generate_signing_key(self, key_id: str, algorithm: SigningAlgorithm = SigningAlgorithm.ED25519,
                                 expires_days: Optional[int] = None) -> SigningKey:
        """Generate a new signing key pair."""
        try:
            logger.info("Generating signing key",
                       key_id=key_id,
                       algorithm=algorithm.value)
            
            # Create temporary directory for key generation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Generate key pair using cosign
                if algorithm == SigningAlgorithm.ED25519:
                    await self._generate_cosign_key(key_id, temp_path)
                else:
                    await self._generate_gpg_key(key_id, algorithm, temp_path)
                
                # Read generated keys
                public_key_path = temp_path / f"{key_id}.pub"
                private_key_path = temp_path / f"{key_id}"
                
                with open(public_key_path, 'r') as f:
                    public_key = f.read()
                
                # Create signing key
                signing_key = SigningKey(
                    key_id=key_id,
                    algorithm=algorithm,
                    public_key=public_key,
                    private_key_path=str(private_key_path),
                    created_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc).replace(day=datetime.now().day + expires_days) if expires_days else None,
                    metadata={
                        "key_size": 256 if algorithm == SigningAlgorithm.ED25519 else 2048,
                        "generated_by": "ImageSigningManager"
                    }
                )
                
                # Store signing key
                self.signing_keys[key_id] = signing_key
            
            logger.info("Signing key generated successfully", key_id=key_id)
            return signing_key
            
        except Exception as e:
            logger.error("Failed to generate signing key",
                        key_id=key_id,
                        error=str(e))
            raise
    
    async def _generate_cosign_key(self, key_id: str, temp_path: Path):
        """Generate cosign key pair."""
        try:
            # Generate cosign key pair
            result = await asyncio.create_subprocess_exec(
                self.cosign_path, 'generate-key-pair',
                '--output-key-prefix', str(temp_path / key_id),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Cosign key generation failed: {stderr.decode()}")
            
            logger.info("Cosign key pair generated", key_id=key_id)
            
        except Exception as e:
            logger.error("Failed to generate cosign key", error=str(e))
            raise
    
    async def _generate_gpg_key(self, key_id: str, algorithm: SigningAlgorithm, temp_path: Path):
        """Generate GPG key pair."""
        try:
            # Create GPG batch file
            batch_file = temp_path / "gpg_batch.txt"
            with open(batch_file, 'w') as f:
                f.write(f"""Key-Type: {algorithm.value.upper()}
Key-Length: 2048
Name-Real: {key_id}
Name-Comment: Container Image Signing Key
Name-Email: {key_id}@platform.local
Expire-Date: 0
%no-protection
%commit
""")
            
            # Generate GPG key
            result = await asyncio.create_subprocess_exec(
                'gpg', '--batch', '--generate-key', str(batch_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"GPG key generation failed: {stderr.decode()}")
            
            # Export public key
            pub_result = await asyncio.create_subprocess_exec(
                'gpg', '--armor', '--export', key_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            pub_stdout, pub_stderr = await pub_result.communicate()
            
            if pub_result.returncode != 0:
                raise Exception(f"GPG public key export failed: {pub_stderr.decode()}")
            
            # Save public key
            public_key_path = temp_path / f"{key_id}.pub"
            with open(public_key_path, 'wb') as f:
                f.write(pub_stdout)
            
            logger.info("GPG key pair generated", key_id=key_id)
            
        except Exception as e:
            logger.error("Failed to generate GPG key", error=str(e))
            raise
    
    async def sign_image(self, image_name: str, signing_key_id: str,
                        signature_format: SignatureFormat = SignatureFormat.COSIGN,
                        metadata: Optional[Dict[str, Any]] = None) -> ImageSignature:
        """Sign a container image."""
        try:
            logger.info("Signing image",
                       image_name=image_name,
                       signing_key_id=signing_key_id,
                       signature_format=signature_format.value)
            
            # Check if signing key exists
            if signing_key_id not in self.signing_keys:
                raise ValueError(f"Signing key {signing_key_id} not found")
            
            signing_key = self.signing_keys[signing_key_id]
            
            # Get image manifest
            image_manifest = await self._get_image_manifest(image_name)
            
            # Sign image based on format
            if signature_format == SignatureFormat.COSIGN:
                signature = await self._sign_with_cosign(image_name, signing_key)
            elif signature_format == SignatureFormat.DOCKER_CONTENT_TRUST:
                signature = await self._sign_with_docker_content_trust(image_name, signing_key)
            elif signature_format == SignatureFormat.NOTARY:
                signature = await self._sign_with_notary(image_name, signing_key)
            else:
                raise ValueError(f"Unsupported signature format: {signature_format}")
            
            # Create image signature
            image_signature = ImageSignature(
                image_name=image_name,
                image_digest=image_manifest.image_digest,
                signature=signature,
                signing_key_id=signing_key_id,
                signature_format=signature_format,
                created_at=datetime.now(timezone.utc),
                expires_at=signing_key.expires_at,
                metadata=metadata or {}
            )
            
            # Store signature
            signature_id = f"{image_name}@{image_manifest.image_digest}"
            self.image_signatures[signature_id] = image_signature
            
            logger.info("Image signed successfully",
                       image_name=image_name,
                       signature_id=signature_id)
            
            return image_signature
            
        except Exception as e:
            logger.error("Failed to sign image",
                        image_name=image_name,
                        error=str(e))
            raise
    
    async def _get_image_manifest(self, image_name: str) -> ImageManifest:
        """Get image manifest information."""
        try:
            # In production, this would use docker or containerd APIs
            # For this implementation, we'll simulate manifest retrieval
            
            # Simulate image digest calculation
            image_digest = hashlib.sha256(image_name.encode()).hexdigest()
            manifest_digest = hashlib.sha256(f"{image_name}:manifest".encode()).hexdigest()
            
            # Simulate layers
            layers = [
                f"sha256:{hashlib.sha256(f'{image_name}:layer{i}'.encode()).hexdigest()}"
                for i in range(3)
            ]
            
            manifest = ImageManifest(
                image_name=image_name,
                image_digest=image_digest,
                manifest_digest=manifest_digest,
                layers=layers,
                created_at=datetime.now(timezone.utc),
                size_bytes=1024 * 1024 * 100,  # 100MB
                metadata={
                    "platform": "linux/amd64",
                    "architecture": "amd64",
                    "os": "linux"
                }
            )
            
            # Store manifest
            self.image_manifests[image_name] = manifest
            
            return manifest
            
        except Exception as e:
            logger.error("Failed to get image manifest", error=str(e))
            raise
    
    async def _sign_with_cosign(self, image_name: str, signing_key: SigningKey) -> str:
        """Sign image with cosign."""
        try:
            # In production, this would use cosign CLI or library
            # For this implementation, we'll simulate cosign signing
            
            # Simulate cosign signature generation
            signature_data = f"cosign_signature:{image_name}:{signing_key.key_id}:{datetime.now().isoformat()}"
            signature = hashlib.sha256(signature_data.encode()).hexdigest()
            
            logger.info("Image signed with cosign", image_name=image_name)
            return signature
            
        except Exception as e:
            logger.error("Failed to sign with cosign", error=str(e))
            raise
    
    async def _sign_with_docker_content_trust(self, image_name: str, signing_key: SigningKey) -> str:
        """Sign image with Docker Content Trust."""
        try:
            # In production, this would use Docker Content Trust
            # For this implementation, we'll simulate DCT signing
            
            # Simulate DCT signature generation
            signature_data = f"dct_signature:{image_name}:{signing_key.key_id}:{datetime.now().isoformat()}"
            signature = hashlib.sha256(signature_data.encode()).hexdigest()
            
            logger.info("Image signed with Docker Content Trust", image_name=image_name)
            return signature
            
        except Exception as e:
            logger.error("Failed to sign with Docker Content Trust", error=str(e))
            raise
    
    async def _sign_with_notary(self, image_name: str, signing_key: SigningKey) -> str:
        """Sign image with Notary."""
        try:
            # In production, this would use Notary
            # For this implementation, we'll simulate Notary signing
            
            # Simulate Notary signature generation
            signature_data = f"notary_signature:{image_name}:{signing_key.key_id}:{datetime.now().isoformat()}"
            signature = hashlib.sha256(signature_data.encode()).hexdigest()
            
            logger.info("Image signed with Notary", image_name=image_name)
            return signature
            
        except Exception as e:
            logger.error("Failed to sign with Notary", error=str(e))
            raise
    
    async def verify_image_signature(self, image_name: str, signature_id: Optional[str] = None) -> Tuple[SignatureStatus, Optional[ImageSignature]]:
        """Verify image signature."""
        try:
            logger.info("Verifying image signature", image_name=image_name)
            
            # Find signature
            if signature_id:
                signature = self.image_signatures.get(signature_id)
            else:
                # Find latest signature for image
                signatures = [s for s in self.image_signatures.values() if s.image_name == image_name]
                if not signatures:
                    return SignatureStatus.UNSIGNED, None
                
                signature = max(signatures, key=lambda s: s.created_at)
            
            if not signature:
                return SignatureStatus.UNSIGNED, None
            
            # Check if signature is expired
            if signature.expires_at and signature.expires_at < datetime.now(timezone.utc):
                return SignatureStatus.EXPIRED, signature
            
            # Verify signature based on format
            if signature.signature_format == SignatureFormat.COSIGN:
                is_valid = await self._verify_cosign_signature(image_name, signature)
            elif signature.signature_format == SignatureFormat.DOCKER_CONTENT_TRUST:
                is_valid = await self._verify_docker_content_trust_signature(image_name, signature)
            elif signature.signature_format == SignatureFormat.NOTARY:
                is_valid = await self._verify_notary_signature(image_name, signature)
            else:
                return SignatureStatus.INVALID, signature
            
            if is_valid:
                return SignatureStatus.SIGNED, signature
            else:
                return SignatureStatus.INVALID, signature
            
        except Exception as e:
            logger.error("Failed to verify image signature", error=str(e))
            return SignatureStatus.INVALID, None
    
    async def _verify_cosign_signature(self, image_name: str, signature: ImageSignature) -> bool:
        """Verify cosign signature."""
        try:
            # In production, this would use cosign verification
            # For this implementation, we'll simulate verification
            
            # Simulate cosign verification
            logger.info("Verifying cosign signature", image_name=image_name)
            return True  # Simulate successful verification
            
        except Exception as e:
            logger.error("Failed to verify cosign signature", error=str(e))
            return False
    
    async def _verify_docker_content_trust_signature(self, image_name: str, signature: ImageSignature) -> bool:
        """Verify Docker Content Trust signature."""
        try:
            # In production, this would use DCT verification
            # For this implementation, we'll simulate verification
            
            logger.info("Verifying Docker Content Trust signature", image_name=image_name)
            return True  # Simulate successful verification
            
        except Exception as e:
            logger.error("Failed to verify Docker Content Trust signature", error=str(e))
            return False
    
    async def _verify_notary_signature(self, image_name: str, signature: ImageSignature) -> bool:
        """Verify Notary signature."""
        try:
            # In production, this would use Notary verification
            # For this implementation, we'll simulate verification
            
            logger.info("Verifying Notary signature", image_name=image_name)
            return True  # Simulate successful verification
            
        except Exception as e:
            logger.error("Failed to verify Notary signature", error=str(e))
            return False
    
    async def revoke_signature(self, signature_id: str, reason: str = "Manual revocation") -> bool:
        """Revoke an image signature."""
        try:
            logger.info("Revoking signature", signature_id=signature_id)
            
            if signature_id not in self.image_signatures:
                logger.error("Signature not found", signature_id=signature_id)
                return False
            
            signature = self.image_signatures[signature_id]
            
            # Mark signature as revoked
            signature.metadata = signature.metadata or {}
            signature.metadata["revoked"] = True
            signature.metadata["revocation_reason"] = reason
            signature.metadata["revoked_at"] = datetime.now(timezone.utc).isoformat()
            
            logger.info("Signature revoked successfully", signature_id=signature_id)
            return True
            
        except Exception as e:
            logger.error("Failed to revoke signature", error=str(e))
            return False
    
    async def get_image_signatures(self, image_name: str) -> List[ImageSignature]:
        """Get all signatures for an image."""
        try:
            signatures = [
                signature for signature in self.image_signatures.values()
                if signature.image_name == image_name
            ]
            
            # Sort by creation date (newest first)
            signatures.sort(key=lambda s: s.created_at, reverse=True)
            
            return signatures
            
        except Exception as e:
            logger.error("Failed to get image signatures", error=str(e))
            return []
    
    async def get_signing_keys(self) -> List[SigningKey]:
        """Get all signing keys."""
        try:
            return list(self.signing_keys.values())
            
        except Exception as e:
            logger.error("Failed to get signing keys", error=str(e))
            return []
    
    async def export_signing_key(self, key_id: str, output_path: str) -> bool:
        """Export signing key to file."""
        try:
            if key_id not in self.signing_keys:
                logger.error("Signing key not found", key_id=key_id)
                return False
            
            signing_key = self.signing_keys[key_id]
            
            # Export public key
            with open(output_path, 'w') as f:
                f.write(signing_key.public_key)
            
            logger.info("Signing key exported", key_id=key_id, output_path=output_path)
            return True
            
        except Exception as e:
            logger.error("Failed to export signing key", error=str(e))
            return False
    
    async def import_signing_key(self, key_id: str, public_key: str, algorithm: SigningAlgorithm) -> bool:
        """Import signing key from public key."""
        try:
            signing_key = SigningKey(
                key_id=key_id,
                algorithm=algorithm,
                public_key=public_key,
                created_at=datetime.now(timezone.utc),
                metadata={
                    "imported": True,
                    "imported_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            self.signing_keys[key_id] = signing_key
            
            logger.info("Signing key imported", key_id=key_id)
            return True
            
        except Exception as e:
            logger.error("Failed to import signing key", error=str(e))
            return False
    
    async def get_signing_statistics(self) -> Dict[str, Any]:
        """Get signing statistics."""
        try:
            total_signatures = len(self.image_signatures)
            signed_images = len(set(s.image_name for s in self.image_signatures.values()))
            
            # Count signatures by format
            signatures_by_format = {}
            for signature in self.image_signatures.values():
                format_name = signature.signature_format.value
                signatures_by_format[format_name] = signatures_by_format.get(format_name, 0) + 1
            
            # Count signatures by key
            signatures_by_key = {}
            for signature in self.image_signatures.values():
                key_id = signature.signing_key_id
                signatures_by_key[key_id] = signatures_by_key.get(key_id, 0) + 1
            
            return {
                "total_signatures": total_signatures,
                "signed_images": signed_images,
                "total_signing_keys": len(self.signing_keys),
                "signatures_by_format": signatures_by_format,
                "signatures_by_key": signatures_by_key,
                "signing_algorithms": [key.algorithm.value for key in self.signing_keys.values()]
            }
            
        except Exception as e:
            logger.error("Failed to get signing statistics", error=str(e))
            return {}
