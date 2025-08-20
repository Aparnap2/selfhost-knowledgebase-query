"""
Comprehensive monitoring and metrics collection for enterprise knowledge base.
Includes Prometheus metrics, performance tracking, and health monitoring.
"""

import time
import psutil
import logging
from typing import Dict, Any, List, Optional
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import asyncio
from functools import wraps
import threading
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    'kb_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'kb_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_SESSIONS = Gauge(
    'kb_active_sessions',
    'Number of active user sessions'
)

DOCUMENT_COUNT = Gauge(
    'kb_documents_total',
    'Total number of documents in knowledge base'
)

QUERY_COUNT = Counter(
    'kb_queries_total',
    'Total number of queries processed',
    ['query_type', 'success']
)

QUERY_DURATION = Histogram(
    'kb_query_duration_seconds',
    'Query processing duration in seconds',
    ['query_type']
)

LLM_REQUESTS = Counter(
    'kb_llm_requests_total',
    'Total LLM requests',
    ['model', 'success']
)

LLM_TOKEN_COUNT = Counter(
    'kb_llm_tokens_total',
    'Total LLM tokens processed',
    ['model', 'type']  # type: input/output
)

EMBEDDING_REQUESTS = Counter(
    'kb_embedding_requests_total',
    'Total embedding requests',
    ['success']
)

VECTOR_DB_OPERATIONS = Counter(
    'kb_vector_db_operations_total',
    'Vector database operations',
    ['operation', 'success']
)

SYSTEM_CPU_USAGE = Gauge(
    'kb_system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'kb_system_memory_usage_percent',
    'System memory usage percentage'
)

SYSTEM_DISK_USAGE = Gauge(
    'kb_system_disk_usage_percent',
    'System disk usage percentage'
)

DATABASE_CONNECTIONS = Gauge(
    'kb_database_connections_active',
    'Active database connections'
)

ERROR_COUNT = Counter(
    'kb_errors_total',
    'Total errors by type',
    ['error_type', 'component']
)

AUDIT_EVENTS = Counter(
    'kb_audit_events_total',
    'Total audit events',
    ['event_type', 'severity']
)

SECURITY_EVENTS = Counter(
    'kb_security_events_total',
    'Security-related events',
    ['event_type', 'severity']
)

APPLICATION_INFO = Info(
    'kb_application_info',
    'Application information'
)

class MetricsCollector:
    """Collects and manages application metrics."""
    
    def __init__(self, db_session_factory):
        """Initialize metrics collector."""
        self.db_session_factory = db_session_factory
        self.collection_interval = 30  # seconds
        self.collection_thread = None
        self.stop_event = threading.Event()
        
        # Initialize application info
        APPLICATION_INFO.info({
            'version': os.getenv('APP_VERSION', '1.0.0'),
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'instance': os.getenv('INSTANCE_ID', 'default')
        })
    
    def start_collection(self):
        """Start background metrics collection."""
        if self.collection_thread and self.collection_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.collection_thread = threading.Thread(target=self._collection_loop)
        self.collection_thread.daemon = True
        self.collection_thread.start()
        logger.info("Metrics collection started")
    
    def stop_collection(self):
        """Stop background metrics collection."""
        if self.collection_thread:
            self.stop_event.set()
            self.collection_thread.join(timeout=5)
            logger.info("Metrics collection stopped")
    
    def _collection_loop(self):
        """Main collection loop running in background thread."""
        while not self.stop_event.wait(self.collection_interval):
            try:
                self._collect_system_metrics()
                self._collect_database_metrics()
                self._collect_application_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {str(e)}")
    
    def _collect_system_metrics(self):
        """Collect system-level metrics."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        SYSTEM_CPU_USAGE.set(cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.percent)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        SYSTEM_DISK_USAGE.set(disk_percent)
    
    def _collect_database_metrics(self):
        """Collect database-related metrics."""
        try:
            db = next(self.db_session_factory())
            
            # Count active sessions
            from ..auth.database import UserSession
            active_sessions_count = db.query(UserSession).filter(
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).count()
            ACTIVE_SESSIONS.set(active_sessions_count)
            
            # Count documents
            from ..auth.database import DocumentMetadata
            document_count = db.query(DocumentMetadata).count()
            DOCUMENT_COUNT.set(document_count)
            
            # Database connection info
            connection_count = self._get_database_connection_count(db)
            DATABASE_CONNECTIONS.set(connection_count)
            
            db.close()
        except Exception as e:
            logger.error(f"Error collecting database metrics: {str(e)}")
    
    def _get_database_connection_count(self, db: Session) -> int:
        """Get active database connection count."""
        try:
            result = db.execute(text("PRAGMA compile_options"))
            return len(result.fetchall())  # Simplified for SQLite
        except:
            return 0
    
    def _collect_application_metrics(self):
        """Collect application-specific metrics."""
        # This can be extended with more application-specific metrics
        pass
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        return {
            'system': {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
            },
            'database': {
                'active_sessions': ACTIVE_SESSIONS._value._value,
                'document_count': DOCUMENT_COUNT._value._value,
                'connections': DATABASE_CONNECTIONS._value._value
            },
            'requests': {
                'total': REQUEST_COUNT._value.sum(),
                'avg_duration': REQUEST_DURATION._value.sum() / max(REQUEST_DURATION._value.count(), 1)
            },
            'queries': {
                'total': QUERY_COUNT._value.sum(),
                'avg_duration': QUERY_DURATION._value.sum() / max(QUERY_DURATION._value.count(), 1)
            }
        }

class PerformanceTracker:
    """Tracks performance metrics and provides insights."""
    
    def __init__(self):
        """Initialize performance tracker."""
        self.active_operations = {}
    
    @contextmanager
    def track_operation(self, operation_name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager to track operation performance."""
        start_time = time.time()
        operation_id = f"{operation_name}_{int(start_time * 1000)}"
        
        self.active_operations[operation_id] = {
            'name': operation_name,
            'start_time': start_time,
            'labels': labels or {}
        }
        
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            
            # Update Prometheus metrics
            if operation_name.startswith('query_'):
                query_type = operation_name.replace('query_', '')
                QUERY_DURATION.labels(query_type=query_type).observe(duration)
                QUERY_COUNT.labels(query_type=query_type, success=str(success)).inc()
            elif operation_name.startswith('llm_'):
                model = labels.get('model', 'unknown') if labels else 'unknown'
                LLM_REQUESTS.labels(model=model, success=str(success)).inc()
            elif operation_name.startswith('embedding_'):
                EMBEDDING_REQUESTS.labels(success=str(success)).inc()
            elif operation_name.startswith('vector_'):
                operation = operation_name.replace('vector_', '')
                VECTOR_DB_OPERATIONS.labels(operation=operation, success=str(success)).inc()
            
            # Clean up
            self.active_operations.pop(operation_id, None)
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get currently active operations."""
        current_time = time.time()
        active_ops = []
        
        for op_id, op_data in self.active_operations.items():
            duration = current_time - op_data['start_time']
            active_ops.append({
                'id': op_id,
                'name': op_data['name'],
                'duration': duration,
                'labels': op_data['labels']
            })
        
        return sorted(active_ops, key=lambda x: x['duration'], reverse=True)

class HealthMonitor:
    """Monitors system health and service availability."""
    
    def __init__(self, db_session_factory):
        """Initialize health monitor."""
        self.db_session_factory = db_session_factory
        self.health_checks = {
            'database': self._check_database,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
            'ollama': self._check_ollama,
            'chroma': self._check_chroma
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {},
            'overall_health': True
        }
        
        for check_name, check_func in self.health_checks.items():
            try:
                check_result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
                health_status['checks'][check_name] = check_result
                
                if not check_result.get('healthy', False):
                    health_status['overall_health'] = False
                    
            except Exception as e:
                health_status['checks'][check_name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                health_status['overall_health'] = False
        
        health_status['status'] = 'healthy' if health_status['overall_health'] else 'unhealthy'
        return health_status
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            db = next(self.db_session_factory())
            db.execute(text("SELECT 1"))
            db.close()
            
            return {
                'healthy': True,
                'message': 'Database is accessible',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Database connection failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        disk_usage = psutil.disk_usage('/')
        free_percent = (disk_usage.free / disk_usage.total) * 100
        
        healthy = free_percent > 10  # Alert if less than 10% free space
        
        return {
            'healthy': healthy,
            'free_space_percent': free_percent,
            'free_space_gb': disk_usage.free / (1024**3),
            'message': f'Disk usage: {100 - free_percent:.1f}%',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage."""
        memory = psutil.virtual_memory()
        healthy = memory.percent < 90  # Alert if more than 90% used
        
        return {
            'healthy': healthy,
            'usage_percent': memory.percent,
            'available_gb': memory.available / (1024**3),
            'message': f'Memory usage: {memory.percent:.1f}%',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _check_ollama(self) -> Dict[str, Any]:
        """Check Ollama service availability."""
        import aiohttp
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{ollama_host}/api/version") as response:
                    if response.status == 200:
                        return {
                            'healthy': True,
                            'message': 'Ollama is responding',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            'healthy': False,
                            'message': f'Ollama returned status {response.status}',
                            'timestamp': datetime.utcnow().isoformat()
                        }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Ollama connection failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _check_chroma(self) -> Dict[str, Any]:
        """Check ChromaDB availability."""
        import aiohttp
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = os.getenv("CHROMA_PORT", "8000")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"http://{chroma_host}:{chroma_port}/api/v1/heartbeat") as response:
                    if response.status == 200:
                        return {
                            'healthy': True,
                            'message': 'ChromaDB is responding',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    else:
                        return {
                            'healthy': False,
                            'message': f'ChromaDB returned status {response.status}',
                            'timestamp': datetime.utcnow().isoformat()
                        }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'ChromaDB connection failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }

class AlertManager:
    """Manages alerts based on metrics and health checks."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.alert_thresholds = {
            'cpu_usage': 80,  # percentage
            'memory_usage': 85,  # percentage
            'disk_usage': 90,  # percentage
            'error_rate': 5,  # percentage
            'response_time': 5.0  # seconds
        }
        self.active_alerts = {}
    
    def check_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        current_time = datetime.utcnow()
        
        # Check system metrics
        system_metrics = metrics.get('system', {})
        
        if system_metrics.get('cpu_usage', 0) > self.alert_thresholds['cpu_usage']:
            alerts.append(self._create_alert(
                'high_cpu_usage',
                'High CPU Usage',
                f"CPU usage is {system_metrics['cpu_usage']:.1f}%",
                'warning'
            ))
        
        if system_metrics.get('memory_usage', 0) > self.alert_thresholds['memory_usage']:
            alerts.append(self._create_alert(
                'high_memory_usage',
                'High Memory Usage',
                f"Memory usage is {system_metrics['memory_usage']:.1f}%",
                'warning'
            ))
        
        if system_metrics.get('disk_usage', 0) > self.alert_thresholds['disk_usage']:
            alerts.append(self._create_alert(
                'high_disk_usage',
                'High Disk Usage',
                f"Disk usage is {system_metrics['disk_usage']:.1f}%",
                'critical'
            ))
        
        # Update active alerts
        for alert in alerts:
            alert_key = alert['type']
            self.active_alerts[alert_key] = alert
        
        # Clean up resolved alerts
        self._cleanup_resolved_alerts(metrics)
        
        return alerts
    
    def _create_alert(self, alert_type: str, title: str, message: str, severity: str) -> Dict[str, Any]:
        """Create an alert dictionary."""
        return {
            'type': alert_type,
            'title': title,
            'message': message,
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat(),
            'resolved': False
        }
    
    def _cleanup_resolved_alerts(self, metrics: Dict[str, Any]):
        """Remove alerts that are no longer active."""
        system_metrics = metrics.get('system', {})
        resolved_alerts = []
        
        for alert_key, alert in self.active_alerts.items():
            if alert_key == 'high_cpu_usage' and system_metrics.get('cpu_usage', 0) <= self.alert_thresholds['cpu_usage']:
                resolved_alerts.append(alert_key)
            elif alert_key == 'high_memory_usage' and system_metrics.get('memory_usage', 0) <= self.alert_thresholds['memory_usage']:
                resolved_alerts.append(alert_key)
            elif alert_key == 'high_disk_usage' and system_metrics.get('disk_usage', 0) <= self.alert_thresholds['disk_usage']:
                resolved_alerts.append(alert_key)
        
        for alert_key in resolved_alerts:
            del self.active_alerts[alert_key]
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

# Decorators for automatic metrics collection
def track_request_metrics(func):
    """Decorator to track HTTP request metrics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = args[0] if args else kwargs.get('request')
        method = request.method if request else 'UNKNOWN'
        path = request.url.path if request else 'unknown'
        
        start_time = time.time()
        
        try:
            response = await func(*args, **kwargs)
            status_code = getattr(response, 'status_code', 200)
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
            return response
        except Exception as e:
            REQUEST_COUNT.labels(method=method, endpoint=path, status_code=500).inc()
            ERROR_COUNT.labels(error_type=type(e).__name__, component='api').inc()
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)
    
    return wrapper

def track_query_metrics(query_type: str):
    """Decorator to track query processing metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                QUERY_COUNT.labels(query_type=query_type, success='true').inc()
                return result
            except Exception as e:
                QUERY_COUNT.labels(query_type=query_type, success='false').inc()
                ERROR_COUNT.labels(error_type=type(e).__name__, component='query').inc()
                raise
            finally:
                duration = time.time() - start_time
                QUERY_DURATION.labels(query_type=query_type).observe(duration)
        
        return wrapper
    return decorator

# Global instances
metrics_collector = None
performance_tracker = PerformanceTracker()
health_monitor = None
alert_manager = AlertManager()

def initialize_monitoring(db_session_factory):
    """Initialize monitoring components."""
    global metrics_collector, health_monitor
    
    metrics_collector = MetricsCollector(db_session_factory)
    health_monitor = HealthMonitor(db_session_factory)
    
    metrics_collector.start_collection()
    logger.info("Monitoring system initialized")

def shutdown_monitoring():
    """Shutdown monitoring components."""
    global metrics_collector
    
    if metrics_collector:
        metrics_collector.stop_collection()
    logger.info("Monitoring system shutdown")