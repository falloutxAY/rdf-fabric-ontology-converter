"""
Centralized input validation utilities for the RDF/DTDL Fabric Ontology Converter.

This module provides shared input validation with consistent error messages for:
- TTL content validation
- File path validation with security checks
- Parameter type and value checking

Security features:
- Path traversal detection (../ sequences)
- Symlink detection and warning
- Extension validation
- Directory boundary awareness

Usage:
    from core.validators import InputValidator
    
    # Validate file path with security checks
    validated_path = InputValidator.validate_file_path(
        path, 
        allowed_extensions=['.ttl', '.rdf'],
        check_exists=True
    )
    
    # Validate TTL content
    content = InputValidator.validate_ttl_content(content)
"""

import os
import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class InputValidator:
    """
    Centralized input validation for RDF converter public methods.
    
    Provides consistent validation with clear error messages for:
    - TTL content validation
    - File path validation with security checks
    - Parameter type and value checking
    
    Security features:
    - Path traversal detection (../ sequences)
    - Symlink detection and warning
    - Extension validation
    - Directory boundary awareness
    """
    
    # Allowed extensions for different file types
    TTL_EXTENSIONS = ['.ttl', '.rdf', '.owl', '.n3', '.nt', '.nq', '.trig']
    JSON_EXTENSIONS = ['.json']
    OUTPUT_EXTENSIONS = ['.ttl', '.json', '.txt', '.md']
    
    @staticmethod
    def validate_ttl_content(content: Any) -> str:
        """
        Validate TTL content parameter.
        
        Args:
            content: Content to validate (should be non-empty string)
            
        Returns:
            Validated content string
            
        Raises:
            ValueError: If content is None or empty
            TypeError: If content is not a string
        """
        if content is None:
            raise ValueError("TTL content cannot be None")
        
        if not isinstance(content, str):
            raise TypeError(f"TTL content must be string, got {type(content).__name__}")
        
        if not content.strip():
            raise ValueError("TTL content cannot be empty or whitespace-only")
        
        return content
    
    @staticmethod
    def _check_path_traversal(path_str: str) -> None:
        """
        Check for path traversal attempts.
        
        Args:
            path_str: Path string to check
            
        Raises:
            ValueError: If path traversal detected
        """
        # Normalize separators for consistent checking
        normalized = path_str.replace('\\', '/')
        
        # Check for obvious traversal patterns
        traversal_patterns = ['../', '..\\', '/..', '\\..']
        for pattern in traversal_patterns:
            if pattern in path_str or pattern in normalized:
                raise ValueError(
                    f"Path traversal detected in path: {path_str}. "
                    f"Paths containing '..' are not allowed for security reasons."
                )
        
        # Also check if resolved path contains '..' components
        try:
            path_obj = Path(path_str)
            # Check each component
            for part in path_obj.parts:
                if part == '..':
                    raise ValueError(
                        f"Path traversal detected in path: {path_str}. "
                        f"Paths containing '..' components are not allowed."
                    )
        except Exception:
            pass  # If Path parsing fails, let later validation catch it
    
    @staticmethod
    def _check_symlink(path_obj: Path, strict: bool = False) -> None:
        """
        Check if path is a symlink.
        
        Args:
            path_obj: Path object to check
            strict: If True, raise exception on symlink; if False, log warning
            
        Raises:
            ValueError: If symlink detected and strict mode enabled
        """
        try:
            if path_obj.is_symlink():
                msg = (
                    f"Security error: Symlink detected: {path_obj}. "
                    f"Symlinks are not allowed for security reasons. "
                    f"Please use the actual file path instead."
                )
                if strict:
                    raise ValueError(msg)
                else:
                    logger.warning(msg)
        except OSError:
            # Some systems may raise OSError when checking symlinks
            if strict:
                raise ValueError(f"Cannot verify symlink status for: {path_obj}")
            pass  # Ignore errors in symlink detection in non-strict mode
    
    @staticmethod
    def _check_directory_boundary(path_obj: Path, warn_only: bool = True) -> None:
        """
        Check if path is outside current working directory.
        
        Args:
            path_obj: Resolved absolute path to check
            warn_only: If True, only log warning; if False, raise exception
        """
        try:
            cwd = Path.cwd().resolve()
            path_obj.relative_to(cwd)
        except ValueError:
            msg = f"Path is outside current directory: {path_obj}"
            if warn_only:
                logger.warning(msg + " (this may be intentional for absolute paths)")
            else:
                raise ValueError(msg + ". Access to paths outside working directory is restricted.")
    
    @classmethod
    def validate_file_path(
        cls, 
        path: Any, 
        allowed_extensions: Optional[List[str]] = None,
        check_exists: bool = True,
        check_readable: bool = True,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate file path for security and correctness.
        
        Security checks performed:
        - Path traversal detection (../)
        - Symlink detection (configurable: warning or hard reject)
        - Directory boundary check (optional enforcement)
        - Extension validation (optional)
        
        Args:
            path: Path to validate (should be non-empty string)
            allowed_extensions: List of allowed extensions (e.g., ['.ttl', '.rdf'])
            check_exists: Whether to verify file exists
            check_readable: Whether to verify file is readable
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks; if False, warn only
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object (resolved to absolute path)
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, traversal detected, or symlink found (if reject_symlinks=True)
            FileNotFoundError: If file doesn't exist (when check_exists=True)
            PermissionError: If file is not readable (when check_readable=True)
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal BEFORE resolving
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                # Also check parts for '..'
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    # Fall back to strict traversal check
                    pass
        if not allow_relative_up:
            # Original strict check
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks (strict by default for input files)
        cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            # Enforce that relative-up stays within cwd
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Existence check
        if check_exists:
            if not path_obj.exists():
                raise FileNotFoundError(f"File not found: {path_obj}")
            
            if not path_obj.is_file():
                raise ValueError(f"Path is not a file: {path_obj}")
        
        # Extension validation
        if allowed_extensions:
            # Normalize extensions to lowercase with leading dot
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Readability check
        if check_readable and check_exists:
            if not os.access(path_obj, os.R_OK):
                raise PermissionError(f"File is not readable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_input_ttl_path(
        cls, 
        path: Any, 
        restrict_to_cwd: bool = False, 
        reject_symlinks: bool = True, 
        allow_relative_up: bool = False
    ) -> Path:
        """
        Validate input TTL/RDF file path.
        
        Convenience method with TTL-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to TTL file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.TTL_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_input_json_path(
        cls, 
        path: Any, 
        restrict_to_cwd: bool = False, 
        reject_symlinks: bool = True, 
        allow_relative_up: bool = False
    ) -> Path:
        """
        Validate input JSON file path.
        
        Convenience method with JSON-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to JSON file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_output_file_path(
        cls, 
        path: Any,
        allowed_extensions: Optional[List[str]] = None,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate output file path for writing.
        
        Similar to validate_file_path but:
        - Does not require file to exist
        - Validates parent directory exists and is writable
        
        Args:
            path: Path for output file
            allowed_extensions: List of allowed extensions
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception if output target is symlink
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, or traversal detected
            PermissionError: If parent directory is not writable
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    pass
        if not allow_relative_up:
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks if file exists
        if path_obj.exists():
            cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Extension validation
        if allowed_extensions:
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Check parent directory exists and is writable
        parent_dir = path_obj.parent
        if not parent_dir.exists():
            raise ValueError(f"Parent directory does not exist: {parent_dir}")
        
        if not os.access(parent_dir, os.W_OK):
            raise PermissionError(f"Cannot write to directory: {parent_dir}")
        
        # If file exists, check it's writable
        if path_obj.exists() and not os.access(path_obj, os.W_OK):
            raise PermissionError(f"File exists but is not writable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_config_file_path(cls, path: Any) -> Path:
        """
        Validate configuration file path.
        
        Configuration files have stricter validation:
        - Must be JSON
        - Must be readable
        - Must be in safe location (within cwd)
        - Symlinks are rejected
        
        Args:
            path: Path to config file
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is invalid or outside current directory
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable or symlink detected
        """
        validated_path = cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=True,  # Strict: config must be in cwd
            reject_symlinks=True   # Hard reject symlinks
        )
        
        return validated_path
    
    @staticmethod
    def validate_id_prefix(prefix: Any) -> int:
        """
        Validate ID prefix parameter.
        
        Args:
            prefix: Prefix to validate (should be non-negative integer)
            
        Returns:
            Validated prefix integer
            
        Raises:
            TypeError: If prefix is not an integer
            ValueError: If prefix is negative
        """
        if not isinstance(prefix, int):
            raise TypeError(f"ID prefix must be integer, got {type(prefix).__name__}")
        
        if prefix < 0:
            raise ValueError(f"ID prefix must be non-negative, got {prefix}")
        
        return prefix


class URLValidator:
    """
    SSRF (Server-Side Request Forgery) protection for URL handling.
    
    Provides validation for URLs to prevent SSRF attacks when loading
    remote ontology files or making HTTP requests.
    
    Security features:
    - Protocol validation (only https allowed by default)
    - Private IP address blocking
    - Domain allowlist support
    - Port restriction
    
    Usage:
        from core.validators import URLValidator
        
        # Basic validation
        validated_url = URLValidator.validate_url(url)
        
        # With allowlist
        validated_url = URLValidator.validate_url(
            url,
            allowed_domains=['example.com', 'trusted.org']
        )
    """
    
    # Private IPv4 address ranges (RFC 1918, RFC 5735)
    PRIVATE_IPV4_RANGES = [
        ('10.0.0.0', '10.255.255.255'),       # Class A private
        ('172.16.0.0', '172.31.255.255'),     # Class B private  
        ('192.168.0.0', '192.168.255.255'),   # Class C private
        ('127.0.0.0', '127.255.255.255'),     # Loopback
        ('169.254.0.0', '169.254.255.255'),   # Link-local
        ('0.0.0.0', '0.255.255.255'),         # Current network
        ('100.64.0.0', '100.127.255.255'),    # Shared address space
        ('192.0.0.0', '192.0.0.255'),         # IETF protocol assignments
        ('192.0.2.0', '192.0.2.255'),         # TEST-NET-1
        ('198.51.100.0', '198.51.100.255'),   # TEST-NET-2
        ('203.0.113.0', '203.0.113.255'),     # TEST-NET-3
        ('224.0.0.0', '239.255.255.255'),     # Multicast
        ('240.0.0.0', '255.255.255.255'),     # Reserved/Broadcast
    ]
    
    # Private IPv6 patterns
    PRIVATE_IPV6_PATTERNS = [
        '::1',          # Loopback
        'fe80:',        # Link-local
        'fc00:',        # Unique local (ULA)
        'fd00:',        # Unique local (ULA)
        'ff00:',        # Multicast
    ]
    
    # Default allowed protocols
    DEFAULT_ALLOWED_PROTOCOLS = ['https']
    
    # Default allowed ports
    DEFAULT_ALLOWED_PORTS = [443, 8443]
    
    @classmethod
    def _ip_to_int(cls, ip: str) -> int:
        """Convert IPv4 address string to integer for range comparison."""
        parts = ip.split('.')
        return sum(int(part) << (8 * (3 - i)) for i, part in enumerate(parts))
    
    @classmethod
    def _is_private_ipv4(cls, ip: str) -> bool:
        """Check if IPv4 address is in a private range."""
        try:
            ip_int = cls._ip_to_int(ip)
            for start, end in cls.PRIVATE_IPV4_RANGES:
                if cls._ip_to_int(start) <= ip_int <= cls._ip_to_int(end):
                    return True
            return False
        except (ValueError, AttributeError):
            return False
    
    @classmethod
    def _is_private_ipv6(cls, ip: str) -> bool:
        """Check if IPv6 address is private/reserved."""
        ip_lower = ip.lower()
        for pattern in cls.PRIVATE_IPV6_PATTERNS:
            if ip_lower.startswith(pattern.lower()):
                return True
        return False
    
    @classmethod
    def _is_private_ip(cls, hostname: str) -> bool:
        """Check if hostname is a private IP address."""
        import socket
        
        # Try to resolve hostname to IP
        try:
            # Check if it's already an IP address
            socket.inet_aton(hostname)
            return cls._is_private_ipv4(hostname)
        except socket.error:
            pass
        
        # Check IPv6
        try:
            socket.inet_pton(socket.AF_INET6, hostname)
            return cls._is_private_ipv6(hostname)
        except socket.error:
            pass
        
        # It's a hostname, try to resolve it
        try:
            info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in info:
                ip = sockaddr[0]
                if family == socket.AF_INET and cls._is_private_ipv4(ip):
                    return True
                elif family == socket.AF_INET6 and cls._is_private_ipv6(ip):
                    return True
        except socket.gaierror:
            # DNS resolution failed - treat as potentially unsafe
            logger.warning(f"Could not resolve hostname: {hostname}")
            pass
        
        return False
    
    @classmethod
    def validate_url(
        cls,
        url: Any,
        allowed_protocols: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None,
        allowed_ports: Optional[List[int]] = None,
        allow_private_ips: bool = False,
        check_dns: bool = True,
    ) -> str:
        """
        Validate a URL with SSRF protection.
        
        Security checks performed:
        - Protocol validation (https only by default)
        - Private IP blocking (prevents access to internal network)
        - Domain allowlist support
        - Port restriction
        
        Args:
            url: URL to validate
            allowed_protocols: List of allowed protocols (default: ['https'])
            allowed_domains: Optional list of allowed domains (empty = all public domains allowed)
            allowed_ports: List of allowed ports (default: [443, 8443])
            allow_private_ips: If True, allow private/internal IP addresses
            check_dns: If True, resolve hostname and check if it points to private IP
            
        Returns:
            Validated URL string
            
        Raises:
            TypeError: If URL is not a string
            ValueError: If URL is invalid, uses disallowed protocol, domain, or port
            SecurityError (ValueError subclass): If URL points to private IP
        """
        from urllib.parse import urlparse
        
        # Type check
        if not isinstance(url, str):
            raise TypeError(f"URL must be string, got {type(url).__name__}")
        
        # Empty check
        url = url.strip()
        if not url:
            raise ValueError("URL cannot be empty")
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        # Validate scheme/protocol
        if allowed_protocols is None:
            allowed_protocols = cls.DEFAULT_ALLOWED_PROTOCOLS
        
        allowed_protocols_lower = [p.lower() for p in allowed_protocols]
        
        if not parsed.scheme:
            raise ValueError("URL must include protocol scheme (e.g., https://)")
        
        if parsed.scheme.lower() not in allowed_protocols_lower:
            raise ValueError(
                f"URL protocol '{parsed.scheme}' not allowed. "
                f"Allowed protocols: {', '.join(allowed_protocols)}"
            )
        
        # Validate hostname
        if not parsed.hostname:
            raise ValueError("URL must include a hostname")
        
        hostname = parsed.hostname.lower()
        
        # Check for localhost variants
        localhost_variants = ['localhost', 'localhost.localdomain', '127.0.0.1', '::1', '0.0.0.0']
        if hostname in localhost_variants:
            if not allow_private_ips:
                raise ValueError(
                    f"SSRF Protection: Access to localhost ({hostname}) is not allowed. "
                    f"This could be an attempt to access internal services."
                )
        
        # Validate domain allowlist
        if allowed_domains:
            allowed_domains_lower = [d.lower() for d in allowed_domains]
            domain_allowed = False
            
            for domain in allowed_domains_lower:
                if hostname == domain or hostname.endswith(f".{domain}"):
                    domain_allowed = True
                    break
            
            if not domain_allowed:
                raise ValueError(
                    f"Domain '{hostname}' not in allowed list. "
                    f"Allowed domains: {', '.join(allowed_domains)}"
                )
        
        # Validate port
        port = parsed.port
        if port is None:
            # Use default port based on scheme
            port = 443 if parsed.scheme.lower() == 'https' else 80
        
        if allowed_ports is None:
            allowed_ports = cls.DEFAULT_ALLOWED_PORTS
        
        if port not in allowed_ports:
            raise ValueError(
                f"Port {port} not allowed. Allowed ports: {', '.join(map(str, allowed_ports))}"
            )
        
        # Check for private IP (SSRF protection)
        if not allow_private_ips and check_dns:
            if cls._is_private_ip(hostname):
                raise ValueError(
                    f"SSRF Protection: URL points to private/internal IP address. "
                    f"Access to internal network resources is not allowed. "
                    f"Hostname: {hostname}"
                )
        
        return url
    
    @classmethod
    def validate_ontology_url(
        cls,
        url: Any,
        allowed_domains: Optional[List[str]] = None,
    ) -> str:
        """
        Validate an ontology URL with strict SSRF protection.
        
        Specifically designed for loading remote ontology files.
        Only allows HTTPS from public domains.
        
        Args:
            url: URL to validate
            allowed_domains: Optional list of trusted domains for ontology files
            
        Returns:
            Validated URL string
            
        Raises:
            TypeError: If URL is not a string
            ValueError: If URL fails security validation
        """
        # Default trusted domains for ontology files
        default_ontology_domains = [
            'w3.org',                 # W3C standards
            'purl.org',               # Persistent URLs
            'schema.org',             # Schema.org
            'xmlns.com',              # XML namespaces
            'github.com',             # GitHub
            'raw.githubusercontent.com',  # GitHub raw files
        ]
        
        if allowed_domains is None:
            allowed_domains = default_ontology_domains
        
        return cls.validate_url(
            url,
            allowed_protocols=['https'],
            allowed_domains=allowed_domains,
            allowed_ports=[443],
            allow_private_ips=False,
            check_dns=True,
        )
    
    @classmethod
    def is_url(cls, value: str) -> bool:
        """
        Check if a string looks like a URL.
        
        Args:
            value: String to check
            
        Returns:
            True if the string appears to be a URL
        """
        if not isinstance(value, str):
            return False
        
        value = value.strip().lower()
        return value.startswith(('http://', 'https://', 'ftp://'))
    
    @classmethod
    def sanitize_url_for_logging(cls, url: str) -> str:
        """
        Remove sensitive parts from URL for safe logging.
        
        Args:
            url: URL to sanitize
            
        Returns:
            URL with credentials and query params removed
        """
        from urllib.parse import urlparse, urlunparse
        
        try:
            parsed = urlparse(url)
            # Remove username, password, and query string
            sanitized = parsed._replace(
                netloc=parsed.hostname or '',
                query='',
                fragment=''
            )
            return urlunparse(sanitized)
        except Exception:
            return "[URL sanitization failed]"


class ValidationRateLimiter:
    """
    Rate limiter and resource guard for local validation operations.
    
    Provides protection against resource exhaustion attacks by limiting:
    - Number of validation requests per time period
    - Maximum content size per validation
    - Maximum concurrent validations
    - Memory usage during validation
    
    This is useful when exposing validation as a service or endpoint,
    preventing denial-of-service through excessive validation requests.
    
    Usage:
        from core.validators import ValidationRateLimiter
        
        # Create limiter with default settings
        limiter = ValidationRateLimiter()
        
        # Check if validation is allowed
        allowed, reason = limiter.check_validation_allowed(content)
        if not allowed:
            raise ValueError(f"Validation not allowed: {reason}")
        
        # Use context manager for automatic tracking
        with limiter.validation_context() as ctx:
            if not ctx.allowed:
                raise ValueError(ctx.reason)
            # Perform validation
            result = validate_content(content)
    """
    
    # Default configuration
    DEFAULT_REQUESTS_PER_MINUTE = 30
    DEFAULT_MAX_CONTENT_SIZE_MB = 50
    DEFAULT_MAX_CONCURRENT = 5
    DEFAULT_MAX_MEMORY_PERCENT = 80
    
    def __init__(
        self,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        max_content_size_mb: float = DEFAULT_MAX_CONTENT_SIZE_MB,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        max_memory_percent: float = DEFAULT_MAX_MEMORY_PERCENT,
        enabled: bool = True,
    ):
        """
        Initialize the validation rate limiter.
        
        Args:
            requests_per_minute: Maximum validation requests per minute
            max_content_size_mb: Maximum content size in MB for single validation
            max_concurrent: Maximum concurrent validation operations
            max_memory_percent: Maximum system memory usage percent before rejecting
            enabled: Whether rate limiting is enabled
        """
        import threading
        
        self.requests_per_minute = requests_per_minute
        self.max_content_size_mb = max_content_size_mb
        self.max_concurrent = max_concurrent
        self.max_memory_percent = max_memory_percent
        self.enabled = enabled
        
        # Internal state
        self._lock = threading.Lock()
        self._request_times: List[float] = []
        self._concurrent_count = 0
        
        # Statistics
        self._total_validations = 0
        self._rejected_rate_limit = 0
        self._rejected_size = 0
        self._rejected_memory = 0
        self._rejected_concurrent = 0
    
    def _cleanup_old_requests(self) -> None:
        """Remove request timestamps older than 1 minute."""
        import time
        cutoff = time.time() - 60
        self._request_times = [t for t in self._request_times if t > cutoff]
    
    def _get_memory_percent(self) -> float:
        """Get current system memory usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            # psutil not available - assume safe
            return 0.0
        except Exception:
            # Error getting memory - assume safe
            return 0.0
    
    def _get_content_size_mb(self, content: str) -> float:
        """Get content size in MB."""
        return len(content.encode('utf-8')) / (1024 * 1024)
    
    def check_rate_limit(self) -> tuple:
        """
        Check if request rate is within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Rate limiting disabled"
        
        import time
        
        with self._lock:
            self._cleanup_old_requests()
            
            if len(self._request_times) >= self.requests_per_minute:
                oldest = self._request_times[0]
                wait_time = 60 - (time.time() - oldest)
                return False, f"Rate limit exceeded. Try again in {wait_time:.1f} seconds"
            
            return True, "Within rate limit"
    
    def check_content_size(self, content: str) -> tuple:
        """
        Check if content size is within limits.
        
        Args:
            content: Content to validate
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Size limiting disabled"
        
        size_mb = self._get_content_size_mb(content)
        
        if size_mb > self.max_content_size_mb:
            return False, (
                f"Content size ({size_mb:.2f} MB) exceeds maximum "
                f"({self.max_content_size_mb} MB)"
            )
        
        return True, f"Content size OK ({size_mb:.2f} MB)"
    
    def check_memory(self) -> tuple:
        """
        Check if system memory is within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Memory limiting disabled"
        
        memory_percent = self._get_memory_percent()
        
        if memory_percent > self.max_memory_percent:
            return False, (
                f"System memory usage ({memory_percent:.1f}%) exceeds maximum "
                f"({self.max_memory_percent}%). Try again later."
            )
        
        return True, f"Memory OK ({memory_percent:.1f}%)"
    
    def check_concurrent(self) -> tuple:
        """
        Check if concurrent validations are within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Concurrent limiting disabled"
        
        with self._lock:
            if self._concurrent_count >= self.max_concurrent:
                return False, (
                    f"Maximum concurrent validations ({self.max_concurrent}) reached. "
                    f"Try again later."
                )
            
            return True, f"Concurrent OK ({self._concurrent_count}/{self.max_concurrent})"
    
    def check_validation_allowed(self, content: str) -> tuple:
        """
        Check all limits for validation.
        
        Args:
            content: Content to validate
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check rate limit
        allowed, reason = self.check_rate_limit()
        if not allowed:
            with self._lock:
                self._rejected_rate_limit += 1
            return False, reason
        
        # Check content size
        allowed, reason = self.check_content_size(content)
        if not allowed:
            with self._lock:
                self._rejected_size += 1
            return False, reason
        
        # Check memory
        allowed, reason = self.check_memory()
        if not allowed:
            with self._lock:
                self._rejected_memory += 1
            return False, reason
        
        # Check concurrent
        allowed, reason = self.check_concurrent()
        if not allowed:
            with self._lock:
                self._rejected_concurrent += 1
            return False, reason
        
        return True, "Validation allowed"
    
    def record_validation_start(self) -> None:
        """Record the start of a validation operation."""
        import time
        
        with self._lock:
            self._request_times.append(time.time())
            self._concurrent_count += 1
            self._total_validations += 1
    
    def record_validation_end(self) -> None:
        """Record the end of a validation operation."""
        with self._lock:
            self._concurrent_count = max(0, self._concurrent_count - 1)
    
    def validation_context(self):
        """
        Context manager for validation operations.
        
        Returns:
            ValidationContext object
        """
        return ValidationContext(self)
    
    def get_statistics(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            self._cleanup_old_requests()
            
            return {
                'enabled': self.enabled,
                'requests_per_minute': self.requests_per_minute,
                'max_content_size_mb': self.max_content_size_mb,
                'max_concurrent': self.max_concurrent,
                'max_memory_percent': self.max_memory_percent,
                'current_requests_in_window': len(self._request_times),
                'current_concurrent': self._concurrent_count,
                'current_memory_percent': self._get_memory_percent(),
                'total_validations': self._total_validations,
                'rejected_rate_limit': self._rejected_rate_limit,
                'rejected_size': self._rejected_size,
                'rejected_memory': self._rejected_memory,
                'rejected_concurrent': self._rejected_concurrent,
            }
    
    def reset(self) -> None:
        """Reset the rate limiter state."""
        with self._lock:
            self._request_times = []
            self._concurrent_count = 0
    
    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._total_validations = 0
            self._rejected_rate_limit = 0
            self._rejected_size = 0
            self._rejected_memory = 0
            self._rejected_concurrent = 0


class ValidationContext:
    """
    Context manager for validation operations with rate limiting.
    
    Automatically tracks validation start/end and provides
    access to whether validation is allowed.
    
    Usage:
        limiter = ValidationRateLimiter()
        
        with limiter.validation_context() as ctx:
            if not ctx.allowed:
                print(f"Validation blocked: {ctx.reason}")
                return
            
            # Perform validation
            result = validate(content)
    """
    
    def __init__(self, limiter: ValidationRateLimiter):
        """
        Initialize context.
        
        Args:
            limiter: ValidationRateLimiter instance
        """
        self.limiter = limiter
        self.allowed = False
        self.reason = ""
        self._started = False
    
    def check(self, content: str) -> 'ValidationContext':
        """
        Check if validation is allowed for content.
        
        Args:
            content: Content to validate
            
        Returns:
            self for method chaining
        """
        self.allowed, self.reason = self.limiter.check_validation_allowed(content)
        return self
    
    def __enter__(self) -> 'ValidationContext':
        """Enter context - record start if allowed."""
        if self.allowed:
            self.limiter.record_validation_start()
            self._started = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - record end."""
        if self._started:
            self.limiter.record_validation_end()
        return None
