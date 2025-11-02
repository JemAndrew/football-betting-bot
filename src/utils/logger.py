"""
Logging configuration for the betting bot.

Uses Loguru for structured, coloured logging with automatic rotation.
"""

import sys
import os
from pathlib import Path
from loguru import logger
from typing import Optional


class BettingLogger:
    """
    Centralised logging system for the betting bot.
    
    Features:
    - Coloured console output
    - File logging with rotation
    - Separate logs for different components
    - Structured logging with context
    """
    
    def __init__(
        self,
        log_dir: str = "logs",
        log_level: str = "INFO",
        rotation: str = "00:00",  # Rotate at midnight
        retention: str = "30 days",  # Keep logs for 30 days
        console_output: bool = True,
    ):
        """
        Initialise the logging system.
        
        Args:
            log_dir: Directory to store log files
            log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            rotation: When to rotate logs (time or size)
            retention: How long to keep old logs
            console_output: Whether to output to console
        """
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self.rotation = rotation
        self.retention = retention
        self.console_output = console_output
        
        # Create log directories
        self._create_log_directories()
        
        # Remove default logger
        logger.remove()
        
        # Configure loggers
        self._setup_console_logger()
        self._setup_file_loggers()
    
    def _create_log_directories(self):
        """Create log directory structure."""
        directories = [
            self.log_dir,
            self.log_dir / "api",
            self.log_dir / "models",
            self.log_dir / "bets",
            self.log_dir / "backtest",
            self.log_dir / "errors",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _setup_console_logger(self):
        """Set up coloured console output."""
        if self.console_output:
            logger.add(
                sys.stdout,
                level=self.log_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
                colorize=True,
            )
    
    def _setup_file_loggers(self):
        """Set up file-based logging with rotation."""
        # Main application log
        logger.add(
            self.log_dir / "app.log",
            level=self.log_level,
            rotation=self.rotation,
            retention=self.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            backtrace=True,
            diagnose=True,
        )
        
        # API calls log
        logger.add(
            self.log_dir / "api" / "api_{time:YYYY-MM-DD}.log",
            level="DEBUG",
            rotation=self.rotation,
            retention=self.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=lambda record: "api" in record["extra"],
        )
        
        # Model predictions log
        logger.add(
            self.log_dir / "models" / "predictions_{time:YYYY-MM-DD}.log",
            level="INFO",
            rotation=self.rotation,
            retention=self.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=lambda record: "model" in record["extra"],
        )
        
        # Betting decisions log
        logger.add(
            self.log_dir / "bets" / "bets_{time:YYYY-MM-DD}.log",
            level="INFO",
            rotation=self.rotation,
            retention=self.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=lambda record: "bet" in record["extra"],
        )
        
        # Error log (separate file for errors only)
        logger.add(
            self.log_dir / "errors" / "errors_{time:YYYY-MM-DD}.log",
            level="ERROR",
            rotation=self.rotation,
            retention=self.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            backtrace=True,
            diagnose=True,
        )
    
    @staticmethod
    def get_logger(component: str = "general"):
        """
        Get a logger for a specific component.
        
        Args:
            component: Component name (api, model, bet, etc.)
        
        Returns:
            Logger with component context
        """
        return logger.bind(component=component)


# Initialise default logger
def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    console_output: bool = True,
):
    """
    Set up logging for the application.
    
    Args:
        log_dir: Directory for log files
        log_level: Minimum log level
        console_output: Whether to output to console
    
    Returns:
        Configured logger instance
    """
    betting_logger = BettingLogger(
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output,
    )
    return betting_logger.get_logger()


# Convenience functions for different log types
def log_api_call(endpoint: str, status_code: int, response_time: float):
    """Log an API call with context."""
    logger.bind(api=True).info(
        f"API Call: {endpoint} | Status: {status_code} | Time: {response_time:.2f}s"
    )


def log_model_prediction(
    match_id: str,
    model_name: str,
    prediction: float,
    confidence: float,
):
    """Log a model prediction."""
    logger.bind(model=True).info(
        f"Prediction: Match {match_id} | Model: {model_name} | "
        f"Predicted: {prediction:.3f} | Confidence: {confidence:.2f}"
    )


def log_bet_decision(
    match_id: str,
    market: str,
    stake: float,
    odds: float,
    expected_value: float,
):
    """Log a betting decision."""
    logger.bind(bet=True).info(
        f"Bet Placed: Match {match_id} | Market: {market} | "
        f"Stake: £{stake:.2f} | Odds: {odds:.2f} | EV: {expected_value:.2%}"
    )


def log_bet_result(
    match_id: str,
    market: str,
    result: str,
    profit: float,
):
    """Log a bet result."""
    logger.bind(bet=True).info(
        f"Bet Result: Match {match_id} | Market: {market} | "
        f"Result: {result} | Profit: £{profit:.2f}"
    )


# Example usage
if __name__ == "__main__":
    # Set up logging
    app_logger = setup_logging(log_level="DEBUG")
    
    # Test different log types
    app_logger.debug("This is a debug message")
    app_logger.info("Application started successfully")
    app_logger.warning("This is a warning")
    app_logger.error("This is an error")
    
    # Test component-specific logging
    log_api_call("/fixtures", 200, 0.45)
    log_model_prediction("match_123", "poisson", 0.65, 0.82)
    log_bet_decision("match_123", "BTTS", 10.0, 1.95, 0.12)
    log_bet_result("match_123", "BTTS", "WON", 9.50)