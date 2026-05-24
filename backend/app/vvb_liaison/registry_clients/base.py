"""Base registry client with retry logic and error handling."""

import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)


class RegistryClientError(Exception):
    """Base exception for registry API errors."""
    pass


class RegistryAuthenticationError(RegistryClientError):
    """Authentication failed."""
    pass


class RegistryAPIError(RegistryClientError):
    """API returned error status."""
    def __init__(self, message: str, status_code: int = None, response_body: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}


class BaseRegistryClient(ABC):
    """Base class for VVB registry API clients with retry and error handling."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=json_data,
                    params=params,
                )
                
                if response.status_code == 401:
                    raise RegistryAuthenticationError("Invalid API credentials")
                
                if response.status_code >= 500:
                    raise RegistryAPIError(
                        f"Server error: {response.status_code}",
                        status_code=response.status_code,
                    )
                
                response.raise_for_status()
                
                if response.status_code == 204:
                    return {"success": True}
                
                return response.json()
                
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "registry_request_retry",
                    url=url,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                
            except RegistryAuthenticationError:
                raise
            except httpx.HTTPStatusError as e:
                raise RegistryAPIError(
                    f"HTTP error: {e.response.status_code}",
                    status_code=e.response.status_code,
                    response_body=e.response.json() if e.response.text else {},
                )
        
        raise RegistryClientError(f"Max retries exceeded: {last_error}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("POST", endpoint, json_data=json_data)
    
    def close(self):
        self.client.close()
    
    @abstractmethod
    def submit_monitoring_report(self, project_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a monitoring report to the registry."""
        pass
    
    @abstractmethod
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get current project verification status."""
        pass
    
    @abstractmethod
    def get_verification_history(self, project_id: str) -> Dict[str, Any]:
        """Get verification history for a project."""
        pass
