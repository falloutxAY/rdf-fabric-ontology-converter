"""
Consolidated validation and integration tests.

This module contains:
- Pre-flight validation tests (preflight_validator)
- Exporter tests (fabric_to_ttl)
- CLI integration tests (main.py entry point)
- End-to-end tests with sample files

Run specific test categories:
    pytest -m validation                     # All validation tests
    pytest -m samples                        # Tests using sample files
    pytest tests/test_validation.py -k "Preflight"  # Preflight tests only
"""

import pytest
import json
import tempfile
import os
import sys
import concurrent.futures
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rdf import (
    PreflightValidator,
    ValidationReport,
    ValidationIssue,
    IssueSeverity,
    IssueCategory,
    validate_ttl_content,
    validate_ttl_file,
    generate_import_log,
    FabricToTTLConverter,
    compare_ontologies,
    round_trip_test,
    parse_ttl_content,
)


# =============================================================================
# PRE-FLIGHT VALIDATION TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestPreflightValidator:
    """Test the PreflightValidator class."""

    def test_validate_simple_clean_ontology(self):
        """Test validation of a simple, clean ontology with no issues."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:name a owl:DatatypeProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:string .
        
        ex:age a owl:DatatypeProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:integer .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        assert report.can_import_seamlessly is True
        assert report.issues_by_severity.get('error', 0) == 0
        assert report.issues_by_severity.get('warning', 0) == 0
        assert report.summary['declared_classes'] == 1
        assert report.summary['declared_properties'] == 2

    def test_validate_missing_domain(self):
        """Test detection of properties missing rdfs:domain."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:name a owl:DatatypeProperty ;
            rdfs:range xsd:string .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        assert report.can_import_seamlessly is False
        assert report.issues_by_severity.get('warning', 0) >= 1
        
        missing_sig_issues = [i for i in report.issues 
                             if i.category == IssueCategory.MISSING_SIGNATURE]
        assert len(missing_sig_issues) >= 1

    def test_validate_missing_range(self):
        """Test detection of properties missing rdfs:range."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:name a owl:DatatypeProperty ;
            rdfs:domain ex:Person .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        assert report.can_import_seamlessly is False
        missing_sig_issues = [i for i in report.issues 
                             if i.category == IssueCategory.MISSING_SIGNATURE]
        assert len(missing_sig_issues) >= 1

    def test_validate_external_import(self):
        """Test detection of owl:imports statements."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        <http://example.org/ontology> a owl:Ontology ;
            owl:imports <http://xmlns.com/foaf/0.1/> .

        ex:Person a owl:Class .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        import_issues = [i for i in report.issues 
                        if i.category == IssueCategory.EXTERNAL_IMPORT]
        assert len(import_issues) == 1
        assert "foaf" in import_issues[0].uri.lower()

    def test_validate_owl_restriction(self):
        """Test detection of OWL restrictions."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class ;
            rdfs:subClassOf [
                a owl:Restriction ;
                owl:onProperty ex:age ;
                owl:minCardinality 1
            ] .
        
        ex:age a owl:DatatypeProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:integer .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        restriction_issues = [i for i in report.issues 
                             if i.category == IssueCategory.PROPERTY_RESTRICTION]
        assert len(restriction_issues) >= 1

    def test_validate_functional_property(self):
        """Test detection of functional property characteristic."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:ssn a owl:DatatypeProperty, owl:FunctionalProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:string .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        char_issues = [i for i in report.issues 
                      if i.category == IssueCategory.PROPERTY_CHARACTERISTIC]
        assert len(char_issues) >= 1
        assert any("FunctionalProperty" in i.message for i in char_issues)

    def test_validate_symmetric_property(self):
        """Test detection of symmetric property characteristic."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:knows a owl:ObjectProperty, owl:SymmetricProperty ;
            rdfs:domain ex:Person ;
            rdfs:range ex:Person .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        char_issues = [i for i in report.issues 
                      if i.category == IssueCategory.PROPERTY_CHARACTERISTIC]
        assert len(char_issues) >= 1
        assert any("SymmetricProperty" in i.message for i in char_issues)

    def test_validate_transitive_property(self):
        """Test detection of transitive property characteristic."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Location a owl:Class .
        
        ex:locatedIn a owl:ObjectProperty, owl:TransitiveProperty ;
            rdfs:domain ex:Location ;
            rdfs:range ex:Location .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        char_issues = [i for i in report.issues 
                      if i.category == IssueCategory.PROPERTY_CHARACTERISTIC]
        assert len(char_issues) >= 1
        assert any("TransitiveProperty" in i.message for i in char_issues)

    def test_validate_inverse_property(self):
        """Test detection of inverse property declarations."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        ex:Company a owl:Class .
        
        ex:employs a owl:ObjectProperty ;
            rdfs:domain ex:Company ;
            rdfs:range ex:Person ;
            owl:inverseOf ex:worksFor .
        
        ex:worksFor a owl:ObjectProperty ;
            rdfs:domain ex:Person ;
            rdfs:range ex:Company .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        chain_issues = [i for i in report.issues 
                       if i.category == IssueCategory.PROPERTY_CHAIN]
        inverse_issues = [i for i in chain_issues if "inverse" in i.message.lower()]
        assert len(inverse_issues) >= 1

    def test_validate_equivalent_class(self):
        """Test detection of owl:equivalentClass."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class ;
            owl:equivalentClass ex:Human .
        
        ex:Human a owl:Class .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        axiom_issues = [i for i in report.issues 
                       if i.category == IssueCategory.CLASS_AXIOM]
        equiv_issues = [i for i in axiom_issues if "equivalent" in i.message.lower()]
        assert len(equiv_issues) >= 1

    def test_validate_disjoint_class(self):
        """Test detection of owl:disjointWith."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Cat a owl:Class ;
            owl:disjointWith ex:Dog .
        
        ex:Dog a owl:Class .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        axiom_issues = [i for i in report.issues 
                       if i.category == IssueCategory.CLASS_AXIOM]
        disjoint_issues = [i for i in axiom_issues if "disjoint" in i.message.lower()]
        assert len(disjoint_issues) >= 1

    def test_validate_intersection_of(self):
        """Test detection of owl:intersectionOf."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        ex:Employee a owl:Class .
        
        ex:WorkingPerson a owl:Class ;
            owl:intersectionOf (ex:Person ex:Employee) .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        complex_issues = [i for i in report.issues 
                        if i.category == IssueCategory.COMPLEX_CLASS_EXPRESSION]
        intersection_issues = [i for i in complex_issues 
                              if "intersectionOf" in i.message]
        assert len(intersection_issues) >= 1

    def test_validate_named_individuals(self):
        """Test detection of named individuals."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:John a owl:NamedIndividual, ex:Person .
        ex:Jane a owl:NamedIndividual, ex:Person .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        individual_issues = [i for i in report.issues 
                            if i.category == IssueCategory.INDIVIDUAL]
        assert len(individual_issues) >= 1
        assert any("2 named individuals" in i.message for i in individual_issues)

    def test_validate_unsupported_xsd_datatype(self):
        """Test detection of unsupported XSD datatypes."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:data a owl:DatatypeProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:hexBinary .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        datatype_issues = [i for i in report.issues 
                         if i.category == IssueCategory.UNSUPPORTED_DATATYPE]
        assert len(datatype_issues) >= 1

    def test_validate_reification(self):
        """Test detection of RDF reification."""
        ttl_content = """
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:statement1 a rdf:Statement ;
            rdf:subject ex:John ;
            rdf:predicate ex:knows ;
            rdf:object ex:Jane .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        reification_issues = [i for i in report.issues 
                             if i.category == IssueCategory.REIFICATION]
        assert len(reification_issues) >= 1

    def test_validate_unresolved_domain_class(self):
        """Test detection of properties with unresolved domain class."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .
        @prefix foaf: <http://xmlns.com/foaf/0.1/> .

        ex:Person a owl:Class .
        
        ex:name a owl:DatatypeProperty ;
            rdfs:domain foaf:Agent ;
            rdfs:range xsd:string .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        missing_sig_issues = [i for i in report.issues 
                             if i.category == IssueCategory.MISSING_SIGNATURE]
        unresolved_issues = [i for i in missing_sig_issues 
                           if "not declared locally" in i.message]
        assert len(unresolved_issues) >= 1


@pytest.mark.unit
class TestValidationReport:
    """Test the ValidationReport class."""

    def test_report_to_dict(self):
        """Test that ValidationReport can be converted to dict."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .
        ex:Person a owl:Class .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        report_dict = report.to_dict()
        
        assert 'file_path' in report_dict
        assert 'timestamp' in report_dict
        assert 'can_import_seamlessly' in report_dict
        assert 'total_issues' in report_dict
        assert 'issues' in report_dict
        assert isinstance(report_dict['issues'], list)

    def test_report_save_to_file(self):
        """Test saving ValidationReport to JSON file."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .
        ex:Person a owl:Class .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            report.save_to_file(temp_path)
            
            with open(temp_path, 'r') as f:
                loaded = json.load(f)
            
            assert loaded['file_path'] == "test.ttl"
            assert 'can_import_seamlessly' in loaded
        finally:
            os.unlink(temp_path)

    def test_human_readable_summary(self):
        """Test generating human-readable summary."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .
        
        ex:Person a owl:Class .
        ex:name a owl:DatatypeProperty .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        summary = report.get_human_readable_summary()
        
        assert "PRE-FLIGHT VALIDATION REPORT" in summary
        assert "test.ttl" in summary
        assert "ONTOLOGY STATISTICS" in summary


@pytest.mark.unit
class TestValidationIssue:
    """Test the ValidationIssue dataclass."""

    def test_issue_to_dict(self):
        """Test converting ValidationIssue to dict."""
        issue = ValidationIssue(
            category=IssueCategory.MISSING_SIGNATURE,
            severity=IssueSeverity.WARNING,
            message="Property 'name' missing domain",
            uri="http://example.org/name",
            details="This property will be skipped.",
            recommendation="Add rdfs:domain declaration.",
        )
        
        issue_dict = issue.to_dict()
        
        assert issue_dict['category'] == 'missing_signature'
        assert issue_dict['severity'] == 'warning'
        assert issue_dict['message'] == "Property 'name' missing domain"
        assert issue_dict['uri'] == "http://example.org/name"
        assert issue_dict['recommendation'] == "Add rdfs:domain declaration."


@pytest.mark.unit
class TestValidationEdgeCases:
    """Test edge cases and error handling for validation."""

    def test_validate_invalid_ttl(self):
        """Test validation of invalid TTL content."""
        invalid_ttl = "this is not valid turtle syntax {{{"
        
        report = validate_ttl_content(invalid_ttl, "invalid.ttl")
        
        assert report.issues_by_severity.get('error', 0) >= 1

    def test_validate_empty_content(self):
        """Test validation of empty TTL content."""
        empty_ttl = ""
        
        report = validate_ttl_content(empty_ttl, "empty.ttl")
        assert report is not None

    def test_validate_only_prefixes(self):
        """Test validation of TTL with only prefix declarations."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .
        """
        
        report = validate_ttl_content(ttl_content, "prefixes_only.ttl")
        
        assert report.summary['declared_classes'] == 0
        assert report.summary['declared_properties'] == 0


@pytest.mark.unit
class TestIssueSeverityLevels:
    """Test that issue severity levels are correctly assigned."""

    def test_info_level_for_property_characteristics(self):
        """Test that property characteristics are INFO level (not blocking)."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        ex:ssn a owl:DatatypeProperty, owl:FunctionalProperty ;
            rdfs:domain ex:Person ;
            rdfs:range xsd:string .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        char_issues = [i for i in report.issues 
                      if i.category == IssueCategory.PROPERTY_CHARACTERISTIC]
        
        assert all(i.severity == IssueSeverity.INFO for i in char_issues)

    def test_warning_level_for_missing_signature(self):
        """Test that missing signatures are WARNING level."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        ex:name a owl:DatatypeProperty .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        sig_issues = [i for i in report.issues 
                     if i.category == IssueCategory.MISSING_SIGNATURE]
        
        assert all(i.severity == IssueSeverity.WARNING for i in sig_issues)


# =============================================================================
# EXPORTER TESTS
# =============================================================================

@pytest.mark.unit
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
        
        assert "EmptyOntology" in ttl or "@prefix" in ttl


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
class TestExporterEdgeCases:
    """Test edge cases and error handling for exporter."""
    
    def test_invalid_fabric_definition(self):
        """Test handling of invalid Fabric definition."""
        converter = FabricToTTLConverter()
        
        result = converter.convert({"displayName": "Test", "definition": {}})
        assert result is not None
    
    def test_missing_parts(self):
        """Test handling of missing parts array."""
        converter = FabricToTTLConverter()
        
        fabric_def = {
            "displayName": "Test",
            "definition": {}
        }
        
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
                        "dataType": "UnknownType",
                        "parentEntity": "Entity"
                    }
                ]
            }
        }
        
        converter = FabricToTTLConverter()
        result = converter.convert(fabric_def)
        assert result is not None


# =============================================================================
# CLI INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestConfigLoading:
    """Test configuration file loading"""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file"""
        from cli import load_config
        
        config_data = {
            "tenant_id": "test-tenant",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "workspace_id": "test-workspace"
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = load_config(str(config_file))
        
        assert config["tenant_id"] == "test-tenant"
        assert config["client_id"] == "test-client"
    
    def test_load_missing_config(self):
        """Test handling of missing configuration file"""
        from cli import load_config
        
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.json")
    
    def test_load_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in config"""
        from cli import load_config
        
        config_file = tmp_path / "bad_config.json"
        config_file.write_text("{ invalid json }")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(str(config_file))
    
    def test_load_empty_path(self):
        """Test handling of empty config path"""
        from cli import load_config
        
        with pytest.raises(ValueError):
            load_config("")


@pytest.mark.integration
class TestConvertCommand:
    """Test the convert command (TTL to JSON)"""
    
    @pytest.fixture
    def sample_ttl(self, tmp_path):
        """Create a sample TTL file"""
        ttl_content = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :TestOntology a owl:Ontology ;
            rdfs:label "Test Ontology" .
        
        :Person a owl:Class ;
            rdfs:label "Person" .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:string .
        """
        
        ttl_file = tmp_path / "test.ttl"
        ttl_file.write_text(ttl_content)
        return ttl_file
    
    def test_convert_ttl_to_json(self, sample_ttl, tmp_path):
        """Test converting TTL to JSON definition"""
        from rdf import parse_ttl_file
        
        output_file = tmp_path / "output.json"
        
        definition, name = parse_ttl_file(str(sample_ttl))
        
        with open(output_file, 'w') as f:
            json.dump(definition, f, indent=2)
        
        assert output_file.exists()
        
        with open(output_file, 'r') as f:
            loaded = json.load(f)
        
        assert "parts" in loaded
        assert len(loaded["parts"]) > 0


@pytest.mark.integration
class TestRobustness:
    """Test robustness and error recovery"""
    
    def test_large_file_handling(self, tmp_path):
        """Test handling of reasonably large TTL files"""
        ttl_lines = [
            "@prefix : <http://example.org/> .",
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            ""
        ]
        
        for i in range(100):
            ttl_lines.append(f":Class{i} a owl:Class ; rdfs:label \"Class {i}\" .")
        
        for i in range(100):
            ttl_lines.append(
                f":prop{i} a owl:DatatypeProperty ; "
                f"rdfs:domain :Class{i} ; rdfs:range xsd:string ."
            )
        
        ttl_content = "\n".join(ttl_lines)
        ttl_file = tmp_path / "large.ttl"
        ttl_file.write_text(ttl_content)
        
        from rdf import parse_ttl_file
        
        definition, name = parse_ttl_file(str(ttl_file))
        
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) == 100
    
    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode characters in TTL"""
        ttl_content = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Person a owl:Class ;
            rdfs:label "人" ;
            rdfs:comment "Una persona" .
        """
        
        ttl_file = tmp_path / "unicode.ttl"
        ttl_file.write_text(ttl_content, encoding='utf-8')
        
        from rdf import parse_ttl_file
        
        definition, name = parse_ttl_file(str(ttl_file))
        assert "parts" in definition
    
    def test_special_characters_in_names(self, tmp_path):
        """Test handling of special characters that need sanitization"""
        ttl_content = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        
        :My-Special-Class a owl:Class .
        :Another.Class a owl:Class .
        :Class_With_Underscores a owl:Class .
        """
        
        ttl_file = tmp_path / "special.ttl"
        ttl_file.write_text(ttl_content)
        
        from rdf import parse_ttl_file
        import base64
        
        definition, name = parse_ttl_file(str(ttl_file))
        
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        
        for part in entity_parts:
            payload = base64.b64decode(part["payload"]).decode()
            entity = json.loads(payload)
            name = entity["name"]
            
            assert "-" not in name
            assert "." not in name
            assert name.replace("_", "").isalnum()


@pytest.mark.integration
class TestThreadSafeTokenCaching:
    """Test thread-safe token acquisition in FabricOntologyClient"""
    
    def test_concurrent_token_acquisition(self):
        """Test that concurrent token requests are handled thread-safely"""
        from core import FabricOntologyClient, FabricConfig
        
        config = FabricConfig(workspace_id="12345678-1234-1234-1234-123456789012")
        client = FabricOntologyClient(config)
        
        token_acquisition_count = []
        
        def mock_get_token(scope):
            time.sleep(0.01)
            token_acquisition_count.append(1)
            token = MagicMock()
            token.token = f"token_{len(token_acquisition_count)}"
            token.expires_on = time.time() + 3600
            return token
        
        with patch.object(client, '_get_credential') as mock_cred:
            mock_cred_instance = MagicMock()
            mock_cred_instance.get_token = mock_get_token
            mock_cred.return_value = mock_cred_instance
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(client._get_access_token) 
                    for _ in range(5)
                ]
                tokens = [f.result() for f in futures]
            
            unique_tokens = set(tokens)
            assert len(unique_tokens) == 1
            assert len(token_acquisition_count) <= 2


# =============================================================================
# SAMPLE FILE TESTS
# =============================================================================

@pytest.mark.samples
class TestSampleFilesValidation:
    """Test validation on actual sample files."""

    @pytest.fixture
    def samples_dir(self):
        """Get the samples/rdf directory path for RDF tests."""
        samples = Path(__file__).parent.parent / "samples" / "rdf"
        if not samples.exists():
            pytest.skip("samples/rdf directory not found")
        return samples

    def test_validate_sample_ontology(self, samples_dir):
        """Test that sample_supply_chain_ontology.ttl can be imported seamlessly."""
        sample_file = samples_dir / "sample_supply_chain_ontology.ttl"
        
        if sample_file.exists():
            report = validate_ttl_file(str(sample_file))
            assert report.can_import_seamlessly is True

    def test_validate_foaf_ontology(self, samples_dir):
        """Test validation of FOAF ontology (expected to have issues)."""
        foaf_file = samples_dir / "sample_foaf_ontology.ttl"
        
        if foaf_file.exists():
            report = validate_ttl_file(str(foaf_file))
            assert report.can_import_seamlessly is False
            assert report.issues_by_severity.get('warning', 0) > 0

    def test_validate_iot_ontology(self, samples_dir):
        """Test validation of IoT ontology."""
        iot_file = samples_dir / "sample_iot_ontology.ttl"
        
        if iot_file.exists():
            report = validate_ttl_file(str(iot_file))
            assert report.summary['declared_classes'] > 0

    def test_validate_fibo_ontology(self, samples_dir):
        """Test validation of FIBO ontology."""
        fibo_file = samples_dir / "sample_fibo_ontology.ttl"
        
        if fibo_file.exists():
            report = validate_ttl_file(str(fibo_file))
            assert report.summary['declared_classes'] > 0


@pytest.mark.samples
class TestSampleFilesRoundTrip:
    """Test round-trip with actual sample files."""
    
    @pytest.fixture
    def samples_dir(self):
        """Get the samples/rdf directory path for RDF tests."""
        samples = Path(__file__).parent.parent / "samples" / "rdf"
        if not samples.exists():
            pytest.skip("samples/rdf directory not found")
        return samples
    
    def test_foaf_roundtrip(self, samples_dir):
        """Test round-trip with FOAF ontology."""
        ttl_path = samples_dir / 'sample_foaf_ontology.ttl'
        if not ttl_path.exists():
            pytest.skip("FOAF TTL not found")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True
        assert result["comparison"]["classes"]["count1"] > 0
        assert result["comparison"]["classes"]["count2"] > 0
    
    def test_sample_ontology_roundtrip(self, samples_dir):
        """Test round-trip with supply chain ontology."""
        ttl_path = samples_dir / 'sample_supply_chain_ontology.ttl'
        if not ttl_path.exists():
            pytest.skip("Supply chain TTL not found")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True
    
    def test_iot_roundtrip(self, samples_dir):
        """Test round-trip with IoT ontology."""
        ttl_path = samples_dir / 'sample_iot_ontology.ttl'
        if not ttl_path.exists():
            pytest.skip("IoT TTL not found")
        
        with open(ttl_path, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
        
        result = round_trip_test(original_ttl)
        
        assert result["success"] == True


@pytest.mark.samples
@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests"""
    
    @pytest.fixture
    def samples_dir(self):
        """Get samples/rdf directory for RDF tests"""
        return Path(__file__).parent.parent / "samples" / "rdf"
    
    def test_parse_sample_ontology_complete(self, samples_dir):
        """Complete test of parsing sample_supply_chain_ontology.ttl"""
        sample_file = samples_dir / "sample_supply_chain_ontology.ttl"
        
        if not sample_file.exists():
            pytest.skip("Sample file not found")
        
        from rdf import parse_ttl_file
        import base64
        
        definition, name = parse_ttl_file(str(sample_file))
        
        assert "parts" in definition
        parts = definition["parts"]
        assert len(parts) > 0
        
        entity_parts = [p for p in parts if "EntityTypes" in p["path"]]
        assert len(entity_parts) >= 3
        
        for part in entity_parts:
            payload = base64.b64decode(part["payload"]).decode()
            entity = json.loads(payload)
            
            assert "id" in entity
            assert "name" in entity
            assert "namespace" in entity
            assert "namespaceType" in entity
            assert entity["id"].isdigit()
            assert len(entity["name"]) > 0
    
    def test_multiple_files_sequentially(self, samples_dir):
        """Test parsing multiple files in sequence"""
        from rdf import parse_ttl_file
        
        ttl_files = [
            "sample_supply_chain_ontology.ttl",
            "sample_iot_ontology.ttl",
            "sample_foaf_ontology.ttl"
        ]
        
        results = []
        
        for filename in ttl_files:
            filepath = samples_dir / filename
            if not filepath.exists():
                continue
            
            try:
                definition, name = parse_ttl_file(str(filepath))
                entity_count = len([p for p in definition["parts"] if "EntityTypes" in p["path"]])
                results.append((filename, "SUCCESS", entity_count))
            except Exception as e:
                results.append((filename, "FAILED", str(e)))
        
        assert len(results) > 0
        successes = [r for r in results if r[1] == "SUCCESS"]
        assert len(successes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
