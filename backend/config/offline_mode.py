"""
Offline mode configuration and detection.
"""

import os
import logging
import socket
import requests
from typing import Dict, Any, Optional, Tuple
import time

logger = logging.getLogger(__name__)

class OfflineModeManager:
    """Manager for offline mode configuration and detection."""
    
    def __init__(self):
        """Initialize offline mode manager."""
        self.offline_mode = os.getenv("OFFLINE_MODE", "auto").lower()
        self.last_check_time = 0
        self.check_interval = 60  # Check connectivity every 60 seconds
        self.is_offline = None  # None means not checked yet
        self.connectivity_endpoints = [
            "https://www.google.com",
            "https://www.cloudflare.com",
            "https://www.amazon.com"
        ]
    
    def get_offline_status(self) -> Dict[str, Any]:
        """
        Get current offline mode status.
        
        Returns:
            Dict[str, Any]: Offline mode status
        """
        # Check if we need to detect connectivity
        if self.offline_mode == "auto" and (
            self.is_offline is None or 
            time.time() - self.last_check_time > self.check_interval
        ):
            self.is_offline = not self._check_connectivity()
            self.last_check_time = time.time()
        elif self.offline_mode == "true" or self.offline_mode == "on":
            self.is_offline = True
        elif self.offline_mode == "false" or self.offline_mode == "off":
            self.is_offline = False
        
        return {
            "offline_mode": self.offline_mode,
            "is_offline": self.is_offline,
            "last_check_time": self.last_check_time
        }
    
    def set_offline_mode(self, mode: str) -> Dict[str, Any]:
        """
        Set offline mode.
        
        Args:
            mode: Offline mode ("auto", "true", "false")
            
        Returns:
            Dict[str, Any]: Updated offline mode status
        """
        if mode.lower() not in ["auto", "true", "false", "on", "off"]:
            raise ValueError("Invalid offline mode. Must be 'auto', 'true', or 'false'")
        
        self.offline_mode = mode.lower()
        
        # Update environment variable
        os.environ["OFFLINE_MODE"] = self.offline_mode
        
        # Reset status if mode changed
        if self.offline_mode == "auto":
            self.is_offline = None  # Force re-check
        elif self.offline_mode in ["true", "on"]:
            self.is_offline = True
        elif self.offline_mode in ["false", "off"]:
            self.is_offline = False
        
        return self.get_offline_status()
    
    def _check_connectivity(self) -> bool:
        """
        Check internet connectivity.
        
        Returns:
            bool: True if online, False if offline
        """
        # First check if we can resolve DNS
        try:
            socket.gethostbyname("www.google.com")
        except socket.gaierror:
            logger.info("DNS resolution failed, system appears to be offline")
            return False
        
        # Then try to connect to endpoints
        for endpoint in self.connectivity_endpoints:
            try:
                response = requests.get(endpoint, timeout=2)
                if response.status_code == 200:
                    logger.info(f"Successfully connected to {endpoint}, system is online")
                    return True
            except requests.RequestException:
                continue
        
        logger.info("Failed to connect to any endpoint, system appears to be offline")
        return False
    
    def check_ollama_availability(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Ollama is available.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_available, error_message)
        """
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=2)
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Ollama returned status code {response.status_code}"
        except requests.RequestException as e:
            return False, f"Failed to connect to Ollama: {str(e)}"
    
    def check_model_availability(self, model_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a specific model is available in Ollama.
        
        Args:
            model_name: Model name to check
            
        Returns:
            Tuple[bool, Optional[str]]: (is_available, error_message)
        """
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    if model.get("name") == model_name:
                        return True, None
                
                return False, f"Model '{model_name}' not found in Ollama"
            else:
                return False, f"Ollama returned status code {response.status_code}"
        except requests.RequestException as e:
            return False, f"Failed to connect to Ollama: {str(e)}"