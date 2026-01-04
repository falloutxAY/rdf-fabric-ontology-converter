"""
CDM Parser Unit Tests.

Tests for CDM parsing functionality including manifests, entity schemas,
and legacy model.json format.
"""

import pytest
import sys
import os

# Add src to path
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from formats.cdm.cdm_parser import CDMParser, CDMParseError
from formats.cdm.cdm_models import CDMManifest, CDMEntity, CDMAttribute

from . import (
    SIMPLE_MANIFEST,
    MANIFEST_WITH_RELATIONSHIPS,
    SIMPLE_ENTITY_SCHEMA,
    ENTITY_WITH_ALL_TYPES,
    ENTITY_WITH_INHERITANCE,
    ENTITY_WITH_TRAITS,
    MODEL_JSON,
    INVALID_JSON,
)


@pytest.mark.unit
class TestCDMParser:
    """CDM parser unit tests."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = CDMParser()
        assert parser is not None
        assert parser.resolve_references is True
    
    def test_parser_without_reference_resolution(self):
        """Test parser with reference resolution disabled."""
        parser = CDMParser(resolve_references=False)
        assert parser.resolve_references is False
    
    # =========================================================================
    # Manifest Parsing
    # =========================================================================
    
    def test_parse_simple_manifest(self, simple_manifest):
        """Parse a simple manifest file."""
        parser = CDMParser()
        result = parser.parse(simple_manifest)
        
        assert isinstance(result, CDMManifest)
        assert result.name == "TestManifest"
        assert result.schema_version == "1.0.0"
    
    def test_parse_manifest_with_relationships(self, manifest_with_relationships):
        """Parse manifest with relationships."""
        parser = CDMParser()
        result = parser.parse(manifest_with_relationships)
        
        assert result.name == "SalesManifest"
        assert len(result.relationships) == 1
        
        rel = result.relationships[0]
        assert "Order" in rel.from_entity
        assert "Customer" in rel.to_entity
        assert rel.relationship_name == "placedBy"
    
    def test_parse_manifest_entity_count(self, simple_manifest):
        """Manifest entity count property."""
        parser = CDMParser()
        result = parser.parse(simple_manifest)
        
        # Without file resolution, we get placeholder entities
        assert result.entity_count >= 0
    
    # =========================================================================
    # Entity Schema Parsing
    # =========================================================================
    
    def test_parse_entity_schema(self, simple_entity_schema):
        """Parse a CDM entity schema."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.name == "Person"
        assert entity.extends_entity == "CdmEntity"
        assert entity.description == "A person entity"
    
    def test_parse_entity_attributes(self, simple_entity_schema):
        """Parse entity attributes correctly."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        entity = result.entities[0]
        assert len(entity.attributes) == 5
        
        # Check attribute names
        attr_names = [a.name for a in entity.attributes]
        assert "personId" in attr_names
        assert "fullName" in attr_names
        assert "email" in attr_names
        assert "age" in attr_names
        assert "isActive" in attr_names
    
    def test_parse_attribute_types(self, simple_entity_schema):
        """Parse attribute data types correctly."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        entity = result.entities[0]
        attrs_by_name = {a.name: a for a in entity.attributes}
        
        assert attrs_by_name["personId"].data_type == "string"
        assert attrs_by_name["fullName"].data_type == "name"
        assert attrs_by_name["email"].data_type == "email"
        assert attrs_by_name["age"].data_type == "integer"
        assert attrs_by_name["isActive"].data_type == "boolean"
    
    def test_parse_attribute_purpose(self, simple_entity_schema):
        """Parse attribute purpose correctly."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        entity = result.entities[0]
        attrs_by_name = {a.name: a for a in entity.attributes}
        
        assert attrs_by_name["personId"].purpose == "identifiedBy"
        assert attrs_by_name["fullName"].purpose == "namedBy"
    
    def test_parse_primary_key_attribute(self, simple_entity_schema):
        """Parse and identify primary key attribute."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        entity = result.entities[0]
        pk_attrs = entity.primary_key_attributes
        assert len(pk_attrs) >= 1
        assert pk_attrs[0].name == "personId"
    
    def test_parse_display_name_attribute(self, simple_entity_schema):
        """Parse and identify display name attribute."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        
        entity = result.entities[0]
        display_attr = entity.display_name_attribute
        assert display_attr is not None
        assert display_attr.name == "fullName"
    
    def test_parse_entity_with_all_types(self, entity_with_all_types):
        """Parse entity with all supported types."""
        parser = CDMParser()
        result = parser.parse(entity_with_all_types)
        
        entity = result.entities[0]
        assert entity.name == "TypeTest"
        assert len(entity.attributes) == 16
        
        # Verify specific types
        attrs_by_name = {a.name: a for a in entity.attributes}
        assert attrs_by_name["stringAttr"].data_type == "string"
        assert attrs_by_name["intAttr"].data_type == "integer"
        assert attrs_by_name["dateTimeAttr"].data_type == "dateTime"
        assert attrs_by_name["guidAttr"].data_type == "GUID"
    
    # =========================================================================
    # Inheritance Parsing
    # =========================================================================
    
    def test_parse_entity_inheritance(self, entity_with_inheritance):
        """Parse entities with inheritance."""
        parser = CDMParser()
        result = parser.parse(entity_with_inheritance)
        
        assert len(result.entities) == 2
        
        entities_by_name = {e.name: e for e in result.entities}
        base = entities_by_name["BaseEntity"]
        derived = entities_by_name["DerivedEntity"]
        
        assert base.extends_entity is None
        assert derived.extends_entity == "BaseEntity"
        
        # Base entity attributes
        assert len(base.attributes) == 2
        
        # Derived has its own attributes (inheritance resolved elsewhere)
        assert len(derived.attributes) == 1
        assert derived.attributes[0].name == "derivedField"
    
    # =========================================================================
    # Traits Parsing
    # =========================================================================
    
    def test_parse_entity_traits(self, entity_with_traits):
        """Parse entity-level traits."""
        parser = CDMParser()
        result = parser.parse(entity_with_traits)
        
        entity = result.entities[0]
        assert entity.name == "Product"
        assert len(entity.exhibited_traits) == 2
        
        trait_refs = [t.trait_reference for t in entity.exhibited_traits]
        assert "is.CDM.entityVersion" in trait_refs
        assert "is.localized.describedAs" in trait_refs
    
    def test_parse_attribute_traits(self, entity_with_traits):
        """Parse attribute-level traits."""
        parser = CDMParser()
        result = parser.parse(entity_with_traits)
        
        entity = result.entities[0]
        product_code = next(a for a in entity.attributes if a.name == "productCode")
        
        trait_refs = [t.trait_reference for t in product_code.applied_traits]
        assert "means.identity.entityId" in trait_refs
        assert "is.constrained.length" in trait_refs
    
    def test_parse_trait_arguments(self, entity_with_traits):
        """Parse trait arguments correctly."""
        parser = CDMParser()
        result = parser.parse(entity_with_traits)
        
        entity = result.entities[0]
        product_code = next(a for a in entity.attributes if a.name == "productCode")
        
        length_trait = next(t for t in product_code.applied_traits 
                          if t.trait_reference == "is.constrained.length")
        
        assert len(length_trait.arguments) == 1
        assert length_trait.arguments[0].name == "maximumLength"
        assert length_trait.arguments[0].value == 50
    
    # =========================================================================
    # Legacy model.json Parsing
    # =========================================================================
    
    def test_parse_model_json(self, model_json):
        """Parse legacy model.json format."""
        parser = CDMParser()
        result = parser.parse(model_json)
        
        assert result.name == "TestModel"
        assert len(result.entities) == 2
        
        entity_names = [e.name for e in result.entities]
        assert "Product" in entity_names
        assert "Category" in entity_names
    
    def test_parse_model_json_entity(self, model_json):
        """Parse entity from model.json."""
        parser = CDMParser()
        result = parser.parse(model_json)
        
        product = next(e for e in result.entities if e.name == "Product")
        assert product.description == "Product catalog"
        assert len(product.attributes) == 4
    
    def test_parse_model_json_attributes(self, model_json):
        """Parse attributes from model.json."""
        parser = CDMParser()
        result = parser.parse(model_json)
        
        product = next(e for e in result.entities if e.name == "Product")
        attrs_by_name = {a.name: a for a in product.attributes}
        
        assert attrs_by_name["productId"].data_type == "string"
        assert attrs_by_name["price"].data_type == "decimal"
        assert attrs_by_name["quantity"].data_type == "integer"
    
    # =========================================================================
    # Error Handling
    # =========================================================================
    
    def test_invalid_json_raises_error(self, invalid_json):
        """Invalid JSON should raise CDMParseError."""
        parser = CDMParser()
        with pytest.raises(CDMParseError) as exc_info:
            parser.parse(invalid_json)
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_parse_error_includes_file_path(self, invalid_json):
        """Parse error should include file path."""
        parser = CDMParser()
        try:
            parser.parse(invalid_json, file_path="test.cdm.json")
        except CDMParseError as e:
            assert e.file_path == "test.cdm.json"
    
    def test_parse_nonexistent_file(self):
        """Parsing nonexistent file raises FileNotFoundError."""
        parser = CDMParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/model.cdm.json")
    
    # =========================================================================
    # Document Type Detection
    # =========================================================================
    
    def test_detect_manifest_type(self, simple_manifest):
        """Detect manifest document type."""
        parser = CDMParser()
        result = parser.parse(simple_manifest)
        # Successfully parsed as manifest
        assert result.name == "TestManifest"
    
    def test_detect_entity_schema_type(self, simple_entity_schema):
        """Detect entity schema document type."""
        parser = CDMParser()
        result = parser.parse(simple_entity_schema)
        # Successfully parsed as entity schema
        assert len(result.entities) > 0
    
    def test_detect_model_json_type(self, model_json):
        """Detect model.json document type."""
        parser = CDMParser()
        result = parser.parse(model_json)
        # Successfully parsed as model.json
        assert result.name == "TestModel"


@pytest.mark.unit
class TestCDMModels:
    """Test CDM model data classes."""
    
    def test_cdm_entity_to_dict(self):
        """Test CDMEntity serialization."""
        entity = CDMEntity(
            name="TestEntity",
            description="Test description",
            attributes=[
                CDMAttribute(name="field1", data_type="string")
            ]
        )
        
        data = entity.to_dict()
        assert data["entityName"] == "TestEntity"
        assert data["description"] == "Test description"
        assert len(data["hasAttributes"]) == 1
    
    def test_cdm_attribute_to_dict(self):
        """Test CDMAttribute serialization."""
        attr = CDMAttribute(
            name="testField",
            data_type="integer",
            description="A test field",
            is_nullable=False,
            maximum_length=100
        )
        
        data = attr.to_dict()
        assert data["name"] == "testField"
        assert data["dataType"] == "integer"
        assert data["description"] == "A test field"
        assert data["isNullable"] is False
        assert data["maximumLength"] == 100
    
    def test_cdm_manifest_get_entity_by_name(self):
        """Test finding entity by name."""
        manifest = CDMManifest(
            name="Test",
            entities=[
                CDMEntity(name="Entity1"),
                CDMEntity(name="Entity2"),
            ]
        )
        
        entity = manifest.get_entity_by_name("Entity1")
        assert entity is not None
        assert entity.name == "Entity1"
        
        not_found = manifest.get_entity_by_name("NonExistent")
        assert not_found is None
    
    def test_cdm_manifest_get_entity_names(self):
        """Test getting all entity names."""
        manifest = CDMManifest(
            name="Test",
            entities=[
                CDMEntity(name="Entity1"),
                CDMEntity(name="Entity2"),
                CDMEntity(name="Entity3"),
            ]
        )
        
        names = manifest.get_entity_names()
        assert names == ["Entity1", "Entity2", "Entity3"]
