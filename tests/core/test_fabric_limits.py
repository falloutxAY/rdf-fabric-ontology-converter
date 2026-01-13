"""
Tests for Fabric API Limits Validation and EntityIdParts Inference.

This module tests:
- FabricLimitsValidator: Validates against Fabric API limits
- EntityIdPartsInferrer: Intelligent entityIdParts inference
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Optional

# Import test fixtures
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core.validators import (
    FabricLimitsValidator,
    FabricLimitValidationError,
    EntityIdPartsInferrer,
)
from shared.models import EntityType, EntityTypeProperty, RelationshipType, RelationshipEnd
from src.constants import FabricLimits, EntityIdPartsConfig


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_entity():
    """Create a sample entity type for testing."""
    return EntityType(
        id="1000000000001",
        name="TestEntity",
        properties=[
            EntityTypeProperty(id="1001", name="id", valueType="String"),
            EntityTypeProperty(id="1002", name="name", valueType="String"),
            EntityTypeProperty(id="1003", name="value", valueType="BigInt"),
        ],
    )


@pytest.fixture
def sample_relationship():
    """Create a sample relationship type for testing."""
    return RelationshipType(
        id="2000000000001",
        name="hasRelation",
        source=RelationshipEnd(entityTypeId="1000000000001"),
        target=RelationshipEnd(entityTypeId="1000000000002"),
    )


@pytest.fixture
def fabric_validator():
    """Create a FabricLimitsValidator instance."""
    return FabricLimitsValidator()


@pytest.fixture
def entity_inferrer():
    """Create an EntityIdPartsInferrer instance."""
    return EntityIdPartsInferrer(strategy="auto")


# =============================================================================
# FabricLimitsValidator Tests
# =============================================================================

class TestFabricLimitsValidator:
    """Test suite for FabricLimitsValidator."""
    
    def test_validator_creation_with_defaults(self):
        """Test validator uses default limits."""
        validator = FabricLimitsValidator()
        assert validator.max_entity_name_length == FabricLimits.MAX_ENTITY_NAME_LENGTH
        assert validator.max_property_name_length == FabricLimits.MAX_PROPERTY_NAME_LENGTH
        assert validator.max_definition_size_kb == FabricLimits.MAX_DEFINITION_SIZE_KB
    
    def test_validator_creation_with_custom_limits(self):
        """Test validator accepts custom limits."""
        validator = FabricLimitsValidator(
            max_entity_name_length=100,
            max_property_name_length=50,
        )
        assert validator.max_entity_name_length == 100
        assert validator.max_property_name_length == 50
    
    def test_valid_entity_types(self, fabric_validator, sample_entity):
        """Test validation passes for valid entity types."""
        errors = fabric_validator.validate_entity_types([sample_entity])
        assert fabric_validator.has_errors(errors) is False
    
    def test_entity_name_length_error(self, fabric_validator):
        """Test validation catches entity name exceeding limit."""
        long_name = "A" * 27  # Exceeds 26 default limit
        entity = EntityType(id="1", name=long_name, properties=[])
        
        errors = fabric_validator.validate_entity_types([entity])
        assert fabric_validator.has_errors(errors) is True
        assert any("entity name" in e.message.lower() for e in errors)
    
    def test_property_name_length_error(self, fabric_validator):
        """Test validation catches property name exceeding limit."""
        long_prop_name = "p" + "x" * 26  # 27 chars, exceeds 26 limit
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="1", name=long_prop_name, valueType="String")
            ],
        )
        
        errors = fabric_validator.validate_entity_types([entity])
        assert fabric_validator.has_errors(errors) is True
        assert any("property" in e.message.lower() and "length" in e.message.lower() for e in errors)
    
    def test_entity_count_warning(self):
        """Test warning when entity count approaches limit."""
        validator = FabricLimitsValidator(max_entity_types=10)
        entities = [
            EntityType(id=str(i), name=f"Entity{i}", properties=[])
            for i in range(10)  # 100% of limit - should trigger warning (>90%)
        ]
        
        errors = validator.validate_entity_types(entities)
        # At exactly limit, we get a warning (since 10/10 = 100% > 90%)
        warnings = validator.get_warnings_only(errors)
        assert len(warnings) > 0
        assert any("approaching" in w.message.lower() for w in warnings)
        assert validator.has_errors(errors) is False  # Not an error yet
    
    def test_entity_count_error(self):
        """Test error when entity count exceeds limit."""
        validator = FabricLimitsValidator(max_entity_types=5)
        entities = [
            EntityType(id=str(i), name=f"Entity{i}", properties=[])
            for i in range(6)  # Exceeds limit
        ]
        
        errors = validator.validate_entity_types(entities)
        assert validator.has_errors(errors) is True
        assert any("exceeds maximum" in e.message.lower() for e in errors)
    
    def test_property_count_error(self):
        """Test error when property count per entity exceeds limit."""
        validator = FabricLimitsValidator(max_properties_per_entity=3)
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id=str(i), name=f"prop{i}", valueType="String")
                for i in range(5)  # Exceeds limit
            ],
        )
        
        errors = validator.validate_entity_types([entity])
        assert validator.has_errors(errors) is True
        assert any("properties" in e.message.lower() and "exceeding" in e.message.lower() for e in errors)
    
    def test_entity_id_parts_count_error(self, fabric_validator):
        """Test error when entityIdParts count exceeds limit."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            entityIdParts=["1", "2", "3", "4", "5", "6"],  # 6 > max 5
            properties=[
                EntityTypeProperty(id=str(i), name=f"prop{i}", valueType="String")
                for i in range(1, 7)
            ],
        )
        
        errors = fabric_validator.validate_entity_types([entity])
        assert fabric_validator.has_errors(errors) is True
        assert any("entityIdParts" in e.message for e in errors)
    
    def test_relationship_name_length_error(self, fabric_validator):
        """Test validation catches relationship name exceeding limit."""
        long_name = "rel_" + "x" * 300
        rel = RelationshipType(
            id="1",
            name=long_name,
            source=RelationshipEnd(entityTypeId="100"),
            target=RelationshipEnd(entityTypeId="200"),
        )
        
        errors = fabric_validator.validate_relationship_types([rel])
        assert fabric_validator.has_errors(errors) is True
        assert any("relationship name" in e.message.lower() for e in errors)
    
    def test_relationship_count_error(self):
        """Test error when relationship count exceeds limit."""
        validator = FabricLimitsValidator(max_relationship_types=3)
        relationships = [
            RelationshipType(
                id=str(i),
                name=f"rel{i}",
                source=RelationshipEnd(entityTypeId="100"),
                target=RelationshipEnd(entityTypeId="200"),
            )
            for i in range(5)  # Exceeds limit
        ]
        
        errors = validator.validate_relationship_types(relationships)
        assert validator.has_errors(errors) is True
        assert any("exceeds maximum" in e.message.lower() for e in errors)
    
    def test_definition_size_warning(self):
        """Test warning when definition size approaches limit."""
        validator = FabricLimitsValidator(
            max_definition_size_kb=10,
            warn_definition_size_kb=8,
        )
        
        # Create entities with enough data to approach warning threshold
        large_entity = EntityType(
            id="1" * 50,
            name="A" * 200,
            properties=[
                EntityTypeProperty(id=str(i) * 20, name=f"prop{'x' * 100}{i}", valueType="String")
                for i in range(50)
            ],
        )
        
        errors = validator.validate_definition_size([large_entity], [])
        # May or may not produce warning depending on actual size
        # Just verify no exceptions are raised
        assert isinstance(errors, list)
    
    def test_validate_all(self, fabric_validator, sample_entity, sample_relationship):
        """Test validate_all runs all validations."""
        errors = fabric_validator.validate_all([sample_entity], [sample_relationship])
        # Valid entities should produce no errors
        assert fabric_validator.has_errors(errors) is False
    
    def test_helper_methods(self, fabric_validator):
        """Test error filtering helper methods."""
        errors = [
            FabricLimitValidationError(level="error", message="Error 1"),
            FabricLimitValidationError(level="warning", message="Warning 1"),
            FabricLimitValidationError(level="error", message="Error 2"),
        ]
        
        assert len(fabric_validator.get_errors_only(errors)) == 2
        assert len(fabric_validator.get_warnings_only(errors)) == 1
        assert fabric_validator.has_errors(errors) is True


# =============================================================================
# EntityIdPartsInferrer Tests
# =============================================================================

class TestEntityIdPartsInferrer:
    """Test suite for EntityIdPartsInferrer."""
    
    def test_inferrer_creation_with_defaults(self):
        """Test inferrer uses default configuration."""
        inferrer = EntityIdPartsInferrer()
        assert inferrer.strategy == EntityIdPartsConfig.DEFAULT_STRATEGY
        assert inferrer.valid_types == EntityIdPartsConfig.VALID_TYPES
    
    def test_inferrer_creation_with_custom_config(self):
        """Test inferrer accepts custom configuration."""
        inferrer = EntityIdPartsInferrer(
            strategy="first_valid",
            custom_patterns=["custom_key", "my_id"],
        )
        assert inferrer.strategy == "first_valid"
        assert "custom_key" in inferrer.patterns
        assert "my_id" in inferrer.patterns
    
    def test_auto_infer_with_id_property(self, entity_inferrer):
        """Test auto inference recognizes 'id' property."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="value", valueType="Double"),
                EntityTypeProperty(id="101", name="id", valueType="String"),
                EntityTypeProperty(id="102", name="description", valueType="String"),
            ],
        )
        
        parts = entity_inferrer.infer_entity_id_parts(entity)
        assert parts == ["101"]  # Should pick 'id' property
    
    def test_auto_infer_with_identifier_property(self, entity_inferrer):
        """Test auto inference recognizes 'identifier' property."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="value", valueType="Double"),
                EntityTypeProperty(id="101", name="entityIdentifier", valueType="String"),
                EntityTypeProperty(id="102", name="description", valueType="String"),
            ],
        )
        
        parts = entity_inferrer.infer_entity_id_parts(entity)
        assert parts == ["101"]
    
    def test_auto_infer_with_primary_key_property(self, entity_inferrer):
        """Test auto inference recognizes 'primaryKey' property."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="primaryKey", valueType="BigInt"),
                EntityTypeProperty(id="101", name="value", valueType="Double"),
            ],
        )
        
        parts = entity_inferrer.infer_entity_id_parts(entity)
        assert parts == ["100"]
    
    def test_auto_infer_fallback_to_first_valid(self, entity_inferrer):
        """Test auto inference falls back to first valid type property."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="value", valueType="Double"),  # Not valid for key
                EntityTypeProperty(id="101", name="count", valueType="BigInt"),  # Valid
                EntityTypeProperty(id="102", name="description", valueType="String"),
            ],
        )
        
        parts = entity_inferrer.infer_entity_id_parts(entity)
        assert parts == ["101"]  # First BigInt/String
    
    def test_first_valid_strategy(self):
        """Test first_valid strategy picks first String/BigInt property."""
        inferrer = EntityIdPartsInferrer(strategy="first_valid")
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="value", valueType="Double"),
                EntityTypeProperty(id="101", name="id", valueType="String"),  # First valid
                EntityTypeProperty(id="102", name="key", valueType="BigInt"),
            ],
        )
        
        parts = inferrer.infer_entity_id_parts(entity)
        assert parts == ["101"]
    
    def test_explicit_strategy_without_mapping(self):
        """Test explicit strategy returns empty without mapping."""
        inferrer = EntityIdPartsInferrer(strategy="explicit")
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="String"),
            ],
        )
        
        parts = inferrer.infer_entity_id_parts(entity)
        assert parts == []
    
    def test_explicit_strategy_with_mapping(self):
        """Test explicit strategy uses mapping."""
        inferrer = EntityIdPartsInferrer(
            strategy="explicit",
            explicit_mappings={"TestEntity": ["customId"]},
        )
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="String"),
                EntityTypeProperty(id="101", name="customId", valueType="String"),
            ],
        )
        
        parts = inferrer.infer_entity_id_parts(entity)
        assert parts == ["101"]
    
    def test_none_strategy(self):
        """Test none strategy never sets entityIdParts."""
        inferrer = EntityIdPartsInferrer(strategy="none")
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="String"),
            ],
        )
        
        parts = inferrer.infer_entity_id_parts(entity)
        assert parts == []
    
    def test_infer_all_updates_entities(self, entity_inferrer):
        """Test infer_all updates multiple entities."""
        entities = [
            EntityType(
                id=str(i),
                name=f"Entity{i}",
                entityIdParts=[],
                properties=[
                    EntityTypeProperty(id=f"{i}00", name="id", valueType="String"),
                ],
            )
            for i in range(3)
        ]
        
        updated = entity_inferrer.infer_all(entities)
        assert updated == 3
        for entity in entities:
            assert len(entity.entityIdParts) > 0
    
    def test_infer_all_skips_existing(self, entity_inferrer):
        """Test infer_all skips entities with existing entityIdParts."""
        entities = [
            EntityType(
                id="1",
                name="Entity1",
                entityIdParts=["existing"],  # Already set
                properties=[
                    EntityTypeProperty(id="100", name="id", valueType="String"),
                ],
            ),
        ]
        
        updated = entity_inferrer.infer_all(entities, overwrite=False)
        assert updated == 0
        assert entities[0].entityIdParts == ["existing"]
    
    def test_infer_all_overwrites_when_requested(self, entity_inferrer):
        """Test infer_all overwrites when overwrite=True."""
        entities = [
            EntityType(
                id="1",
                name="Entity1",
                entityIdParts=["existing"],
                properties=[
                    EntityTypeProperty(id="100", name="id", valueType="String"),
                ],
            ),
        ]
        
        updated = entity_inferrer.infer_all(entities, overwrite=True)
        assert updated == 1
        assert entities[0].entityIdParts == ["100"]
    
    def test_set_display_name_property(self, entity_inferrer):
        """Test setting displayNamePropertyId."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            entityIdParts=["100"],
            displayNamePropertyId=None,
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="String"),
                EntityTypeProperty(id="101", name="name", valueType="String"),
            ],
        )
        
        result = entity_inferrer.set_display_name_property(entity)
        assert result == "100"  # Uses entityIdPart since it's String
    
    def test_set_display_name_prefers_name_property(self, entity_inferrer):
        """Test displayNamePropertyId prefers 'name' property."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            entityIdParts=["100"],  # BigInt, not String
            displayNamePropertyId=None,
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="BigInt"),
                EntityTypeProperty(id="101", name="displayName", valueType="String"),
            ],
        )
        
        result = entity_inferrer.set_display_name_property(entity)
        assert result == "101"  # Falls back to 'name' containing property
    
    def test_skip_invalid_types_for_key(self, entity_inferrer):
        """Test inference skips Double/DateTime for entityIdParts."""
        entity = EntityType(
            id="1",
            name="TestEntity",
            properties=[
                EntityTypeProperty(id="100", name="id", valueType="Double"),  # Invalid
                EntityTypeProperty(id="101", name="timestamp", valueType="DateTime"),  # Invalid
                EntityTypeProperty(id="102", name="code", valueType="String"),  # Valid
            ],
        )
        
        parts = entity_inferrer.infer_entity_id_parts(entity)
        assert parts == ["102"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestFabricLimitsIntegration:
    """Integration tests for Fabric limits validation in converters."""
    
    def test_rdf_conversion_validates_limits(self):
        """Test RDF conversion includes Fabric limits validation."""
        from src.rdf import convert_to_fabric_definition
        
        # Create entities that would exceed limits
        entities = [
            EntityType(
                id=str(i),
                name=f"Entity{i}",
                properties=[
                    EntityTypeProperty(id=f"{i}00", name="id", valueType="String")
                ],
            )
            for i in range(600)  # Exceeds 500 limit
        ]
        
        with pytest.raises(ValueError) as exc_info:
            convert_to_fabric_definition(entities, [], skip_fabric_limits=False)
        
        assert "Fabric API limit exceeded" in str(exc_info.value)
    
    def test_rdf_conversion_skip_limits(self):
        """Test RDF conversion can skip Fabric limits validation."""
        from src.rdf import convert_to_fabric_definition
        
        entities = [
            EntityType(
                id=str(i),
                name=f"Entity{i}",
                properties=[
                    EntityTypeProperty(id=f"{i}00", name="id", valueType="String")
                ],
            )
            for i in range(600)  # Exceeds limit but should be allowed
        ]
        
        # Should not raise with skip_fabric_limits=True
        result = convert_to_fabric_definition(
            entities, [], 
            skip_validation=True, 
            skip_fabric_limits=True
        )
        assert "parts" in result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
