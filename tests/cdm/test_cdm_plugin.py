"""
CDM Plugin Unit Tests.

Tests for the CDM plugin wrapper.
"""

import pytest
import sys
import os

# Add src to path
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from plugins.builtin.cdm_plugin import CDMPlugin


@pytest.mark.unit
class TestCDMPlugin:
    """CDM plugin unit tests."""
    
    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = CDMPlugin()
        assert plugin is not None
    
    def test_format_name(self):
        """Test format name property."""
        plugin = CDMPlugin()
        assert plugin.format_name == "cdm"
    
    def test_display_name(self):
        """Test display name property."""
        plugin = CDMPlugin()
        assert "CDM" in plugin.display_name
        assert "Common Data Model" in plugin.display_name
    
    def test_file_extensions(self):
        """Test supported file extensions."""
        plugin = CDMPlugin()
        extensions = plugin.file_extensions
        
        assert ".cdm.json" in extensions
        assert ".manifest.cdm.json" in extensions
        assert ".json" in extensions
    
    def test_version(self):
        """Test plugin version."""
        plugin = CDMPlugin()
        assert plugin.version == "1.0.0"
    
    def test_author(self):
        """Test plugin author."""
        plugin = CDMPlugin()
        assert plugin.author is not None
        assert len(plugin.author) > 0
    
    def test_description(self):
        """Test plugin description."""
        plugin = CDMPlugin()
        assert plugin.description is not None
        assert "CDM" in plugin.description or "Common Data Model" in plugin.description
    
    def test_dependencies_empty(self):
        """Test plugin has no external dependencies."""
        plugin = CDMPlugin()
        assert plugin.dependencies == []
    
    # =========================================================================
    # Component Access
    # =========================================================================
    
    def test_get_parser(self):
        """Test getting parser instance."""
        plugin = CDMPlugin()
        parser = plugin.get_parser()
        
        assert parser is not None
        assert hasattr(parser, 'parse')
        assert hasattr(parser, 'parse_file')
    
    def test_get_validator(self):
        """Test getting validator instance."""
        plugin = CDMPlugin()
        validator = plugin.get_validator()
        
        assert validator is not None
        assert hasattr(validator, 'validate')
    
    def test_get_converter(self):
        """Test getting converter instance."""
        plugin = CDMPlugin()
        converter = plugin.get_converter()
        
        assert converter is not None
        assert hasattr(converter, 'convert')
    
    def test_get_type_mappings(self):
        """Test getting type mappings."""
        plugin = CDMPlugin()
        mappings = plugin.get_type_mappings()
        
        assert isinstance(mappings, dict)
        assert len(mappings) > 0
        assert "string" in mappings
        assert "integer" in mappings
        assert mappings["string"] == "String"
    
    # =========================================================================
    # File Detection
    # =========================================================================
    
    def test_can_handle_cdm_json(self):
        """Test detection of .cdm.json files."""
        plugin = CDMPlugin()
        
        assert plugin.can_handle_file("Person.cdm.json") is True
        assert plugin.can_handle_file("/path/to/Entity.cdm.json") is True
        assert plugin.can_handle_file("C:\\folder\\Model.cdm.json") is True
    
    def test_can_handle_manifest(self):
        """Test detection of manifest files."""
        plugin = CDMPlugin()
        
        assert plugin.can_handle_file("test.manifest.cdm.json") is True
        assert plugin.can_handle_file("/path/to/model.manifest.cdm.json") is True
    
    def test_can_handle_model_json(self):
        """Test detection of model.json files."""
        plugin = CDMPlugin()
        
        assert plugin.can_handle_file("model.json") is True
        assert plugin.can_handle_file("/path/to/model.json") is True
    
    def test_cannot_handle_other_extensions(self):
        """Test rejection of non-CDM files."""
        plugin = CDMPlugin()
        
        # These are JSON but need content inspection
        assert plugin.can_handle_file("data.txt") is False
        assert plugin.can_handle_file("schema.xml") is False
        assert plugin.can_handle_file("ontology.ttl") is False
    
    # =========================================================================
    # Document Type Detection
    # =========================================================================
    
    def test_detect_manifest_type(self):
        """Detect manifest document type."""
        plugin = CDMPlugin()
        
        content = '{"manifestName": "Test", "entities": []}'
        doc_type = plugin.detect_cdm_document_type(content)
        
        assert doc_type == "manifest"
    
    def test_detect_entity_schema_type(self):
        """Detect entity schema document type."""
        plugin = CDMPlugin()
        
        content = '{"definitions": [{"entityName": "Test"}]}'
        doc_type = plugin.detect_cdm_document_type(content)
        
        assert doc_type == "entity_schema"
    
    def test_detect_model_json_type(self):
        """Detect model.json document type."""
        plugin = CDMPlugin()
        
        content = '{"name": "TestModel", "entities": [{"$type": "LocalEntity"}]}'
        doc_type = plugin.detect_cdm_document_type(content)
        
        assert doc_type == "model_json"
    
    def test_detect_invalid_json(self):
        """Invalid JSON returns None."""
        plugin = CDMPlugin()
        
        content = "{ invalid json }"
        doc_type = plugin.detect_cdm_document_type(content)
        
        assert doc_type is None


@pytest.mark.unit
class TestCDMPluginIntegration:
    """Integration tests using plugin components together."""
    
    def test_parse_and_validate(self):
        """Parse and validate using plugin components."""
        plugin = CDMPlugin()
        
        content = '''
        {
            "jsonSchemaSemanticVersion": "1.0.0",
            "definitions": [
                {
                    "entityName": "Product",
                    "hasAttributes": [
                        {"name": "productId", "dataType": "string"},
                        {"name": "price", "dataType": "decimal"}
                    ]
                }
            ]
        }'''
        
        parser = plugin.get_parser()
        manifest = parser.parse(content)
        
        validator = plugin.get_validator()
        result = validator.validate_manifest(manifest)
        
        assert result.is_valid is True
    
    def test_full_pipeline(self):
        """Run full parse-validate-convert pipeline."""
        plugin = CDMPlugin()
        
        content = '''
        {
            "jsonSchemaSemanticVersion": "1.0.0",
            "definitions": [
                {
                    "entityName": "Customer",
                    "hasAttributes": [
                        {"name": "customerId", "dataType": "string", "purpose": "identifiedBy"},
                        {"name": "fullName", "dataType": "name"},
                        {"name": "email", "dataType": "email"}
                    ]
                }
            ]
        }'''
        
        # Parse
        parser = plugin.get_parser()
        manifest = parser.parse(content)
        assert len(manifest.entities) == 1
        
        # Validate
        validator = plugin.get_validator()
        validation_result = validator.validate_manifest(manifest)
        assert validation_result.is_valid is True
        
        # Convert
        converter = plugin.get_converter()
        conversion_result = converter.convert_manifest(manifest)
        assert len(conversion_result.entity_types) == 1
        
        entity = conversion_result.entity_types[0]
        assert entity.name == "Customer"
        assert len(entity.properties) == 3
