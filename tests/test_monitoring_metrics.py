"""
Comprehensive test suite for monitoring and metrics collection.
Tests Prometheus metrics, performance tracking, health monitoring, and alerting.
"""

import pytest
import asyncio
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
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
def db_session_factory(test_db_session):
    """Create database session factory for testing."""
    def get_db():
        yield test_db_session
    return get_db

@pytest.fixture
def metrics_collector(db_session_factory):
    """Create metrics collector for testing."""
    from backend.monitoring.metrics import MetricsCollector
    collector = MetricsCollector(db_session_factory)
    yield collector
    collector.stop_collection()

@pytest.fixture
def performance_tracker():
    """Create performance tracker for testing."""
    from backend.monitoring.metrics import PerformanceTracker
    return PerformanceTracker()

@pytest.fixture
def health_monitor(db_session_factory):
    """Create health monitor for testing."""
    from backend.monitoring.metrics import HealthMonitor
    return HealthMonitor(db_session_factory)

@pytest.fixture
def alert_manager():
    """Create alert manager for testing."""
    from backend.monitoring.metrics import AlertManager
    return AlertManager()

class TestMetricsCollector:
    """Test Prometheus metrics collection."""
    
    def test_metrics_collector_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector.collection_interval == 30
        assert metrics_collector.stop_event is not None
        assert metrics_collector.collection_thread is None
    
    def test_start_stop_collection(self, metrics_collector):
        """Test starting and stopping metrics collection."""
        # Start collection
        metrics_collector.start_collection()
        
        # Should have started thread
        assert metrics_collector.collection_thread is not None
        assert metrics_collector.collection_thread.is_alive()
        
        # Stop collection
        metrics_collector.stop_collection()
        
        # Thread should be stopped
        time.sleep(0.1)  # Give thread time to stop
        assert not metrics_collector.collection_thread.is_alive()
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_collect_system_metrics(self, mock_disk_usage, mock_virtual_memory, 
                                   mock_cpu_percent, metrics_collector):
        """Test system metrics collection."""
        from backend.monitoring.metrics import SYSTEM_CPU_USAGE, SYSTEM_MEMORY_USAGE, SYSTEM_DISK_USAGE
        
        # Mock system metrics
        mock_cpu_percent.return_value = 45.5
        
        mock_memory = Mock()
        mock_memory.percent = 67.2
        mock_virtual_memory.return_value = mock_memory
        
        mock_disk = Mock()
        mock_disk.used = 80 * 1024**3  # 80 GB used
        mock_disk.total = 100 * 1024**3  # 100 GB total
        mock_disk_usage.return_value = mock_disk
        
        # Collect system metrics
        metrics_collector._collect_system_metrics()
        
        # Verify metrics were set
        assert SYSTEM_CPU_USAGE._value._value == 45.5
        assert SYSTEM_MEMORY_USAGE._value._value == 67.2
        assert SYSTEM_DISK_USAGE._value._value == 80.0
    
    def test_collect_database_metrics(self, metrics_collector, test_db_session):
        """Test database metrics collection."""
        from backend.monitoring.metrics import ACTIVE_SESSIONS, DOCUMENT_COUNT
        from backend.auth.database import UserSession, DocumentMetadata, User
        
        # Create test data
        user = User(
            username="metrics_test_user",
            email="metrics@test.com",
            hashed_password="hashed",
        )
        test_db_session.add(user)
        test_db_session.commit()
        
        session = UserSession(
            user_id=user.id,
            session_token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True
        )
        
        document = DocumentMetadata(
            document_id="metrics_test_doc",
            filename="metrics_test.pdf",
            file_type="pdf",
            file_size=1024
        )
        
        test_db_session.add_all([session, document])
        test_db_session.commit()
        
        # Collect database metrics
        metrics_collector._collect_database_metrics()
        
        # Verify metrics were updated
        assert ACTIVE_SESSIONS._value._value >= 1
        assert DOCUMENT_COUNT._value._value >= 1
    
    def test_get_metrics_summary(self, metrics_collector):
        """Test getting metrics summary."""
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value.percent = 60.0
            mock_disk.return_value.used = 70 * 1024**3
            mock_disk.return_value.total = 100 * 1024**3
            
            summary = metrics_collector.get_metrics_summary()
            
            assert "system" in summary
            assert "database" in summary
            assert "requests" in summary
            assert "queries" in summary
            
            assert summary["system"]["cpu_usage"] == 50.0
            assert summary["system"]["memory_usage"] == 60.0
            assert summary["system"]["disk_usage"] == 70.0

class TestPerformanceTracker:
    """Test performance tracking functionality."""
    
    def test_track_operation_success(self, performance_tracker):
        """Test tracking successful operations."""
        from backend.monitoring.metrics import QUERY_COUNT, QUERY_DURATION
        
        # Clear counters
        QUERY_COUNT._value.clear()
        QUERY_DURATION._value.clear()
        
        # Track operation
        with performance_tracker.track_operation("query_document_search"):
            time.sleep(0.01)  # Simulate work
        
        # Verify metrics were updated
        assert QUERY_COUNT._value._value.get(("document_search", "True"), 0) >= 1
        assert QUERY_DURATION._value.sum() > 0
    
    def test_track_operation_failure(self, performance_tracker):
        """Test tracking failed operations."""
        from backend.monitoring.metrics import QUERY_COUNT, ERROR_COUNT
        
        # Clear counters
        QUERY_COUNT._value.clear()
        ERROR_COUNT._value.clear()
        
        # Track failed operation
        with pytest.raises(ValueError):
            with performance_tracker.track_operation("query_test_operation"):
                raise ValueError("Test error")
        
        # Verify error metrics were updated
        assert ERROR_COUNT._value._value.get(("ValueError", "query"), 0) >= 1
        assert QUERY_COUNT._value._value.get(("test_operation", "False"), 0) >= 1
    
    def test_track_llm_operation(self, performance_tracker):
        """Test tracking LLM operations."""
        from backend.monitoring.metrics import LLM_REQUESTS
        
        # Clear counters
        LLM_REQUESTS._value.clear()
        
        # Track LLM operation
        with performance_tracker.track_operation("llm_generate", {"model": "test_model"}):
            time.sleep(0.01)
        
        # Verify LLM metrics were updated
        assert LLM_REQUESTS._value._value.get(("test_model", "True"), 0) >= 1
    
    def test_track_embedding_operation(self, performance_tracker):
        """Test tracking embedding operations."""
        from backend.monitoring.metrics import EMBEDDING_REQUESTS
        
        # Clear counters
        EMBEDDING_REQUESTS._value.clear()
        
        # Track embedding operation
        with performance_tracker.track_operation("embedding_generate"):
            time.sleep(0.01)
        
        # Verify embedding metrics were updated
        assert EMBEDDING_REQUESTS._value._value.get(("True",), 0) >= 1
    
    def test_track_vector_db_operation(self, performance_tracker):
        """Test tracking vector database operations."""
        from backend.monitoring.metrics import VECTOR_DB_OPERATIONS
        
        # Clear counters
        VECTOR_DB_OPERATIONS._value.clear()
        
        # Track vector DB operation
        with performance_tracker.track_operation("vector_search"):
            time.sleep(0.01)
        
        # Verify vector DB metrics were updated
        assert VECTOR_DB_OPERATIONS._value._value.get(("search", "True"), 0) >= 1
    
    def test_get_active_operations(self, performance_tracker):
        """Test getting active operations."""
        # Start long-running operation in thread
        def long_operation():
            with performance_tracker.track_operation("test_long_operation", {"test": "label"}):
                time.sleep(0.1)
        
        thread = threading.Thread(target=long_operation)
        thread.start()
        
        # Give thread time to start
        time.sleep(0.01)
        
        # Get active operations
        active_ops = performance_tracker.get_active_operations()
        
        # Should have one active operation
        assert len(active_ops) >= 1
        
        active_op = active_ops[0]
        assert active_op["name"] == "test_long_operation"
        assert active_op["labels"]["test"] == "label"
        assert active_op["duration"] > 0
        
        # Wait for thread to complete
        thread.join()
        
        # Should have no active operations
        active_ops = performance_tracker.get_active_operations()
        assert len(active_ops) == 0

class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    def test_check_database_health(self, health_monitor):
        """Test database health check."""
        result = health_monitor._check_database()
        
        assert "healthy" in result
        assert "message" in result
        assert "timestamp" in result
        
        # Database should be healthy in test environment
        assert result["healthy"] is True
    
    @patch('psutil.disk_usage')
    def test_check_disk_space_healthy(self, mock_disk_usage, health_monitor):
        """Test disk space health check - healthy scenario."""
        mock_disk = Mock()
        mock_disk.free = 50 * 1024**3  # 50 GB free
        mock_disk.total = 100 * 1024**3  # 100 GB total
        mock_disk_usage.return_value = mock_disk
        
        result = health_monitor._check_disk_space()
        
        assert result["healthy"] is True
        assert result["free_space_percent"] == 50.0
        assert "message" in result
    
    @patch('psutil.disk_usage')
    def test_check_disk_space_unhealthy(self, mock_disk_usage, health_monitor):
        """Test disk space health check - unhealthy scenario."""
        mock_disk = Mock()
        mock_disk.free = 5 * 1024**3  # 5 GB free (5%)
        mock_disk.total = 100 * 1024**3  # 100 GB total
        mock_disk_usage.return_value = mock_disk
        
        result = health_monitor._check_disk_space()
        
        assert result["healthy"] is False
        assert result["free_space_percent"] == 5.0
    
    @patch('psutil.virtual_memory')
    def test_check_memory_healthy(self, mock_virtual_memory, health_monitor):
        """Test memory health check - healthy scenario."""
        mock_memory = Mock()
        mock_memory.percent = 70.0  # 70% used (healthy)
        mock_memory.available = 8 * 1024**3  # 8 GB available
        mock_virtual_memory.return_value = mock_memory
        
        result = health_monitor._check_memory()
        
        assert result["healthy"] is True
        assert result["usage_percent"] == 70.0
    
    @patch('psutil.virtual_memory')
    def test_check_memory_unhealthy(self, mock_virtual_memory, health_monitor):
        """Test memory health check - unhealthy scenario."""
        mock_memory = Mock()
        mock_memory.percent = 95.0  # 95% used (unhealthy)
        mock_memory.available = 1 * 1024**3  # 1 GB available
        mock_virtual_memory.return_value = mock_memory
        
        result = health_monitor._check_memory()
        
        assert result["healthy"] is False
        assert result["usage_percent"] == 95.0
    
    @pytest.mark.asyncio
    async def test_check_ollama_healthy(self, health_monitor):
        """Test Ollama health check - healthy scenario."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status = 200
            
            mock_session_instance = Mock()
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            result = await health_monitor._check_ollama()
            
            assert result["healthy"] is True
            assert "Ollama is responding" in result["message"]
    
    @pytest.mark.asyncio
    async def test_check_ollama_unhealthy(self, health_monitor):
        """Test Ollama health check - unhealthy scenario."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status = 500
            
            mock_session_instance = Mock()
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            result = await health_monitor._check_ollama()
            
            assert result["healthy"] is False
            assert "500" in result["message"]
    
    @pytest.mark.asyncio
    async def test_check_chroma_healthy(self, health_monitor):
        """Test ChromaDB health check - healthy scenario."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status = 200
            
            mock_session_instance = Mock()
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            result = await health_monitor._check_chroma()
            
            assert result["healthy"] is True
            assert "ChromaDB is responding" in result["message"]
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self, health_monitor):
        """Test comprehensive health check."""
        with patch.object(health_monitor, '_check_database', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_disk_space', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_memory', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_ollama', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_chroma', return_value={"healthy": True}):
            
            health_status = await health_monitor.check_health()
            
            assert health_status["status"] == "healthy"
            assert health_status["overall_health"] is True
            assert "checks" in health_status
            
            # All checks should be present
            expected_checks = ["database", "disk_space", "memory", "ollama", "chroma"]
            for check in expected_checks:
                assert check in health_status["checks"]
                assert health_status["checks"][check]["healthy"] is True
    
    @pytest.mark.asyncio
    async def test_health_check_with_failure(self, health_monitor):
        """Test health check with one failing component."""
        with patch.object(health_monitor, '_check_database', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_disk_space', return_value={"healthy": False}), \
             patch.object(health_monitor, '_check_memory', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_ollama', return_value={"healthy": True}), \
             patch.object(health_monitor, '_check_chroma', return_value={"healthy": True}):
            
            health_status = await health_monitor.check_health()
            
            assert health_status["status"] == "unhealthy"
            assert health_status["overall_health"] is False
            assert health_status["checks"]["disk_space"]["healthy"] is False

class TestAlertManager:
    """Test alerting functionality."""
    
    def test_alert_thresholds_configuration(self, alert_manager):
        """Test alert thresholds are properly configured."""
        thresholds = alert_manager.alert_thresholds
        
        assert "cpu_usage" in thresholds
        assert "memory_usage" in thresholds
        assert "disk_usage" in thresholds
        assert "error_rate" in thresholds
        assert "response_time" in thresholds
        
        # Check reasonable default values
        assert thresholds["cpu_usage"] > 0
        assert thresholds["memory_usage"] > 0
        assert thresholds["disk_usage"] > 0
    
    def test_check_alerts_no_issues(self, alert_manager):
        """Test alert checking with normal metrics."""
        metrics = {
            "system": {
                "cpu_usage": 50.0,  # Below threshold
                "memory_usage": 60.0,  # Below threshold
                "disk_usage": 70.0  # Below threshold
            }
        }
        
        alerts = alert_manager.check_alerts(metrics)
        
        # Should have no alerts
        assert len(alerts) == 0
    
    def test_check_alerts_high_cpu(self, alert_manager):
        """Test alert checking with high CPU usage."""
        metrics = {
            "system": {
                "cpu_usage": 90.0,  # Above threshold (80%)
                "memory_usage": 60.0,
                "disk_usage": 70.0
            }
        }
        
        alerts = alert_manager.check_alerts(metrics)
        
        # Should have CPU alert
        assert len(alerts) >= 1
        cpu_alert = next((a for a in alerts if a["type"] == "high_cpu_usage"), None)
        assert cpu_alert is not None
        assert cpu_alert["severity"] == "warning"
        assert "90.0%" in cpu_alert["message"]
    
    def test_check_alerts_high_memory(self, alert_manager):
        """Test alert checking with high memory usage."""
        metrics = {
            "system": {
                "cpu_usage": 50.0,
                "memory_usage": 90.0,  # Above threshold (85%)
                "disk_usage": 70.0
            }
        }
        
        alerts = alert_manager.check_alerts(metrics)
        
        # Should have memory alert
        assert len(alerts) >= 1
        memory_alert = next((a for a in alerts if a["type"] == "high_memory_usage"), None)
        assert memory_alert is not None
        assert memory_alert["severity"] == "warning"
    
    def test_check_alerts_high_disk(self, alert_manager):
        """Test alert checking with high disk usage."""
        metrics = {
            "system": {
                "cpu_usage": 50.0,
                "memory_usage": 60.0,
                "disk_usage": 95.0  # Above threshold (90%)
            }
        }
        
        alerts = alert_manager.check_alerts(metrics)
        
        # Should have disk alert
        assert len(alerts) >= 1
        disk_alert = next((a for a in alerts if a["type"] == "high_disk_usage"), None)
        assert disk_alert is not None
        assert disk_alert["severity"] == "critical"  # Disk alerts are critical
    
    def test_check_alerts_multiple_issues(self, alert_manager):
        """Test alert checking with multiple issues."""
        metrics = {
            "system": {
                "cpu_usage": 90.0,  # High CPU
                "memory_usage": 90.0,  # High memory
                "disk_usage": 95.0  # High disk
            }
        }
        
        alerts = alert_manager.check_alerts(metrics)
        
        # Should have multiple alerts
        assert len(alerts) == 3
        
        alert_types = [a["type"] for a in alerts]
        assert "high_cpu_usage" in alert_types
        assert "high_memory_usage" in alert_types
        assert "high_disk_usage" in alert_types
    
    def test_get_active_alerts(self, alert_manager):
        """Test getting active alerts."""
        # Generate some alerts
        metrics = {
            "system": {
                "cpu_usage": 90.0,
                "memory_usage": 60.0,
                "disk_usage": 70.0
            }
        }
        
        alert_manager.check_alerts(metrics)
        
        active_alerts = alert_manager.get_active_alerts()
        
        assert len(active_alerts) >= 1
        assert any(a["type"] == "high_cpu_usage" for a in active_alerts)
    
    def test_alert_cleanup_resolved(self, alert_manager):
        """Test cleanup of resolved alerts."""
        # Generate alert
        high_metrics = {
            "system": {
                "cpu_usage": 90.0,
                "memory_usage": 60.0,
                "disk_usage": 70.0
            }
        }
        
        alerts = alert_manager.check_alerts(high_metrics)
        assert len(alerts) >= 1
        
        active_alerts = alert_manager.get_active_alerts()
        assert len(active_alerts) >= 1
        
        # Resolve the issue
        normal_metrics = {
            "system": {
                "cpu_usage": 50.0,  # Back to normal
                "memory_usage": 60.0,
                "disk_usage": 70.0
            }
        }
        
        alerts = alert_manager.check_alerts(normal_metrics)
        
        # Alert should be resolved
        active_alerts = alert_manager.get_active_alerts()
        cpu_alerts = [a for a in active_alerts if a["type"] == "high_cpu_usage"]
        assert len(cpu_alerts) == 0

# Decorator tests
class TestMetricsDecorators:
    """Test metrics collection decorators."""
    
    def test_track_request_metrics_success(self):
        """Test request metrics tracking decorator."""
        from backend.monitoring.metrics import track_request_metrics, REQUEST_COUNT
        
        # Clear counter
        REQUEST_COUNT._value.clear()
        
        @track_request_metrics
        async def mock_endpoint(request):
            return Mock(status_code=200)
        
        # Mock request
        request = Mock()
        request.method = "GET"
        request.url.path = "/test"
        
        # Call endpoint
        asyncio.run(mock_endpoint(request))
        
        # Verify metrics were recorded
        assert REQUEST_COUNT._value._value.get(("GET", "/test", "200"), 0) >= 1
    
    def test_track_request_metrics_error(self):
        """Test request metrics tracking decorator with error."""
        from backend.monitoring.metrics import track_request_metrics, REQUEST_COUNT, ERROR_COUNT
        
        # Clear counters
        REQUEST_COUNT._value.clear()
        ERROR_COUNT._value.clear()
        
        @track_request_metrics
        async def mock_endpoint_error(request):
            raise ValueError("Test error")
        
        # Mock request
        request = Mock()
        request.method = "POST"
        request.url.path = "/error"
        
        # Call endpoint (should raise error)
        with pytest.raises(ValueError):
            asyncio.run(mock_endpoint_error(request))
        
        # Verify error metrics were recorded
        assert REQUEST_COUNT._value._value.get(("POST", "/error", "500"), 0) >= 1
        assert ERROR_COUNT._value._value.get(("ValueError", "api"), 0) >= 1
    
    def test_track_query_metrics_decorator(self):
        """Test query metrics tracking decorator."""
        from backend.monitoring.metrics import track_query_metrics, QUERY_COUNT, QUERY_DURATION
        
        # Clear counters
        QUERY_COUNT._value.clear()
        QUERY_DURATION._value.clear()
        
        @track_query_metrics("test_query")
        async def mock_query():
            time.sleep(0.01)  # Simulate work
            return "result"
        
        # Call query
        result = asyncio.run(mock_query())
        
        assert result == "result"
        assert QUERY_COUNT._value._value.get(("test_query", "true"), 0) >= 1
        assert QUERY_DURATION._value.sum() > 0

# Integration tests
class TestMonitoringIntegration:
    """Integration tests for monitoring system."""
    
    def test_monitoring_initialization(self, db_session_factory):
        """Test monitoring system initialization."""
        from backend.monitoring.metrics import initialize_monitoring, shutdown_monitoring
        
        # Initialize monitoring
        initialize_monitoring(db_session_factory)
        
        # Should have global instances
        from backend.monitoring.metrics import metrics_collector, health_monitor
        assert metrics_collector is not None
        assert health_monitor is not None
        
        # Shutdown monitoring
        shutdown_monitoring()
    
    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self, db_session_factory):
        """Test complete monitoring cycle."""
        from backend.monitoring.metrics import (
            initialize_monitoring, shutdown_monitoring,
            metrics_collector, health_monitor, alert_manager
        )
        
        # Initialize monitoring
        initialize_monitoring(db_session_factory)
        
        # Give collector time to start
        time.sleep(0.1)
        
        # Get metrics summary
        summary = metrics_collector.get_metrics_summary()
        assert "system" in summary
        
        # Check health
        health_status = await health_monitor.check_health()
        assert "status" in health_status
        
        # Check alerts
        alerts = alert_manager.check_alerts(summary)
        assert isinstance(alerts, list)
        
        # Shutdown monitoring
        shutdown_monitoring()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])