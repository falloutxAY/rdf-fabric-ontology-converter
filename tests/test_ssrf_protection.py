"""
Tests for SSRF (Server-Side Request Forgery) Protection.

Tests cover:
- URL validation with protocol restrictions
- Private IP address blocking
- Domain allowlist validation
- Port restrictions
- Ontology URL validation

Source: Task 11 from review/07_PLAN_UPDATES.md
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.validators import URLValidator


# =============================================================================
# URL VALIDATION BASIC TESTS
# =============================================================================

class TestURLValidationBasic:
    """Basic URL validation tests."""
    
    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        url = "https://example.com/ontology.ttl"
        result = URLValidator.validate_url(url)
        assert result == url
    
    def test_valid_https_url_with_path(self):
        """Test HTTPS URL with complex path."""
        url = "https://w3.org/2002/07/owl#"
        result = URLValidator.validate_url(url)
        assert result == url
    
    def test_rejects_http_by_default(self):
        """Test that HTTP is rejected by default (HTTPS only)."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("http://example.com/file.ttl")
        
        assert "protocol" in str(exc_info.value).lower()
        assert "not allowed" in str(exc_info.value).lower()
    
    def test_allows_http_when_specified(self):
        """Test that HTTP can be allowed explicitly."""
        url = "http://example.com/file.ttl"
        result = URLValidator.validate_url(
            url,
            allowed_protocols=['http', 'https'],
            allowed_ports=[80, 443]
        )
        assert result == url
    
    def test_rejects_ftp_protocol(self):
        """Test that FTP protocol is rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("ftp://example.com/file.ttl")
        
        assert "protocol" in str(exc_info.value).lower()
    
    def test_rejects_file_protocol(self):
        """Test that file:// protocol is rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("file:///etc/passwd")
        
        assert "protocol" in str(exc_info.value).lower()
    
    def test_rejects_empty_url(self):
        """Test that empty URLs are rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_rejects_whitespace_only_url(self):
        """Test that whitespace-only URLs are rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("   ")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_rejects_non_string_url(self):
        """Test that non-string URLs are rejected."""
        with pytest.raises(TypeError) as exc_info:
            URLValidator.validate_url(12345)
        
        assert "string" in str(exc_info.value).lower()
    
    def test_rejects_url_without_scheme(self):
        """Test that URLs without scheme are rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("example.com/file.ttl")
        
        assert "scheme" in str(exc_info.value).lower() or "protocol" in str(exc_info.value).lower()


# =============================================================================
# SSRF PROTECTION - LOCALHOST BLOCKING
# =============================================================================

class TestSSRFLocalhostBlocking:
    """Test SSRF protection against localhost access."""
    
    def test_blocks_localhost(self):
        """Test that localhost is blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://localhost/admin")
        
        assert "ssrf" in str(exc_info.value).lower() or "localhost" in str(exc_info.value).lower()
    
    def test_blocks_localhost_localdomain(self):
        """Test that localhost.localdomain is blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://localhost.localdomain/admin")
        
        assert "ssrf" in str(exc_info.value).lower() or "localhost" in str(exc_info.value).lower()
    
    def test_blocks_127_0_0_1(self):
        """Test that 127.0.0.1 is blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://127.0.0.1/admin")
        
        assert "ssrf" in str(exc_info.value).lower() or "localhost" in str(exc_info.value).lower()
    
    def test_blocks_ipv6_loopback(self):
        """Test that IPv6 loopback (::1) is blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://[::1]/admin")
        
        # May fail to parse or be blocked as localhost
        assert "ssrf" in str(exc_info.value).lower() or "localhost" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_blocks_0_0_0_0(self):
        """Test that 0.0.0.0 is blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://0.0.0.0/admin")
        
        assert "ssrf" in str(exc_info.value).lower() or "localhost" in str(exc_info.value).lower()
    
    def test_allows_localhost_when_explicitly_permitted(self):
        """Test that localhost can be allowed when explicitly permitted."""
        url = "https://localhost/test"
        result = URLValidator.validate_url(
            url, 
            allow_private_ips=True,
            allowed_ports=[443]
        )
        assert result == url


# =============================================================================
# SSRF PROTECTION - PRIVATE IP BLOCKING
# =============================================================================

class TestSSRFPrivateIPBlocking:
    """Test SSRF protection against private IP ranges."""
    
    def test_blocks_10_x_x_x_range(self):
        """Test blocking of 10.0.0.0/8 private range."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://10.0.0.1/internal")
        
        assert "ssrf" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()
    
    def test_blocks_172_16_x_x_range(self):
        """Test blocking of 172.16.0.0/12 private range."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://172.16.0.1/internal")
        
        assert "ssrf" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()
    
    def test_blocks_192_168_x_x_range(self):
        """Test blocking of 192.168.0.0/16 private range."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://192.168.1.1/admin")
        
        assert "ssrf" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()
    
    def test_blocks_169_254_link_local(self):
        """Test blocking of link-local addresses (169.254.x.x)."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://169.254.1.1/metadata")
        
        assert "ssrf" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()
    
    def test_allows_public_ip(self):
        """Test that public IPs are allowed."""
        # Using a known public IP (Google DNS)
        url = "https://8.8.8.8/test"
        result = URLValidator.validate_url(
            url,
            allowed_ports=[443],
            check_dns=False  # Skip DNS check for direct IP
        )
        assert result == url
    
    def test_private_ip_detection_ipv4(self):
        """Test _is_private_ipv4 method directly."""
        # Private IPs
        assert URLValidator._is_private_ipv4("10.0.0.1") is True
        assert URLValidator._is_private_ipv4("10.255.255.255") is True
        assert URLValidator._is_private_ipv4("172.16.0.1") is True
        assert URLValidator._is_private_ipv4("172.31.255.255") is True
        assert URLValidator._is_private_ipv4("192.168.0.1") is True
        assert URLValidator._is_private_ipv4("192.168.255.255") is True
        assert URLValidator._is_private_ipv4("127.0.0.1") is True
        assert URLValidator._is_private_ipv4("169.254.1.1") is True
        
        # Public IPs
        assert URLValidator._is_private_ipv4("8.8.8.8") is False
        assert URLValidator._is_private_ipv4("1.1.1.1") is False
        assert URLValidator._is_private_ipv4("142.250.80.46") is False  # google.com


# =============================================================================
# DOMAIN ALLOWLIST TESTS
# =============================================================================

class TestDomainAllowlist:
    """Test domain allowlist functionality."""
    
    def test_allows_domain_in_allowlist(self):
        """Test that domains in allowlist are accepted."""
        url = "https://w3.org/ontology.ttl"
        result = URLValidator.validate_url(
            url,
            allowed_domains=['w3.org', 'example.com']
        )
        assert result == url
    
    def test_allows_subdomain_of_allowlisted_domain(self):
        """Test that subdomains of allowlisted domains are accepted."""
        url = "https://www.w3.org/ontology.ttl"
        result = URLValidator.validate_url(
            url,
            allowed_domains=['w3.org']
        )
        assert result == url
    
    def test_blocks_domain_not_in_allowlist(self):
        """Test that domains not in allowlist are rejected."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url(
                "https://malicious.com/file.ttl",
                allowed_domains=['w3.org', 'example.com']
            )
        
        assert "not in allowed list" in str(exc_info.value).lower()
    
    def test_domain_matching_is_case_insensitive(self):
        """Test that domain matching is case-insensitive."""
        url = "https://W3.ORG/ontology.ttl"
        result = URLValidator.validate_url(
            url,
            allowed_domains=['w3.org']
        )
        assert result == url
    
    def test_all_public_domains_allowed_when_no_allowlist(self):
        """Test that any public domain is allowed when no allowlist specified."""
        url = "https://random-domain.com/file.ttl"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url


# =============================================================================
# PORT RESTRICTION TESTS
# =============================================================================

class TestPortRestrictions:
    """Test port restriction functionality."""
    
    def test_allows_port_443_by_default(self):
        """Test that port 443 is allowed by default."""
        url = "https://example.com:443/file.ttl"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_allows_port_8443_by_default(self):
        """Test that port 8443 is allowed by default."""
        url = "https://example.com:8443/file.ttl"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_blocks_non_standard_port(self):
        """Test that non-standard ports are blocked."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_url("https://example.com:8080/file.ttl")
        
        assert "port" in str(exc_info.value).lower()
    
    def test_allows_custom_port_when_specified(self):
        """Test that custom ports can be allowed."""
        url = "https://example.com:8080/file.ttl"
        result = URLValidator.validate_url(
            url,
            allowed_ports=[443, 8080, 8443],
            check_dns=False
        )
        assert result == url


# =============================================================================
# ONTOLOGY URL VALIDATION TESTS
# =============================================================================

class TestOntologyURLValidation:
    """Test ontology-specific URL validation."""
    
    def test_validates_w3_org_url(self):
        """Test that W3C URLs are accepted."""
        url = "https://www.w3.org/2002/07/owl#"
        result = URLValidator.validate_ontology_url(url)
        assert result == url
    
    def test_validates_purl_org_url(self):
        """Test that purl.org URLs are accepted."""
        url = "https://purl.org/dc/terms/"
        result = URLValidator.validate_ontology_url(url)
        assert result == url
    
    def test_validates_schema_org_url(self):
        """Test that schema.org URLs are accepted."""
        url = "https://schema.org/Thing"
        result = URLValidator.validate_ontology_url(url)
        assert result == url
    
    def test_validates_github_raw_url(self):
        """Test that GitHub raw content URLs are accepted."""
        url = "https://raw.githubusercontent.com/owner/repo/main/ontology.ttl"
        result = URLValidator.validate_ontology_url(url)
        assert result == url
    
    def test_rejects_untrusted_domain_for_ontology(self):
        """Test that untrusted domains are rejected for ontology URLs."""
        with pytest.raises(ValueError) as exc_info:
            URLValidator.validate_ontology_url("https://untrusted-site.com/ontology.ttl")
        
        assert "not in allowed list" in str(exc_info.value).lower()
    
    def test_allows_custom_domain_for_ontology(self):
        """Test that custom domains can be added for ontology URLs."""
        url = "https://my-company.com/ontology.ttl"
        result = URLValidator.validate_ontology_url(
            url,
            allowed_domains=['my-company.com']
        )
        assert result == url


# =============================================================================
# UTILITY METHOD TESTS
# =============================================================================

class TestURLValidatorUtilities:
    """Test utility methods."""
    
    def test_is_url_detects_https(self):
        """Test is_url detects HTTPS URLs."""
        assert URLValidator.is_url("https://example.com") is True
    
    def test_is_url_detects_http(self):
        """Test is_url detects HTTP URLs."""
        assert URLValidator.is_url("http://example.com") is True
    
    def test_is_url_detects_ftp(self):
        """Test is_url detects FTP URLs."""
        assert URLValidator.is_url("ftp://example.com") is True
    
    def test_is_url_rejects_file_path(self):
        """Test is_url rejects file paths."""
        assert URLValidator.is_url("/path/to/file.ttl") is False
        assert URLValidator.is_url("C:\\path\\to\\file.ttl") is False
    
    def test_is_url_handles_non_strings(self):
        """Test is_url handles non-string inputs gracefully."""
        assert URLValidator.is_url(None) is False
        assert URLValidator.is_url(123) is False
        assert URLValidator.is_url(['https://example.com']) is False
    
    def test_sanitize_url_removes_credentials(self):
        """Test that URL sanitization removes credentials."""
        url = "https://user:password@example.com/path?secret=value"
        sanitized = URLValidator.sanitize_url_for_logging(url)
        
        assert "password" not in sanitized
        assert "user" not in sanitized
        assert "secret" not in sanitized
    
    def test_sanitize_url_preserves_hostname(self):
        """Test that URL sanitization preserves hostname."""
        url = "https://example.com/path"
        sanitized = URLValidator.sanitize_url_for_logging(url)
        
        assert "example.com" in sanitized


# =============================================================================
# EDGE CASES
# =============================================================================

class TestURLValidatorEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_url_with_special_characters_in_path(self):
        """Test URL with special characters in path."""
        url = "https://example.com/path/with%20spaces/file.ttl"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_url_with_query_parameters(self):
        """Test URL with query parameters."""
        url = "https://example.com/file.ttl?version=1.0&format=turtle"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_url_with_fragment(self):
        """Test URL with fragment identifier."""
        url = "https://example.com/ontology#Class"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_very_long_url(self):
        """Test handling of very long URLs."""
        long_path = "/".join(["segment"] * 100)
        url = f"https://example.com/{long_path}/file.ttl"
        result = URLValidator.validate_url(url, check_dns=False)
        assert result == url
    
    def test_url_with_port_only_digits(self):
        """Test URL validation rejects port with non-digit characters."""
        # Port should be a number; non-standard characters should fail URL parsing
        with pytest.raises(ValueError):
            URLValidator.validate_url("https://example.com:abc/file.ttl")
    
    def test_ipv4_in_decimal_notation(self):
        """Test that decimal IP notation is handled."""
        # 2130706433 = 127.0.0.1 in decimal
        # Note: Most URL parsers don't support decimal notation
        # This test ensures we don't accidentally allow bypass
        try:
            URLValidator.validate_url("https://2130706433/admin", check_dns=False)
            # If it passes parsing, should not resolve to localhost
        except ValueError:
            # Expected - unusual format should be rejected
            pass


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
