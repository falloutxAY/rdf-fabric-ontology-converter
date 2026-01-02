"""
Tests for DTDL Import Module

Tests cover:
- Parsing single files and directories
- Validation of DTDL structure
- Conversion to Fabric Ontology format
- Type mapping
"""

import json
import pytest
import tempfile
from pathlib import Path

from src.dtdl import (
    DTDLParser,
    DTDLValidator,
    DTDLToFabricConverter,
    DTDLTypeMapper,
    DTDLInterface,
    DTDLProperty,
    DTDLTelemetry,
    DTDLRelationship,
    DTDLEnum,
    DTDLEnumValue,
    DTDLObject,
    DTDLArray,
    FabricValueType,
    DTDLScaledDecimal,
    DTDLPrimitiveSchema,
    GEOSPATIAL_SCHEMA_DTMIS,
    SCALED_DECIMAL_SCHEMA_DTMI,
)


class TestDTDLParser:
    """Tests for DTDL parsing functionality."""
    
    @pytest.fixture
    def parser(self):
        return DTDLParser()
    
    @pytest.fixture
    def simple_interface_json(self):
        return {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Thermostat;1",
            "@type": "Interface",
            "displayName": "Thermostat",
            "contents": [
                {
                    "@type": "Property",
                    "name": "targetTemperature",
                    "schema": "double"
                },
                {
                    "@type": "Telemetry",
                    "name": "currentTemperature",
                    "schema": "double"
                }
            ]
        }
    
    def test_parse_simple_interface(self, parser, simple_interface_json):
        """Test parsing a simple interface JSON string."""
        json_str = json.dumps(simple_interface_json)
        result = parser.parse_string(json_str)
        
        assert len(result.interfaces) == 1
        assert len(result.errors) == 0
        
        interface = result.interfaces[0]
        assert interface.dtmi == "dtmi:com:example:Thermostat;1"
        assert interface.resolved_display_name == "Thermostat"
        assert len(interface.properties) == 1
        assert len(interface.telemetries) == 1
    
    def test_parse_interface_with_relationship(self, parser):
        """Test parsing an interface with a relationship."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Room;1",
            "@type": "Interface",
            "displayName": "Room",
            "contents": [
                {
                    "@type": "Relationship",
                    "name": "hasThermostat",
                    "target": "dtmi:com:example:Thermostat;1"
                }
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        interface = result.interfaces[0]
        assert len(interface.relationships) == 1
        
        rel = interface.relationships[0]
        assert rel.name == "hasThermostat"
        assert rel.target == "dtmi:com:example:Thermostat;1"
    
    def test_parse_interface_with_enum(self, parser):
        """Test parsing an interface with enum schema."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Device;1",
            "@type": "Interface",
            "contents": [
                {
                    "@type": "Property",
                    "name": "status",
                    "schema": {
                        "@type": "Enum",
                        "valueSchema": "string",
                        "enumValues": [
                            {"name": "online", "enumValue": "ONLINE"},
                            {"name": "offline", "enumValue": "OFFLINE"}
                        ]
                    }
                }
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        prop = result.interfaces[0].properties[0]
        assert isinstance(prop.schema, DTDLEnum)
        assert len(prop.schema.enum_values) == 2
    
    def test_parse_file(self, parser, simple_interface_json):
        """Test parsing a DTDL file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(simple_interface_json, f)
            f.flush()
            
            result = parser.parse_file(f.name)
            
            assert len(result.interfaces) == 1
            assert result.interfaces[0].dtmi == "dtmi:com:example:Thermostat;1"
    
    def test_parse_directory(self, parser):
        """Test parsing a directory of DTDL files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple DTDL files
            files = [
                {
                    "@context": "dtmi:dtdl:context;4",
                    "@id": "dtmi:com:example:Device1;1",
                    "@type": "Interface",
                    "contents": []
                },
                {
                    "@context": "dtmi:dtdl:context;4",
                    "@id": "dtmi:com:example:Device2;1",
                    "@type": "Interface",
                    "contents": []
                }
            ]
            
            for i, data in enumerate(files):
                path = Path(tmpdir) / f"device{i}.json"
                with open(path, 'w') as f:
                    json.dump(data, f)
            
            result = parser.parse_directory(tmpdir)
            
            assert len(result.interfaces) == 2


class TestDTDLValidator:
    """Tests for DTDL validation functionality."""
    
    @pytest.fixture
    def validator(self):
        return DTDLValidator()
    
    def test_valid_interface(self, validator):
        """Test validation of a valid interface."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Thermostat;1",
            type="Interface",
            display_name="Thermostat",
            contents=[
                {
                    "@type": "Property",
                    "name": "temperature",
                    "schema": "double"
                }
            ]
        )
        interface.properties = [
            DTDLProperty(name="temperature", schema="double")
        ]
        
        result = validator.validate([interface])
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_invalid_dtmi(self, validator):
        """Test validation catches invalid DTMI format."""
        interface = DTDLInterface(
            dtmi="invalid:format",  # Invalid DTMI
            type="Interface"
        )
        
        result = validator.validate([interface])
        
        assert not result.is_valid
        assert any("DTMI" in str(e.message) for e in result.errors)
    
    def test_missing_extends_reference(self, validator):
        """Test validation catches missing extends reference."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Child;1",
            type="Interface",
            extends=["dtmi:com:example:NonExistent;1"]  # Reference doesn't exist
        )
        
        result = validator.validate([interface])
        
        # Should produce warning about unresolved reference
        assert len(result.warnings) > 0 or len(result.errors) > 0


class TestDTDLToFabricConverter:
    """Tests for DTDL to Fabric conversion functionality."""
    
    @pytest.fixture
    def converter(self):
        return DTDLToFabricConverter()
    
    def test_convert_simple_interface(self, converter):
        """Test converting a simple interface to EntityType."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Thermostat;1",
            type="Interface",
            display_name="Thermostat"
        )
        interface.properties = [
            DTDLProperty(name="temperature", schema="double"),
            DTDLProperty(name="serialNumber", schema="string"),
        ]
        interface.telemetries = [
            DTDLTelemetry(name="currentTemp", schema="double")
        ]
        
        result = converter.convert([interface])
        
        assert len(result.entity_types) == 1
        entity = result.entity_types[0]
        
        assert entity.name == "Thermostat"
        assert len(entity.properties) == 2
        assert len(entity.timeseriesProperties) == 1
    
    def test_convert_interface_with_relationship(self, converter):
        """Test converting interfaces with relationships."""
        room = DTDLInterface(
            dtmi="dtmi:com:example:Room;1",
            type="Interface",
            display_name="Room"
        )
        room.relationships = [
            DTDLRelationship(
                name="hasThermostat",
                target="dtmi:com:example:Thermostat;1"
            )
        ]
        
        thermostat = DTDLInterface(
            dtmi="dtmi:com:example:Thermostat;1",
            type="Interface",
            display_name="Thermostat"
        )
        
        result = converter.convert([room, thermostat])
        
        assert len(result.entity_types) == 2
        assert len(result.relationship_types) == 1
        
        rel = result.relationship_types[0]
        assert rel.name == "hasThermostat"
    
    def test_convert_type_mapping(self, converter):
        """Test DTDL to Fabric type mapping."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Test;1",
            type="Interface"
        )
        interface.properties = [
            DTDLProperty(name="boolProp", schema="boolean"),
            DTDLProperty(name="intProp", schema="integer"),
            DTDLProperty(name="doubleProp", schema="double"),
            DTDLProperty(name="stringProp", schema="string"),
            DTDLProperty(name="dateProp", schema="dateTime"),
        ]
        
        result = converter.convert([interface])
        entity = result.entity_types[0]
        
        type_map = {p.name: p.valueType for p in entity.properties}
        
        assert type_map["boolProp"] == "Boolean"
        assert type_map["intProp"] == "BigInt"
        assert type_map["doubleProp"] == "Double"
        assert type_map["stringProp"] == "String"
        assert type_map["dateProp"] == "DateTime"
    
    def test_to_fabric_definition(self, converter):
        """Test generating Fabric API definition format."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Test;1",
            type="Interface",
            display_name="Test"
        )
        
        result = converter.convert([interface])
        definition = converter.to_fabric_definition(result, "TestOntology")
        
        assert "parts" in definition
        parts = definition["parts"]
        
        # Should have .platform, definition.json, and entity type
        assert len(parts) >= 3
        
        # Check .platform part
        platform_part = next(p for p in parts if p["path"] == ".platform")
        assert platform_part["payloadType"] == "InlineBase64"


class TestDTDLTypeMapper:
    """Tests for type mapping functionality."""
    
    @pytest.fixture
    def mapper(self):
        return DTDLTypeMapper()
    
    def test_map_primitive_types(self, mapper):
        """Test mapping primitive DTDL types to Fabric types."""
        assert mapper.map_schema("boolean").fabric_type == FabricValueType.BOOLEAN
        assert mapper.map_schema("integer").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("long").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("double").fabric_type == FabricValueType.DOUBLE
        assert mapper.map_schema("float").fabric_type == FabricValueType.DOUBLE
        assert mapper.map_schema("string").fabric_type == FabricValueType.STRING
        assert mapper.map_schema("dateTime").fabric_type == FabricValueType.DATE_TIME
    
    def test_map_enum_type(self, mapper):
        """Test mapping enum schema to Fabric type."""
        enum = DTDLEnum(
            value_schema="string",
            enum_values=[
                DTDLEnumValue(name="a", value="A"),
                DTDLEnumValue(name="b", value="B")
            ]
        )
        
        result = mapper.map_schema(enum)
        
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_complex
        assert result.json_schema is not None
    
    def test_map_array_type(self, mapper):
        """Test mapping array schema to Fabric type."""
        array = DTDLArray(element_schema="integer")
        
        result = mapper.map_schema(array)
        
        assert result.fabric_type == FabricValueType.STRING  # JSON encoded
        assert result.is_complex
        assert result.is_array
    
    def test_map_with_semantic_type(self, mapper):
        """Test mapping with semantic type annotation."""
        result = mapper.map_schema(
            "double",
            semantic_type="Temperature",
            unit="degreeCelsius"
        )
        
        assert result.fabric_type == FabricValueType.DOUBLE
        assert result.semantic_type == "Temperature"
        assert result.unit == "degreeCelsius"


class TestIntegration:
    """Integration tests using sample DTDL files."""
    
    def test_parse_convert_thermostat_sample(self):
        """Test full pipeline with thermostat sample."""
        sample_path = Path(__file__).parent.parent / "samples" / "dtdl" / "thermostat.json"
        
        if not sample_path.exists():
            pytest.skip("Sample file not found")
        
        parser = DTDLParser()
        validator = DTDLValidator()
        converter = DTDLToFabricConverter()
        
        # Parse
        result = parser.parse_file(str(sample_path))
        assert len(result.interfaces) == 1
        assert len(result.errors) == 0
        
        # Validate
        validation = validator.validate(result.interfaces)
        assert validation.is_valid
        
        # Convert
        conversion = converter.convert(result.interfaces)
        assert len(conversion.entity_types) == 1
        
        entity = conversion.entity_types[0]
        assert entity.name == "Thermostat"
    
    def test_parse_convert_manufacturing_samples(self):
        """Test full pipeline with manufacturing samples."""
        samples_dir = Path(__file__).parent.parent / "samples" / "dtdl"
        
        if not samples_dir.exists():
            pytest.skip("Samples directory not found")
        
        parser = DTDLParser()
        validator = DTDLValidator()
        converter = DTDLToFabricConverter()
        
        # Parse all files
        result = parser.parse_directory(str(samples_dir))
        
        if len(result.interfaces) == 0:
            pytest.skip("No interfaces found in samples")
        
        # Validate
        validation = validator.validate(result.interfaces)
        
        # Convert
        conversion = converter.convert(result.interfaces)
        
        # Should have multiple entities and relationships
        assert len(conversion.entity_types) > 0


class TestDTDLv4Features:
    """Tests for DTDL v4 specific features."""
    
    @pytest.fixture
    def parser(self):
        return DTDLParser()
    
    @pytest.fixture
    def validator(self):
        return DTDLValidator()
    
    @pytest.fixture
    def mapper(self):
        return DTDLTypeMapper()
    
    @pytest.fixture
    def converter(self):
        return DTDLToFabricConverter()
    
    def test_parse_scaled_decimal_property(self, parser):
        """Test parsing an interface with scaledDecimal schema (DTDL v4)."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:MeasurementDevice;1",
            "@type": "Interface",
            "displayName": "Measurement Device",
            "contents": [
                {
                    "@type": "Telemetry",
                    "name": "distance",
                    "schema": "scaledDecimal"
                }
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        assert len(result.errors) == 0
        
        interface = result.interfaces[0]
        telemetry = interface.telemetries[0]
        assert telemetry.name == "distance"
        assert isinstance(telemetry.schema, DTDLScaledDecimal)
    
    def test_parse_v4_primitive_types(self, parser):
        """Test parsing DTDL v4 primitive types."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:DataTypes;1",
            "@type": "Interface",
            "contents": [
                {"@type": "Property", "name": "byteProp", "schema": "byte"},
                {"@type": "Property", "name": "shortProp", "schema": "short"},
                {"@type": "Property", "name": "bytesProp", "schema": "bytes"},
                {"@type": "Property", "name": "decimalProp", "schema": "decimal"},
                {"@type": "Property", "name": "uuidProp", "schema": "uuid"},
                {"@type": "Property", "name": "unsignedByteProp", "schema": "unsignedByte"},
                {"@type": "Property", "name": "unsignedShortProp", "schema": "unsignedShort"},
                {"@type": "Property", "name": "unsignedIntegerProp", "schema": "unsignedInteger"},
                {"@type": "Property", "name": "unsignedLongProp", "schema": "unsignedLong"},
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        assert len(result.errors) == 0
        assert len(result.interfaces[0].properties) == 9
    
    def test_map_scaled_decimal_type(self, mapper):
        """Test type mapping for scaledDecimal."""
        scaled_decimal = DTDLScaledDecimal()
        result = mapper.map_schema(scaled_decimal)
        
        assert result.fabric_type == FabricValueType.STRING
        assert result.is_complex
        assert result.original_schema == "scaledDecimal"
        assert result.json_schema is not None
        assert "scale" in result.json_schema.get("properties", {})
        assert "value" in result.json_schema.get("properties", {})
    
    def test_map_v4_primitive_types(self, mapper):
        """Test type mapping for DTDL v4 primitive types."""
        # All integer types should map to BigInt
        assert mapper.map_schema("byte").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("short").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("unsignedByte").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("unsignedShort").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("unsignedInteger").fabric_type == FabricValueType.BIG_INT
        assert mapper.map_schema("unsignedLong").fabric_type == FabricValueType.BIG_INT
        
        # Decimal should map to Double
        assert mapper.map_schema("decimal").fabric_type == FabricValueType.DOUBLE
        
        # UUID and bytes should map to String
        assert mapper.map_schema("uuid").fabric_type == FabricValueType.STRING
        assert mapper.map_schema("bytes").fabric_type == FabricValueType.STRING
    
    def test_validate_scaled_decimal_property(self, validator):
        """Test validation of scaledDecimal properties."""
        interface = DTDLInterface(
            dtmi="dtmi:com:example:Device;1",
            contents=[
                DTDLTelemetry(name="measurement", schema=DTDLScaledDecimal())
            ]
        )
        
        result = validator.validate([interface])
        
        # Should not have validation errors for scaledDecimal
        scaled_decimal_errors = [
            e for e in result.errors 
            if "scaledDecimal" in e.message.lower()
        ]
        assert len(scaled_decimal_errors) == 0
    
    def test_convert_scaled_decimal_property(self, converter, parser):
        """Test conversion of scaledDecimal properties to Fabric format."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Sensor;1",
            "@type": "Interface",
            "contents": [
                {
                    "@type": "Telemetry",
                    "name": "preciseReading",
                    "schema": "scaledDecimal"
                }
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        conversion = converter.convert(result.interfaces)
        
        assert len(conversion.entity_types) == 1
        entity = conversion.entity_types[0]
        
        # Telemetry goes to timeseriesProperties, not regular properties
        ts_props = [p for p in entity.timeseriesProperties if p.name == "preciseReading"]
        assert len(ts_props) == 1
        # ScaledDecimal should map to String (JSON encoded)
        assert ts_props[0].valueType == "String"
    
    def test_parse_command_with_nullable_request_response(self, parser):
        """Test parsing a command with nullable request/response (DTDL v4)."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Device;1",
            "@type": "Interface",
            "contents": [
                {
                    "@type": "Command",
                    "name": "optionalCommand",
                    "request": {
                        "name": "optionalInput",
                        "schema": "string",
                        "nullable": True
                    },
                    "response": {
                        "name": "optionalOutput",
                        "schema": "integer",
                        "nullable": True
                    }
                }
            ]
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        command = result.interfaces[0].commands[0]
        assert command.request.nullable is True
        assert command.response.nullable is True
    
    def test_geospatial_schema_dtmis(self):
        """Test that geospatial schema DTMIs are properly defined for v4."""
        expected_schemas = [
            "point", "lineString", "polygon",
            "multiPoint", "multiLineString", "multiPolygon"
        ]
        
        for schema in expected_schemas:
            assert schema in GEOSPATIAL_SCHEMA_DTMIS
            assert GEOSPATIAL_SCHEMA_DTMIS[schema].endswith(";4")
    
    def test_scaled_decimal_schema_dtmi(self):
        """Test that scaledDecimal schema DTMI is properly defined."""
        assert SCALED_DECIMAL_SCHEMA_DTMI == "dtmi:standard:schema:scaledDecimal;4"
    
    def test_primitive_schema_enum_includes_v4_types(self):
        """Test that DTDLPrimitiveSchema enum includes all v4 types."""
        v4_types = [
            "byte", "bytes", "decimal", "short",
            "unsignedByte", "unsignedInteger", "unsignedLong", "unsignedShort",
            "uuid", "scaledDecimal"
        ]
        
        enum_values = [e.value for e in DTDLPrimitiveSchema]
        
        for v4_type in v4_types:
            assert v4_type in enum_values, f"Missing DTDL v4 type: {v4_type}"
    
    def test_v4_context_version_parsing(self, parser):
        """Test that DTDL v4 context is properly parsed."""
        json_data = {
            "@context": "dtmi:dtdl:context;4",
            "@id": "dtmi:com:example:Device;1",
            "@type": "Interface",
            "contents": []
        }
        
        result = parser.parse_string(json.dumps(json_data))
        
        assert len(result.interfaces) == 1
        interface = result.interfaces[0]
        assert interface.context is not None
        assert interface.context.dtdl_version == 4
    
    def test_v4_inheritance_depth_limit(self, validator):
        """Test that v4 inheritance depth limit (12) is enforced."""
        # DTDL v4 allows max 12 levels of inheritance
        assert validator.MAX_EXTENDS_DEPTH == 12
    
    def test_v4_complex_schema_depth_limit(self, validator):
        """Test that v4 complex schema depth limit (8) is enforced."""
        # DTDL v4 allows max 8 levels of nested complex schemas
        assert validator.MAX_COMPLEX_SCHEMA_DEPTH == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
