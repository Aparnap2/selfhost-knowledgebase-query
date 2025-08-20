"""
Comprehensive test suite for GDPR compliance features.
Tests PII detection, data anonymization, consent management, and right to be forgotten.
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    return engine

@pytest.fixture(scope="session")
def test_db_session(test_engine):
    """Create test database session."""
    from backend.auth.database import Base
    Base.metadata.create_all(bind=test_engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_user(test_db_session):
    """Create test user."""
    from backend.auth.database import User
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="gdpr_testuser",
        email="gdpr.test@example.com",
        full_name="GDPR Test User",
        hashed_password=pwd_context.hash("testpass123"),
        department="engineering"
    )
    
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    
    yield user
    
    # Cleanup
    test_db_session.delete(user)
    test_db_session.commit()

@pytest.fixture
def pii_detector():
    """Create PII detector for testing."""
    from backend.privacy.gdpr_compliance import PIIDetector
    return PIIDetector()

@pytest.fixture
def consent_manager(test_db_session):
    """Create consent manager for testing."""
    from backend.privacy.gdpr_compliance import ConsentManager
    return ConsentManager(test_db_session)

@pytest.fixture
def retention_manager(test_db_session):
    """Create data retention manager for testing."""
    from backend.privacy.gdpr_compliance import DataRetentionManager
    return DataRetentionManager(test_db_session)

@pytest.fixture
def erasure_manager(test_db_session):
    """Create right to be forgotten manager for testing."""
    from backend.privacy.gdpr_compliance import RightToBeForgotenManager
    return RightToBeForgotenManager(test_db_session)

@pytest.fixture
def portability_manager(test_db_session):
    """Create data portability manager for testing."""
    from backend.privacy.gdpr_compliance import DataPortabilityManager
    return DataPortabilityManager(test_db_session)

class TestPIIDetector:
    """Test PII detection and anonymization."""
    
    def test_detect_email_addresses(self, pii_detector):
        """Test email address detection."""
        text = "Contact me at john.doe@example.com or support@company.org"
        entities = pii_detector.detect_pii(text)
        
        email_entities = [e for e in entities if e.label == "EMAIL"]
        assert len(email_entities) == 2
        assert "john.doe@example.com" in [e.text for e in email_entities]
        assert "support@company.org" in [e.text for e in email_entities]
    
    def test_detect_phone_numbers(self, pii_detector):
        """Test phone number detection."""
        text = "Call me at +1-555-123-4567 or (555) 987-6543"
        entities = pii_detector.detect_pii(text)
        
        phone_entities = [e for e in entities if e.label == "PHONE"]
        assert len(phone_entities) >= 1  # At least one phone number detected
    
    def test_detect_ssn(self, pii_detector):
        """Test SSN detection."""
        text = "My SSN is 123-45-6789"
        entities = pii_detector.detect_pii(text)
        
        ssn_entities = [e for e in entities if e.label == "SSN"]
        assert len(ssn_entities) == 1
        assert "123-45-6789" in [e.text for e in ssn_entities]
    
    def test_detect_credit_card(self, pii_detector):
        """Test credit card number detection."""
        text = "My card number is 4532-1234-5678-9012"
        entities = pii_detector.detect_pii(text)
        
        cc_entities = [e for e in entities if e.label == "CREDIT_CARD"]
        assert len(cc_entities) == 1
        assert "4532-1234-5678-9012" in [e.text for e in cc_entities]
    
    def test_anonymize_text(self, pii_detector):
        """Test text anonymization."""
        text = "Contact John Doe at john.doe@example.com or call 555-123-4567"
        anonymized_text, replacement_map = pii_detector.anonymize_text(text)
        
        # Original PII should not be in anonymized text
        assert "john.doe@example.com" not in anonymized_text
        assert "555-123-4567" not in anonymized_text
        
        # Should have replacement tokens
        assert "[EMAIL_" in anonymized_text
        assert "[PHONE_" in anonymized_text
        
        # Replacement map should contain mappings
        assert "john.doe@example.com" in replacement_map
    
    def test_consistent_anonymization(self, pii_detector):
        """Test that same PII gets same replacement token."""
        text1 = "Email me at john@example.com"
        text2 = "Also reach out to john@example.com"
        
        anonymized1, map1 = pii_detector.anonymize_text(text1)
        anonymized2, map2 = pii_detector.anonymize_text(text2, map1)
        
        # Same email should get same replacement token
        email_token1 = map1["john@example.com"]
        email_token2 = map2["john@example.com"]
        assert email_token1 == email_token2
        
        # Both texts should use the same token
        assert email_token1 in anonymized1
        assert email_token1 in anonymized2
    
    @patch('spacy.load')
    def test_spacy_integration(self, mock_spacy_load, pii_detector):
        """Test spaCy NLP integration."""
        # Mock spaCy model
        mock_doc = Mock()
        mock_entity = Mock()
        mock_entity.text = "John Doe"
        mock_entity.label_ = "PERSON"
        mock_entity.start_char = 0
        mock_entity.end_char = 8
        mock_doc.ents = [mock_entity]
        
        mock_nlp = Mock()
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp
        
        # Create new detector to trigger spaCy loading
        from backend.privacy.gdpr_compliance import PIIDetector
        detector = PIIDetector()
        detector.nlp = mock_nlp
        detector.use_nlp = True
        
        text = "John Doe is a person"
        entities = detector.detect_pii(text)
        
        # Should find the person entity
        person_entities = [e for e in entities if e.label == "PERSON"]
        assert len(person_entities) == 1
        assert person_entities[0].text == "John Doe"

class TestConsentManager:
    """Test consent management system."""
    
    def test_record_consent(self, consent_manager, test_user):
        """Test recording user consent."""
        from backend.privacy.gdpr_compliance import ConsentType, DataProcessingPurpose
        
        consent_id = consent_manager.record_consent(
            str(test_user.id),
            ConsentType.DATA_PROCESSING,
            DataProcessingPurpose.SERVICE_PROVISION,
            True,
            {"ip_address": "192.168.1.100", "user_agent": "Test Browser"}
        )
        
        assert consent_id is not None
        assert len(consent_id) > 0
    
    def test_get_user_consents(self, consent_manager, test_user):
        """Test retrieving user consents."""
        from backend.privacy.gdpr_compliance import ConsentType, DataProcessingPurpose
        
        # Record multiple consents
        consent_manager.record_consent(
            str(test_user.id),
            ConsentType.DATA_PROCESSING,
            DataProcessingPurpose.SERVICE_PROVISION,
            True
        )
        
        consent_manager.record_consent(
            str(test_user.id),
            ConsentType.ANALYTICS,
            DataProcessingPurpose.ANALYTICS,
            False
        )
        
        # Get consents
        consents = consent_manager.get_user_consents(str(test_user.id))
        
        assert len(consents) == 2
        
        # Check specific consents
        data_consent_key = f"{ConsentType.DATA_PROCESSING.value}_{DataProcessingPurpose.SERVICE_PROVISION.value}"
        analytics_consent_key = f"{ConsentType.ANALYTICS.value}_{DataProcessingPurpose.ANALYTICS.value}"
        
        assert data_consent_key in consents
        assert analytics_consent_key in consents
        
        assert consents[data_consent_key]["granted"] is True
        assert consents[analytics_consent_key]["granted"] is False
    
    def test_withdraw_consent(self, consent_manager, test_user):
        """Test withdrawing consent."""
        from backend.privacy.gdpr_compliance import ConsentType, DataProcessingPurpose
        
        # Record consent
        consent_manager.record_consent(
            str(test_user.id),
            ConsentType.MARKETING,
            DataProcessingPurpose.MARKETING,
            True
        )
        
        # Withdraw consent
        result = consent_manager.withdraw_consent(
            str(test_user.id),
            ConsentType.MARKETING,
            DataProcessingPurpose.MARKETING
        )
        
        assert result is not None  # Should return consent record ID
        
        # Verify withdrawal
        consents = consent_manager.get_user_consents(str(test_user.id))
        consent_key = f"{ConsentType.MARKETING.value}_{DataProcessingPurpose.MARKETING.value}"
        
        assert consents[consent_key]["granted"] is False

class TestDataRetentionManager:
    """Test data retention and cleanup."""
    
    def test_retention_policies_configuration(self, retention_manager):
        """Test retention policies are properly configured."""
        policies = retention_manager.retention_policies
        
        assert "conversation_memory" in policies
        assert "user_sessions" in policies
        assert "audit_logs" in policies
        
        # Check that policies are timedelta objects
        assert isinstance(policies["conversation_memory"], timedelta)
        assert isinstance(policies["user_sessions"], timedelta)
    
    def test_get_retention_summary(self, retention_manager, test_user, test_db_session):
        """Test getting retention summary for a user."""
        from backend.auth.database import ConversationMemory, DocumentMetadata, UserSession
        
        # Create test data
        conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="test_session",
            messages=[{"role": "user", "content": "Test message"}]
        )
        
        document = DocumentMetadata(
            document_id="retention_test_doc",
            filename="retention_test.pdf",
            file_type="pdf",
            file_size=1024,
            created_by=test_user.id
        )
        
        session = UserSession(
            user_id=test_user.id,
            session_token="test_token_hash",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        test_db_session.add_all([conversation, document, session])
        test_db_session.commit()
        
        # Get retention summary
        summary = retention_manager.get_retention_summary(str(test_user.id))
        
        assert summary["conversations"] >= 1
        assert summary["sessions"] >= 1
        assert summary["documents_created"] >= 1
    
    def test_apply_retention_policies(self, retention_manager, test_user, test_db_session):
        """Test applying retention policies."""
        from backend.auth.database import ConversationMemory, UserSession
        
        # Create old data that should be cleaned up
        old_date = datetime.utcnow() - timedelta(days=400)  # Older than retention policy
        
        old_conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="old_session",
            messages=[{"role": "user", "content": "Old message"}],
            created_at=old_date,
            updated_at=old_date
        )
        
        old_session = UserSession(
            user_id=test_user.id,
            session_token="old_token_hash",
            created_at=old_date,
            expires_at=old_date + timedelta(hours=1),
            is_active=False
        )
        
        # Create recent data that should be kept
        recent_conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="recent_session",
            messages=[{"role": "user", "content": "Recent message"}]
        )
        
        test_db_session.add_all([old_conversation, old_session, recent_conversation])
        test_db_session.commit()
        
        # Apply retention policies
        cleanup_counts = retention_manager.apply_retention_policies()
        
        # Verify cleanup occurred
        assert cleanup_counts["conversation_memory"] >= 1
        assert cleanup_counts["user_sessions"] >= 1
        
        # Verify recent data still exists
        remaining_conversations = test_db_session.query(ConversationMemory).filter(
            ConversationMemory.user_id == test_user.id,
            ConversationMemory.session_id == "recent_session"
        ).count()
        assert remaining_conversations == 1

class TestRightToBeForgotten:
    """Test right to be forgotten (erasure) functionality."""
    
    def test_full_erasure(self, erasure_manager, test_user, test_db_session):
        """Test full user data erasure."""
        from backend.auth.database import ConversationMemory, DocumentMetadata, UserSession
        
        # Create user data
        conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="erasure_test_session",
            messages=[{"role": "user", "content": "Test message"}]
        )
        
        document = DocumentMetadata(
            document_id="erasure_test_doc",
            filename="erasure_test.pdf",
            file_type="pdf",
            file_size=1024,
            created_by=test_user.id
        )
        
        session = UserSession(
            user_id=test_user.id,
            session_token="erasure_test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        test_db_session.add_all([conversation, document, session])
        test_db_session.commit()
        
        # Process erasure request
        summary = erasure_manager.process_erasure_request(str(test_user.id), "full")
        
        assert summary["erasure_scope"] == "full"
        assert len(summary["actions_taken"]) > 0
        assert len(summary["errors"]) == 0
        
        # Verify data was erased
        remaining_conversations = test_db_session.query(ConversationMemory).filter(
            ConversationMemory.user_id == test_user.id
        ).count()
        assert remaining_conversations == 0
        
        remaining_sessions = test_db_session.query(UserSession).filter(
            UserSession.user_id == test_user.id
        ).count()
        assert remaining_sessions == 0
        
        # Document should be anonymized, not deleted
        remaining_document = test_db_session.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == "erasure_test_doc"
        ).first()
        assert remaining_document is not None
        assert remaining_document.created_by is None  # Ownership anonymized
    
    def test_partial_erasure(self, erasure_manager, test_user, test_db_session):
        """Test partial user data erasure."""
        from backend.auth.database import ConversationMemory
        
        # Create old and recent conversations
        old_date = datetime.utcnow() - timedelta(days=60)
        recent_date = datetime.utcnow() - timedelta(days=10)
        
        old_conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="old_session",
            messages=[{"role": "user", "content": "Old message"}],
            created_at=old_date,
            updated_at=old_date
        )
        
        recent_conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="recent_session",
            messages=[{"role": "user", "content": "Recent message"}],
            created_at=recent_date,
            updated_at=recent_date
        )
        
        test_db_session.add_all([old_conversation, recent_conversation])
        test_db_session.commit()
        
        # Process partial erasure
        summary = erasure_manager.process_erasure_request(str(test_user.id), "partial")
        
        assert summary["erasure_scope"] == "partial"
        assert len(summary["actions_taken"]) > 0
        
        # Old conversation should be deleted, recent should remain
        remaining_conversations = test_db_session.query(ConversationMemory).filter(
            ConversationMemory.user_id == test_user.id
        ).all()
        
        # Should have one remaining conversation (the recent one)
        assert len(remaining_conversations) == 1
        assert remaining_conversations[0].session_id == "recent_session"
    
    def test_anonymize_user_data(self, erasure_manager, test_user, test_db_session):
        """Test user data anonymization."""
        from backend.auth.database import ConversationMemory
        
        # Create conversation with PII
        conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="anonymize_session",
            messages=[
                {"role": "user", "content": "My email is john.doe@example.com and phone is 555-123-4567"},
                {"role": "assistant", "content": "I'll help you with that."}
            ]
        )
        
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Process anonymization
        summary = erasure_manager.process_erasure_request(str(test_user.id), "anonymize")
        
        assert summary["erasure_scope"] == "anonymize"
        assert len(summary["actions_taken"]) > 0
        
        # Verify conversation was anonymized
        anonymized_conversation = test_db_session.query(ConversationMemory).filter(
            ConversationMemory.user_id == test_user.id
        ).first()
        
        assert anonymized_conversation is not None
        
        # PII should be anonymized in messages
        message_content = anonymized_conversation.messages[0]["content"]
        assert "john.doe@example.com" not in message_content
        assert "555-123-4567" not in message_content
        assert "[EMAIL_" in message_content
        assert "[PHONE_" in message_content
        
        # User profile should be anonymized
        test_db_session.refresh(test_user)
        assert "[ANONYMIZED_" in test_user.full_name
        assert "anonymized_" in test_user.email

class TestDataPortability:
    """Test data portability (export) functionality."""
    
    def test_export_user_data(self, portability_manager, test_user, test_db_session):
        """Test exporting all user data."""
        from backend.auth.database import ConversationMemory, DocumentMetadata, UserSession
        
        # Create user data
        conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="export_session",
            messages=[{"role": "user", "content": "Export test message"}]
        )
        
        document = DocumentMetadata(
            document_id="export_test_doc",
            filename="export_test.pdf",
            file_type="pdf",
            file_size=1024,
            created_by=test_user.id
        )
        
        session = UserSession(
            user_id=test_user.id,
            session_token="export_test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        test_db_session.add_all([conversation, document, session])
        test_db_session.commit()
        
        # Export user data
        export_data = portability_manager.export_user_data(str(test_user.id), "json")
        
        # Verify export structure
        assert "export_info" in export_data
        assert "user_profile" in export_data
        assert "conversations" in export_data
        assert "documents" in export_data
        assert "sessions" in export_data
        
        # Verify export metadata
        assert export_data["export_info"]["user_id"] == str(test_user.id)
        assert export_data["export_info"]["format"] == "json"
        
        # Verify user data is included
        assert export_data["user_profile"]["username"] == test_user.username
        assert len(export_data["conversations"]) >= 1
        assert len(export_data["documents"]) >= 1
        assert len(export_data["sessions"]) >= 1
        
        # Verify conversation data
        exported_conversation = export_data["conversations"][0]
        assert exported_conversation["session_id"] == "export_session"
        assert len(exported_conversation["messages"]) == 1
    
    def test_export_nonexistent_user(self, portability_manager):
        """Test exporting data for non-existent user."""
        with pytest.raises(ValueError, match="User not found"):
            portability_manager.export_user_data(str(uuid.uuid4()), "json")

class TestGDPRComplianceManager:
    """Test main GDPR compliance manager."""
    
    def test_compliance_dashboard(self, test_user, test_db_session):
        """Test comprehensive compliance dashboard."""
        from backend.privacy.gdpr_compliance import GDPRComplianceManager
        
        compliance_manager = GDPRComplianceManager(test_db_session)
        
        # Get compliance dashboard
        dashboard = compliance_manager.get_compliance_dashboard(str(test_user.id))
        
        assert "user_id" in dashboard
        assert "consents" in dashboard
        assert "data_retention" in dashboard
        assert "mfa_status" in dashboard
        assert "last_activity" in dashboard
        assert "privacy_settings" in dashboard
        
        assert dashboard["user_id"] == str(test_user.id)

# Integration tests
class TestGDPRIntegration:
    """Integration tests for GDPR compliance features."""
    
    def test_full_gdpr_workflow(self, test_user, test_db_session):
        """Test complete GDPR workflow: consent → processing → erasure."""
        from backend.privacy.gdpr_compliance import (
            ConsentManager, ConsentType, DataProcessingPurpose,
            PIIDetector, RightToBeForgotenManager
        )
        from backend.auth.database import ConversationMemory
        
        # Step 1: Record consent
        consent_manager = ConsentManager(test_db_session)
        consent_id = consent_manager.record_consent(
            str(test_user.id),
            ConsentType.DATA_PROCESSING,
            DataProcessingPurpose.SERVICE_PROVISION,
            True
        )
        
        # Step 2: Process data with PII
        conversation = ConversationMemory(
            user_id=test_user.id,
            session_id="gdpr_workflow_session",
            messages=[{"role": "user", "content": "My email is workflow@example.com"}]
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Step 3: User requests anonymization
        erasure_manager = RightToBeForgotenManager(test_db_session)
        summary = erasure_manager.process_erasure_request(str(test_user.id), "anonymize")
        
        # Verify complete workflow
        assert consent_id is not None
        assert summary["erasure_scope"] == "anonymize"
        assert len(summary["actions_taken"]) > 0
        
        # Verify PII was anonymized
        anonymized_conversation = test_db_session.query(ConversationMemory).filter(
            ConversationMemory.user_id == test_user.id
        ).first()
        
        message_content = anonymized_conversation.messages[0]["content"]
        assert "workflow@example.com" not in message_content
        assert "[EMAIL_" in message_content
    
    def test_consent_withdrawal_impact(self, test_user, test_db_session):
        """Test impact of consent withdrawal on data processing."""
        from backend.privacy.gdpr_compliance import (
            ConsentManager, ConsentType, DataProcessingPurpose
        )
        
        consent_manager = ConsentManager(test_db_session)
        
        # Grant consent
        consent_manager.record_consent(
            str(test_user.id),
            ConsentType.ANALYTICS,
            DataProcessingPurpose.ANALYTICS,
            True
        )
        
        # Withdraw consent
        consent_manager.withdraw_consent(
            str(test_user.id),
            ConsentType.ANALYTICS,
            DataProcessingPurpose.ANALYTICS
        )
        
        # Verify withdrawal is recorded
        consents = consent_manager.get_user_consents(str(test_user.id))
        consent_key = f"{ConsentType.ANALYTICS.value}_{DataProcessingPurpose.ANALYTICS.value}"
        
        assert consent_key in consents
        assert consents[consent_key]["granted"] is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])