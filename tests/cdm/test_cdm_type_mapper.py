"""
CDM Type Mapper Unit Tests.

Tests for CDM to Fabric type mapping functionality.
"""

import pytest
import sys
import os

# Add src to path
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from formats.cdm.cdm_type_mapper import (
    CDMTypeMapper,
    CDM_TYPE_MAPPINGS,
    CDM_SEMANTIC_TYPE_MAPPINGS,
    FabricValueType,
)


@pytest.mark.unit
class TestCDMTypeMapper:
    """CDM type mapper unit tests."""
    
    def test_mapper_initialization(self):
        """Test mapper can be initialized."""
        mapper = CDMTypeMapper()
        assert mapper is not None
        assert mapper.strict_mode is False
    
    def test_mapper_strict_mode(self):
        """Test mapper strict mode initialization."""
        mapper = CDMTypeMapper(strict_mode=True)
        assert mapper.strict_mode is True
    
    # =========================================================================
    # Primitive Type Mappings
    # =========================================================================
    
    def test_map_string_type(self):
        """String type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("string")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_exact_match is True
    
    def test_map_integer_type(self):
        """Integer type maps to BigInt."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("integer")
        assert result.fabric_type == FabricValueType.BIGINT
        assert result.is_exact_match is True
    
    def test_map_int64_type(self):
        """Int64 type maps to BigInt."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("int64")
        assert result.fabric_type == FabricValueType.BIGINT
    
    def test_map_double_type(self):
        """Double type maps to Double."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("double")
        assert result.fabric_type == FabricValueType.DOUBLE
    
    def test_map_float_type(self):
        """Float type maps to Double."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("float")
        assert result.fabric_type == FabricValueType.DOUBLE
    
    def test_map_decimal_type(self):
        """Decimal type maps to Decimal."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("decimal")
        assert result.fabric_type == FabricValueType.DECIMAL
    
    def test_map_boolean_type(self):
        """Boolean type maps to Boolean."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("boolean")
        assert result.fabric_type == FabricValueType.BOOLEAN
    
    def test_map_datetime_type(self):
        """DateTime type maps to DateTime."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("dateTime")
        assert result.fabric_type == FabricValueType.DATETIME
    
    def test_map_date_type(self):
        """Date type maps to DateTime."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("date")
        assert result.fabric_type == FabricValueType.DATETIME
    
    def test_map_guid_type(self):
        """GUID type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("GUID")
        assert result.fabric_type == FabricValueType.STRING
    
    def test_map_binary_type(self):
        """Binary type maps to String (base64)."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("binary")
        assert result.fabric_type == FabricValueType.STRING
    
    # =========================================================================
    # Semantic Type Mappings
    # =========================================================================
    
    def test_map_name_type(self):
        """Semantic 'name' type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("name")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_semantic_type is True
    
    def test_map_email_type(self):
        """Semantic 'email' type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("email")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_semantic_type is True
    
    def test_map_phone_type(self):
        """Semantic 'phone' type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("phone")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_semantic_type is True
    
    def test_map_url_type(self):
        """Semantic 'url' type maps to String."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("url")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_semantic_type is True
    
    def test_map_currency_type(self):
        """Semantic 'currency' type maps to Decimal."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("currency")
        assert result.fabric_type == FabricValueType.DECIMAL
        assert result.is_semantic_type is True
    
    def test_map_year_type(self):
        """Semantic 'year' type maps to BigInt."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("year")
        assert result.fabric_type == FabricValueType.BIGINT
        assert result.is_semantic_type is True
    
    def test_map_latitude_type(self):
        """Semantic 'latitude' type maps to Double."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("latitude")
        assert result.fabric_type == FabricValueType.DOUBLE
        assert result.is_semantic_type is True
    
    # =========================================================================
    # Case Insensitivity
    # =========================================================================
    
    def test_case_insensitive_mapping(self):
        """Type mapping should be case-insensitive."""
        mapper = CDMTypeMapper()
        
        result1 = mapper.map_type("STRING")
        assert result1.fabric_type == FabricValueType.STRING
        
        result2 = mapper.map_type("String")
        assert result2.fabric_type == FabricValueType.STRING
        
        result3 = mapper.map_type("INTEGER")
        assert result3.fabric_type == FabricValueType.BIGINT
    
    # =========================================================================
    # Unknown Types
    # =========================================================================
    
    def test_unknown_type_default(self):
        """Unknown types default to String with warning."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("unknownCustomType")
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_exact_match is False
        assert result.warning is not None
        assert "Unknown type" in result.warning
    
    def test_unknown_type_strict_mode(self):
        """Unknown types raise error in strict mode."""
        mapper = CDMTypeMapper(strict_mode=True)
        with pytest.raises(ValueError) as exc_info:
            mapper.map_type("unknownCustomType")
        assert "Unknown CDM type" in str(exc_info.value)
    
    # =========================================================================
    # Entity Reference Types
    # =========================================================================
    
    def test_entity_reference_type(self):
        """Entity reference types are flagged."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("entity")
        assert result.is_entity_reference is True
        assert result.warning is not None
        assert "relationship" in result.warning.lower()
    
    # =========================================================================
    # Trait-based Inference
    # =========================================================================
    
    def test_infer_from_integer_trait(self):
        """Type can be inferred from data format trait."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("customType", traits=["is.dataFormat.integer"])
        assert result.fabric_type == FabricValueType.BIGINT
        assert result.is_exact_match is False
    
    def test_infer_from_boolean_trait(self):
        """Boolean type inferred from trait."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("customType", traits=["is.dataFormat.boolean"])
        assert result.fabric_type == FabricValueType.BOOLEAN
    
    def test_infer_from_datetime_trait(self):
        """DateTime type inferred from trait."""
        mapper = CDMTypeMapper()
        result = mapper.map_type("customType", traits=["is.dataFormat.date"])
        assert result.fabric_type == FabricValueType.DATETIME
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def test_is_supported_type(self):
        """Test supported type checking."""
        mapper = CDMTypeMapper()
        
        assert mapper.is_supported_type("string") is True
        assert mapper.is_supported_type("integer") is True
        assert mapper.is_supported_type("email") is True
        assert mapper.is_supported_type("unknownType") is False
    
    def test_get_all_mappings(self):
        """Test getting all mappings."""
        mapper = CDMTypeMapper()
        all_mappings = mapper.get_all_mappings()
        
        assert "string" in all_mappings
        assert "integer" in all_mappings
        assert "email" in all_mappings
        assert all_mappings["string"] == "String"
    
    def test_get_supported_types(self):
        """Test getting supported type lists."""
        mapper = CDMTypeMapper()
        primitive, semantic = mapper.get_supported_types()
        
        assert "string" in primitive
        assert "integer" in primitive
        assert "email" in semantic
        assert "name" in semantic


@pytest.mark.unit
class TestTypeMappingConstants:
    """Test type mapping constant definitions."""
    
    def test_cdm_type_mappings_not_empty(self):
        """CDM type mappings should not be empty."""
        assert len(CDM_TYPE_MAPPINGS) > 0
    
    def test_cdm_semantic_mappings_not_empty(self):
        """CDM semantic type mappings should not be empty."""
        assert len(CDM_SEMANTIC_TYPE_MAPPINGS) > 0
    
    def test_all_mappings_have_valid_fabric_types(self):
        """All mappings should produce valid Fabric types."""
        valid_types = {"String", "Boolean", "DateTime", "BigInt", "Double", "Decimal"}
        
        for cdm_type, fabric_type in CDM_TYPE_MAPPINGS.items():
            assert fabric_type in valid_types, f"Invalid type for {cdm_type}: {fabric_type}"
        
        for cdm_type, fabric_type in CDM_SEMANTIC_TYPE_MAPPINGS.items():
            assert fabric_type in valid_types, f"Invalid type for {cdm_type}: {fabric_type}"
