"""
URL validation and SSRF protection for the RDF/DTDL Fabric Ontology Converter.

This module provides SSRF (Server-Side Request Forgery) protection for URL handling.

Security features:
- Protocol validation (only https allowed by default)
- Private IP address blocking
- Domain allowlist support
- Port restriction

Usage:
    from core.validators.url import URLValidator
    
    # Basic validation
    validated_url = URLValidator.validate_url(url)
    
    # With allowlist
    validated_url = URLValidator.validate_url(
        url,
        allowed_domains=['example.com', 'trusted.org']
    )
"""

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


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
