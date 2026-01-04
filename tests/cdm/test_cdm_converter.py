"""
CDM Converter Unit Tests.

Tests for CDM to Fabric conversion functionality.
"""

import pytest
import sys
import os

# Add src to path
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from formats.cdm.cdm_converter import CDMToFabricConverter
from formats.cdm.cdm_models import CDMManifest, CDMEntity, CDMAttribute, CDMRelationship
from shared.models.conversion import ConversionResult
from shared.models.fabric_types import EntityType, RelationshipType

from . import (
    SIMPLE_ENTITY_SCHEMA,
    ENTITY_WITH_ALL_TYPES,
    ENTITY_WITH_INHERITANCE,
    MANIFEST_WITH_RELATIONSHIPS,
    MODEL_JSON,
)


@pytest.mark.unit
class TestCDMConverter:
    """CDM converter unit tests."""
    
    def test_converter_initialization(self):
        """Test converter can be initialized."""
        converter = CDMToFabricConverter()
        assert converter is not None
        assert converter.namespace == "usertypes"
        assert converter.flatten_inheritance is True
    
    def test_converter_custom_namespace(self):
        """Test converter with custom namespace."""
        converter = CDMToFabricConverter(namespace="customns")
        assert converter.namespace == "customns"
    
    # =========================================================================
    # Entity Conversion
    # =========================================================================
    
    def test_convert_simple_entity(self, simple_entity_schema):
        """Convert basic entity to EntityType."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        assert isinstance(result, ConversionResult)
        assert len(result.entity_types) == 1
        
        entity = result.entity_types[0]
        assert isinstance(entity, EntityType)
        assert entity.name == "Person"
        assert entity.namespace == "usertypes"
    
    def test_convert_entity_id(self, simple_entity_schema):
        """Converted entity has valid ID."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        assert entity.id is not None
        assert len(entity.id) >= 10  # 13-digit string
        assert entity.id.isdigit()
    
    def test_convert_entity_properties(self, simple_entity_schema):
        """Convert entity attributes to properties."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        assert len(entity.properties) >= 4  # At least 4 properties (email has semantic meaning)
        
        prop_names = [p.name for p in entity.properties]
        assert "personId" in prop_names
        assert "fullName" in prop_names
        assert "age" in prop_names
        assert "isActive" in prop_names
    
    def test_convert_property_types(self, simple_entity_schema):
        """Property types are correctly mapped."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        props_by_name = {p.name: p for p in entity.properties}
        
        assert props_by_name["personId"].valueType == "String"
        assert props_by_name["fullName"].valueType == "String"  # 'name' maps to String
        assert props_by_name["age"].valueType == "BigInt"  # integer maps to BigInt
        assert props_by_name["isActive"].valueType == "Boolean"
    
    def test_convert_all_types(self, entity_with_all_types):
        """Convert entity with all data types."""
        converter = CDMToFabricConverter()
        result = converter.convert(entity_with_all_types)
        
        entity = result.entity_types[0]
        props_by_name = {p.name: p for p in entity.properties}
        
        # Verify type mappings
        assert props_by_name["stringAttr"].valueType == "String"
        assert props_by_name["intAttr"].valueType == "BigInt"
        assert props_by_name["int64Attr"].valueType == "BigInt"
        assert props_by_name["doubleAttr"].valueType == "Double"
        assert props_by_name["floatAttr"].valueType == "Double"
        assert props_by_name["decimalAttr"].valueType == "Decimal"
        assert props_by_name["boolAttr"].valueType == "Boolean"
        assert props_by_name["dateAttr"].valueType == "DateTime"
        assert props_by_name["dateTimeAttr"].valueType == "DateTime"
        assert props_by_name["guidAttr"].valueType == "String"
        
        # Semantic types
        assert props_by_name["nameAttr"].valueType == "String"
        assert props_by_name["emailAttr"].valueType == "String"
        assert props_by_name["phoneAttr"].valueType == "String"
        assert props_by_name["urlAttr"].valueType == "String"
        assert props_by_name["currencyAttr"].valueType == "Decimal"
        assert props_by_name["yearAttr"].valueType == "BigInt"
    
    def test_convert_primary_key(self, simple_entity_schema):
        """Primary key attribute is tracked in entityIdParts."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        # Should have entityIdParts set
        assert len(entity.entityIdParts) >= 1
        
        # The ID should reference personId property
        pk_id = entity.entityIdParts[0]
        pk_prop = next(p for p in entity.properties if p.id == pk_id)
        assert pk_prop.name == "personId"
    
    def test_convert_display_name_property(self, simple_entity_schema):
        """Display name property is identified."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        assert entity.displayNamePropertyId is not None
        
        display_prop = next(p for p in entity.properties 
                          if p.id == entity.displayNamePropertyId)
        assert display_prop.name == "fullName"
    
    # =========================================================================
    # Inheritance Handling
    # =========================================================================
    
    def test_convert_inheritance_flattened(self, entity_with_inheritance):
        """Inherited attributes are flattened."""
        converter = CDMToFabricConverter(flatten_inheritance=True)
        result = converter.convert(entity_with_inheritance)
        
        # Should have 2 entity types
        assert len(result.entity_types) == 2
        
        entities_by_name = {e.name: e for e in result.entity_types}
        derived = entities_by_name["DerivedEntity"]
        
        # DerivedEntity should have inherited + own attributes
        prop_names = [p.name for p in derived.properties]
        assert "derivedField" in prop_names
        assert "id" in prop_names  # Inherited from BaseEntity
        assert "createdOn" in prop_names  # Inherited from BaseEntity
    
    def test_convert_inheritance_not_flattened(self, entity_with_inheritance):
        """Inheritance preserved when not flattening."""
        converter = CDMToFabricConverter(flatten_inheritance=False)
        result = converter.convert(entity_with_inheritance)
        
        entities_by_name = {e.name: e for e in result.entity_types}
        derived = entities_by_name["DerivedEntity"]
        
        # DerivedEntity should only have its own attributes
        prop_names = [p.name for p in derived.properties]
        assert "derivedField" in prop_names
        # Should not have inherited attributes
        assert len(prop_names) == 1
    
    # =========================================================================
    # Relationship Conversion
    # =========================================================================
    
    def test_convert_relationships(self, manifest_with_relationships):
        """Convert CDM relationships to RelationshipTypes."""
        converter = CDMToFabricConverter()
        result = converter.convert(manifest_with_relationships)
        
        assert len(result.relationship_types) == 1
        
        rel = result.relationship_types[0]
        assert isinstance(rel, RelationshipType)
        assert rel.name == "placedBy"
        assert rel.namespace == "usertypes"
    
    def test_convert_relationship_endpoints(self, manifest_with_relationships):
        """Relationship endpoints reference correct entities."""
        converter = CDMToFabricConverter()
        result = converter.convert(manifest_with_relationships)
        
        rel = result.relationship_types[0]
        
        # Source and target should have entity IDs
        assert rel.source.entityTypeId is not None
        assert rel.target.entityTypeId is not None
        
        # IDs should be different
        assert rel.source.entityTypeId != rel.target.entityTypeId
    
    def test_convert_relationship_id(self, manifest_with_relationships):
        """Converted relationship has valid ID."""
        converter = CDMToFabricConverter()
        result = converter.convert(manifest_with_relationships)
        
        rel = result.relationship_types[0]
        assert rel.id is not None
        assert len(rel.id) >= 10
        assert rel.id.isdigit()
    
    # =========================================================================
    # Legacy model.json Conversion
    # =========================================================================
    
    def test_convert_model_json(self, model_json):
        """Convert legacy model.json format."""
        converter = CDMToFabricConverter()
        result = converter.convert(model_json)
        
        assert len(result.entity_types) == 2
        
        entity_names = [e.name for e in result.entity_types]
        assert "Product" in entity_names
        assert "Category" in entity_names
    
    def test_convert_model_json_properties(self, model_json):
        """Convert model.json entity properties."""
        converter = CDMToFabricConverter()
        result = converter.convert(model_json)
        
        product = next(e for e in result.entity_types if e.name == "Product")
        assert len(product.properties) == 4
        
        props_by_name = {p.name: p for p in product.properties}
        assert props_by_name["productId"].valueType == "String"
        assert props_by_name["price"].valueType == "Decimal"
        assert props_by_name["quantity"].valueType == "BigInt"
    
    # =========================================================================
    # Conversion Result
    # =========================================================================
    
    def test_conversion_result_statistics(self, simple_entity_schema):
        """Conversion result includes statistics."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        assert result.interface_count >= 1
        assert result.success_rate > 0
    
    def test_conversion_result_no_skipped(self, simple_entity_schema):
        """Valid content has no skipped items."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        assert len(result.skipped_items) == 0
    
    def test_conversion_result_summary(self, simple_entity_schema):
        """Conversion result has summary."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        summary = result.get_summary()
        assert "Entity Types" in summary
        assert "1" in summary  # At least 1 entity
    
    # =========================================================================
    # Entity ID Map
    # =========================================================================
    
    def test_entity_id_map(self, simple_entity_schema):
        """Converter tracks entity name to ID mapping."""
        converter = CDMToFabricConverter()
        converter.convert(simple_entity_schema)
        
        id_map = converter.get_entity_id_map()
        assert "Person" in id_map
        assert id_map["Person"].isdigit()


@pytest.mark.unit  
class TestCDMConverterEdgeCases:
    """Test converter edge cases."""
    
    def test_empty_manifest(self):
        """Convert empty manifest."""
        converter = CDMToFabricConverter()
        
        manifest = CDMManifest(name="Empty", entities=[])
        result = converter.convert_manifest(manifest)
        
        assert len(result.entity_types) == 0
        assert len(result.relationship_types) == 0
    
    def test_entity_without_attributes(self):
        """Convert entity with no attributes."""
        converter = CDMToFabricConverter()
        
        manifest = CDMManifest(
            name="Test",
            entities=[CDMEntity(name="EmptyEntity")]
        )
        result = converter.convert_manifest(manifest)
        
        assert len(result.entity_types) == 1
        entity = result.entity_types[0]
        assert len(entity.properties) == 0
    
    def test_entity_reference_attribute_skipped(self):
        """Entity reference attributes are skipped."""
        converter = CDMToFabricConverter()
        
        manifest = CDMManifest(
            name="Test",
            entities=[
                CDMEntity(
                    name="TestEntity",
                    attributes=[
                        CDMAttribute(name="regularField", data_type="string"),
                        CDMAttribute(name="entityRef", data_type="entity"),
                    ]
                )
            ]
        )
        result = converter.convert_manifest(manifest)
        
        entity = result.entity_types[0]
        # Entity reference should be skipped
        prop_names = [p.name for p in entity.properties]
        assert "regularField" in prop_names
        assert "entityRef" not in prop_names
    
    def test_unique_ids_generated(self):
        """All generated IDs are unique."""
        converter = CDMToFabricConverter()
        
        content = '''
        {
            "jsonSchemaSemanticVersion": "1.0.0",
            "definitions": [
                {
                    "entityName": "Entity1",
                    "hasAttributes": [
                        {"name": "field1", "dataType": "string"},
                        {"name": "field2", "dataType": "integer"}
                    ]
                },
                {
                    "entityName": "Entity2",
                    "hasAttributes": [
                        {"name": "field3", "dataType": "boolean"}
                    ]
                }
            ]
        }'''
        
        result = converter.convert(content)
        
        # Collect all IDs
        all_ids = []
        for entity in result.entity_types:
            all_ids.append(entity.id)
            for prop in entity.properties:
                all_ids.append(prop.id)
        
        # All IDs should be unique
        assert len(all_ids) == len(set(all_ids))
    
    def test_convert_error_handling(self):
        """Converter handles invalid content gracefully."""
        converter = CDMToFabricConverter()
        
        result = converter.convert("{ invalid json }")
        
        # Should have skipped items
        assert len(result.skipped_items) >= 1
        assert "Parse error" in result.skipped_items[0].reason


@pytest.mark.unit
class TestFabricTypeOutput:
    """Test Fabric type output format."""
    
    def test_entity_type_to_dict(self, simple_entity_schema):
        """EntityType can be serialized to dict."""
        converter = CDMToFabricConverter()
        result = converter.convert(simple_entity_schema)
        
        entity = result.entity_types[0]
        data = entity.to_dict()
        
        assert "id" in data
        assert "name" in data
        assert "namespace" in data
        assert "properties" in data
    
    def test_relationship_type_to_dict(self, manifest_with_relationships):
        """RelationshipType can be serialized to dict."""
        converter = CDMToFabricConverter()
        result = converter.convert(manifest_with_relationships)
        
        rel = result.relationship_types[0]
        data = rel.to_dict()
        
        assert "id" in data
        assert "name" in data
        assert "source" in data
        assert "target" in data
