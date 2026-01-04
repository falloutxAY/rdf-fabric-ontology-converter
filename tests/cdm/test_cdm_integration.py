"""
CDM Integration Tests.

End-to-end tests for the CDM format plugin including full pipeline tests.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path

# Add src to path
import sys
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from formats.cdm import (
    CDMParser,
    CDMValidator,
    CDMToFabricConverter,
    CDM_TYPE_MAPPINGS,
    CDM_SEMANTIC_TYPE_MAPPINGS,
)
from plugins.builtin.cdm_plugin import CDMPlugin
from shared.models import EntityType, RelationshipType


# Sample directory
SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "cdm"


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================

@pytest.mark.integration
class TestCDMPipeline:
    """Full CDM pipeline integration tests."""
    
    def test_full_pipeline_simple_manifest(self):
        """Test full pipeline with simple manifest."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        
        # 1. Read file
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 2. Parse
        parser = CDMParser()
        parsed = parser.parse(content, str(manifest_path))
        assert parsed is not None
        assert len(parsed.entities) >= 3
        
        # 3. Validate
        validator = CDMValidator()
        validation = validator.validate(content, str(manifest_path))
        assert validation.is_valid is True
        
        # 4. Convert
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        assert result.success_rate == 100.0
        assert len(result.entity_types) >= 3
        
        # 5. Verify entity types
        for entity_type in result.entity_types:
            assert isinstance(entity_type, EntityType)
            assert entity_type.name is not None
            assert entity_type.id is not None
            # Properties may be empty for some entities
    
    def test_full_pipeline_healthcare_industry(self):
        """Test full pipeline with healthcare industry samples."""
        manifest_path = SAMPLES_DIR / "industry" / "healthcare" / "healthcare.manifest.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse
        parser = CDMParser()
        parsed = parser.parse(content, str(manifest_path))
        assert parsed.name == "HealthcareManifest"
        
        # Validate
        validator = CDMValidator()
        validation = validator.validate(content, str(manifest_path))
        assert validation.is_valid is True
        
        # Convert
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        assert result.success_rate == 100.0
        
        # Verify healthcare-specific entities
        entity_names = {e.name for e in result.entity_types}
        assert "Patient" in entity_names
        assert "Practitioner" in entity_names
        assert "Encounter" in entity_names
        assert "Appointment" in entity_names
    
    def test_full_pipeline_model_json(self):
        """Test full pipeline with model.json format."""
        model_path = SAMPLES_DIR / "model-json" / "OrdersProducts" / "model.json"
        
        with open(model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse
        parser = CDMParser()
        parsed = parser.parse(content, str(model_path))
        assert parsed.name == "OrdersProductsModel"
        
        # Validate
        validator = CDMValidator()
        validation = validator.validate(content, str(model_path))
        assert validation.is_valid is True
        
        # Convert
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(model_path))
        assert result.success_rate == 100.0
        
        # Verify entities
        entity_names = {e.name for e in result.entity_types}
        assert "Customer" in entity_names
        assert "Product" in entity_names
        assert "Order" in entity_names


# =============================================================================
# Plugin Integration Tests
# =============================================================================

@pytest.mark.integration
class TestCDMPluginIntegration:
    """CDM plugin integration tests."""
    
    def test_plugin_full_workflow(self):
        """Test complete plugin workflow."""
        plugin = CDMPlugin()
        
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get components from plugin
        parser = plugin.get_parser()
        validator = plugin.get_validator()
        converter = plugin.get_converter()
        
        # Execute pipeline
        parsed = parser.parse(content, str(manifest_path))
        assert parsed is not None
        
        validation = validator.validate(content, str(manifest_path))
        assert validation.is_valid is True
        
        result = converter.convert(content, source_path=str(manifest_path))
        assert result.success_rate == 100.0
    
    def test_plugin_file_detection(self):
        """Test plugin file detection."""
        plugin = CDMPlugin()
        
        # Should handle CDM files
        assert plugin.can_handle_file("test.cdm.json") is True
        assert plugin.can_handle_file("test.manifest.cdm.json") is True
        assert plugin.can_handle_file("model.json") is True
        
        # Should not handle non-CDM files
        assert plugin.can_handle_file("test.ttl") is False
        assert plugin.can_handle_file("test.rdf") is False
    
    def test_plugin_type_mappings(self):
        """Test plugin type mappings are accessible."""
        plugin = CDMPlugin()
        
        mappings = plugin.get_type_mappings()
        
        assert "string" in mappings
        assert "integer" in mappings
        assert "boolean" in mappings
        assert mappings["string"] == "String"
        assert mappings["integer"] == "BigInt"
    
    def test_plugin_format_info(self):
        """Test plugin format information."""
        plugin = CDMPlugin()
        
        assert plugin.format_name == "cdm"
        assert "CDM" in plugin.display_name or "Common Data Model" in plugin.display_name
        assert plugin.version is not None


# =============================================================================
# Entity Type Verification Tests
# =============================================================================

@pytest.mark.integration
class TestEntityTypeOutput:
    """Tests verifying EntityType output structure."""
    
    def test_entity_type_structure(self):
        """Verify EntityType output has correct structure."""
        manifest_path = SAMPLES_DIR / "simple" / "Person.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        assert result.success_rate == 100.0
        assert len(result.entity_types) > 0
        
        person = result.entity_types[0]
        assert person.name == "Person"
        assert person.id is not None
        assert len(person.id) == 13  # Fabric ID format
        assert person.id.isdigit()
        
        # Verify properties
        assert len(person.properties) > 0
        prop_names = {p.name for p in person.properties}
        assert "personId" in prop_names
        assert "firstName" in prop_names
        assert "lastName" in prop_names
    
    def test_entity_type_property_types(self):
        """Verify property types are correctly mapped."""
        manifest_path = SAMPLES_DIR / "simple" / "Person.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        person = result.entity_types[0]
        
        # Find specific properties
        props_by_name = {p.name: p for p in person.properties}
        
        # String types
        assert props_by_name["personId"].valueType == "String"
        
        # Date types
        if "dateOfBirth" in props_by_name:
            assert props_by_name["dateOfBirth"].valueType == "DateTime"
        
        # Boolean types
        if "isActive" in props_by_name:
            assert props_by_name["isActive"].valueType == "Boolean"
    
    def test_relationship_type_output(self):
        """Verify RelationshipType output from manifest."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        # Should have relationships
        assert len(result.relationship_types) > 0
        
        for rel in result.relationship_types:
            assert isinstance(rel, RelationshipType)
            assert rel.name is not None
            assert rel.id is not None
            assert len(rel.id) == 13


# =============================================================================
# Cross-Industry Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.industry
class TestCrossIndustryIntegration:
    """Integration tests across different industries."""
    
    @pytest.mark.parametrize("industry,manifest_name", [
        ("healthcare", "healthcare.manifest.cdm.json"),
        ("financial-services", "banking.manifest.cdm.json"),
        ("automotive", "automotive.manifest.cdm.json"),
        ("education", "education.manifest.cdm.json"),
    ])
    def test_industry_manifest_pipeline(self, industry, manifest_name):
        """Test full pipeline for each industry manifest."""
        manifest_path = SAMPLES_DIR / "industry" / industry / manifest_name
        
        if not manifest_path.exists():
            pytest.skip(f"Industry manifest not found: {manifest_path}")
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Full pipeline
        parser = CDMParser()
        validator = CDMValidator()
        converter = CDMToFabricConverter()
        
        parsed = parser.parse(content, str(manifest_path))
        assert parsed is not None
        
        validation = validator.validate(content, str(manifest_path))
        assert validation.is_valid is True, f"Validation failed for {industry}"
        
        result = converter.convert(content, source_path=str(manifest_path))
        assert result.success_rate == 100.0, f"Conversion failed for {industry}"
        assert len(result.entity_types) > 0


# =============================================================================
# Error Handling Integration Tests
# =============================================================================

@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling."""
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON."""
        invalid_json = "{ invalid json content }"
        
        parser = CDMParser()
        validator = CDMValidator()
        
        # Parser should handle gracefully
        with pytest.raises(Exception):
            parser.parse(invalid_json, "test.cdm.json")
        
        # Validator should report error
        result = validator.validate(invalid_json, "test.cdm.json")
        assert result.is_valid is False
    
    def test_empty_manifest_handling(self):
        """Test handling of empty manifest."""
        empty_manifest = json.dumps({
            "manifestName": "Empty",
            "jsonSchemaSemanticVersion": "1.0.0",
            "entities": []
        })
        
        parser = CDMParser()
        result = parser.parse(empty_manifest, "empty.manifest.cdm.json")
        
        assert result is not None
        assert result.name == "Empty"
        assert len(result.entities) == 0
    
    def test_missing_attribute_type_handling(self):
        """Test handling of missing attribute data type."""
        schema = json.dumps({
            "jsonSchemaSemanticVersion": "1.0.0",
            "definitions": [{
                "entityName": "Test",
                "hasAttributes": [
                    {"name": "testAttr"}  # Missing dataType
                ]
            }]
        })
        
        validator = CDMValidator()
        result = validator.validate(schema, "test.cdm.json")
        
        # Missing type defaults to string, may have info messages
        # The validator is lenient about missing types
        assert result is not None


# =============================================================================
# Output Serialization Tests
# =============================================================================

@pytest.mark.integration
class TestOutputSerialization:
    """Tests for output serialization."""
    
    def test_entity_type_to_dict(self):
        """Test EntityType serialization to dict."""
        manifest_path = SAMPLES_DIR / "simple" / "Person.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        for entity_type in result.entity_types:
            entity_dict = entity_type.to_dict()
            
            assert "name" in entity_dict
            assert "id" in entity_dict
            assert "properties" in entity_dict
            assert isinstance(entity_dict["properties"], list)
    
    def test_conversion_result_to_json(self):
        """Test ConversionResult can be serialized to JSON."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        # Should be serializable
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict, indent=2)
        
        assert len(json_str) > 0
        
        # Should be parseable
        parsed = json.loads(json_str)
        assert "entity_types_count" in parsed
        assert parsed["entity_types_count"] >= 3
    
    def test_save_output_to_file(self):
        """Test saving conversion output to file."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(result.to_dict(), f, indent=2)
            temp_path = f.name
        
        try:
            # Read back and verify
            with open(temp_path, 'r') as f:
                loaded = json.load(f)
            
            assert "entity_types_count" in loaded
            assert loaded["entity_types_count"] > 0
        finally:
            os.unlink(temp_path)


# =============================================================================
# Performance Integration Tests
# =============================================================================

@pytest.mark.integration
class TestPerformance:
    """Performance-related integration tests."""
    
    def test_large_entity_conversion(self):
        """Test conversion of entity with many attributes."""
        # Healthcare Patient has many attributes
        patient_path = SAMPLES_DIR / "industry" / "healthcare" / "Patient.cdm.json"
        
        with open(patient_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(patient_path))
        
        assert result.success_rate == 100.0
        
        patient = result.entity_types[0]
        assert len(patient.properties) > 20  # Patient has many attributes
    
    def test_manifest_with_relationships(self):
        """Test manifest with multiple relationships."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        assert result.success_rate == 100.0
        assert len(result.relationship_types) >= 3  # PersonHasContact, OrderBelongsToPerson, etc.
