"""Integration tests for cross-format conversions.

Tests that verify RDF and DTDL converters produce compatible outputs
and can handle various edge cases.
"""

import pytest
from pathlib import Path

from src.rdf import parse_ttl_with_result
from src.dtdl import DTDLParser, DTDLToFabricConverter


class TestCrossFormatCompatibility:
    """Test compatibility between RDF and DTDL conversion outputs."""

    @pytest.fixture
    def samples_dir(self) -> Path:
        """Get the samples/rdf directory path for RDF tests."""
        return Path(__file__).parent.parent.parent / "samples" / "rdf"

    @pytest.fixture
    def dtdl_parser(self) -> DTDLParser:
        return DTDLParser()

    @pytest.fixture
    def dtdl_converter(self) -> DTDLToFabricConverter:
        return DTDLToFabricConverter(namespace="usertypes")

    def test_output_structure_compatibility(
        self, samples_dir: Path, dtdl_parser: DTDLParser, dtdl_converter: DTDLToFabricConverter
    ):
        """Verify both converters produce compatible Fabric definition structures."""
        # Convert RDF - returns API format with 'parts' key
        iot_ttl = samples_dir / "sample_iot_ontology.ttl"
        if iot_ttl.exists():
            ttl_content = iot_ttl.read_text(encoding="utf-8")
            rdf_definition, _, rdf_result = parse_ttl_with_result(ttl_content)

            # Verify RDF output structure (API format)
            assert "parts" in rdf_definition
            # Verify result has entity types
            assert len(rdf_result.entity_types) > 0 or len(rdf_result.relationship_types) > 0

        # Convert DTDL - also returns API format with 'parts'
        dtdl_dir = samples_dir / "dtdl"
        if dtdl_dir.exists():
            parse_result = dtdl_parser.parse_directory(str(dtdl_dir))
            if parse_result.interfaces:
                dtdl_result = dtdl_converter.convert(parse_result.interfaces)
                dtdl_definition = dtdl_converter.to_fabric_definition(dtdl_result, "test")

                # Verify DTDL output structure (also API format)
                assert "parts" in dtdl_definition
                # Verify result has entity types
                assert len(dtdl_result.entity_types) > 0

    def test_entity_type_field_consistency(
        self, samples_dir: Path, dtdl_parser: DTDLParser, dtdl_converter: DTDLToFabricConverter
    ):
        """Verify entity types from both formats have consistent fields."""
        required_fields = {"id", "name", "namespace"}

        # Get RDF entity - use result object
        iot_ttl = samples_dir / "sample_iot_ontology.ttl"
        if iot_ttl.exists():
            content = iot_ttl.read_text(encoding="utf-8")
            definition, _, result = parse_ttl_with_result(content)
            if result.entity_types:
                # Check entity has required attributes
                entity = result.entity_types[0]
                for field in required_fields:
                    assert hasattr(entity, field), f"RDF entity missing: {field}"

        # Get DTDL entity
        dtdl_dir = samples_dir / "dtdl"
        dtdl_entity_fields = set()
        if dtdl_dir.exists():
            parse_result = dtdl_parser.parse_directory(str(dtdl_dir))
            if parse_result.interfaces:
                result = dtdl_converter.convert(parse_result.interfaces)
                definition = dtdl_converter.to_fabric_definition(result, "test")
                if definition.get("entityTypes"):
                    dtdl_entity_fields = set(definition["entityTypes"][0].keys())

        # DTDL output should have required fields
        if dtdl_entity_fields:
            missing = required_fields - dtdl_entity_fields
            assert not missing, f"DTDL missing fields: {missing}"

    def test_property_value_types_consistency(
        self, samples_dir: Path, dtdl_parser: DTDLParser, dtdl_converter: DTDLToFabricConverter
    ):
        """Verify both converters produce valid Fabric value types."""
        valid_types = {"String", "Boolean", "BigInt", "Double", "DateTime"}

        # Check RDF properties - use result object
        iot_ttl = samples_dir / "sample_iot_ontology.ttl"
        if iot_ttl.exists():
            content = iot_ttl.read_text(encoding="utf-8")
            definition, _, result = parse_ttl_with_result(content)
            for entity in result.entity_types:
                for prop in entity.properties:
                    assert prop.valueType in valid_types, (
                        f"Invalid RDF property type: {prop.valueType}"
                    )

        # Check DTDL properties
        dtdl_dir = samples_dir / "dtdl"
        if dtdl_dir.exists():
            parse_result = dtdl_parser.parse_directory(str(dtdl_dir))
            if parse_result.interfaces:
                result = dtdl_converter.convert(parse_result.interfaces)
                definition = dtdl_converter.to_fabric_definition(result, "test")
                for entity in definition.get("entityTypes", []):
                    for prop in entity.get("properties", []):
                        assert prop["valueType"] in valid_types, (
                            f"Invalid DTDL property type: {prop['valueType']}"
                        )


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_ttl_handling(self):
        """Test handling of empty or minimal TTL content."""
        # Empty file - should raise ValueError per validation
        with pytest.raises(ValueError, match="empty"):
            parse_ttl_with_result("")

        # Only prefix declarations with no triples - should raise error
        minimal_ttl = """
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        """
        with pytest.raises(ValueError, match="No RDF triples"):
            parse_ttl_with_result(minimal_ttl)

    def test_empty_dtdl_handling(self):
        """Test handling of empty DTDL input."""
        converter = DTDLToFabricConverter()
        result = converter.convert([])
        
        assert result.entity_types == []
        assert result.relationship_types == []

    def test_unicode_handling_in_rdf(self):
        """Test that unicode characters in TTL are handled correctly."""
        unicode_ttl = """
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .
        
        ex:Büro a owl:Class ;
            rdfs:label "Büro (Office)"@de ;
            rdfs:comment "日本語テスト"@ja .
        """
        definition, name, result = parse_ttl_with_result(unicode_ttl)
        assert definition is not None
        # Should not crash

    def test_large_id_prefix(self):
        """Test handling of large ID prefixes."""
        simple_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .
        
        ex:TestClass a owl:Class .
        """
        large_prefix = 9999999999999
        definition, name, result = parse_ttl_with_result(simple_ttl, id_prefix=large_prefix)
        
        assert definition is not None
        if definition.get("entityTypes"):
            entity_id = int(definition["entityTypes"][0]["id"])
            assert entity_id >= large_prefix
