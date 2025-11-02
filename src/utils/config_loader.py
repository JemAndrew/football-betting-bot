"""
Configuration loader for the betting bot.

Loads configuration from YAML files and environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class ConfigLoader:
    """
    Load and manage application configuration.
    
    Loads configuration from:
    1. YAML files in config/
    2. Environment variables from .env
    3. Default values
    """
    
    def __init__(self, config_dir: str = "config", env_file: str = ".env"):
        """
        Initialise configuration loader.
        
        Args:
            config_dir: Directory containing YAML config files
            env_file: Path to .env file
        """
        self.config_dir = Path(config_dir)
        self.env_file = Path(env_file)
        
        # Load environment variables
        if self.env_file.exists():
            load_dotenv(self.env_file)
        else:
            print(f"Warning: {self.env_file} not found. Using environment variables only.")
        
        # Store loaded configs
        self.configs: Dict[str, Dict] = {}
        
        # Load all config files
        self._load_all_configs()
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML file.
        
        Args:
            filename: Name of YAML file (with or without .yaml extension)
        
        Returns:
            Dictionary of configuration values
        """
        if not filename.endswith('.yaml'):
            filename = f"{filename}.yaml"
        
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            print(f"Warning: Config file {filepath} not found. Using defaults.")
            return {}
        
        try:
            with open(filepath, 'r') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    
    def _load_all_configs(self):
        """Load all configuration files."""
        # Load each config file
        config_files = ['api_config', 'betting_config', 'leagues', 'model_config']
        
        for config_file in config_files:
            self.configs[config_file] = self._load_yaml(config_file)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Tries in order:
        1. Environment variable
        2. Config files
        3. Default value
        
        Args:
            key: Configuration key (can use dot notation: 'api.base_url')
            default: Default value if key not found
        
        Returns:
            Configuration value
        
        Example:
            >>> config.get('api.football_data.base_url')
            'https://api.football-data.org/v4'
        """
        # Try environment variable first (uppercase with underscores)
        env_key = key.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # Try config files
        if '.' in key:
            parts = key.split('.')
            value = self.configs
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return value
        
        # Simple key lookup across all configs
        for config in self.configs.values():
            if key in config:
                return config[key]
        
        return default
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return self.configs.get('api_config', {})
    
    def get_betting_config(self) -> Dict[str, Any]:
        """Get betting configuration."""
        return self.configs.get('betting_config', {})
    
    def get_leagues_config(self) -> Dict[str, Any]:
        """Get leagues configuration."""
        return self.configs.get('leagues', {})
    
    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration."""
        return self.configs.get('model_config', {})
    
    def get_database_url(self) -> str:
        """
        Get database connection URL.
        
        Returns:
            Database URL from environment or default
        """
        return os.getenv('DATABASE_URL', 'sqlite:///data/betting_bot.db')
    
    def get_log_level(self) -> str:
        """
        Get logging level.
        
        Returns:
            Log level from environment or default
        """
        return os.getenv('LOG_LEVEL', 'INFO')
    
    def get_log_dir(self) -> str:
        """
        Get log directory.
        
        Returns:
            Log directory path
        """
        return os.getenv('LOG_DIR', 'logs')
    
    def get_enabled_leagues(self) -> list:
        """
        Get list of enabled leagues.
        
        Returns:
            List of league IDs
        """
        leagues_config = self.get_leagues_config()
        return [
            league_id 
            for league_id, config in leagues_config.items() 
            if config.get('enabled', True)
        ]
    
    def reload(self):
        """Reload all configuration files."""
        self._load_all_configs()


# Global config instance
_config_instance: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """
    Get the global configuration instance.
    
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ConfigLoader()
    
    return _config_instance


def load_config(config_dir: str = "config", env_file: str = ".env") -> ConfigLoader:
    """
    Load configuration (convenience function).
    
    Args:
        config_dir: Directory containing config files
        env_file: Path to .env file
    
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    _config_instance = ConfigLoader(config_dir, env_file)
    return _config_instance


# Example usage
if __name__ == "__main__":
    # Load config
    config = load_config()
    
    # Access configuration
    print("Database URL:", config.get_database_url())
    print("Log Level:", config.get_log_level())
    print("Enabled Leagues:", config.get_enabled_leagues())
    
    # Access nested config with dot notation
    print("API Key:", config.get('api.football_data.key', 'NOT_SET'))
    
    # Access specific config sections
    print("\nAPI Config:", config.get_api_config())
    print("\nBetting Config:", config.get_betting_config())