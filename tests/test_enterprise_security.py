"""
Comprehensive test suite for enterprise security features.
Tests RBAC, MFA, session management, and audit logging.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Test database setup
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
def rbac_manager(test_db_session):
    """Create RBAC manager for testing."""
    from backend.auth.rbac import RBACManager
    return RBACManager(test_db_session)

@pytest.fixture
def mfa_manager(test_db_session):
    """Create MFA manager for testing."""
    from backend.auth.mfa import MFAManager
    return MFAManager(test_db_session)

@pytest.fixture
def session_manager(test_db_session):
    """Create session manager for testing."""
    from backend.auth.mfa import SessionManager
    return SessionManager(test_db_session)

@pytest.fixture
def test_user(test_db_session):
    """Create test user."""
    from backend.auth.database import User
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password=pwd_context.hash("testpass123"),
        department="engineering",
        is_active=True
    )
    
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    
    yield user
    
    # Cleanup
    test_db_session.delete(user)
    test_db_session.commit()

@pytest.fixture
def test_admin_user(test_db_session):
    """Create test admin user."""
    from backend.auth.database import User
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="testadmin",
        email="admin@example.com",
        full_name="Test Admin",
        hashed_password=pwd_context.hash("adminpass123"),
        department="general",
        is_active=True,
        is_admin=True
    )
    
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    
    yield user
    
    # Cleanup
    test_db_session.delete(user)
    test_db_session.commit()

class TestRBAC:
    """Test Role-Based Access Control system."""
    
    def test_check_permission_admin_user(self, rbac_manager, test_admin_user):
        """Test that admin users have all permissions."""
        from backend.auth.models import Permission
        
        # Admin users should have all permissions
        assert rbac_manager.check_permission(str(test_admin_user.id), Permission.DOCUMENT_READ)
        assert rbac_manager.check_permission(str(test_admin_user.id), Permission.SYSTEM_ADMIN)
        assert rbac_manager.check_permission(str(test_admin_user.id), Permission.USER_MANAGE)
    
    def test_check_permission_regular_user(self, rbac_manager, test_user, test_db_session):
        """Test permission checking for regular users."""
        from backend.auth.database import Role
        from backend.auth.models import Permission
        
        # Create a test role
        role = Role(
            name="TestRole",
            description="Test role for permissions",
            permissions=[Permission.DOCUMENT_READ.value, Permission.QUERY_BASIC.value]
        )
        test_db_session.add(role)
        test_db_session.commit()
        
        # Assign role to user
        test_user.roles.append(role)
        test_db_session.commit()
        
        # Test permissions
        assert rbac_manager.check_permission(str(test_user.id), Permission.DOCUMENT_READ)
        assert rbac_manager.check_permission(str(test_user.id), Permission.QUERY_BASIC)
        assert not rbac_manager.check_permission(str(test_user.id), Permission.DOCUMENT_DELETE)
        assert not rbac_manager.check_permission(str(test_user.id), Permission.SYSTEM_ADMIN)
    
    def test_get_user_permissions(self, rbac_manager, test_user, test_db_session):
        """Test getting user permissions."""
        from backend.auth.database import Role
        from backend.auth.models import Permission
        
        # Create a test role
        role = Role(
            name="TestRole2",
            description="Test role for permissions",
            permissions=[Permission.DOCUMENT_READ.value, Permission.QUERY_BASIC.value]
        )
        test_db_session.add(role)
        test_db_session.commit()
        
        # Assign role to user
        test_user.roles.append(role)
        test_db_session.commit()
        
        # Get user permissions
        permissions = rbac_manager.get_user_permissions(str(test_user.id))
        
        assert Permission.DOCUMENT_READ.value in permissions
        assert Permission.QUERY_BASIC.value in permissions
        assert Permission.SYSTEM_ADMIN.value not in permissions
    
    def test_filter_documents_by_permission(self, rbac_manager, test_user, test_db_session):
        """Test document filtering by permission."""
        from backend.auth.database import Role, DocumentMetadata
        from backend.auth.models import Permission, DocumentSensitivity, Department
        
        # Create a test role with document access
        role = Role(
            name="TestRole3",
            description="Test role for document access",
            permissions=[Permission.DOCUMENT_READ.value],
            document_access={
                DocumentSensitivity.PUBLIC.value: True,
                DocumentSensitivity.INTERNAL.value: True,
                DocumentSensitivity.CONFIDENTIAL.value: False,
                DocumentSensitivity.RESTRICTED.value: False
            },
            department_access=[Department.ENGINEERING.value, Department.GENERAL.value]
        )
        test_db_session.add(role)
        test_db_session.commit()
        
        # Assign role to user
        test_user.roles.append(role)
        test_db_session.commit()
        
        # Create test documents
        doc1 = DocumentMetadata(
            document_id="doc1",
            filename="test1.pdf",
            file_type="pdf",
            file_size=1024,
            sensitivity_level=DocumentSensitivity.PUBLIC.value,
            department=Department.ENGINEERING.value
        )
        
        doc2 = DocumentMetadata(
            document_id="doc2",
            filename="test2.pdf",
            file_type="pdf",
            file_size=2048,
            sensitivity_level=DocumentSensitivity.CONFIDENTIAL.value,
            department=Department.ENGINEERING.value
        )
        
        test_db_session.add_all([doc1, doc2])
        test_db_session.commit()
        
        # Filter documents
        accessible_docs = rbac_manager.filter_documents_by_permission(str(test_user.id))
        
        assert "doc1" in accessible_docs  # Public document in engineering
        assert "doc2" not in accessible_docs  # Confidential document (no access)

class TestMFA:
    """Test Multi-Factor Authentication system."""
    
    def test_enable_totp_for_user(self, mfa_manager, test_user):
        """Test enabling TOTP for a user."""
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        assert "secret" in setup_info
        assert "qr_code" in setup_info
        assert "provisioning_uri" in setup_info
        assert "backup_codes" in setup_info
        assert "device_id" in setup_info
        
        # Verify backup codes are provided
        assert len(setup_info["backup_codes"]) == 10
        
        # QR code should be base64 encoded PNG
        assert setup_info["qr_code"].startswith("data:image/png;base64,")
    
    @patch('pyotp.TOTP')
    def test_verify_totp_setup(self, mock_totp_class, mfa_manager, test_user):
        """Test TOTP setup verification."""
        # Setup MFA
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        # Mock TOTP verification
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        
        # Verify setup
        result = mfa_manager.verify_totp_setup(
            str(test_user.id),
            setup_info["device_id"],
            "123456"
        )
        
        assert result is True
        mock_totp.verify.assert_called_once_with("123456", valid_window=2)
    
    @patch('pyotp.TOTP')
    def test_verify_totp_token(self, mock_totp_class, mfa_manager, test_user):
        """Test TOTP token verification for login."""
        # Setup and verify MFA
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        # Mock TOTP for setup
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        
        mfa_manager.verify_totp_setup(
            str(test_user.id),
            setup_info["device_id"],
            "123456"
        )
        
        # Test token verification
        result = mfa_manager.verify_totp_token(str(test_user.id), "654321")
        assert result is True
        
        # Verify TOTP was called correctly
        calls = mock_totp.verify.call_args_list
        assert len(calls) == 2  # Setup + login verification
        assert calls[1] == (("654321",), {"valid_window": 1})
    
    def test_verify_backup_code(self, mfa_manager, test_user):
        """Test backup code verification."""
        # Setup MFA
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        # Mock TOTP verification for setup
        with patch('pyotp.TOTP') as mock_totp_class:
            mock_totp = Mock()
            mock_totp.verify.return_value = True
            mock_totp_class.return_value = mock_totp
            
            mfa_manager.verify_totp_setup(
                str(test_user.id),
                setup_info["device_id"],
                "123456"
            )
        
        # Get a backup code and verify it
        backup_code = setup_info["backup_codes"][0]
        result = mfa_manager.verify_backup_code(str(test_user.id), backup_code)
        
        assert result is True
        
        # Verify the same backup code can't be used again
        result = mfa_manager.verify_backup_code(str(test_user.id), backup_code)
        assert result is False
    
    def test_get_user_mfa_status(self, mfa_manager, test_user):
        """Test getting user MFA status."""
        # Initially no MFA
        status = mfa_manager.get_user_mfa_status(str(test_user.id))
        assert status["enabled"] is False
        
        # Enable MFA
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        with patch('pyotp.TOTP') as mock_totp_class:
            mock_totp = Mock()
            mock_totp.verify.return_value = True
            mock_totp_class.return_value = mock_totp
            
            mfa_manager.verify_totp_setup(
                str(test_user.id),
                setup_info["device_id"],
                "123456"
            )
        
        # Check status after enabling
        status = mfa_manager.get_user_mfa_status(str(test_user.id))
        assert status["enabled"] is True
        assert status["device_type"] == "totp"
        assert status["backup_codes_remaining"] == 10
    
    def test_disable_mfa_for_user(self, mfa_manager, test_user):
        """Test disabling MFA for a user."""
        # Enable MFA first
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        # Disable MFA
        result = mfa_manager.disable_mfa_for_user(str(test_user.id))
        assert result is True
        
        # Verify MFA is disabled
        status = mfa_manager.get_user_mfa_status(str(test_user.id))
        assert status["enabled"] is False

class TestSessionManager:
    """Test enhanced session management."""
    
    def test_create_session(self, session_manager, test_user):
        """Test creating a user session."""
        token = session_manager.create_session(
            str(test_user.id),
            "192.168.1.100",
            "Mozilla/5.0 Test Browser"
        )
        
        assert token is not None
        assert len(token) > 20  # Should be a secure token
    
    def test_validate_session(self, session_manager, test_user):
        """Test session validation."""
        token = session_manager.create_session(
            str(test_user.id),
            "192.168.1.100",
            "Mozilla/5.0 Test Browser"
        )
        
        # Validate session
        user_id = session_manager.validate_session(token)
        assert user_id == str(test_user.id)
    
    def test_session_expiry(self, session_manager, test_user):
        """Test session expiry."""
        # Create session with short timeout
        session_manager.session_timeout_minutes = 0  # Immediate expiry for testing
        
        token = session_manager.create_session(
            str(test_user.id),
            "192.168.1.100",
            "Mozilla/5.0 Test Browser"
        )
        
        # Session should be expired
        user_id = session_manager.validate_session(token)
        assert user_id is None
    
    def test_max_sessions_per_user(self, session_manager, test_user):
        """Test maximum sessions per user limit."""
        session_manager.max_sessions_per_user = 2
        
        # Create maximum allowed sessions
        tokens = []
        for i in range(3):  # Try to create 3 sessions (limit is 2)
            token = session_manager.create_session(
                str(test_user.id),
                f"192.168.1.{100+i}",
                "Mozilla/5.0 Test Browser"
            )
            tokens.append(token)
        
        # First session should be invalidated, last two should be valid
        assert session_manager.validate_session(tokens[0]) is None  # Oldest session removed
        assert session_manager.validate_session(tokens[1]) == str(test_user.id)
        assert session_manager.validate_session(tokens[2]) == str(test_user.id)
    
    def test_revoke_session(self, session_manager, test_user):
        """Test session revocation."""
        token = session_manager.create_session(
            str(test_user.id),
            "192.168.1.100",
            "Mozilla/5.0 Test Browser"
        )
        
        # Session should be valid
        user_id = session_manager.validate_session(token)
        assert user_id == str(test_user.id)
        
        # Revoke session
        result = session_manager.revoke_session(token)
        assert result is True
        
        # Session should no longer be valid
        user_id = session_manager.validate_session(token)
        assert user_id is None
    
    def test_revoke_all_user_sessions(self, session_manager, test_user):
        """Test revoking all sessions for a user."""
        # Create multiple sessions
        tokens = []
        for i in range(3):
            token = session_manager.create_session(
                str(test_user.id),
                f"192.168.1.{100+i}",
                "Mozilla/5.0 Test Browser"
            )
            tokens.append(token)
        
        # All sessions should be valid
        for token in tokens:
            assert session_manager.validate_session(token) == str(test_user.id)
        
        # Revoke all sessions
        revoked_count = session_manager.revoke_all_user_sessions(str(test_user.id))
        assert revoked_count == 3
        
        # All sessions should now be invalid
        for token in tokens:
            assert session_manager.validate_session(token) is None

class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_metadata_audit_logging(self, test_db_session, test_user):
        """Test document metadata audit logging."""
        from backend.document_processing.audit import MetadataAuditLogger
        from backend.auth.database import DocumentMetadata
        
        audit_logger = MetadataAuditLogger(test_db_session)
        
        # Create test document
        doc = DocumentMetadata(
            document_id="audit_test_doc",
            filename="audit_test.pdf",
            file_type="pdf",
            file_size=1024,
            created_by=test_user.id
        )
        test_db_session.add(doc)
        test_db_session.commit()
        
        # Test audit logging
        with patch('backend.document_processing.audit.logger') as mock_logger:
            audit_logger.log_metadata_access(
                str(test_user.id),
                "audit_test_doc",
                "read"
            )
            
            # Verify logging was called
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "METADATA ACCESS: read" in call_args
            assert str(test_user.username) in call_args
            assert "audit_test_doc" in call_args

# Integration tests
class TestSecurityIntegration:
    """Integration tests for security features."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app."""
        from fastapi import FastAPI
        app = FastAPI()
        return app
    
    def test_permission_middleware_integration(self, test_db_session, test_user, app):
        """Test permission middleware integration."""
        from backend.auth.middleware import create_permission_middleware
        from backend.auth.models import Permission
        
        # Create permission middleware
        def get_db():
            return test_db_session
        
        permission_middleware = create_permission_middleware(get_db)
        
        # Test permission requirement
        permission_dep = permission_middleware.require_permissions([Permission.DOCUMENT_READ])
        
        # This would be tested in a full FastAPI integration test
        assert permission_dep is not None
    
    def test_rbac_with_mfa_integration(self, rbac_manager, mfa_manager, test_user, test_db_session):
        """Test RBAC working with MFA."""
        from backend.auth.database import Role
        from backend.auth.models import Permission
        
        # Setup user with role
        role = Role(
            name="SecureRole",
            description="Role requiring MFA",
            permissions=[Permission.DOCUMENT_READ.value, Permission.SYSTEM_MONITOR.value]
        )
        test_db_session.add(role)
        test_user.roles.append(role)
        test_db_session.commit()
        
        # Enable MFA
        setup_info = mfa_manager.enable_totp_for_user(str(test_user.id))
        
        with patch('pyotp.TOTP') as mock_totp_class:
            mock_totp = Mock()
            mock_totp.verify.return_value = True
            mock_totp_class.return_value = mock_totp
            
            mfa_manager.verify_totp_setup(
                str(test_user.id),
                setup_info["device_id"],
                "123456"
            )
        
        # Test that user has permissions
        assert rbac_manager.check_permission(str(test_user.id), Permission.DOCUMENT_READ)
        assert rbac_manager.check_permission(str(test_user.id), Permission.SYSTEM_MONITOR)
        
        # Test MFA is enabled
        mfa_status = mfa_manager.get_user_mfa_status(str(test_user.id))
        assert mfa_status["enabled"] is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])