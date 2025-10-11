"""
ITH REST API Client.
Handles all communication with the ITH backend API.
"""
import requests
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger('receiver.ith_client')


class IthAPIClient:
    """
    Client for ITH REST API.
    """

    def __init__(self, base_url: str, proxy_key: str, workspace_id: Optional[str] = None):
        """
        Initialize API client.

        Args:
            base_url: Base URL for API (e.g., http://localhost:8000)
            proxy_key: Proxy API key
            workspace_id: Workspace identifier (optional, only needed for data access endpoints)
        """
        self.base_url = base_url.rstrip('/')
        self.proxy_key = proxy_key
        self.workspace_id = workspace_id

        if proxy_key:
            self.headers = {'X-Proxy-Key': proxy_key}
            logger.info(f"API client initialized with proxy key: {proxy_key[:8]}...")
        else:
            self.headers = {}
            logger.warning("API client initialized without proxy key")

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def set_workspace_id(self, workspace_id: str):
        """Set workspace ID (typically obtained from WebSocket connection)."""
        self.workspace_id = workspace_id
        logger.info(f"API client workspace_id set to: {workspace_id}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        timeout: int = 1200  # 20 minutes default timeout
    ) -> requests.Response:
        """
        Make HTTP request to API.

        Args:
            method: HTTP method
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters
            json_data: JSON request body
            stream: Whether to stream response
            timeout: Request timeout in seconds (default: 1200 = 20 minutes)

        Returns:
            requests.Response: HTTP response

        Raises:
            requests.HTTPError: On HTTP error
        """
        url = f"{self.base_url}{endpoint}"

        logger.debug(f"{method} {url}")

        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_data,
                stream=stream,
                timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout after {timeout} seconds: {e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    # ==================== Proxy Configuration ====================

    def get_proxy_configuration(self) -> Optional[Dict[str, Any]]:
        """
        Get proxy configuration from API.

        Endpoint: GET /api/v1/proxy/configuration
        Authentication: X-Proxy-Key header

        Returns:
            dict: Proxy configuration or None if failed
        """
        endpoint = "/api/v1/proxy/configuration"

        try:
            response = self._request("GET", endpoint)
            config_data = response.json()
            logger.info(f"Retrieved proxy configuration: {config_data.get('name')}")
            return config_data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Invalid proxy key - authentication failed")
            elif e.response.status_code == 403:
                logger.error("Proxy is inactive or access denied")
            elif e.response.status_code == 404:
                logger.error("Proxy not found")
            else:
                logger.error(f"HTTP error fetching configuration: {e}")
            return None

        except Exception as e:
            logger.error(f"Error fetching proxy configuration: {e}", exc_info=True)
            return None

    # ==================== Subjects ====================

    def list_subjects(self, **filters) -> Dict[str, Any]:
        """
        List all subjects in workspace.

        Args:
            **filters: Optional filters (species, search_query, etc.)

        Returns:
            dict: Response with subjects list
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/subjects"
        response = self._request("GET", endpoint, params=filters)
        return response.json()

    def get_subject(self, subject_id: str, include_deleted: bool = False) -> Dict[str, Any]:
        """
        Get specific subject by ID.

        Args:
            subject_id: Subject identifier
            include_deleted: Include if soft-deleted

        Returns:
            dict: Subject data
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/subjects/{subject_id}"
        params = {'include_deleted': include_deleted} if include_deleted else None
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def download_subject(
        self,
        subject_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Download subject archive with optional progress reporting.

        Args:
            subject_id: Subject identifier
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path: Path to downloaded file
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/subjects/{subject_id}/download"
        params = {
            'compression_format': compression_format,
            'compression_level': compression_level
        }

        response = self._request("GET", endpoint, params=params, stream=True)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_downloaded += len(chunk)

                if progress_callback:
                    progress_callback(bytes_downloaded, total_size)

        logger.info(f"Downloaded subject {subject_id} to {output_path}")
        return output_path

    # ==================== Sessions ====================

    def list_sessions(self, **filters) -> Dict[str, Any]:
        """
        List all sessions in workspace.

        Args:
            **filters: Optional filters (subject_id, modality, etc.)

        Returns:
            dict: Response with sessions list
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/sessions"
        response = self._request("GET", endpoint, params=filters)
        return response.json()

    def get_session(self, session_id: str, include_deleted: bool = False) -> Dict[str, Any]:
        """
        Get specific session by ID.

        Args:
            session_id: Session identifier
            include_deleted: Include if soft-deleted

        Returns:
            dict: Session data
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/sessions/{session_id}"
        params = {'include_deleted': include_deleted} if include_deleted else None
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def download_session(
        self,
        session_id: str,
        subject_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Download session archive with optional progress reporting.

        Args:
            session_id: Session identifier
            subject_id: Parent subject ID
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path: Path to downloaded file
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/sessions/{session_id}/download"
        params = {
            'subject_id': subject_id,
            'compression_format': compression_format,
            'compression_level': compression_level
        }

        response = self._request("GET", endpoint, params=params, stream=True)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_downloaded += len(chunk)

                if progress_callback:
                    progress_callback(bytes_downloaded, total_size)

        logger.info(f"Downloaded session {session_id} to {output_path}")
        return output_path

    # ==================== Scans ====================

    def list_scans(self, subject_id: str, session_id: str, **filters) -> Dict[str, Any]:
        """
        List all scans for a session.

        Args:
            subject_id: Subject ID
            session_id: Session ID
            **filters: Optional filters (modality, quality, etc.)

        Returns:
            dict: Response with scans list
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/scans"
        params = {
            'subject_id': subject_id,
            'session_id': session_id,
            **filters
        }
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def get_scan(self, scan_id: str, include_deleted: bool = False) -> Dict[str, Any]:
        """
        Get specific scan by ID.

        Args:
            scan_id: Scan identifier
            include_deleted: Include if soft-deleted

        Returns:
            dict: Scan data
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/scans/{scan_id}"
        params = {'include_deleted': include_deleted} if include_deleted else None
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def download_scan(
        self,
        scan_id: str,
        subject_id: str,
        session_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Download scan archive with optional progress reporting.

        Args:
            scan_id: Scan identifier
            subject_id: Parent subject ID
            session_id: Parent session ID
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path: Path to downloaded file
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/scans/{scan_id}/download"
        params = {
            'subject_id': subject_id,
            'session_id': session_id,
            'compression_format': compression_format,
            'compression_level': compression_level
        }

        response = self._request("GET", endpoint, params=params, stream=True)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_downloaded += len(chunk)

                if progress_callback:
                    progress_callback(bytes_downloaded, total_size)

        logger.info(f"Downloaded scan {scan_id} to {output_path}")
        return output_path

    # ==================== Archives ====================

    def create_archive(
        self,
        archive_name: str,
        entity_selections: List[Dict[str, Any]],
        compression_format: str = 'zip',
        compression_level: int = 6
    ) -> Dict[str, Any]:
        """
        Create custom archive.

        Args:
            archive_name: Name for the archive
            entity_selections: List of entities to include
            compression_format: zip or tar.gz
            compression_level: 0-9

        Returns:
            dict: Archive creation response with archive_id
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/archives"
        data = {
            'archive_name': archive_name,
            'entity_selections': entity_selections,
            'compression_format': compression_format,
            'compression_level': compression_level
        }

        response = self._request("POST", endpoint, json_data=data)
        return response.json()

    def get_archive_status(self, archive_id: str) -> Dict[str, Any]:
        """
        Get archive creation status.

        Args:
            archive_id: Archive identifier

        Returns:
            dict: Archive status
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/archives/{archive_id}"
        response = self._request("GET", endpoint)
        return response.json()

    def download_archive(self, archive_id: str, output_path: Path) -> Path:
        """
        Download completed archive.

        Args:
            archive_id: Archive identifier
            output_path: Path to save archive

        Returns:
            Path: Path to downloaded file
        """
        endpoint = f"/api/v1/proxy/{self.workspace_id}/archives/{archive_id}/download"
        response = self._request("GET", endpoint, stream=True)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded archive {archive_id} to {output_path}")
        return output_path
