"""
Pytest configuration and fixtures for the test suite.

Defines markers for selective test execution:
    pytest -m unit          # Fast unit tests
    pytest -m integration   # Integration tests  
    pytest -m slow          # Tests that take >1s
    pytest -m security      # Security-related tests
    pytest -m resilience    # Rate limiting, circuit breaker, cancellation

Fixtures are centralized in tests/fixtures/ for reuse across all test modules.
"""

import pytest
import json
import sys
import os
from pathlib import Path

# IMPORTANT: Patch tenacity's sleep function BEFORE any other imports
# This must happen before tenacity.Retrying class is defined (which captures defaults)
import tenacity.nap
tenacity.nap.sleep = lambda seconds: None

# Add src to path for imports
src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Add tests directory to path for fixtures import
tests_dir = os.path.dirname(__file__)
if tests_dir not in sys.path:
    # Ensure src directory stays ahead of tests for module resolution
    sys.path.insert(1, tests_dir)

# Import centralized fixtures
from fixtures import (
    # TTL fixtures
    SIMPLE_TTL,
    MINIMAL_TTL,
    INHERITANCE_TTL,
    MULTIPLE_DOMAINS_TTL,
    UNION_DOMAIN_TTL,
    RESTRICTION_TTL,
    FUNCTIONAL_PROPERTY_TTL,
    EXTERNAL_IMPORT_TTL,
    MISSING_DOMAIN_TTL,
    MISSING_RANGE_TTL,
    generate_large_ttl,
    
    # DTDL fixtures
    SIMPLE_DTDL_INTERFACE,
    DTDL_WITH_RELATIONSHIP,
    DTDL_WITH_ENUM,
    DTDL_WITH_TELEMETRY,
    DTDL_WITH_COMPONENT,
    DTDL_WITH_INHERITANCE,
    
    # Config fixtures
    SAMPLE_FABRIC_CONFIG,
    MINIMAL_FABRIC_CONFIG,
    SERVICE_PRINCIPAL_CONFIG,
)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live integration tests against real Fabric API"
    )
    parser.addoption(
        "--workspace-id",
        action="store",
        default=None,
        help="Override workspace ID for live tests"
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Fast unit tests")
    config.addinivalue_line("markers", "integration: Integration tests requiring setup")
    config.addinivalue_line("markers", "slow: Tests that take more than 1 second")
    config.addinivalue_line("markers", "security: Security-related tests (path traversal, symlinks)")
    config.addinivalue_line("markers", "resilience: Rate limiting, circuit breaker, cancellation tests")
    config.addinivalue_line("markers", "samples: Tests using sample ontology files")
    config.addinivalue_line("markers", "live: Live integration tests against real Fabric API")
    config.addinivalue_line("markers", "contract: Contract tests validating API schema compliance")
    config.addinivalue_line("markers", "e2e: End-to-end smoke tests")
    
    # Set environment variable if --run-live is passed
    if config.getoption("--run-live"):
        os.environ["FABRIC_LIVE_TESTS"] = "1"
    
    # Override workspace ID if provided
    workspace_id = config.getoption("--workspace-id")
    if workspace_id:
        os.environ["FABRIC_WORKSPACE_ID"] = workspace_id


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless explicitly enabled."""
    if config.getoption("--run-live"):
        # Don't skip live tests
        return
    
    skip_live = pytest.mark.skip(
        reason="Live tests disabled. Use --run-live to enable or set FABRIC_LIVE_TESTS=1"
    )
    
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# =============================================================================
# TTL/RDF Fixtures
# =============================================================================

@pytest.fixture
def sample_ttl_content():
    """Minimal valid TTL content for testing."""
    return MINIMAL_TTL


@pytest.fixture
def simple_ttl():
    """Simple TTL content with Person, Organization, and relationships."""
    return SIMPLE_TTL


@pytest.fixture
def inheritance_ttl():
    """TTL content demonstrating class inheritance (Animal -> Mammal -> Dog)."""
    return INHERITANCE_TTL


@pytest.fixture
def multiple_domains_ttl():
    """TTL content with property having multiple domains."""
    return MULTIPLE_DOMAINS_TTL


@pytest.fixture
def union_domain_ttl():
    """TTL content with property having union domain."""
    return UNION_DOMAIN_TTL


@pytest.fixture
def restriction_ttl():
    """TTL content with OWL restrictions."""
    return RESTRICTION_TTL


@pytest.fixture
def functional_property_ttl():
    """TTL content with functional property."""
    return FUNCTIONAL_PROPERTY_TTL


@pytest.fixture
def external_import_ttl():
    """TTL content with owl:imports statement."""
    return EXTERNAL_IMPORT_TTL


@pytest.fixture
def missing_domain_ttl():
    """TTL content with property missing rdfs:domain."""
    return MISSING_DOMAIN_TTL


@pytest.fixture
def missing_range_ttl():
    """TTL content with property missing rdfs:range."""
    return MISSING_RANGE_TTL


@pytest.fixture
def large_ttl():
    """Generate a large TTL file for stress testing."""
    return generate_large_ttl(num_classes=50, properties_per_class=3, relationships_per_class=1)


@pytest.fixture
def sample_ontology_path():
    """Path to sample supply chain ontology."""
    return os.path.join(
        os.path.dirname(__file__), 
        '..', 'samples', 'sample_supply_chain_ontology.ttl'
    )


@pytest.fixture
def temp_ttl_file(tmp_path, sample_ttl_content):
    """Create a temporary TTL file for testing."""
    ttl_file = tmp_path / "test_ontology.ttl"
    ttl_file.write_text(sample_ttl_content)
    return str(ttl_file)


# =============================================================================
# DTDL Fixtures
# =============================================================================

@pytest.fixture
def simple_dtdl_interface():
    """Simple DTDL interface with property and telemetry."""
    return SIMPLE_DTDL_INTERFACE.copy()


@pytest.fixture
def dtdl_with_relationship():
    """DTDL interface with a relationship."""
    return DTDL_WITH_RELATIONSHIP.copy()


@pytest.fixture
def dtdl_with_enum():
    """DTDL interface with enum property."""
    return DTDL_WITH_ENUM.copy()


@pytest.fixture
def dtdl_with_telemetry():
    """DTDL interface with multiple telemetry properties."""
    return DTDL_WITH_TELEMETRY.copy()


@pytest.fixture
def dtdl_with_component():
    """DTDL interface with component."""
    return DTDL_WITH_COMPONENT.copy()


@pytest.fixture
def dtdl_with_inheritance():
    """DTDL interface with extends."""
    return DTDL_WITH_INHERITANCE.copy()


@pytest.fixture
def temp_dtdl_file(tmp_path, simple_dtdl_interface):
    """Create a temporary DTDL JSON file for testing."""
    dtdl_file = tmp_path / "test_interface.json"
    dtdl_file.write_text(json.dumps(simple_dtdl_interface, indent=2))
    return str(dtdl_file)


@pytest.fixture
def temp_dtdl_directory(tmp_path):
    """Create a temporary directory with multiple DTDL files."""
    dtdl_dir = tmp_path / "dtdl_models"
    dtdl_dir.mkdir()
    
    # Write thermostat interface
    thermostat_file = dtdl_dir / "thermostat.json"
    thermostat_file.write_text(json.dumps(SIMPLE_DTDL_INTERFACE, indent=2))
    
    # Write room interface
    room_file = dtdl_dir / "room.json"
    room_file.write_text(json.dumps(DTDL_WITH_RELATIONSHIP, indent=2))
    
    return str(dtdl_dir)


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def sample_config():
    """Sample Fabric configuration dictionary."""
    return SAMPLE_FABRIC_CONFIG.copy()


@pytest.fixture
def minimal_config():
    """Minimal Fabric configuration dictionary."""
    return MINIMAL_FABRIC_CONFIG.copy()


@pytest.fixture
def service_principal_config():
    """Service principal configuration dictionary."""
    return SERVICE_PRINCIPAL_CONFIG.copy()


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """Create a temporary configuration file for testing."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(sample_config, indent=2))
    return str(config_file)


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def rdf_converter():
    """Create an RDFToFabricConverter instance."""
    from src.rdf import RDFToFabricConverter
    return RDFToFabricConverter()


@pytest.fixture
def input_validator():
    """Get InputValidator class for path validation tests."""
    from src.core.validators import InputValidator
    return InputValidator
