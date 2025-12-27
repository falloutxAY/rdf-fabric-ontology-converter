"""
Tests for the pre-flight validation module.

Tests the PreflightValidator class and related functions that check
RDF/OWL TTL files for Fabric Ontology API compatibility.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from preflight_validator import (
    PreflightValidator,
    ValidationReport,
    ValidationIssue,
    IssueSeverity,
    IssueCategory,
    validate_ttl_content,
    validate_ttl_file,
    generate_import_log,
)


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
        
        # Check that the issue is about missing signature
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

    def test_validate_complement_of(self):
        """Test detection of owl:complementOf."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:NonPerson a owl:Class ;
            owl:complementOf ex:Person .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        complex_issues = [i for i in report.issues 
                        if i.category == IssueCategory.COMPLEX_CLASS_EXPRESSION]
        complement_issues = [i for i in complex_issues 
                           if "complementOf" in i.message]
        assert len(complement_issues) >= 1

    def test_validate_one_of(self):
        """Test detection of owl:oneOf (enumeration)."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:DayOfWeek a owl:Class ;
            owl:oneOf (ex:Monday ex:Tuesday ex:Wednesday) .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        complex_issues = [i for i in report.issues 
                        if i.category == IssueCategory.COMPLEX_CLASS_EXPRESSION]
        oneof_issues = [i for i in complex_issues if "oneOf" in i.message]
        assert len(oneof_issues) >= 1

    def test_validate_property_chain(self):
        """Test detection of owl:propertyChainAxiom."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .

        ex:Person a owl:Class .
        
        ex:hasParent a owl:ObjectProperty ;
            rdfs:domain ex:Person ;
            rdfs:range ex:Person .
        
        ex:hasGrandparent a owl:ObjectProperty ;
            rdfs:domain ex:Person ;
            rdfs:range ex:Person ;
            owl:propertyChainAxiom (ex:hasParent ex:hasParent) .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        chain_issues = [i for i in report.issues 
                       if i.category == IssueCategory.PROPERTY_CHAIN]
        prop_chain_issues = [i for i in chain_issues 
                           if "chain" in i.message.lower()]
        assert len(prop_chain_issues) >= 1

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


class TestValidateTTLFile:
    """Test the validate_ttl_file function."""

    def test_validate_existing_file(self):
        """Test validating an existing TTL file."""
        # Use one of the sample files
        samples_dir = Path(__file__).parent.parent / "samples"
        sample_file = samples_dir / "sample_supply_chain_ontology.ttl"
        
        if sample_file.exists():
            report = validate_ttl_file(str(sample_file))
            assert report.file_path == str(sample_file)
            assert report.summary['total_triples'] > 0


class TestGenerateImportLog:
    """Test the generate_import_log function."""

    def test_generate_import_log(self):
        """Test generating an import log file."""
        ttl_content = """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex: <http://example.org/> .
        
        ex:Person a owl:Class .
        ex:name a owl:DatatypeProperty .
        """
        
        report = validate_ttl_content(ttl_content, "test.ttl")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = generate_import_log(report, temp_dir, "TestOntology")
            
            assert os.path.exists(log_path)
            assert "TestOntology" in log_path
            
            with open(log_path, 'r') as f:
                log_data = json.load(f)
            
            assert log_data['ontology_name'] == "TestOntology"
            assert 'import_timestamp' in log_data
            assert 'limitations' in log_data


class TestSampleFilesValidation:
    """Test validation on actual sample files."""

    def test_validate_sample_ontology(self):
        """Test that sample_supply_chain_ontology.ttl can be imported seamlessly."""
        samples_dir = Path(__file__).parent.parent / "samples"
        sample_file = samples_dir / "sample_supply_chain_ontology.ttl"
        
        if sample_file.exists():
            report = validate_ttl_file(str(sample_file))
            # This file should be clean
            assert report.can_import_seamlessly is True

    def test_validate_foaf_ontology(self):
        """Test validation of FOAF ontology (expected to have issues)."""
        samples_dir = Path(__file__).parent.parent / "samples"
        foaf_file = samples_dir / "sample_foaf_ontology.ttl"
        
        if foaf_file.exists():
            report = validate_ttl_file(str(foaf_file))
            # FOAF is known to have many properties without explicit signatures
            assert report.can_import_seamlessly is False
            assert report.issues_by_severity.get('warning', 0) > 0

    def test_validate_iot_ontology(self):
        """Test validation of IoT ontology."""
        samples_dir = Path(__file__).parent.parent / "samples"
        iot_file = samples_dir / "sample_iot_ontology.ttl"
        
        if iot_file.exists():
            report = validate_ttl_file(str(iot_file))
            assert report.summary['declared_classes'] > 0

    def test_validate_fibo_ontology(self):
        """Test validation of FIBO ontology."""
        samples_dir = Path(__file__).parent.parent / "samples"
        fibo_file = samples_dir / "sample_fibo_ontology.ttl"
        
        if fibo_file.exists():
            report = validate_ttl_file(str(fibo_file))
            assert report.summary['declared_classes'] > 0


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


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_validate_invalid_ttl(self):
        """Test validation of invalid TTL content."""
        invalid_ttl = "this is not valid turtle syntax {{{"
        
        report = validate_ttl_content(invalid_ttl, "invalid.ttl")
        
        assert report.issues_by_severity.get('error', 0) >= 1

    def test_validate_empty_content(self):
        """Test validation of empty TTL content."""
        # Empty but valid TTL
        empty_ttl = ""
        
        report = validate_ttl_content(empty_ttl, "empty.ttl")
        # Should handle gracefully
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
        
        # Property characteristics should be INFO, not WARNING
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
