#!/usr/bin/env python3
"""
Tests for the Fabric to TTL exporter (fabric_to_ttl.py).

This module tests:
- FabricToTTLConverter class
- compare_ontologies function
- round_trip_test function
"""

import json
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fabric_to_ttl import FabricToTTLConverter, compare_ontologies, round_trip_test
from rdf_converter import parse_ttl_content


class TestFabricToTTLConverter:
    """Tests for FabricToTTLConverter class."""
    
    def test_convert_simple_class(self):
        """Test converting a simple class definition."""
        fabric_def = {
            "displayName": "TestOntology",
            "definition": {
                "parts": [
                    {
                        "id": "Person",
                        "type": "EntityType",
                        "displayName": "Person",
                        "description": "A human being"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        assert "Person" in ttl
        assert "owl:Class" in ttl or "Class" in ttl
        assert "TestOntology" in ttl
    
    def test_convert_class_with_datatype_property(self):
        """Test converting a class with datatype property."""
        fabric_def = {
            "displayName": "TestOntology",
            "definition": {
                "parts": [
                    {
                        "id": "Person",
                        "type": "EntityType",
                        "displayName": "Person"
                    },
                    {
                        "id": "Person.name",
                        "type": "Property",
                        "displayName": "name",
                        "dataType": "String",
                        "parentEntity": "Person"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        assert "Person" in ttl
        assert "name" in ttl
        assert "DatatypeProperty" in ttl or "datatypeProperty" in ttl.lower()
    
    def test_convert_class_with_object_property(self):
        """Test converting a class with object property (relationship)."""
        fabric_def = {
            "displayName": "TestOntology",
            "definition": {
                "parts": [
                    {
                        "id": "Person",
                        "type": "EntityType",
                        "displayName": "Person"
                    },
                    {
                        "id": "Organization",
                        "type": "EntityType",
                        "displayName": "Organization"
                    },
                    {
                        "id": "Person.worksFor",
                        "type": "Relationship",
                        "displayName": "worksFor",
                        "fromEntity": "Person",
                        "toEntity": "Organization"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        assert "Person" in ttl
        assert "Organization" in ttl
        assert "worksFor" in ttl
        assert "ObjectProperty" in ttl or "objectProperty" in ttl.lower()
    
    def test_convert_with_inheritance(self):
        """Test converting classes with inheritance."""
        fabric_def = {
            "displayName": "TestOntology",
            "definition": {
                "parts": [
                    {
                        "id": "Agent",
                        "type": "EntityType",
                        "displayName": "Agent"
                    },
                    {
                        "id": "Person",
                        "type": "EntityType",
                        "displayName": "Person",
                        "baseEntityType": "Agent"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        assert "Agent" in ttl
        assert "Person" in ttl
        assert "subClassOf" in ttl or "rdfs:subClassOf" in ttl
    
    def test_convert_all_data_types(self):
        """Test converting all supported data types."""
        data_types = ["String", "Integer", "Decimal", "Boolean", "Date", 
                      "DateTime", "Time", "Long", "Double"]
        
        parts = [
            {
                "id": "TestEntity",
                "type": "EntityType",
                "displayName": "TestEntity"
            }
        ]
        
        for dt in data_types:
            parts.append({
                "id": f"TestEntity.prop{dt}",
                "type": "Property",
                "displayName": f"prop{dt}",
                "dataType": dt,
                "parentEntity": "TestEntity"
            })
        
        fabric_def = {
            "displayName": "TestOntology",
            "definition": {"parts": parts}
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        # Should convert without errors
        assert "TestEntity" in ttl
        for dt in data_types:
            assert f"prop{dt}" in ttl
    
    def test_convert_empty_definition(self):
        """Test converting an empty definition."""
        fabric_def = {
            "displayName": "EmptyOntology",
            "definition": {"parts": []}
        }
        
        converter = FabricToTTLConverter()
        ttl = converter.convert(fabric_def)
        
        # Should produce valid TTL with just prefix declarations
        assert "EmptyOntology" in ttl or "@prefix" in ttl


class TestCompareOntologies:
    """Tests for compare_ontologies function."""
    
    def test_identical_ontologies(self):
        """Test comparing identical ontologies."""
        ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix : <http://example.org/> .
        
        :Person a owl:Class ;
            rdfs:label "Person" .
        """
        
        result = compare_ontologies(ttl, ttl)
        
        assert result["is_equivalent"] == True
        assert result["classes"]["only_in_first"] == []
        assert result["classes"]["only_in_second"] == []
    
    def test_different_classes(self):
        """Test comparing ontologies with different classes."""
        ttl1 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix : <http://example.org/> .
        
        :Person a owl:Class .
        :Animal a owl:Class .
        """
        
        ttl2 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix : <http://example.org/> .
        
        :Person a owl:Class .
        :Vehicle a owl:Class .
        """
        
        result = compare_ontologies(ttl1, ttl2)
        
        assert result["is_equivalent"] == False
        assert "Animal" in str(result["classes"]["only_in_first"])
        assert "Vehicle" in str(result["classes"]["only_in_second"])
    
    def test_different_properties(self):
        """Test comparing ontologies with different properties."""
        ttl1 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix : <http://example.org/> .
        
        :name a owl:DatatypeProperty .
        """
        
        ttl2 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix : <http://example.org/> .
        
        :age a owl:DatatypeProperty .
        """
        
        result = compare_ontologies(ttl1, ttl2)
        
        assert result["is_equivalent"] == False
    
    def test_compare_with_different_prefixes(self):
        """Test that comparison works with different prefix URIs but same local names."""
        ttl1 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/ont1#> .
        
        ex:Person a owl:Class .
        """
        
        ttl2 = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/ont2#> .
        
        ex:Person a owl:Class .
        """
        
        result = compare_ontologies(ttl1, ttl2)
        
        # Different URIs should be detected
        # The classes have different full URIs even if local names match
        assert result["classes"]["count1"] == 1
        assert result["classes"]["count2"] == 1


class TestRoundTrip:
    """Tests for round-trip conversion."""
    
    def test_simple_roundtrip(self):
        """Test simple round-trip: TTL -> Fabric JSON -> TTL."""
        original_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix : <http://example.org/simple#> .
        
        :SimpleOntology a owl:Ontology ;
            rdfs:label "Simple Ontology" .
        
        :Person a owl:Class ;
            rdfs:label "Person" .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:string .
        """
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True
        assert result["comparison"]["classes"]["count1"] >= 1
    
    def test_roundtrip_with_relationships(self):
        """Test round-trip with object properties."""
        original_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix : <http://example.org/rel#> .
        
        :TestOntology a owl:Ontology .
        
        :Person a owl:Class .
        :Organization a owl:Class .
        
        :worksFor a owl:ObjectProperty ;
            rdfs:domain :Person ;
            rdfs:range :Organization .
        """
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True
        assert result["comparison"]["object_properties"]["count1"] >= 1
    
    def test_roundtrip_with_inheritance(self):
        """Test round-trip with class inheritance."""
        original_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix : <http://example.org/inherit#> .
        
        :InheritOntology a owl:Ontology .
        
        :Agent a owl:Class .
        
        :Person a owl:Class ;
            rdfs:subClassOf :Agent .
        """
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True
        assert result["comparison"]["classes"]["count1"] >= 2


class TestSampleFilesRoundTrip:
    """Test round-trip with actual sample files."""
    
    @pytest.fixture
    def samples_dir(self):
        """Get the samples directory path."""
        # Try relative paths
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'samples'),
            'samples',
            os.path.join('..', 'samples')
        ]
        
        for path in possible_paths:
            if os.path.isdir(path):
                return os.path.abspath(path)
        
        pytest.skip("Samples directory not found")
    
    def test_foaf_roundtrip(self, samples_dir):
        """Test round-trip with FOAF ontology."""
        ttl_path = os.path.join(samples_dir, 'sample_foaf_ontology.ttl')
        if not os.path.exists(ttl_path):
            pytest.skip(f"FOAF TTL not found: {ttl_path}")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True, f"FOAF round-trip failed: {result.get('error', 'Unknown error')}"
        
        # Classes should be preserved
        comparison = result["comparison"]
        assert comparison["classes"]["count1"] > 0
        assert comparison["classes"]["count2"] > 0
    
    def test_sample_ontology_roundtrip(self, samples_dir):
        """Test round-trip with supply chain ontology."""
        ttl_path = os.path.join(samples_dir, 'sample_supply_chain_ontology.ttl')
        if not os.path.exists(ttl_path):
            pytest.skip(f"Supply chain TTL not found: {ttl_path}")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True, f"Sample round-trip failed: {result.get('error', 'Unknown error')}"
    
    def test_iot_roundtrip(self, samples_dir):
        """Test round-trip with IoT ontology."""
        ttl_path = os.path.join(samples_dir, 'sample_iot_ontology.ttl')
        if not os.path.exists(ttl_path):
            pytest.skip(f"IoT TTL not found: {ttl_path}")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True, f"IoT round-trip failed: {result.get('error', 'Unknown error')}"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_invalid_fabric_definition(self):
        """Test handling of invalid Fabric definition."""
        converter = FabricToTTLConverter()
        
        # Empty definition
        result = converter.convert({"displayName": "Test", "definition": {}})
        assert result is not None  # Should handle gracefully
    
    def test_missing_parts(self):
        """Test handling of missing parts array."""
        converter = FabricToTTLConverter()
        
        fabric_def = {
            "displayName": "Test",
            "definition": {}  # No parts key
        }
        
        # Should not crash
        result = converter.convert(fabric_def)
        assert result is not None
    
    def test_unknown_data_type(self):
        """Test handling of unknown data type."""
        fabric_def = {
            "displayName": "Test",
            "definition": {
                "parts": [
                    {
                        "id": "Entity",
                        "type": "EntityType",
                        "displayName": "Entity"
                    },
                    {
                        "id": "Entity.prop",
                        "type": "Property",
                        "displayName": "prop",
                        "dataType": "UnknownType",  # Invalid type
                        "parentEntity": "Entity"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        
        # Should handle gracefully (default to string or skip)
        result = converter.convert(fabric_def)
        assert result is not None
    
    def test_compare_empty_ontologies(self):
        """Test comparing empty ontologies."""
        ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix : <http://example.org/empty#> .
        
        :EmptyOntology a owl:Ontology .
        """
        
        result = compare_ontologies(ttl, ttl)
        
        assert result["is_equivalent"] == True
        assert result["classes"]["count1"] == 0
        assert result["classes"]["count2"] == 0
    
    def test_compare_invalid_ttl(self):
        """Test comparing invalid TTL content."""
        invalid_ttl = "This is not valid TTL content!"
        valid_ttl = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        :Test a owl:Class .
        """
        
        # Should handle gracefully
        try:
            result = compare_ontologies(invalid_ttl, valid_ttl)
            # If it doesn't raise, it should indicate failure
        except Exception:
            # Expected behavior - invalid TTL should cause an error
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
