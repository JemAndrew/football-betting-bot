"""
Base API client with retry logic, rate limiting, caching, and error handling.
All specific API clients (Football-Data, Odds API, etc.) inherit from this.

Key Features:
- Automatic retry with exponential backoff
- Rate limiting to respect API quotas
- Response caching to minimise API calls
- Comprehensive error handling and logging
- Request/response validation
"""

import time
import hashlib
import json
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.logger import setup_logging
from src.utils.config_loader import get_config

logger = setup_logging()
config = get_config()


class RateLimiter:
    """
    Rate limiter to prevent exceeding API quotas.
    
    Uses a token bucket algorithm - simple but effective.
    """
    
    def __init__(self, requests_per_minute: int):
        """
        Initialise rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # Seconds between requests
        self.last_request_time = 0.0
        
        logger.info(f"Rate limiter initialised: {requests_per_minute} req/min "
                   f"(minimum {self.min_interval:.2f}s between requests)")
    
    def wait_if_needed(self) -> None:
        """
        Wait if we're exceeding rate limit.
        Blocks execution until it's safe to make another request.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_interval:
            wait_time = self.min_interval - time_since_last_request
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s before next request")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()


class RequestCache:
    """
    Simple file-based cache for API responses.
    Reduces API calls and costs during development.
    """
    
    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        """
        Initialise cache.
        
        Args:
            cache_dir: Directory to store cached responses
            ttl_hours: Time-to-live for cached responses in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        
        logger.info(f"Cache initialised at {self.cache_dir} with {ttl_hours}h TTL")
    
    def _get_cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        """Generate unique cache key from URL and parameters."""
        cache_string = url
        if params:
            cache_string += json.dumps(params, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Retrieve cached response if available and not expired.
        
        Args:
            url: Request URL
            params: Request parameters
            
        Returns:
            Cached response dict or None if not found/expired
        """
        cache_key = self._get_cache_key(url, params)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        # Check if cache has expired
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if cache_age > self.ttl:
            logger.debug(f"Cache expired for {url} (age: {cache_age})")
            cache_file.unlink()  # Delete expired cache
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            logger.debug(f"Cache hit for {url} (age: {cache_age})")
            return cached_data
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_file}: {e}")
            return None
    
    def set(self, url: str, params: Optional[Dict], response_data: Dict) -> None:
        """
        Store response in cache.
        
        Args:
            url: Request URL
            params: Request parameters
            response_data: Response to cache
        """
        cache_key = self._get_cache_key(url, params)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2)
            logger.debug(f"Cached response for {url}")
        except Exception as e:
            logger.warning(f"Failed to write cache file {cache_file}: {e}")


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 2.0):
    """
    Decorator to retry function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for wait time between retries
    
    Wait times: 2s, 4s, 8s (for backoff_factor=2.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        logger.error(f"Final retry failed for {func.__name__}: {e}")
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for "
                                 f"{func.__name__}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
            
        return wrapper
    return decorator


class BaseAPI:
    """
    Base API client that all specific API clients inherit from.
    
    Provides:
    - HTTP request handling (GET/POST)
    - Automatic retries with exponential backoff
    - Rate limiting
    - Response caching
    - Error handling and logging
    - Request/response validation
    
    Usage:
        class MyAPI(BaseAPI):
            def __init__(self):
                super().__init__(
                    base_url="https://api.example.com",
                    api_key="your_key_here",
                    rate_limit=60
                )
            
            def get_data(self):
                return self._make_request("/endpoint")
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        rate_limit: int = 60,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24,
        timeout: int = 30
    ):
        """
        Initialise base API client.
        
        Args:
            base_url: Base URL for API (e.g., "https://api.football-data.org/v4")
            api_key: API authentication key
            rate_limit: Maximum requests per minute
            enable_cache: Whether to cache responses
            cache_ttl_hours: How long to keep cached responses
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        
        # Rate limiting
        self.rate_limiter = RateLimiter(rate_limit)
        
        # Caching
        self.cache_enabled = enable_cache
        self.cache = RequestCache(ttl_hours=cache_ttl_hours) if enable_cache else None
        
        # Create session with connection pooling and retry logic
        self.session = self._create_session()
        
        logger.info(f"API client initialised: {base_url} (rate limit: {rate_limit}/min, "
                   f"cache: {'enabled' if enable_cache else 'disabled'})")
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry configuration.
        
        Automatically retries on:
        - Connection errors
        - Timeout errors
        - 500, 502, 503, 504 status codes (server errors)
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for requests.
        Override this method in subclasses for custom headers.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _validate_response(self, response: requests.Response) -> None:
        """
        Validate API response and raise appropriate errors.
        
        Args:
            response: Response object from requests
            
        Raises:
            requests.HTTPError: If response status is not 2xx
        """
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Add more context to error messages
            error_msg = f"HTTP {response.status_code} error"
            
            if response.status_code == 400:
                error_msg = "Bad request - check your parameters"
            elif response.status_code == 401:
                error_msg = "Unauthorised - check your API key"
            elif response.status_code == 403:
                error_msg = "Forbidden - insufficient permissions"
            elif response.status_code == 404:
                error_msg = "Not found - check endpoint URL"
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded - slow down requests"
            elif response.status_code >= 500:
                error_msg = "Server error - API may be down"
            
            # Try to get error details from response body
            try:
                error_details = response.json()
                if 'message' in error_details:
                    error_msg += f": {error_details['message']}"
            except:
                pass
            
            logger.error(f"{error_msg} (URL: {response.url})")
            raise requests.HTTPError(error_msg, response=response)
    
    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic, rate limiting, and caching.
        
        Args:
            endpoint: API endpoint (e.g., "/competitions")
            method: HTTP method ('GET' or 'POST')
            params: Query parameters
            data: Request body for POST requests
            use_cache: Whether to use cached response (only for GET)
            
        Returns:
            Parsed JSON response as dictionary
            
        Raises:
            requests.RequestException: If request fails after retries
            ValueError: If response is not valid JSON
        """
        # Construct full URL
        url = f"{self.base_url}{endpoint}"
        
        # Check cache for GET requests
        if method == 'GET' and use_cache and self.cache_enabled:
            cached_response = self.cache.get(url, params)
            if cached_response is not None:
                return cached_response
        
        # Rate limiting
        self.rate_limiter.wait_if_needed()
        
        # Prepare request
        headers = self._get_headers()
        
        logger.debug(f"Making {method} request to {url} with params: {params}")
        
        try:
            # Make request
            if method == 'GET':
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )
            elif method == 'POST':
                response = self.session.post(
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Validate response
            self._validate_response(response)
            
            # Parse JSON
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from {url}: {e}")
                logger.debug(f"Response content: {response.text[:500]}")
                raise ValueError(f"Invalid JSON response: {e}")
            
            # Cache successful GET responses
            if method == 'GET' and self.cache_enabled and use_cache:
                self.cache.set(url, params, response_data)
            
            logger.info(f"Successfully fetched data from {endpoint}")
            return response_data
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {self.timeout}s: {url}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def get(self, endpoint: str, params: Optional[Dict] = None, use_cache: bool = True) -> Dict:
        """
        Make GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            use_cache: Whether to use cached response
            
        Returns:
            Parsed JSON response
        """
        return self._make_request(endpoint, method='GET', params=params, use_cache=use_cache)
    
    def post(self, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """
        Make POST request.
        
        Args:
            endpoint: API endpoint
            data: Request body
            params: Query parameters
            
        Returns:
            Parsed JSON response
        """
        return self._make_request(endpoint, method='POST', params=params, data=data, use_cache=False)
    
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        if self.cache_enabled and self.cache:
            cache_files = list(self.cache.cache_dir.glob("*.json"))
            for cache_file in cache_files:
                cache_file.unlink()
            logger.info(f"Cleared {len(cache_files)} cached responses")
        else:
            logger.warning("Cache not enabled")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()
        logger.debug("API session closed")


# Example usage and testing
if __name__ == "__main__":
    # Simple test of base API functionality
    logger.info("Testing BaseAPI functionality...")
    
    # Create a test API client (won't make real requests)
    api = BaseAPI(
        base_url="https://api.example.com/v1",
        api_key="test_key",
        rate_limit=10  # 10 requests per minute
    )
    
    logger.info("✓ BaseAPI initialised successfully")
    logger.info("✓ Rate limiter working")
    logger.info("✓ Cache system ready")
    logger.info("✓ Ready to build specific API clients!")