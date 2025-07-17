"""
Model availability checking for offline mode.
"""

import os
import logging
import requests
import json
from typing import Dict, Any, List, Tuple, Optional
import time

logger = logging.getLogger(__name__)

class ModelChecker:
    """Model availability checker for offline mode."""
    
    def __init__(self):
        """Initialize model checker."""
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        self.required_models = [
            os.getenv("MODEL_NAME", "gemma3:1b-it-qat"),
            os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        ]
        self.last_check_time = 0
        self.check_interval = 300  # Check model availability every 5 minutes
        self.model_status = {}
    
    def get_model_status(self, force_check: bool = False) -> Dict[str, Any]:
        """
        Get model availability status.
        
        Args:
            force_check: Force a new check regardless of cache
            
        Returns:
            Dict[str, Any]: Model status
        """
        # Check if we need to refresh status
        if force_check or not self.model_status or time.time() - self.last_check_time > self.check_interval:
            self._check_models()
            self.last_check_time = time.time()
        
        return {
            "models": self.model_status,
            "all_available": all(model["available"] for model in self.model_status.values()),
            "last_check_time": self.last_check_time
        }
    
    def _check_models(self) -> None:
        """Check availability of required models."""
        # First check if Ollama is available
        ollama_available, ollama_error = self._check_ollama_availability()
        
        if not ollama_available:
            # If Ollama is not available, mark all models as unavailable
            self.model_status = {
                model: {
                    "name": model,
                    "available": False,
                    "error": ollama_error or "Ollama service unavailable"
                }
                for model in self.required_models
            }
            return
        
        # Get list of available models
        available_models = self._get_available_models()
        
        # Check each required model
        self.model_status = {}
        for model in self.required_models:
            if model in available_models:
                self.model_status[model] = {
                    "name": model,
                    "available": True,
                    "size": available_models[model].get("size", "unknown"),
                    "modified_at": available_models[model].get("modified_at", "unknown")
                }
            else:
                self.model_status[model] = {
                    "name": model,
                    "available": False,
                    "error": "Model not found in Ollama"
                }
    
    def _check_ollama_availability(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Ollama is available.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_available, error_message)
        """
        try:
            response = requests.get(f"{self.ollama_host}/api/version", timeout=2)
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Ollama returned status code {response.status_code}"
        except requests.RequestException as e:
            return False, f"Failed to connect to Ollama: {str(e)}"
    
    def _get_available_models(self) -> Dict[str, Any]:
        """
        Get list of available models from Ollama.
        
        Returns:
            Dict[str, Any]: Available models
        """
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = {}
                for model in response.json().get("models", []):
                    models[model.get("name")] = model
                return models
            else:
                logger.error(f"Failed to get models: {response.status_code}")
                return {}
        except requests.RequestException as e:
            logger.error(f"Failed to get models: {str(e)}")
            return {}
    
    def pull_missing_models(self) -> Dict[str, Any]:
        """
        Pull missing models from Ollama.
        
        Returns:
            Dict[str, Any]: Pull status
        """
        # First check model status
        status = self.get_model_status(force_check=True)
        
        # Find missing models
        missing_models = [
            model for model, info in self.model_status.items()
            if not info["available"]
        ]
        
        # Pull missing models
        pull_results = {}
        for model in missing_models:
            try:
                logger.info(f"Pulling model: {model}")
                response = requests.post(
                    f"{self.ollama_host}/api/pull",
                    json={"model": model},
                    timeout=30  # Longer timeout for model pulling
                )
                
                if response.status_code == 200:
                    pull_results[model] = {
                        "success": True,
                        "message": f"Successfully pulled model: {model}"
                    }
                else:
                    pull_results[model] = {
                        "success": False,
                        "error": f"Failed to pull model: {response.status_code}"
                    }
            except requests.RequestException as e:
                pull_results[model] = {
                    "success": False,
                    "error": f"Failed to pull model: {str(e)}"
                }
        
        # Update model status
        self._check_models()
        
        return {
            "pull_results": pull_results,
            "updated_status": self.get_model_status()
        }