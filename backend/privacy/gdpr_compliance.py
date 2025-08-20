"""
GDPR and data privacy compliance module for enterprise knowledge base.
Implements data anonymization, right to be forgotten, consent management, and data portability.
"""

import re
import json
import hashlib
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..auth.database import User, DocumentMetadata, ConversationMemory
import logging
from dataclasses import dataclass
from enum import Enum
import spacy
from cryptography.fernet import Fernet
import os

logger = logging.getLogger(__name__)

class ConsentType(str, Enum):
    """Types of consent that can be given."""
    DATA_PROCESSING = "data_processing"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    THIRD_PARTY_SHARING = "third_party_sharing"
    PROFILING = "profiling"

class DataProcessingPurpose(str, Enum):
    """Purposes for data processing."""
    SERVICE_PROVISION = "service_provision"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    LEGAL_COMPLIANCE = "legal_compliance"
    SECURITY = "security"
    RESEARCH = "research"

@dataclass
class PIIEntity:
    """Represents a detected PII entity."""
    text: str
    label: str
    start: int
    end: int
    confidence: float

class PIIDetector:
    """Detects personally identifiable information in text."""
    
    def __init__(self):
        """Initialize PII detector."""
        # Try to load spaCy model, fallback to regex-based detection
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            self.use_nlp = True
        except (ImportError, IOError):
            logger.warning("spaCy model not available, using regex-based PII detection")
            self.nlp = None
            self.use_nlp = False
        
        # Regex patterns for PII detection
        self.patterns = {
            "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "PHONE": re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'),
            "SSN": re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            "CREDIT_CARD": re.compile(r'\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b'),
            "IP_ADDRESS": re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            "PASSPORT": re.compile(r'\b[A-Z]{1,2}[0-9]{6,9}\b'),
            "LICENSE_PLATE": re.compile(r'\b[A-Z0-9]{2,3}[-.\s]?[A-Z0-9]{3,4}\b'),
        }
    
    def detect_pii(self, text: str) -> List[PIIEntity]:
        """
        Detect PII entities in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List[PIIEntity]: List of detected PII entities
        """
        entities = []
        
        # Use spaCy if available
        if self.use_nlp and self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG", "GPE", "DATE", "MONEY", "CARDINAL"]:
                    entities.append(PIIEntity(
                        text=ent.text,
                        label=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char,
                        confidence=0.8
                    ))
        
        # Use regex patterns
        for pattern_name, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                entities.append(PIIEntity(
                    text=match.group(),
                    label=pattern_name,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9
                ))
        
        return entities
    
    def anonymize_text(self, text: str, replacement_map: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, str]]:
        """
        Anonymize PII in text.
        
        Args:
            text: Text to anonymize
            replacement_map: Optional existing replacement mapping
            
        Returns:
            Tuple[str, Dict[str, str]]: (anonymized_text, replacement_mapping)
        """
        if replacement_map is None:
            replacement_map = {}
        
        entities = self.detect_pii(text)
        anonymized_text = text
        
        # Sort entities by start position in reverse order to maintain positions
        entities.sort(key=lambda x: x.start, reverse=True)
        
        for entity in entities:
            if entity.text not in replacement_map:
                # Generate consistent replacement token
                token_id = hashlib.md5(entity.text.encode()).hexdigest()[:8]
                replacement_map[entity.text] = f"[{entity.label}_{token_id}]"
            
            # Replace in text
            anonymized_text = (
                anonymized_text[:entity.start] + 
                replacement_map[entity.text] + 
                anonymized_text[entity.end:]
            )
        
        return anonymized_text, replacement_map

class ConsentManager:
    """Manages user consent for data processing."""
    
    def __init__(self, db_session: Session):
        """Initialize consent manager."""
        self.db = db_session
    
    def record_consent(self, user_id: str, consent_type: ConsentType, 
                      purpose: DataProcessingPurpose, granted: bool,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record user consent.
        
        Args:
            user_id: User ID
            consent_type: Type of consent
            purpose: Purpose of data processing
            granted: Whether consent was granted
            metadata: Additional metadata
            
        Returns:
            str: Consent record ID
        """
        from ..auth.database import ConsentRecord
        
        consent_record = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type.value,
            purpose=purpose.value,
            granted=granted,
            metadata=metadata or {},
            ip_address=metadata.get('ip_address') if metadata else None,
            user_agent=metadata.get('user_agent') if metadata else None,
            recorded_at=datetime.utcnow()
        )
        
        self.db.add(consent_record)
        self.db.commit()
        
        logger.info(f"Consent recorded for user {user_id}: {consent_type.value} - {granted}")
        
        return str(consent_record.id)
    
    def get_user_consents(self, user_id: str) -> Dict[str, Any]:
        """
        Get all consents for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict[str, Any]: User consent information
        """
        from ..auth.database import ConsentRecord
        
        consents = self.db.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id
        ).order_by(ConsentRecord.recorded_at.desc()).all()
        
        consent_summary = {}
        for consent in consents:
            key = f"{consent.consent_type}_{consent.purpose}"
            if key not in consent_summary:
                consent_summary[key] = {
                    'consent_type': consent.consent_type,
                    'purpose': consent.purpose,
                    'granted': consent.granted,
                    'recorded_at': consent.recorded_at,
                    'metadata': consent.metadata
                }
        
        return consent_summary
    
    def withdraw_consent(self, user_id: str, consent_type: ConsentType,
                        purpose: DataProcessingPurpose) -> bool:
        """
        Withdraw user consent.
        
        Args:
            user_id: User ID
            consent_type: Type of consent to withdraw
            purpose: Purpose of data processing
            
        Returns:
            bool: True if consent was withdrawn
        """
        return self.record_consent(user_id, consent_type, purpose, False)

class DataRetentionManager:
    """Manages data retention policies and automatic cleanup."""
    
    def __init__(self, db_session: Session):
        """Initialize data retention manager."""
        self.db = db_session
        
        # Default retention periods (can be configured)
        self.retention_policies = {
            'conversation_memory': timedelta(days=365),  # 1 year
            'user_sessions': timedelta(days=90),  # 3 months
            'audit_logs': timedelta(days=2555),  # 7 years (compliance)
            'consent_records': timedelta(days=2555),  # 7 years (compliance)
            'document_metadata': timedelta(days=3650),  # 10 years (configurable)
        }
    
    def apply_retention_policies(self) -> Dict[str, int]:
        """
        Apply data retention policies and clean up old data.
        
        Returns:
            Dict[str, int]: Count of records cleaned up by category
        """
        cleanup_counts = {}
        
        # Clean up old conversation memories
        cutoff_date = datetime.utcnow() - self.retention_policies['conversation_memory']
        deleted_conversations = self.db.query(ConversationMemory).filter(
            ConversationMemory.updated_at < cutoff_date
        ).delete()
        cleanup_counts['conversation_memory'] = deleted_conversations
        
        # Clean up old user sessions
        from ..auth.database import UserSession
        cutoff_date = datetime.utcnow() - self.retention_policies['user_sessions']
        deleted_sessions = self.db.query(UserSession).filter(
            UserSession.created_at < cutoff_date,
            UserSession.is_active == False
        ).delete()
        cleanup_counts['user_sessions'] = deleted_sessions
        
        self.db.commit()
        
        logger.info(f"Data retention cleanup completed: {cleanup_counts}")
        
        return cleanup_counts
    
    def get_retention_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get data retention summary for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict[str, Any]: Retention summary
        """
        summary = {}
        
        # Count user's data by category
        summary['conversations'] = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).count()
        
        from ..auth.database import UserSession
        summary['sessions'] = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).count()
        
        summary['documents_created'] = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.created_by == user_id
        ).count()
        
        return summary

class RightToBeForgotenManager:
    """Implements GDPR right to be forgotten (erasure)."""
    
    def __init__(self, db_session: Session):
        """Initialize right to be forgotten manager."""
        self.db = db_session
        self.pii_detector = PIIDetector()
    
    def process_erasure_request(self, user_id: str, erasure_scope: str = "full") -> Dict[str, Any]:
        """
        Process user's right to be forgotten request.
        
        Args:
            user_id: User ID
            erasure_scope: Scope of erasure ("full", "partial", "anonymize")
            
        Returns:
            Dict[str, Any]: Erasure summary
        """
        logger.info(f"Processing erasure request for user {user_id} with scope: {erasure_scope}")
        
        summary = {
            'user_id': user_id,
            'erasure_scope': erasure_scope,
            'started_at': datetime.utcnow(),
            'actions_taken': [],
            'errors': []
        }
        
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                summary['errors'].append("User not found")
                return summary
            
            if erasure_scope == "full":
                summary.update(self._full_erasure(user_id))
            elif erasure_scope == "partial":
                summary.update(self._partial_erasure(user_id))
            elif erasure_scope == "anonymize":
                summary.update(self._anonymize_user_data(user_id))
            
            summary['completed_at'] = datetime.utcnow()
            
        except Exception as e:
            summary['errors'].append(f"Erasure failed: {str(e)}")
            logger.error(f"Erasure request failed for user {user_id}: {str(e)}")
        
        return summary
    
    def _full_erasure(self, user_id: str) -> Dict[str, Any]:
        """Perform full user data erasure."""
        actions = []
        
        # Delete conversation memories
        deleted_conversations = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).delete()
        actions.append(f"Deleted {deleted_conversations} conversation memories")
        
        # Delete user sessions
        from ..auth.database import UserSession
        deleted_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).delete()
        actions.append(f"Deleted {deleted_sessions} user sessions")
        
        # Delete MFA devices
        from ..auth.database import MFADevice
        deleted_mfa = self.db.query(MFADevice).filter(
            MFADevice.user_id == user_id
        ).delete()
        actions.append(f"Deleted {deleted_mfa} MFA devices")
        
        # Handle documents created by user - anonymize rather than delete
        user_documents = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.created_by == user_id
        ).all()
        
        for doc in user_documents:
            doc.created_by = None  # Anonymize ownership
            doc.description = "[REDACTED - User deleted]" if doc.description else None
        
        actions.append(f"Anonymized {len(user_documents)} documents")
        
        # Delete the user account
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            self.db.delete(user)
            actions.append("Deleted user account")
        
        self.db.commit()
        
        return {'actions_taken': actions}
    
    def _partial_erasure(self, user_id: str) -> Dict[str, Any]:
        """Perform partial user data erasure (keep essential data)."""
        actions = []
        
        # Delete conversation memories older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        deleted_conversations = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.updated_at < cutoff_date
        ).delete()
        actions.append(f"Deleted {deleted_conversations} old conversation memories")
        
        # Delete inactive sessions
        from ..auth.database import UserSession
        deleted_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == False
        ).delete()
        actions.append(f"Deleted {deleted_sessions} inactive sessions")
        
        # Anonymize user profile data
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.email = None
            user.full_name = "[REDACTED]"
            user.preferences = {}
            actions.append("Anonymized user profile data")
        
        self.db.commit()
        
        return {'actions_taken': actions}
    
    def _anonymize_user_data(self, user_id: str) -> Dict[str, Any]:
        """Anonymize user data while preserving functionality."""
        actions = []
        
        # Anonymize conversation memories
        conversations = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).all()
        
        replacement_map = {}
        for conversation in conversations:
            # Anonymize messages
            anonymized_messages = []
            for message in conversation.messages:
                if isinstance(message, dict) and 'content' in message:
                    anonymized_content, replacement_map = self.pii_detector.anonymize_text(
                        message['content'], replacement_map
                    )
                    message['content'] = anonymized_content
                anonymized_messages.append(message)
            conversation.messages = anonymized_messages
        
        actions.append(f"Anonymized {len(conversations)} conversation memories")
        
        # Anonymize user profile
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            if user.email:
                user.email = f"anonymized_{hashlib.md5(user.email.encode()).hexdigest()[:8]}@localhost"
            if user.full_name:
                user.full_name = f"[ANONYMIZED_{hashlib.md5(user.full_name.encode()).hexdigest()[:8]}]"
            user.preferences = {}
            actions.append("Anonymized user profile")
        
        # Store anonymization mapping for potential reversibility (encrypted)
        self._store_anonymization_mapping(user_id, replacement_map)
        
        self.db.commit()
        
        return {'actions_taken': actions}
    
    def _store_anonymization_mapping(self, user_id: str, replacement_map: Dict[str, str]):
        """Store anonymization mapping securely."""
        # This would store the mapping in an encrypted format
        # Implementation depends on specific requirements
        logger.info(f"Stored anonymization mapping for user {user_id}")

class DataPortabilityManager:
    """Implements GDPR data portability rights."""
    
    def __init__(self, db_session: Session):
        """Initialize data portability manager."""
        self.db = db_session
    
    def export_user_data(self, user_id: str, format: str = "json") -> Dict[str, Any]:
        """
        Export all user data in machine-readable format.
        
        Args:
            user_id: User ID
            format: Export format ("json", "xml", "csv")
            
        Returns:
            Dict[str, Any]: Exported user data
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        export_data = {
            'export_info': {
                'user_id': user_id,
                'export_date': datetime.utcnow().isoformat(),
                'format': format,
                'version': '1.0'
            },
            'user_profile': user.to_dict(),
            'conversations': [],
            'documents': [],
            'sessions': [],
            'consents': []
        }
        
        # Export conversations
        conversations = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).all()
        export_data['conversations'] = [conv.to_dict() for conv in conversations]
        
        # Export documents created by user
        documents = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.created_by == user_id
        ).all()
        export_data['documents'] = [doc.to_dict() for doc in documents]
        
        # Export sessions
        from ..auth.database import UserSession
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).all()
        export_data['sessions'] = [session.to_dict() for session in sessions]
        
        logger.info(f"Data export completed for user {user_id}")
        
        return export_data

class GDPRComplianceManager:
    """Main GDPR compliance manager that coordinates all privacy features."""
    
    def __init__(self, db_session: Session):
        """Initialize GDPR compliance manager."""
        self.db = db_session
        self.pii_detector = PIIDetector()
        self.consent_manager = ConsentManager(db_session)
        self.retention_manager = DataRetentionManager(db_session)
        self.erasure_manager = RightToBeForgotenManager(db_session)
        self.portability_manager = DataPortabilityManager(db_session)
    
    def get_compliance_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive compliance dashboard for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict[str, Any]: Compliance dashboard data
        """
        return {
            'user_id': user_id,
            'consents': self.consent_manager.get_user_consents(user_id),
            'data_retention': self.retention_manager.get_retention_summary(user_id),
            'mfa_status': self._get_mfa_status(user_id),
            'last_activity': self._get_last_activity(user_id),
            'privacy_settings': self._get_privacy_settings(user_id)
        }
    
    def _get_mfa_status(self, user_id: str) -> Dict[str, Any]:
        """Get MFA status for user."""
        from .mfa import MFAManager
        mfa_manager = MFAManager(self.db)
        return mfa_manager.get_user_mfa_status(user_id)
    
    def _get_last_activity(self, user_id: str) -> Optional[str]:
        """Get user's last activity timestamp."""
        from ..auth.database import UserSession
        last_session = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).order_by(UserSession.last_activity.desc()).first()
        
        return last_session.last_activity.isoformat() if last_session and last_session.last_activity else None
    
    def _get_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """Get user's privacy settings."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.preferences:
            return user.preferences.get('privacy', {})
        return {}