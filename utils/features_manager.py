import os
import json
import time
from pathlib import Path
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class FeatureManager:
    def __init__(self, app):
        self.app = app
        self.global_config_path = Path(app.root_path) / 'config' / 'features.json'
        self._ensure_global_config()
        self.cache_timeout = 300  # 5 minutes
        self.last_load_time = {}
        self.feature_cache = {}
        
    def _ensure_global_config(self):
        """Ensure the global feature configuration file exists"""
        if not self.global_config_path.exists():
            logger.info(f"Creating default global feature configuration at {self.global_config_path}")
            os.makedirs(self.global_config_path.parent, exist_ok=True)
            default_config = {
                "features": {
                    "demand-projection": {"enabled": True, "description": "Demand projections"},
                    "load-curve": {"enabled": True, "description": "Load curve creation"}
                },
                "feature_groups": {
                    "basic": ["demand-projection", "load-curve"]
                }
            }
            with open(self.global_config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
    
    def _load_global_features(self):
        """Load the global feature configuration"""
        try:
            with open(self.global_config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading global features: {e}")
            return {"features": {}, "feature_groups": {}}
    
    def _load_project_features(self, project_path):
        """Load project-specific feature configuration"""
        if not project_path:
            return {"features": {}, "feature_groups": {}}
        
        project_config_path = Path(project_path) / 'config' / 'features.json'
        if not project_config_path.exists():
            return {"features": {}, "feature_groups": {}}
        
        try:
            with open(project_config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading project features from {project_config_path}: {e}")
            return {"features": {}, "feature_groups": {}}
    
    def _needs_reload(self, cache_key):
        """Check if the feature configuration needs to be reloaded"""
        if cache_key not in self.feature_cache:
            return True
        
        last_load = self.last_load_time.get(cache_key, 0)
        return time.time() - last_load > self.cache_timeout
    
    @lru_cache(maxsize=32)
    def get_merged_features(self, project_path=None):
        """Get merged feature configuration with caching"""
        cache_key = project_path or 'global'
        
        if self._needs_reload(cache_key):
            logger.debug(f"Loading feature configuration for {cache_key}")
            global_config = self._load_global_features()
            
            if project_path:
                project_config = self._load_project_features(project_path)
                
                # Merge project-specific features into global features
                merged_features = dict(global_config.get("features", {}))
                for feature_id, feature_config in project_config.get("features", {}).items():
                    if feature_id in merged_features:
                        merged_features[feature_id].update(feature_config)
                    else:
                        merged_features[feature_id] = feature_config
                
                # Merge feature groups
                merged_groups = dict(global_config.get("feature_groups", {}))
                for group_id, features in project_config.get("feature_groups", {}).items():
                    merged_groups[group_id] = features
                
                config = {
                    "features": merged_features,
                    "feature_groups": merged_groups
                }
            else:
                config = global_config
            
            self.feature_cache[cache_key] = config
            self.last_load_time[cache_key] = time.time()
        
        return self.feature_cache[cache_key]
    
    def is_feature_enabled(self, feature_id, project_path=None):
        """Check if a feature is enabled"""
        try:
            features = self.get_merged_features(project_path)
            feature_config = features.get("features", {}).get(feature_id)
            
            if not feature_config:
                logger.debug(f"Feature {feature_id} not found in configuration")
                return False
            
            return feature_config.get("enabled", False)
        except Exception as e:
            logger.exception(f"Error checking feature {feature_id}: {e}")
            return False
    
    def get_enabled_features(self, project_path=None):
        """Get a list of all enabled features"""
        features = self.get_merged_features(project_path)
        return [
            feature_id for feature_id, config in features.get("features", {}).items()
            if config.get("enabled", False)
        ]
    
    def set_feature_enabled(self, feature_id, enabled, project_path=None):
        """Enable or disable a feature"""
        if not project_path:
            config_path = self.global_config_path
        else:
            config_path = Path(project_path) / 'config' / 'features.json'
            os.makedirs(config_path.parent, exist_ok=True)
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {"features": {}, "feature_groups": {}}
            
            if feature_id not in config["features"]:
                config["features"][feature_id] = {}
            
            config["features"][feature_id]["enabled"] = enabled
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Clear cache
            cache_key = project_path or 'global'
            if cache_key in self.feature_cache:
                del self.feature_cache[cache_key]
            
            self.get_merged_features.cache_clear()
            
            return True
        except Exception as e:
            logger.exception(f"Error setting feature {feature_id} to {enabled}: {e}")
            return False