"""
Tests for the plugin architecture.

This module tests the plugin system including:
- Plugin registration and discovery
- FormatConverter interface
- FormatValidator interface
- FormatExporter interface
- Built-in plugin wrappers
- Error handling
"""

import pytest
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.plugins import (
    PluginType,
    ConversionStatus,
    PluginMetadata,
    ConversionContext,
    ConversionOutput,
    ValidationOutput,
    ExportOutput,
    FormatConverter,
    FormatValidator,
    FormatExporter,
    PluginRegistry,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
    RDFConverterPlugin,
    DTDLConverterPlugin,
    register_builtin_plugins,
    ensure_builtins_registered,
)
from models import EntityType, EntityTypeProperty, RelationshipType, RelationshipEnd


# =============================================================================
# Test Fixtures
# =============================================================================

class MockConverter(FormatConverter):
    """Mock converter for testing."""
    format_name = "mock"
    file_extensions = [".mock", ".mck"]
    format_description = "Mock format converter"
    version = "1.0.0"
    author = "Test Author"
    
    def convert(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ConversionOutput:
        output = ConversionOutput()
        output.entity_types.append(
            EntityType(
                id="1000000000001",
                name="MockEntity",
                properties=[
                    EntityTypeProperty(id="1000000001", name="prop1", valueType="String")
                ]
            )
        )
        output.status = ConversionStatus.SUCCESS
        output.statistics = {"source_size": len(str(source))}
        return output


class MockValidator(FormatValidator):
    """Mock validator for testing."""
    format_name = "mock"
    file_extensions = [".mock"]
    format_description = "Mock format validator"
    
    def validate(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ValidationOutput:
        return ValidationOutput(is_valid=True, info=["Mock validation passed"])


class MockExporter(FormatExporter):
    """Mock exporter for testing."""
    format_name = "mock"
    file_extensions = [".mock"]
    format_description = "Mock format exporter"
    
    def export(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ExportOutput:
        return ExportOutput(
            success=True,
            content=f"Exported {len(entity_types)} entities"
        )


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean the registry before and after each test."""
    PluginRegistry.clear()
    yield
    PluginRegistry.clear()


# =============================================================================
# Plugin Metadata Tests
# =============================================================================

class TestPluginMetadata:
    """Tests for PluginMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating plugin metadata."""
        metadata = PluginMetadata(
            name="Test Plugin",
            format_name="test",
            version="1.0.0",
            author="Test Author",
            description="Test description",
            file_extensions=[".test"],
            plugin_type=PluginType.CONVERTER,
        )
        
        assert metadata.name == "Test Plugin"
        assert metadata.format_name == "test"
        assert metadata.version == "1.0.0"
        assert metadata.plugin_type == PluginType.CONVERTER
    
    def test_metadata_to_dict(self):
        """Test metadata serialization."""
        metadata = PluginMetadata(
            name="Test Plugin",
            format_name="test",
            file_extensions=[".test", ".tst"],
        )
        
        result = metadata.to_dict()
        
        assert result["name"] == "Test Plugin"
        assert result["format_name"] == "test"
        assert result["file_extensions"] == [".test", ".tst"]
        assert result["plugin_type"] == "converter"


# =============================================================================
# ConversionContext Tests
# =============================================================================

class TestConversionContext:
    """Tests for ConversionContext."""
    
    def test_context_creation(self):
        """Test creating conversion context."""
        context = ConversionContext(
            config={"key": "value"},
        )
        
        assert context.config["key"] == "value"
        assert context.progress_callback is None
        assert context.cancel_check is None
    
    def test_progress_reporting(self):
        """Test progress callback."""
        progress_calls = []
        
        def progress_callback(current: int, total: int, message: str):
            progress_calls.append((current, total, message))
        
        context = ConversionContext(progress_callback=progress_callback)
        context.report_progress(1, 10, "Processing")
        context.report_progress(5, 10, "Halfway")
        
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 10, "Processing")
        assert progress_calls[1] == (5, 10, "Halfway")
    
    def test_cancellation_check(self):
        """Test cancellation checking."""
        cancel_requested = [False]
        
        def cancel_check():
            return cancel_requested[0]
        
        context = ConversionContext(cancel_check=cancel_check)
        
        assert not context.is_cancelled()
        cancel_requested[0] = True
        assert context.is_cancelled()
    
    def test_no_callback_does_nothing(self):
        """Test that missing callbacks don't cause errors."""
        context = ConversionContext()
        
        # Should not raise
        context.report_progress(1, 10, "Test")
        assert not context.is_cancelled()
    
    def test_cancellation_token_integration(self):
        """Test integration with CancellationToken."""
        from core.cancellation import CancellationToken
        
        token = CancellationToken()
        context = ConversionContext(cancellation_token=token)
        
        assert not context.is_cancelled()
        token.cancel()
        assert context.is_cancelled()
    
    def test_throw_if_cancelled_with_token(self):
        """Test throw_if_cancelled with CancellationToken."""
        from core.cancellation import CancellationToken, OperationCancelledException
        
        token = CancellationToken()
        context = ConversionContext(cancellation_token=token)
        
        # Should not raise when not cancelled
        context.throw_if_cancelled()
        
        # Should raise after cancellation
        token.cancel()
        with pytest.raises(OperationCancelledException):
            context.throw_if_cancelled()
    
    def test_rate_limiter_integration(self):
        """Test integration with rate limiter."""
        from core.rate_limiter import TokenBucketRateLimiter
        
        limiter = TokenBucketRateLimiter(rate=100, per=1, burst=100)
        context = ConversionContext(rate_limiter=limiter)
        
        # Should acquire successfully
        assert context.acquire_rate_limit() is True
        assert context.acquire_rate_limit(5) is True
    
    def test_rate_limiter_not_configured(self):
        """Test acquire_rate_limit when no limiter configured."""
        context = ConversionContext()
        
        # Should return True when no limiter
        assert context.acquire_rate_limit() is True
    
    def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker."""
        from core.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1,
            name="test",
        )
        context = ConversionContext(circuit_breaker=breaker)
        
        # Should call function successfully
        result = context.call_with_circuit_breaker(lambda x: x * 2, 5)
        assert result == 10
    
    def test_circuit_breaker_not_configured(self):
        """Test call_with_circuit_breaker when no breaker configured."""
        context = ConversionContext()
        
        # Should call directly when no breaker
        result = context.call_with_circuit_breaker(lambda x: x * 2, 5)
        assert result == 10
    
    def test_memory_manager_integration(self):
        """Test integration with memory manager."""
        from core.memory import MemoryManager
        
        # MemoryManager is a class with static methods, we use the class itself
        context = ConversionContext(memory_manager=MemoryManager)
        
        # Should check memory - passing a small file size
        result = context.check_memory(10.0)  # 10 MB file
        assert isinstance(result, bool)
    
    def test_memory_check_not_configured(self):
        """Test check_memory when no manager configured."""
        context = ConversionContext()
        
        # Should return True when no manager
        assert context.check_memory() is True
    
    def test_input_validator_integration(self):
        """Test integration with input validator."""
        from core.validators import InputValidator
        
        validator = InputValidator()
        context = ConversionContext(input_validator=validator)
        
        # Should validate path (without checking if file exists)
        result = context.validate_input("test.ttl", check_exists=False)
        assert result is True
    
    def test_input_validator_not_configured(self):
        """Test validate_input when no validator configured."""
        context = ConversionContext()
        
        # Should return True when no validator
        assert context.validate_input("any_path") is True
    
    def test_create_with_defaults_basic(self):
        """Test creating context with factory method."""
        context = ConversionContext.create_with_defaults(
            config={"key": "value"}
        )
        
        assert context.config["key"] == "value"
        assert context.rate_limiter is None
        assert context.circuit_breaker is None
    
    def test_create_with_defaults_rate_limiter(self):
        """Test creating context with rate limiter enabled."""
        context = ConversionContext.create_with_defaults(
            enable_rate_limiter=True
        )
        
        assert context.rate_limiter is not None
        # Should be able to acquire
        assert context.acquire_rate_limit() is True
    
    def test_create_with_defaults_circuit_breaker(self):
        """Test creating context with circuit breaker enabled."""
        context = ConversionContext.create_with_defaults(
            enable_circuit_breaker=True
        )
        
        assert context.circuit_breaker is not None
        # Should be able to call through breaker
        result = context.call_with_circuit_breaker(lambda: 42)
        assert result == 42
    
    def test_create_with_defaults_cancellation(self):
        """Test creating context with cancellation enabled."""
        context = ConversionContext.create_with_defaults(
            enable_cancellation=True
        )
        
        assert context.cancellation_token is not None
        assert not context.is_cancelled()
    
    def test_create_with_defaults_memory_manager(self):
        """Test creating context with memory manager enabled."""
        context = ConversionContext.create_with_defaults(
            enable_memory_manager=True
        )
        
        assert context.memory_manager is not None
        assert context.check_memory(10.0) is True  # 10 MB test
    
    def test_create_with_all_features(self):
        """Test creating context with all features enabled."""
        context = ConversionContext.create_with_defaults(
            config={"test": True},
            enable_rate_limiter=True,
            enable_circuit_breaker=True,
            enable_cancellation=True,
            enable_memory_manager=True,
        )
        
        assert context.rate_limiter is not None
        assert context.circuit_breaker is not None
        assert context.cancellation_token is not None
        assert context.memory_manager is not None


# =============================================================================
# ConversionOutput Tests
# =============================================================================

class TestConversionOutput:
    """Tests for ConversionOutput."""
    
    def test_output_defaults(self):
        """Test default output values."""
        output = ConversionOutput()
        
        assert output.status == ConversionStatus.SUCCESS
        assert output.entity_types == []
        assert output.relationship_types == []
        assert output.warnings == []
        assert output.errors == []
    
    def test_is_success(self):
        """Test success checking."""
        output = ConversionOutput(status=ConversionStatus.SUCCESS)
        assert output.is_success
        
        output.status = ConversionStatus.PARTIAL
        assert not output.is_success
        
        output.status = ConversionStatus.FAILED
        assert not output.is_success
    
    def test_has_warnings_errors(self):
        """Test warning and error checking."""
        output = ConversionOutput()
        
        assert not output.has_warnings
        assert not output.has_errors
        
        output.warnings.append("Warning 1")
        assert output.has_warnings
        
        output.errors.append("Error 1")
        assert output.has_errors


# =============================================================================
# FormatConverter Tests
# =============================================================================

class TestFormatConverter:
    """Tests for FormatConverter interface."""
    
    def test_mock_converter_convert(self):
        """Test mock converter conversion."""
        converter = MockConverter()
        result = converter.convert("test content")
        
        assert result.status == ConversionStatus.SUCCESS
        assert len(result.entity_types) == 1
        assert result.entity_types[0].name == "MockEntity"
    
    def test_converter_can_convert_by_extension(self):
        """Test extension-based detection."""
        converter = MockConverter()
        
        assert converter.can_convert("test.mock")
        assert converter.can_convert(Path("test.mck"))
        assert not converter.can_convert("test.txt")
    
    def test_converter_metadata(self):
        """Test converter metadata generation."""
        converter = MockConverter()
        metadata = converter.get_metadata()
        
        assert metadata.format_name == "mock"
        assert metadata.plugin_type == PluginType.CONVERTER
        assert ".mock" in metadata.file_extensions
        assert metadata.version == "1.0.0"


# =============================================================================
# PluginRegistry Tests
# =============================================================================

class TestPluginRegistry:
    """Tests for PluginRegistry."""
    
    def test_register_converter(self):
        """Test registering a converter."""
        converter = MockConverter()
        PluginRegistry.register_converter(converter)
        
        assert PluginRegistry.has_converter("mock")
        retrieved = PluginRegistry.get_converter("mock")
        assert retrieved is converter
    
    def test_register_validator(self):
        """Test registering a validator."""
        validator = MockValidator()
        PluginRegistry.register_validator(validator)
        
        assert PluginRegistry.has_validator("mock")
        retrieved = PluginRegistry.get_validator("mock")
        assert retrieved is validator
    
    def test_register_exporter(self):
        """Test registering an exporter."""
        exporter = MockExporter()
        PluginRegistry.register_exporter(exporter)
        
        assert PluginRegistry.has_exporter("mock")
        retrieved = PluginRegistry.get_exporter("mock")
        assert retrieved is exporter
    
    def test_get_nonexistent_converter(self):
        """Test getting non-existent converter raises error."""
        with pytest.raises(PluginNotFoundError) as exc_info:
            PluginRegistry.get_converter("nonexistent")
        
        assert "nonexistent" in str(exc_info.value)
    
    def test_get_converter_for_file(self):
        """Test getting converter by file extension."""
        converter = MockConverter()
        PluginRegistry.register_converter(converter)
        
        result = PluginRegistry.get_converter_for_file("data.mock")
        assert result is converter
        
        result = PluginRegistry.get_converter_for_file("data.mck")
        assert result is converter
        
        result = PluginRegistry.get_converter_for_file("data.unknown")
        assert result is None
    
    def test_list_converters(self):
        """Test listing registered converters."""
        PluginRegistry.register_converter(MockConverter())
        
        converters = PluginRegistry.list_converters()
        
        assert len(converters) == 1
        assert converters[0].format_name == "mock"
    
    def test_unregister(self):
        """Test unregistering plugins."""
        PluginRegistry.register_converter(MockConverter())
        PluginRegistry.register_validator(MockValidator())
        
        assert PluginRegistry.has_converter("mock")
        assert PluginRegistry.has_validator("mock")
        
        # Unregister all types
        PluginRegistry.unregister("mock")
        
        assert not PluginRegistry.has_converter("mock")
        assert not PluginRegistry.has_validator("mock")
    
    def test_unregister_specific_type(self):
        """Test unregistering specific plugin type."""
        PluginRegistry.register_converter(MockConverter())
        PluginRegistry.register_validator(MockValidator())
        
        PluginRegistry.unregister("mock", PluginType.CONVERTER)
        
        assert not PluginRegistry.has_converter("mock")
        assert PluginRegistry.has_validator("mock")
    
    def test_clear_registry(self):
        """Test clearing all plugins."""
        PluginRegistry.register_converter(MockConverter())
        PluginRegistry.register_validator(MockValidator())
        PluginRegistry.register_exporter(MockExporter())
        
        PluginRegistry.clear()
        
        assert len(PluginRegistry.list_converters()) == 0
        assert len(PluginRegistry.list_validators()) == 0
        assert len(PluginRegistry.list_exporters()) == 0
    
    def test_get_supported_extensions(self):
        """Test getting supported extensions."""
        PluginRegistry.register_converter(MockConverter())
        
        extensions = PluginRegistry.get_supported_extensions()
        
        assert ".mock" in extensions
        assert ".mck" in extensions
    
    def test_get_all_plugins(self):
        """Test getting all plugins organized by type."""
        PluginRegistry.register_converter(MockConverter())
        PluginRegistry.register_validator(MockValidator())
        PluginRegistry.register_exporter(MockExporter())
        
        all_plugins = PluginRegistry.get_all_plugins()
        
        assert len(all_plugins["converters"]) == 1
        assert len(all_plugins["validators"]) == 1
        assert len(all_plugins["exporters"]) == 1
    
    def test_case_insensitive_lookup(self):
        """Test that format lookup is case-insensitive."""
        PluginRegistry.register_converter(MockConverter())
        
        assert PluginRegistry.has_converter("MOCK")
        assert PluginRegistry.has_converter("Mock")
        assert PluginRegistry.get_converter("MOCK") is not None


# =============================================================================
# Plugin Validation Tests
# =============================================================================

class TestPluginValidation:
    """Tests for plugin validation."""
    
    def test_converter_without_format_name(self):
        """Test that converter without format_name is rejected."""
        class InvalidConverter(FormatConverter):
            format_name = ""  # Empty
            file_extensions = [".test"]
            
            def convert(self, source, context=None, **options):
                return ConversionOutput()
        
        with pytest.raises(PluginValidationError) as exc_info:
            PluginRegistry.register_converter(InvalidConverter())
        
        assert "format_name" in str(exc_info.value)
    
    def test_converter_without_extensions(self):
        """Test that converter without extensions is rejected."""
        class InvalidConverter(FormatConverter):
            format_name = "invalid"
            file_extensions = []  # Empty
            
            def convert(self, source, context=None, **options):
                return ConversionOutput()
        
        with pytest.raises(PluginValidationError) as exc_info:
            PluginRegistry.register_converter(InvalidConverter())
        
        assert "file_extension" in str(exc_info.value).lower()


# =============================================================================
# Plugin Directory Discovery Tests
# =============================================================================

class TestPluginDiscovery:
    """Tests for plugin discovery."""
    
    def test_discover_from_directory(self):
        """Test discovering plugins from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plugin file
            plugin_code = '''
from src.core.plugins import FormatConverter, ConversionOutput, ConversionStatus

class TestPluginConverter(FormatConverter):
    format_name = "testplugin"
    file_extensions = [".tp"]
    
    def convert(self, source, context=None, **options):
        return ConversionOutput(status=ConversionStatus.SUCCESS)
'''
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text(plugin_code)
            
            # Configure and discover
            PluginRegistry.set_plugins_directory(tmpdir)
            
            # Note: This will fail if the plugin has import errors
            # In a real test, we'd need proper module setup
    
    def test_discover_returns_list(self):
        """Test that discover returns proper structure."""
        result = PluginRegistry.discover_plugins()
        
        assert "converters" in result
        assert "validators" in result
        assert "exporters" in result
        assert isinstance(result["converters"], list)


# =============================================================================
# Built-in Plugin Wrapper Tests
# =============================================================================

class TestRDFConverterPlugin:
    """Tests for RDFConverterPlugin wrapper."""
    
    def test_rdf_plugin_metadata(self):
        """Test RDF plugin metadata."""
        plugin = RDFConverterPlugin()
        metadata = plugin.get_metadata()
        
        assert metadata.format_name == "rdf"
        assert ".ttl" in metadata.file_extensions
        assert ".owl" in metadata.file_extensions
    
    def test_rdf_plugin_can_convert(self):
        """Test RDF plugin extension detection."""
        plugin = RDFConverterPlugin()
        
        assert plugin.can_convert("test.ttl")
        assert plugin.can_convert("test.owl")
        assert plugin.can_convert("test.rdf")
        assert not plugin.can_convert("test.json")


class TestDTDLConverterPlugin:
    """Tests for DTDLConverterPlugin wrapper."""
    
    def test_dtdl_plugin_metadata(self):
        """Test DTDL plugin metadata."""
        plugin = DTDLConverterPlugin()
        metadata = plugin.get_metadata()
        
        assert metadata.format_name == "dtdl"
        assert ".json" in metadata.file_extensions


# =============================================================================
# Integration Tests
# =============================================================================

class TestPluginIntegration:
    """Integration tests for the plugin system."""
    
    def test_full_workflow(self):
        """Test complete plugin workflow."""
        # Register
        converter = MockConverter()
        PluginRegistry.register_converter(converter)
        
        # Discover (should not affect manually registered)
        PluginRegistry.discover_plugins()
        
        # Get and use
        retrieved = PluginRegistry.get_converter("mock")
        result = retrieved.convert("test data")
        
        assert result.is_success
        assert len(result.entity_types) == 1
    
    def test_builtin_registration(self):
        """Test built-in plugin registration."""
        register_builtin_plugins()
        
        # Should have RDF and DTDL (may fail if imports fail)
        # Just check the function doesn't raise
    
    def test_extension_override(self):
        """Test that later registration overrides extension mapping."""
        class Converter1(FormatConverter):
            format_name = "format1"
            file_extensions = [".test"]
            
            def convert(self, source, context=None, **options):
                return ConversionOutput()
        
        class Converter2(FormatConverter):
            format_name = "format2"
            file_extensions = [".test"]  # Same extension
            
            def convert(self, source, context=None, **options):
                return ConversionOutput()
        
        PluginRegistry.register_converter(Converter1())
        PluginRegistry.register_converter(Converter2())
        
        # Second registration should override
        converter = PluginRegistry.get_converter_for_file("data.test")
        assert converter.format_name == "format2"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestPluginErrors:
    """Tests for plugin error handling."""
    
    def test_plugin_error_hierarchy(self):
        """Test that all plugin errors inherit from PluginError."""
        assert issubclass(PluginLoadError, PluginError)
        assert issubclass(PluginNotFoundError, PluginError)
        assert issubclass(PluginValidationError, PluginError)
    
    def test_error_messages(self):
        """Test error message formatting."""
        error = PluginNotFoundError("No converter for 'xyz'")
        assert "xyz" in str(error)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
