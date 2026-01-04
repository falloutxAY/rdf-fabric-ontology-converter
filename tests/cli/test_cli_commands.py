"""
CLI Command Integration Tests.

Tests for CLI command operations including:
- Validate commands for RDF and DTDL formats
- Convert commands for RDF and DTDL formats
- Format detection and plugin dispatch
- Error handling for invalid inputs

These tests were added based on recommendations from the architecture review.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch


# Sample RDF content for testing
SAMPLE_RDF_CONTENT = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix : <http://example.org/test#> .

: a owl:Ontology ;
    rdfs:label "Test Ontology" .

:Person a owl:Class ;
    rdfs:label "Person" ;
    rdfs:comment "A human being" .

:Vehicle a owl:Class ;
    rdfs:label "Vehicle" ;
    rdfs:comment "A mode of transportation" .

:name a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string .

:age a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:integer .

:owns a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Vehicle .
"""

# Sample DTDL content for testing
SAMPLE_DTDL_CONTENT = json.dumps([
    {
        "@context": "dtmi:dtdl:context;3",
        "@id": "dtmi:com:example:Thermostat;1",
        "@type": "Interface",
        "displayName": "Thermostat",
        "description": "A simple thermostat interface",
        "contents": [
            {
                "@type": "Property",
                "name": "temperature",
                "schema": "double"
            },
            {
                "@type": "Property",
                "name": "setPoint",
                "schema": "double"
            },
            {
                "@type": "Property",
                "name": "mode",
                "schema": "string"
            },
            {
                "@type": "Telemetry",
                "name": "currentTemp",
                "schema": "double"
            }
        ]
    },
    {
        "@context": "dtmi:dtdl:context;3",
        "@id": "dtmi:com:example:Room;1",
        "@type": "Interface",
        "displayName": "Room",
        "contents": [
            {
                "@type": "Property",
                "name": "roomName",
                "schema": "string"
            },
            {
                "@type": "Relationship",
                "name": "hasThermostat",
                "target": "dtmi:com:example:Thermostat;1"
            }
        ]
    }
], indent=2)

# Invalid content for error testing
INVALID_RDF_CONTENT = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
This is not valid TTL syntax {
"""

INVALID_DTDL_CONTENT = """{ this is not valid JSON }"""


class TestCLIValidateCommand:
    """Tests for the validate CLI command."""
    
    @pytest.fixture
    def temp_rdf_file(self):
        """Create a temporary RDF file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            f.write(SAMPLE_RDF_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def temp_dtdl_file(self):
        """Create a temporary DTDL file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(SAMPLE_DTDL_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def invalid_rdf_file(self):
        """Create an invalid RDF file for testing error handling."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            f.write(INVALID_RDF_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def invalid_dtdl_file(self):
        """Create an invalid DTDL file for testing error handling."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(INVALID_DTDL_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    def test_validate_rdf_file_valid(self, temp_rdf_file):
        """Test validating a valid RDF file."""
        from formats.rdf import validate_ttl_file
        
        report = validate_ttl_file(temp_rdf_file)
        
        assert report is not None
        assert report.is_valid or report.error_count == 0
    
    def test_validate_rdf_content_valid(self):
        """Test validating valid RDF content directly."""
        from formats.rdf import validate_ttl_content
        
        report = validate_ttl_content(SAMPLE_RDF_CONTENT)
        
        assert report is not None
        assert report.is_valid or report.error_count == 0
    
    def test_validate_rdf_file_invalid(self, invalid_rdf_file):
        """Test validating an invalid RDF file returns errors."""
        from formats.rdf import validate_ttl_file
        
        report = validate_ttl_file(invalid_rdf_file)
        
        # Should return a report with errors
        assert report is not None
        assert not report.is_valid or report.error_count > 0
    
    def test_validate_dtdl_file_valid(self, temp_dtdl_file):
        """Test validating a valid DTDL file."""
        from formats.dtdl import DTDLParser, DTDLValidator
        
        parser = DTDLParser()
        interfaces = parser.parse_file(temp_dtdl_file)
        
        validator = DTDLValidator()
        errors = validator.validate(interfaces)
        
        # Valid DTDL should have no errors
        critical_errors = [e for e in errors if e.severity == 'error']
        assert len(critical_errors) == 0
    
    def test_validate_dtdl_content_valid(self):
        """Test validating valid DTDL content directly."""
        from formats.dtdl import DTDLParser, DTDLValidator
        
        parser = DTDLParser()
        interfaces = parser.parse_content(SAMPLE_DTDL_CONTENT)
        
        validator = DTDLValidator()
        errors = validator.validate(interfaces)
        
        # Valid DTDL should have no errors
        critical_errors = [e for e in errors if e.severity == 'error']
        assert len(critical_errors) == 0
    
    def test_validate_nonexistent_file(self):
        """Test validating a nonexistent file raises appropriate error."""
        from formats.rdf import validate_ttl_file
        
        with pytest.raises(FileNotFoundError):
            validate_ttl_file("/nonexistent/path/file.ttl")


class TestCLIConvertCommand:
    """Tests for the convert CLI command."""
    
    @pytest.fixture
    def temp_rdf_file(self):
        """Create a temporary RDF file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            f.write(SAMPLE_RDF_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def temp_dtdl_file(self):
        """Create a temporary DTDL file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(SAMPLE_DTDL_CONTENT)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    def test_convert_rdf_to_fabric(self, temp_rdf_file):
        """Test converting RDF to Fabric format."""
        from formats.rdf import parse_ttl_file
        
        definition, ontology_name = parse_ttl_file(temp_rdf_file)
        
        assert definition is not None
        assert 'parts' in definition
        assert ontology_name is not None
        
        # Should contain entity types
        entity_parts = [p for p in definition['parts'] if 'EntityTypes' in p.get('path', '')]
        assert len(entity_parts) > 0
    
    def test_convert_rdf_content_to_fabric(self):
        """Test converting RDF content to Fabric format."""
        from formats.rdf import parse_ttl_content
        
        definition, ontology_name = parse_ttl_content(SAMPLE_RDF_CONTENT)
        
        assert definition is not None
        assert 'parts' in definition
        
        # Should contain Person and Vehicle entity types
        entity_parts = [p for p in definition['parts'] if 'EntityTypes' in p.get('path', '')]
        assert len(entity_parts) >= 2  # At least Person and Vehicle
    
    def test_convert_rdf_with_result(self):
        """Test converting RDF with detailed result tracking."""
        from formats.rdf import parse_ttl_with_result
        
        definition, ontology_name, result = parse_ttl_with_result(SAMPLE_RDF_CONTENT)
        
        assert definition is not None
        assert result is not None
        assert len(result.entity_types) >= 2  # Person and Vehicle
        assert len(result.relationship_types) >= 1  # owns relationship
    
    def test_convert_dtdl_to_fabric(self, temp_dtdl_file):
        """Test converting DTDL to Fabric format."""
        from formats.dtdl import DTDLParser, DTDLToFabricConverter
        
        parser = DTDLParser()
        interfaces = parser.parse_file(temp_dtdl_file)
        
        converter = DTDLToFabricConverter()
        result = converter.convert(interfaces)
        
        assert result is not None
        assert len(result.entity_types) >= 2  # Thermostat and Room
        assert len(result.relationship_types) >= 1  # hasThermostat
    
    def test_convert_dtdl_content_to_fabric(self):
        """Test converting DTDL content to Fabric format."""
        from formats.dtdl import DTDLParser, DTDLToFabricConverter
        
        parser = DTDLParser()
        interfaces = parser.parse_content(SAMPLE_DTDL_CONTENT)
        
        converter = DTDLToFabricConverter()
        result = converter.convert(interfaces)
        
        # Should have both interfaces converted
        assert len(result.entity_types) == 2
        
        # Check entity names
        entity_names = [e.name for e in result.entity_types]
        assert 'Thermostat' in entity_names
        assert 'Room' in entity_names
    
    def test_convert_dtdl_to_definition(self):
        """Test converting DTDL to Fabric definition format."""
        from formats.dtdl import DTDLParser, DTDLToFabricConverter
        
        parser = DTDLParser()
        interfaces = parser.parse_content(SAMPLE_DTDL_CONTENT)
        
        converter = DTDLToFabricConverter()
        result = converter.convert(interfaces)
        definition = converter.to_fabric_definition(result, "TestOntology")
        
        assert definition is not None
        assert 'parts' in definition
        
        # Verify structure
        paths = [p['path'] for p in definition['parts']]
        assert '.platform' in paths
        assert 'definition.json' in paths


class TestCLIFormatDetection:
    """Tests for CLI format detection and plugin dispatch."""
    
    def test_detect_rdf_format_from_extension(self):
        """Test detecting RDF format from file extension."""
        from plugins import get_plugin_manager
        
        manager = get_plugin_manager()
        manager.discover_plugins()
        
        # .ttl should map to RDF plugin
        plugin = manager.get_plugin_for_extension('.ttl')
        assert plugin is not None
        assert plugin.format_name == 'rdf'
    
    def test_detect_dtdl_format_from_extension(self):
        """Test detecting DTDL format from file extension."""
        from plugins import get_plugin_manager
        
        manager = get_plugin_manager()
        manager.discover_plugins()
        
        # .json should map to DTDL plugin (or JSON-LD)
        plugin = manager.get_plugin_for_extension('.json')
        # May return dtdl or jsonld plugin
        assert plugin is not None
    
    def test_list_available_formats(self):
        """Test listing all available formats."""
        from plugins import get_plugin_manager
        
        manager = get_plugin_manager()
        manager.discover_plugins()
        
        formats = manager.list_formats()
        
        assert 'rdf' in formats
        assert 'dtdl' in formats
    
    def test_get_plugin_by_name(self):
        """Test getting plugin by format name."""
        from plugins import get_plugin_manager
        
        manager = get_plugin_manager()
        manager.discover_plugins()
        
        rdf_plugin = manager.get_plugin('rdf')
        dtdl_plugin = manager.get_plugin('dtdl')
        
        assert rdf_plugin is not None
        assert rdf_plugin.format_name == 'rdf'
        
        assert dtdl_plugin is not None
        assert dtdl_plugin.format_name == 'dtdl'


class TestCLIErrorHandling:
    """Tests for CLI error handling."""
    
    def test_invalid_file_path_error(self):
        """Test appropriate error for invalid file path."""
        from core.validators import InputValidator
        
        with pytest.raises((FileNotFoundError, ValueError)):
            InputValidator.validate_input_ttl_path("/nonexistent/path.ttl")
    
    def test_invalid_extension_error(self):
        """Test appropriate error for invalid file extension."""
        from core.validators import InputValidator
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
            f.write("content")
            f.flush()
            try:
                with pytest.raises(ValueError, match="extension"):
                    InputValidator.validate_input_ttl_path(f.name)
            finally:
                os.unlink(f.name)
    
    def test_empty_content_error(self):
        """Test appropriate error for empty content."""
        from core.validators import InputValidator
        
        with pytest.raises(ValueError, match="empty"):
            InputValidator.validate_ttl_content("")
    
    def test_whitespace_only_content_error(self):
        """Test appropriate error for whitespace-only content."""
        from core.validators import InputValidator
        
        with pytest.raises(ValueError, match="empty"):
            InputValidator.validate_ttl_content("   \n\t  ")


class TestCLIOutputFormats:
    """Tests for different CLI output formats."""
    
    def test_json_output_format(self):
        """Test JSON output from conversion."""
        from formats.rdf import parse_ttl_content
        
        definition, _ = parse_ttl_content(SAMPLE_RDF_CONTENT)
        
        # Definition should be JSON-serializable
        json_output = json.dumps(definition, indent=2)
        assert json_output is not None
        
        # Should be valid JSON that can be parsed back
        parsed = json.loads(json_output)
        assert 'parts' in parsed
    
    def test_conversion_result_summary(self):
        """Test conversion result summary generation."""
        from formats.rdf import parse_ttl_with_result
        
        _, _, result = parse_ttl_with_result(SAMPLE_RDF_CONTENT)
        
        summary = result.get_summary()
        
        assert 'entity_types' in summary
        assert 'relationship_types' in summary
        assert summary['entity_types'] >= 2
        assert summary['relationship_types'] >= 1


class TestDefinitionValidator:
    """Tests for the extracted FabricDefinitionValidator."""
    
    def test_validate_valid_definition(self):
        """Test validating a valid definition."""
        from core.validators import FabricDefinitionValidator
        from shared.models import EntityType, EntityTypeProperty, RelationshipType, RelationshipEnd
        
        # Create valid entity types
        entity1 = EntityType(
            id="1000000000001",
            name="Person",
            namespace="usertypes",
            properties=[
                EntityTypeProperty(id="1000000000001001", name="name", valueType="String"),
                EntityTypeProperty(id="1000000000001002", name="age", valueType="BigInt"),
            ],
            entityIdParts=["1000000000001001"],
            displayNamePropertyId="1000000000001001",
        )
        
        entity2 = EntityType(
            id="1000000000002",
            name="Vehicle",
            namespace="usertypes",
            properties=[
                EntityTypeProperty(id="1000000000002001", name="make", valueType="String"),
            ],
            entityIdParts=["1000000000002001"],
        )
        
        relationship = RelationshipType(
            id="1000000000003",
            name="owns",
            source=RelationshipEnd(entityTypeId="1000000000001"),
            target=RelationshipEnd(entityTypeId="1000000000002"),
        )
        
        is_valid, errors = FabricDefinitionValidator.validate_definition(
            [entity1, entity2], [relationship]
        )
        
        assert is_valid
        critical_errors = [e for e in errors if e.level == "error"]
        assert len(critical_errors) == 0
    
    def test_validate_invalid_parent_reference(self):
        """Test detecting invalid parent entity reference."""
        from core.validators import FabricDefinitionValidator
        from shared.models import EntityType, EntityTypeProperty
        
        entity = EntityType(
            id="1000000000001",
            name="Child",
            namespace="usertypes",
            baseEntityTypeId="9999999999999",  # Non-existent parent
            properties=[
                EntityTypeProperty(id="1000000000001001", name="prop", valueType="String"),
            ],
        )
        
        is_valid, errors = FabricDefinitionValidator.validate_definition([entity], [])
        
        assert not is_valid
        assert any("non-existent parent" in e.message for e in errors)
    
    def test_validate_self_inheritance(self):
        """Test detecting self-inheritance."""
        from core.validators import FabricDefinitionValidator
        from shared.models import EntityType, EntityTypeProperty
        
        entity = EntityType(
            id="1000000000001",
            name="SelfRef",
            namespace="usertypes",
            baseEntityTypeId="1000000000001",  # Self-reference
            properties=[
                EntityTypeProperty(id="1000000000001001", name="prop", valueType="String"),
            ],
        )
        
        is_valid, errors = FabricDefinitionValidator.validate_definition([entity], [])
        
        assert not is_valid
        assert any("cannot inherit from itself" in e.message for e in errors)
    
    def test_validate_invalid_relationship_reference(self):
        """Test detecting invalid relationship entity reference."""
        from core.validators import FabricDefinitionValidator
        from shared.models import EntityType, EntityTypeProperty, RelationshipType, RelationshipEnd
        
        entity = EntityType(
            id="1000000000001",
            name="Person",
            namespace="usertypes",
            properties=[
                EntityTypeProperty(id="1000000000001001", name="name", valueType="String"),
            ],
        )
        
        relationship = RelationshipType(
            id="1000000000003",
            name="badRelation",
            source=RelationshipEnd(entityTypeId="1000000000001"),
            target=RelationshipEnd(entityTypeId="9999999999999"),  # Non-existent
        )
        
        is_valid, errors = FabricDefinitionValidator.validate_definition([entity], [relationship])
        
        assert not is_valid
        assert any("non-existent entity" in e.message for e in errors)


class TestStreamingConverter:
    """Tests for the extracted StreamingRDFConverter."""
    
    @pytest.fixture
    def temp_large_rdf_file(self):
        """Create a larger temporary RDF file for streaming tests."""
        content_parts = [
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "@prefix : <http://example.org/test#> .",
            "",
            ": a owl:Ontology .",
        ]
        
        # Generate multiple classes
        for i in range(50):
            content_parts.append(f":Class{i} a owl:Class ; rdfs:label \"Class {i}\" .")
            content_parts.append(f":prop{i} a owl:DatatypeProperty ; rdfs:domain :Class{i} ; rdfs:range xsd:string .")
        
        content = "\n".join(content_parts)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    def test_streaming_converter_basic(self, temp_large_rdf_file):
        """Test basic streaming conversion."""
        from formats.rdf import StreamingRDFConverter
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_large_rdf_file)
        
        assert result is not None
        assert len(result.entity_types) == 50  # 50 classes
    
    def test_streaming_converter_with_callback(self, temp_large_rdf_file):
        """Test streaming conversion with progress callback."""
        from formats.rdf import StreamingRDFConverter
        
        progress_calls = []
        
        def progress_callback(count):
            progress_calls.append(count)
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(
            temp_large_rdf_file,
            progress_callback=progress_callback
        )
        
        assert result is not None
        assert len(progress_calls) >= 1  # At least start/end callbacks
    
    def test_streaming_converter_statistics(self, temp_large_rdf_file):
        """Test streaming converter statistics."""
        from formats.rdf import StreamingRDFConverter
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_large_rdf_file)
        
        stats = converter.get_statistics()
        
        assert 'classes_found' in stats
        assert stats['classes_found'] == 50
        assert 'entities_created' in stats
        assert stats['entities_created'] == 50
