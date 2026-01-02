"""
Centralized test fixtures for the RDF/DTDL Fabric Ontology Converter test suite.

This package provides reusable fixtures for testing, including:
- TTL/RDF sample content
- DTDL sample content
- Fabric ontology definitions
- Configuration fixtures

Usage:
    from tests.fixtures import (
        SIMPLE_TTL,
        INHERITANCE_TTL,
        SIMPLE_DTDL_INTERFACE,
        SAMPLE_FABRIC_CONFIG,
    )

Or use the pytest fixtures in conftest.py which import from here.
"""

from .ttl_fixtures import (
    # Simple TTL content
    SIMPLE_TTL,
    EMPTY_TTL,
    MINIMAL_TTL,
    
    # Complex TTL content
    INHERITANCE_TTL,
    MULTIPLE_DOMAINS_TTL,
    UNION_DOMAIN_TTL,
    
    # Edge case TTL content
    RESTRICTION_TTL,
    FUNCTIONAL_PROPERTY_TTL,
    EXTERNAL_IMPORT_TTL,
    MISSING_DOMAIN_TTL,
    MISSING_RANGE_TTL,
    
    # Large/stress test TTL content
    LARGE_TTL_TEMPLATE,
    generate_large_ttl,
)

from .dtdl_fixtures import (
    # Simple DTDL content
    SIMPLE_DTDL_INTERFACE,
    DTDL_WITH_RELATIONSHIP,
    DTDL_WITH_ENUM,
    DTDL_WITH_TELEMETRY,
    DTDL_WITH_COMPONENT,
    DTDL_WITH_INHERITANCE,
    
    # Complex DTDL content
    DTDL_ARRAY_OF_OBJECTS,
    DTDL_NESTED_OBJECTS,
)

from .config_fixtures import (
    SAMPLE_FABRIC_CONFIG,
    MINIMAL_FABRIC_CONFIG,
    SERVICE_PRINCIPAL_CONFIG,
)

__all__ = [
    # TTL fixtures
    "SIMPLE_TTL",
    "EMPTY_TTL",
    "MINIMAL_TTL",
    "INHERITANCE_TTL",
    "MULTIPLE_DOMAINS_TTL",
    "UNION_DOMAIN_TTL",
    "RESTRICTION_TTL",
    "FUNCTIONAL_PROPERTY_TTL",
    "EXTERNAL_IMPORT_TTL",
    "MISSING_DOMAIN_TTL",
    "MISSING_RANGE_TTL",
    "LARGE_TTL_TEMPLATE",
    "generate_large_ttl",
    
    # DTDL fixtures
    "SIMPLE_DTDL_INTERFACE",
    "DTDL_WITH_RELATIONSHIP",
    "DTDL_WITH_ENUM",
    "DTDL_WITH_TELEMETRY",
    "DTDL_WITH_COMPONENT",
    "DTDL_WITH_INHERITANCE",
    "DTDL_ARRAY_OF_OBJECTS",
    "DTDL_NESTED_OBJECTS",
    
    # Config fixtures
    "SAMPLE_FABRIC_CONFIG",
    "MINIMAL_FABRIC_CONFIG",
    "SERVICE_PRINCIPAL_CONFIG",
]
