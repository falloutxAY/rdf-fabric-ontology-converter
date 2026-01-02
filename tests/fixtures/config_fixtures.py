"""
Configuration test fixtures for the test suite.

Contains various configuration samples for testing the Fabric client,
authentication, and related functionality.
"""

# =============================================================================
# Fabric Configuration Fixtures
# =============================================================================

SAMPLE_FABRIC_CONFIG = {
    "fabric": {
        "workspace_id": "12345678-1234-1234-1234-123456789012",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "api_base_url": "https://api.fabric.microsoft.com/v1",
        "use_interactive_auth": True,
        "rate_limit": {
            "enabled": True,
            "requests_per_minute": 10,
            "burst": 15
        },
        "circuit_breaker": {
            "enabled": True,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "success_threshold": 2
        }
    },
    "ontology": {
        "default_namespace": "usertypes",
        "id_prefix": 1000000000000
    },
    "logging": {
        "level": "INFO",
        "file": "logs/test.log",
        "format": "text",
        "rotation": {
            "enabled": True,
            "max_mb": 10,
            "backup_count": 5
        }
    }
}

MINIMAL_FABRIC_CONFIG = {
    "fabric": {
        "workspace_id": "12345678-1234-1234-1234-123456789012",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "use_interactive_auth": True
    }
}

SERVICE_PRINCIPAL_CONFIG = {
    "fabric": {
        "workspace_id": "12345678-1234-1234-1234-123456789012",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "client_id": "app-client-id",
        "use_interactive_auth": False,
        "api_base_url": "https://api.fabric.microsoft.com/v1",
        "rate_limit": {
            "enabled": True,
            "requests_per_minute": 10,
            "burst": 15
        },
        "circuit_breaker": {
            "enabled": True,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "success_threshold": 2
        }
    },
    "ontology": {
        "default_namespace": "usertypes",
        "id_prefix": 1000000000000
    },
    "logging": {
        "level": "INFO"
    }
}


# =============================================================================
# Invalid Configuration Fixtures (for negative testing)
# =============================================================================

INVALID_WORKSPACE_ID_CONFIG = {
    "fabric": {
        "workspace_id": "YOUR_WORKSPACE_ID",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "use_interactive_auth": True
    }
}

MISSING_WORKSPACE_CONFIG = {
    "fabric": {
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "use_interactive_auth": True
    }
}

MALFORMED_GUID_CONFIG = {
    "fabric": {
        "workspace_id": "not-a-valid-guid",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "use_interactive_auth": True
    }
}
