"""
Multi-Factor Authentication (MFA) implementation for enterprise security.
Supports TOTP (Time-based One-Time Password) and SMS-based MFA.
"""

import pyotp
import qrcode
import io
import base64
import json
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from .database import User, MFADevice
from datetime import datetime, timedelta
import logging
import secrets
import hashlib

logger = logging.getLogger(__name__)

class MFAManager:
    """Multi-Factor Authentication manager."""
    
    def __init__(self, db_session: Session):
        """Initialize MFA manager with database session."""
        self.db = db_session
        self.app_name = "Enterprise Knowledge Base"
    
    def enable_totp_for_user(self, user_id: str) -> Dict[str, Any]:
        """
        Enable TOTP for a user and return setup information.
        
        Args:
            user_id: User ID to enable TOTP for
            
        Returns:
            Dict[str, Any]: Setup information including QR code and backup codes
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Generate secret key
        secret = pyotp.random_base32()
        
        # Create TOTP URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email or user.username,
            issuer_name=self.app_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Convert QR code to base64 string
        qr_img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_code_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Generate backup codes
        backup_codes = [secrets.token_hex(8) for _ in range(10)]
        
        # Store MFA device configuration
        mfa_device = MFADevice(
            user_id=user_id,
            device_type="totp",
            secret=secret,
            backup_codes=json.dumps([hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]),
            is_verified=False,
            created_at=datetime.utcnow()
        )
        
        self.db.add(mfa_device)
        self.db.commit()
        
        logger.info(f"TOTP setup initiated for user {user.username}")
        
        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_code_b64}",
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
            "device_id": mfa_device.id
        }
    
    def verify_totp_setup(self, user_id: str, device_id: str, token: str) -> bool:
        """
        Verify TOTP setup with initial token.
        
        Args:
            user_id: User ID
            device_id: MFA device ID
            token: TOTP token to verify
            
        Returns:
            bool: True if verification successful
        """
        device = self.db.query(MFADevice).filter(
            MFADevice.id == device_id,
            MFADevice.user_id == user_id,
            MFADevice.device_type == "totp"
        ).first()
        
        if not device:
            return False
        
        totp = pyotp.TOTP(device.secret)
        
        if totp.verify(token, valid_window=2):  # Allow 2 time windows (60 seconds)
            device.is_verified = True
            device.verified_at = datetime.utcnow()
            self.db.commit()
            
            user = self.db.query(User).filter(User.id == user_id).first()
            logger.info(f"TOTP setup completed for user {user.username}")
            
            return True
        
        return False
    
    def verify_totp_token(self, user_id: str, token: str) -> bool:
        """
        Verify TOTP token for login.
        
        Args:
            user_id: User ID
            token: TOTP token to verify
            
        Returns:
            bool: True if token is valid
        """
        device = self.db.query(MFADevice).filter(
            MFADevice.user_id == user_id,
            MFADevice.device_type == "totp",
            MFADevice.is_verified == True
        ).first()
        
        if not device:
            return False
        
        totp = pyotp.TOTP(device.secret)
        
        if totp.verify(token, valid_window=1):
            device.last_used = datetime.utcnow()
            self.db.commit()
            return True
        
        return False
    
    def verify_backup_code(self, user_id: str, backup_code: str) -> bool:
        """
        Verify backup code and invalidate it after use.
        
        Args:
            user_id: User ID
            backup_code: Backup code to verify
            
        Returns:
            bool: True if backup code is valid
        """
        device = self.db.query(MFADevice).filter(
            MFADevice.user_id == user_id,
            MFADevice.device_type == "totp",
            MFADevice.is_verified == True
        ).first()
        
        if not device:
            return False
        
        # Hash the provided backup code
        code_hash = hashlib.sha256(backup_code.encode()).hexdigest()
        
        # Load backup codes
        backup_codes = json.loads(device.backup_codes)
        
        if code_hash in backup_codes:
            # Remove used backup code
            backup_codes.remove(code_hash)
            device.backup_codes = json.dumps(backup_codes)
            device.last_used = datetime.utcnow()
            self.db.commit()
            
            user = self.db.query(User).filter(User.id == user_id).first()
            logger.warning(f"Backup code used for user {user.username}")
            
            return True
        
        return False
    
    def disable_mfa_for_user(self, user_id: str) -> bool:
        """
        Disable MFA for a user.
        
        Args:
            user_id: User ID to disable MFA for
            
        Returns:
            bool: True if MFA was disabled
        """
        devices = self.db.query(MFADevice).filter(MFADevice.user_id == user_id).all()
        
        for device in devices:
            self.db.delete(device)
        
        self.db.commit()
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            logger.info(f"MFA disabled for user {user.username}")
        
        return len(devices) > 0
    
    def get_user_mfa_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get MFA status for a user.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Dict[str, Any]: MFA status information
        """
        device = self.db.query(MFADevice).filter(
            MFADevice.user_id == user_id,
            MFADevice.is_verified == True
        ).first()
        
        if device:
            backup_codes = json.loads(device.backup_codes) if device.backup_codes else []
            return {
                "enabled": True,
                "device_type": device.device_type,
                "verified_at": device.verified_at,
                "last_used": device.last_used,
                "backup_codes_remaining": len(backup_codes)
            }
        else:
            return {"enabled": False}
    
    def regenerate_backup_codes(self, user_id: str) -> Optional[list]:
        """
        Regenerate backup codes for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Optional[list]: New backup codes or None if MFA not enabled
        """
        device = self.db.query(MFADevice).filter(
            MFADevice.user_id == user_id,
            MFADevice.device_type == "totp",
            MFADevice.is_verified == True
        ).first()
        
        if not device:
            return None
        
        # Generate new backup codes
        backup_codes = [secrets.token_hex(8) for _ in range(10)]
        device.backup_codes = json.dumps([hashlib.sha256(code.encode()).hexdigest() for code in backup_codes])
        self.db.commit()
        
        user = self.db.query(User).filter(User.id == user_id).first()
        logger.info(f"Backup codes regenerated for user {user.username}")
        
        return backup_codes

class SessionManager:
    """Enhanced session management with security features."""
    
    def __init__(self, db_session: Session):
        """Initialize session manager."""
        self.db = db_session
        self.max_sessions_per_user = 5
        self.session_timeout_minutes = int(os.getenv("SESSION_TIMEOUT_MINUTES", "480"))  # 8 hours default
        self.max_idle_minutes = int(os.getenv("MAX_IDLE_MINUTES", "60"))  # 1 hour idle timeout
    
    def create_session(self, user_id: str, ip_address: str, user_agent: str) -> str:
        """
        Create a new user session with security tracking.
        
        Args:
            user_id: User ID
            ip_address: Client IP address
            user_agent: Client user agent string
            
        Returns:
            str: Session token
        """
        from .database import UserSession
        
        # Check for existing sessions and limit
        existing_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(UserSession.created_at.desc()).all()
        
        # Remove old sessions if at limit
        if len(existing_sessions) >= self.max_sessions_per_user:
            sessions_to_remove = existing_sessions[self.max_sessions_per_user-1:]
            for session in sessions_to_remove:
                session.is_active = False
                session.ended_at = datetime.utcnow()
        
        # Create new session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=self.session_timeout_minutes)
        
        session = UserSession(
            user_id=user_id,
            session_token=hashlib.sha256(session_token.encode()).hexdigest(),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            last_activity=datetime.utcnow(),
            is_active=True
        )
        
        self.db.add(session)
        self.db.commit()
        
        logger.info(f"New session created for user {user_id} from IP {ip_address}")
        
        return session_token
    
    def validate_session(self, session_token: str) -> Optional[str]:
        """
        Validate session token and update activity.
        
        Args:
            session_token: Session token to validate
            
        Returns:
            Optional[str]: User ID if session is valid, None otherwise
        """
        from .database import UserSession
        
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        session = self.db.query(UserSession).filter(
            UserSession.session_token == token_hash,
            UserSession.is_active == True
        ).first()
        
        if not session:
            return None
        
        now = datetime.utcnow()
        
        # Check if session expired
        if session.expires_at < now:
            session.is_active = False
            session.ended_at = now
            self.db.commit()
            return None
        
        # Check idle timeout
        if session.last_activity and (now - session.last_activity).total_seconds() > (self.max_idle_minutes * 60):
            session.is_active = False
            session.ended_at = now
            self.db.commit()
            logger.info(f"Session expired due to inactivity for user {session.user_id}")
            return None
        
        # Update last activity
        session.last_activity = now
        self.db.commit()
        
        return session.user_id
    
    def revoke_session(self, session_token: str) -> bool:
        """
        Revoke a specific session.
        
        Args:
            session_token: Session token to revoke
            
        Returns:
            bool: True if session was revoked
        """
        from .database import UserSession
        
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        
        session = self.db.query(UserSession).filter(
            UserSession.session_token == token_hash,
            UserSession.is_active == True
        ).first()
        
        if session:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Session revoked for user {session.user_id}")
            return True
        
        return False
    
    def revoke_all_user_sessions(self, user_id: str) -> int:
        """
        Revoke all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            int: Number of sessions revoked
        """
        from .database import UserSession
        
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).all()
        
        count = 0
        for session in sessions:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            count += 1
        
        self.db.commit()
        logger.info(f"All sessions revoked for user {user_id} (count: {count})")
        
        return count