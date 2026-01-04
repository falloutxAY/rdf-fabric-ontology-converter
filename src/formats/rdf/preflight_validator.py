"""
Pre-flight Validation for RDF/OWL to Microsoft Fabric Ontology Conversion

This module analyzes RDF TTL files before conversion to identify constructs
that cannot be fully represented in Microsoft Fabric Ontology format.

Based on mapping limitations documented in docs/MAPPING_LIMITATIONS.md
"""

import json
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal, BNode
from .rdf_parser import RDFGraphParser

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"           # Informational, no data loss expected
    WARNING = "warning"     # Some semantic nuance may be lost
    ERROR = "error"         # Significant data/semantic loss expected


class IssueCategory(Enum):
    """Categories of validation issues based on MAPPING_LIMITATIONS.md."""
    COMPLEX_CLASS_EXPRESSION = "complex_class_expression"
    PROPERTY_RESTRICTION = "property_restriction"
    PROPERTY_CHARACTERISTIC = "property_characteristic"
    PROPERTY_CHAIN = "property_chain"
    CLASS_AXIOM = "class_axiom"
    MISSING_SIGNATURE = "missing_signature"
    UNSUPPORTED_DATATYPE = "unsupported_datatype"
    EXTERNAL_IMPORT = "external_import"
    INDIVIDUAL = "individual"
    ANNOTATION = "annotation"
    REIFICATION = "reification"
    OTHER = "other"


# Supported XSD types (from rdf_converter.py)
SUPPORTED_XSD_TYPES = {
    str(XSD.string), str(XSD.boolean), str(XSD.dateTime), str(XSD.date),
    str(XSD.dateTimeStamp), str(XSD.integer), str(XSD.int), str(XSD.long),
    str(XSD.double), str(XSD.float), str(XSD.decimal), str(XSD.anyURI),
    str(XSD.time),
}


@dataclass
class ValidationIssue:
    """Represents a single validation issue found in the TTL file."""
    category: IssueCategory
    severity: IssueSeverity
    message: str
    uri: Optional[str] = None
    details: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "uri": self.uri,
            "details": self.details,
            "recommendation": self.recommendation,
        }


@dataclass
class ValidationReport:
    """Complete validation report for a TTL file."""
    file_path: str
    timestamp: str
    can_import_seamlessly: bool
    total_issues: int
    issues_by_severity: Dict[str, int]
    issues_by_category: Dict[str, int]
    issues: List[ValidationIssue]
    summary: Dict[str, Any]

    @property
    def is_valid(self) -> bool:
        """Alias for can_import_seamlessly for backward compatibility."""
        return self.can_import_seamlessly
    
    @property
    def error_count(self) -> int:
        """Return the count of error-level issues."""
        return self.issues_by_severity.get('error', 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "timestamp": self.timestamp,
            "can_import_seamlessly": self.can_import_seamlessly,
            "total_issues": self.total_issues,
            "issues_by_severity": self.issues_by_severity,
            "issues_by_category": self.issues_by_category,
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary,
        }

    def save_to_file(self, output_path: str) -> None:
        """Save the validation report to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    def get_human_readable_summary(self) -> str:
        """Generate a human-readable summary of the validation report."""
        lines = []
        lines.append("=" * 70)
        lines.append("PRE-FLIGHT VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"File: {self.file_path}")
        lines.append(f"Timestamp: {self.timestamp}")
        lines.append("")
        
        if self.can_import_seamlessly:
            lines.append("✓ RESULT: This ontology can be imported seamlessly.")
            lines.append("  No significant conversion issues detected.")
        else:
            lines.append("✗ RESULT: Issues detected that may affect conversion quality.")
            lines.append("")
            lines.append("SUMMARY:")
            lines.append(f"  Total Issues: {self.total_issues}")
            lines.append(f"  - Errors:   {self.issues_by_severity.get('error', 0)}")
            lines.append(f"  - Warnings: {self.issues_by_severity.get('warning', 0)}")
            lines.append(f"  - Info:     {self.issues_by_severity.get('info', 0)}")
        
        lines.append("")
        lines.append("ONTOLOGY STATISTICS:")
        for key, value in self.summary.items():
            lines.append(f"  {key}: {value}")
        
        if self.issues:
            lines.append("")
            lines.append("-" * 70)
            lines.append("DETAILED ISSUES:")
            lines.append("-" * 70)
            
            # Group by category
            by_category: Dict[str, List[ValidationIssue]] = {}
            for issue in self.issues:
                cat = issue.category.value
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(issue)
            
            for category, category_issues in by_category.items():
                lines.append("")
                lines.append(f"[{category.upper().replace('_', ' ')}] ({len(category_issues)} issues)")
                for issue in category_issues[:10]:  # Limit to first 10 per category
                    severity_icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}
                    icon = severity_icon.get(issue.severity.value, "•")
                    lines.append(f"  {icon} {issue.message}")
                    if issue.uri:
                        lines.append(f"    URI: {issue.uri}")
                    if issue.recommendation:
                        lines.append(f"    → {issue.recommendation}")
                if len(category_issues) > 10:
                    lines.append(f"  ... and {len(category_issues) - 10} more")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)


class PreflightValidator:
    """
    Validates RDF TTL files for compatibility with Microsoft Fabric Ontology API.
    
    Detects unsupported RDF/OWL constructs and generates a detailed report.
    """

    def __init__(self):
        self.graph: Optional[Graph] = None
        self.issues: List[ValidationIssue] = []
        self.declared_classes: Set[str] = set()
        self.declared_properties: Set[str] = set()

    def _uri_to_name(self, uri: Any) -> str:
        """Extract a clean name from a URI."""
        if uri is None:
            return "Unknown"
        uri_str = str(uri)
        if '#' in uri_str:
            return uri_str.split('#')[-1]
        elif '/' in uri_str:
            return uri_str.split('/')[-1]
        return uri_str

    def _add_issue(
        self,
        category: IssueCategory,
        severity: IssueSeverity,
        message: str,
        uri: Optional[str] = None,
        details: Optional[str] = None,
        recommendation: Optional[str] = None,
    ) -> None:
        """Add a validation issue to the list."""
        self.issues.append(ValidationIssue(
            category=category,
            severity=severity,
            message=message,
            uri=uri,
            details=details,
            recommendation=recommendation,
        ))

    def validate(
        self,
        ttl_content: str,
        file_path: str = "unknown",
        rdf_format: Optional[str] = None,
        source_path: Optional[Union[str, os.PathLike[str]]] = None,
    ) -> ValidationReport:
        """
        Validate TTL content for Fabric Ontology compatibility.
        
        Args:
            ttl_content: The TTL content as a string
            file_path: Path to the source file (for reporting)
            
        Returns:
            ValidationReport with all detected issues
        """
        self.issues = []
        self.declared_classes = set()
        self.declared_properties = set()
        
        # Parse the RDF content
        self.graph = Graph()
        try:
            format_name = RDFGraphParser.resolve_format(
                rdf_format,
                source_path or file_path,
            )
            self.graph = RDFGraphParser._create_graph(format_name)
            self.graph.parse(data=ttl_content, format=format_name)
        except Exception as e:
            self._add_issue(
                IssueCategory.OTHER,
                IssueSeverity.ERROR,
                f"Failed to parse RDF content: {e}",
                recommendation="Fix RDF syntax errors before validation.",
            )
            return self._build_report(file_path)
        
        # Collect declared classes and properties first
        self._collect_declarations()
        
        # Run all validation checks
        self._check_external_imports()
        self._check_complex_class_expressions()
        self._check_property_restrictions()
        self._check_property_characteristics()
        self._check_property_chains()
        self._check_class_axioms()
        self._check_missing_signatures()
        self._check_unsupported_datatypes()
        self._check_individuals()
        self._check_annotations()
        self._check_reification()
        
        return self._build_report(file_path)

    def _collect_declarations(self) -> None:
        """Collect all declared classes and properties."""
        # Classes
        for s in self.graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                self.declared_classes.add(str(s))
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                self.declared_classes.add(str(s))
        for s in self.graph.subjects(RDFS.subClassOf, None):
            if isinstance(s, URIRef):
                self.declared_classes.add(str(s))
        
        # Properties
        for s in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef):
                self.declared_properties.add(str(s))
        for s in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef):
                self.declared_properties.add(str(s))
        for s in self.graph.subjects(RDF.type, RDF.Property):
            if isinstance(s, URIRef):
                self.declared_properties.add(str(s))

    def _check_external_imports(self) -> None:
        """Check for owl:imports statements."""
        for s, p, o in self.graph.triples((None, OWL.imports, None)):
            self._add_issue(
                IssueCategory.EXTERNAL_IMPORT,
                IssueSeverity.WARNING,
                f"External import detected: {o}",
                uri=str(o),
                details="External vocabularies are not automatically merged.",
                recommendation="Merge required external ontologies into a single TTL file before import.",
            )

    def _check_complex_class_expressions(self) -> None:
        """Check for complex OWL class expressions."""
        # owl:intersectionOf
        for s in self.graph.subjects(OWL.intersectionOf, None):
            self._add_issue(
                IssueCategory.COMPLEX_CLASS_EXPRESSION,
                IssueSeverity.WARNING,
                f"owl:intersectionOf class expression",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Intersection class expressions are not supported; will be flattened or skipped.",
                recommendation="Flatten to explicit class declarations if needed.",
            )
        
        # owl:complementOf
        for s in self.graph.subjects(OWL.complementOf, None):
            self._add_issue(
                IssueCategory.COMPLEX_CLASS_EXPRESSION,
                IssueSeverity.WARNING,
                f"owl:complementOf class expression",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Complement class expressions are not supported.",
                recommendation="Avoid complement expressions; use explicit class hierarchies.",
            )
        
        # owl:oneOf (enumerations)
        for s in self.graph.subjects(OWL.oneOf, None):
            self._add_issue(
                IssueCategory.COMPLEX_CLASS_EXPRESSION,
                IssueSeverity.WARNING,
                f"owl:oneOf enumeration class",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Enumeration classes (oneOf) are not supported.",
                recommendation="Use regular class declarations instead of enumerations.",
            )
        
        # Note: owl:unionOf is supported, so we don't flag it as an issue

    def _check_property_restrictions(self) -> None:
        """Check for OWL property restrictions."""
        restrictions_found = []
        
        for s in self.graph.subjects(RDF.type, OWL.Restriction):
            # Determine restriction type
            restriction_types = []
            
            if (s, OWL.someValuesFrom, None) in self.graph:
                restriction_types.append("someValuesFrom")
            if (s, OWL.allValuesFrom, None) in self.graph:
                restriction_types.append("allValuesFrom")
            if (s, OWL.hasValue, None) in self.graph:
                restriction_types.append("hasValue")
            if (s, OWL.minCardinality, None) in self.graph:
                restriction_types.append("minCardinality")
            if (s, OWL.maxCardinality, None) in self.graph:
                restriction_types.append("maxCardinality")
            if (s, OWL.cardinality, None) in self.graph:
                restriction_types.append("exactCardinality")
            if (s, OWL.minQualifiedCardinality, None) in self.graph:
                restriction_types.append("minQualifiedCardinality")
            if (s, OWL.maxQualifiedCardinality, None) in self.graph:
                restriction_types.append("maxQualifiedCardinality")
            if (s, OWL.qualifiedCardinality, None) in self.graph:
                restriction_types.append("qualifiedCardinality")
            
            on_property = list(self.graph.objects(s, OWL.onProperty))
            prop_name = self._uri_to_name(on_property[0]) if on_property else "unknown"
            
            self._add_issue(
                IssueCategory.PROPERTY_RESTRICTION,
                IssueSeverity.WARNING,
                f"OWL restriction on property '{prop_name}': {', '.join(restriction_types) or 'generic'}",
                uri=str(on_property[0]) if on_property else None,
                details="Property restrictions (cardinality, value constraints) are not preserved.",
                recommendation="Remove restrictions or document expected constraints separately.",
            )

    def _check_property_characteristics(self) -> None:
        """Check for OWL property characteristics."""
        characteristics = [
            (OWL.FunctionalProperty, "FunctionalProperty"),
            (OWL.InverseFunctionalProperty, "InverseFunctionalProperty"),
            (OWL.SymmetricProperty, "SymmetricProperty"),
            (OWL.AsymmetricProperty, "AsymmetricProperty"),
            (OWL.TransitiveProperty, "TransitiveProperty"),
            (OWL.ReflexiveProperty, "ReflexiveProperty"),
            (OWL.IrreflexiveProperty, "IrreflexiveProperty"),
        ]
        
        for char_type, char_name in characteristics:
            for s in self.graph.subjects(RDF.type, char_type):
                if isinstance(s, URIRef):
                    self._add_issue(
                        IssueCategory.PROPERTY_CHARACTERISTIC,
                        IssueSeverity.INFO,
                        f"Property characteristic '{char_name}' on '{self._uri_to_name(s)}'",
                        uri=str(s),
                        details=f"Property characteristic {char_name} is semantic and will not be preserved.",
                        recommendation="These are inference-time semantics; document separately if needed.",
                    )

    def _check_property_chains(self) -> None:
        """Check for property chains and advanced property axioms."""
        # owl:propertyChainAxiom
        for s, p, o in self.graph.triples((None, OWL.propertyChainAxiom, None)):
            self._add_issue(
                IssueCategory.PROPERTY_CHAIN,
                IssueSeverity.WARNING,
                f"Property chain axiom on '{self._uri_to_name(s)}'",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Property chains require reasoning and are not supported.",
                recommendation="Materialize inferred relationships explicitly if needed.",
            )
        
        # owl:equivalentProperty
        for s, p, o in self.graph.triples((None, OWL.equivalentProperty, None)):
            self._add_issue(
                IssueCategory.PROPERTY_CHAIN,
                IssueSeverity.INFO,
                f"Equivalent property: '{self._uri_to_name(s)}' ≡ '{self._uri_to_name(o)}'",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Equivalent property semantics are not preserved.",
            )
        
        # owl:inverseOf
        for s, p, o in self.graph.triples((None, OWL.inverseOf, None)):
            self._add_issue(
                IssueCategory.PROPERTY_CHAIN,
                IssueSeverity.INFO,
                f"Inverse property: '{self._uri_to_name(s)}' inverse of '{self._uri_to_name(o)}'",
                uri=str(s) if isinstance(s, URIRef) else None,
                details="Inverse property relationships are not automatically created.",
                recommendation="Define both directions explicitly as separate relationships.",
            )

    def _check_class_axioms(self) -> None:
        """Check for class-level axioms."""
        # owl:equivalentClass
        for s, p, o in self.graph.triples((None, OWL.equivalentClass, None)):
            if isinstance(s, URIRef):
                self._add_issue(
                    IssueCategory.CLASS_AXIOM,
                    IssueSeverity.INFO,
                    f"Equivalent class: '{self._uri_to_name(s)}' ≡ '{self._uri_to_name(o)}'",
                    uri=str(s),
                    details="Class equivalence semantics are not preserved.",
                )
        
        # owl:disjointWith
        for s, p, o in self.graph.triples((None, OWL.disjointWith, None)):
            if isinstance(s, URIRef):
                self._add_issue(
                    IssueCategory.CLASS_AXIOM,
                    IssueSeverity.INFO,
                    f"Disjoint classes: '{self._uri_to_name(s)}' ⊥ '{self._uri_to_name(o)}'",
                    uri=str(s),
                    details="Class disjointness constraints are not enforced.",
                )
        
        # owl:AllDisjointClasses
        for s in self.graph.subjects(RDF.type, OWL.AllDisjointClasses):
            self._add_issue(
                IssueCategory.CLASS_AXIOM,
                IssueSeverity.INFO,
                "AllDisjointClasses declaration",
                details="Mutual disjointness of classes is not enforced.",
            )

    def _check_missing_signatures(self) -> None:
        """Check for properties missing rdfs:domain or rdfs:range."""
        all_properties = set()
        
        # Collect all declared properties
        for prop_type in [OWL.DatatypeProperty, OWL.ObjectProperty, RDF.Property]:
            for s in self.graph.subjects(RDF.type, prop_type):
                if isinstance(s, URIRef):
                    all_properties.add(s)
        
        for prop_uri in all_properties:
            domains = list(self.graph.objects(prop_uri, RDFS.domain))
            ranges = list(self.graph.objects(prop_uri, RDFS.range))
            
            missing = []
            if not domains:
                missing.append("domain")
            if not ranges:
                missing.append("range")
            
            if missing:
                self._add_issue(
                    IssueCategory.MISSING_SIGNATURE,
                    IssueSeverity.WARNING,
                    f"Property '{self._uri_to_name(prop_uri)}' missing {' and '.join(missing)}",
                    uri=str(prop_uri),
                    details="Properties without explicit domain/range will be SKIPPED during conversion.",
                    recommendation=f"Add explicit rdfs:{'/rdfs:'.join(missing)} declarations.",
                )
            else:
                # Check if domain/range resolve to declared classes
                for domain in domains:
                    if isinstance(domain, URIRef) and str(domain) not in self.declared_classes:
                        self._add_issue(
                            IssueCategory.MISSING_SIGNATURE,
                            IssueSeverity.WARNING,
                            f"Property '{self._uri_to_name(prop_uri)}' domain '{self._uri_to_name(domain)}' not declared locally",
                            uri=str(prop_uri),
                            details="Domain class is not declared in this TTL file.",
                            recommendation="Declare the class locally or merge the defining vocabulary.",
                        )
                
                for range_val in ranges:
                    if isinstance(range_val, URIRef):
                        range_str = str(range_val)
                        # Check if it's a class reference (not XSD type)
                        if not range_str.startswith(str(XSD)) and range_str not in SUPPORTED_XSD_TYPES:
                            if range_str not in self.declared_classes:
                                self._add_issue(
                                    IssueCategory.MISSING_SIGNATURE,
                                    IssueSeverity.WARNING,
                                    f"Property '{self._uri_to_name(prop_uri)}' range '{self._uri_to_name(range_val)}' not declared locally",
                                    uri=str(prop_uri),
                                    details="Range class is not declared in this TTL file.",
                                    recommendation="Declare the class locally or merge the defining vocabulary.",
                                )

    def _check_unsupported_datatypes(self) -> None:
        """Check for unsupported XSD datatypes."""
        for prop_uri in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            if not isinstance(prop_uri, URIRef):
                continue
            
            for range_val in self.graph.objects(prop_uri, RDFS.range):
                if isinstance(range_val, URIRef):
                    range_str = str(range_val)
                    if range_str.startswith(str(XSD)) and range_str not in SUPPORTED_XSD_TYPES:
                        self._add_issue(
                            IssueCategory.UNSUPPORTED_DATATYPE,
                            IssueSeverity.INFO,
                            f"Unsupported XSD datatype on '{self._uri_to_name(prop_uri)}': {self._uri_to_name(range_val)}",
                            uri=str(prop_uri),
                            details="This datatype will be mapped to String.",
                            recommendation="Use a supported datatype (string, boolean, dateTime, integer, double, decimal, anyURI).",
                        )
                elif isinstance(range_val, BNode):
                    # Check for datatype unions
                    if (range_val, OWL.unionOf, None) in self.graph:
                        self._add_issue(
                            IssueCategory.UNSUPPORTED_DATATYPE,
                            IssueSeverity.INFO,
                            f"Datatype union on '{self._uri_to_name(prop_uri)}'",
                            uri=str(prop_uri),
                            details="Datatype unions will be conservatively mapped to String.",
                        )

    def _check_individuals(self) -> None:
        """Check for named individuals and instance data."""
        individuals = set()
        
        # owl:NamedIndividual
        for s in self.graph.subjects(RDF.type, OWL.NamedIndividual):
            if isinstance(s, URIRef):
                individuals.add(s)
        
        # owl:sameAs
        same_as_count = 0
        for s, p, o in self.graph.triples((None, OWL.sameAs, None)):
            same_as_count += 1
        
        # owl:differentFrom
        different_from_count = 0
        for s, p, o in self.graph.triples((None, OWL.differentFrom, None)):
            different_from_count += 1
        
        if individuals:
            self._add_issue(
                IssueCategory.INDIVIDUAL,
                IssueSeverity.INFO,
                f"Found {len(individuals)} named individuals (instance data)",
                details="Named individuals are out of scope for ontology schema conversion.",
                recommendation="Instance data should be loaded separately after ontology schema is created.",
            )
        
        if same_as_count:
            self._add_issue(
                IssueCategory.INDIVIDUAL,
                IssueSeverity.INFO,
                f"Found {same_as_count} owl:sameAs statements",
                details="Identity assertions are not preserved.",
            )
        
        if different_from_count:
            self._add_issue(
                IssueCategory.INDIVIDUAL,
                IssueSeverity.INFO,
                f"Found {different_from_count} owl:differentFrom statements",
                details="Difference assertions are not preserved.",
            )

    def _check_annotations(self) -> None:
        """Check annotation properties usage."""
        annotation_props = set()
        for s in self.graph.subjects(RDF.type, OWL.AnnotationProperty):
            if isinstance(s, URIRef):
                annotation_props.add(s)
        
        if annotation_props:
            self._add_issue(
                IssueCategory.ANNOTATION,
                IssueSeverity.INFO,
                f"Found {len(annotation_props)} custom annotation properties",
                details="Annotation properties (beyond rdfs:label/comment) may not be preserved.",
                recommendation="Standard labels and comments are partially preserved; custom annotations are lost.",
            )

    def _check_reification(self) -> None:
        """Check for RDF reification patterns."""
        reified = set()
        for s in self.graph.subjects(RDF.type, RDF.Statement):
            reified.add(s)
        
        if reified:
            self._add_issue(
                IssueCategory.REIFICATION,
                IssueSeverity.WARNING,
                f"Found {len(reified)} reified statements",
                details="RDF reification (statements about statements) is not supported.",
                recommendation="Model reified information as explicit relationship properties or separate entities.",
            )

    def _build_report(self, file_path: str) -> ValidationReport:
        """Build the final validation report."""
        # Count issues by severity and category
        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        
        for issue in self.issues:
            sev = issue.severity.value
            cat = issue.category.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # Determine if import can be seamless
        # Seamless = no errors and no warnings (only info-level issues)
        error_count = by_severity.get('error', 0)
        warning_count = by_severity.get('warning', 0)
        can_import_seamlessly = (error_count == 0 and warning_count == 0)
        
        # Build summary statistics
        summary = {
            "total_triples": len(self.graph) if self.graph else 0,
            "declared_classes": len(self.declared_classes),
            "declared_properties": len(self.declared_properties),
        }
        
        return ValidationReport(
            file_path=file_path,
            timestamp=datetime.now().isoformat(),
            can_import_seamlessly=can_import_seamlessly,
            total_issues=len(self.issues),
            issues_by_severity=by_severity,
            issues_by_category=by_category,
            issues=self.issues,
            summary=summary,
        )


def validate_ttl_file(file_path: str, rdf_format: Optional[str] = None) -> ValidationReport:
    """
    Validate a TTL file for Fabric Ontology compatibility.
    
    Args:
        file_path: Path to the TTL file
        
    Returns:
        ValidationReport with all detected issues
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        ttl_content = f.read()
    
    validator = PreflightValidator()
    format_hint = rdf_format or RDFGraphParser.infer_format_from_path(Path(file_path))
    return validator.validate(
        ttl_content,
        file_path,
        rdf_format=format_hint,
        source_path=file_path,
    )


def validate_ttl_content(
    ttl_content: str,
    file_path: str = "unknown",
    rdf_format: Optional[str] = None,
) -> ValidationReport:
    """
    Validate TTL content for Fabric Ontology compatibility.
    
    Args:
        ttl_content: The TTL content as a string
        file_path: Path to the source file (for reporting)
        
    Returns:
        ValidationReport with all detected issues
    """
    validator = PreflightValidator()
    return validator.validate(
        ttl_content,
        file_path,
        rdf_format=rdf_format,
        source_path=file_path,
    )


def generate_import_log(
    report: ValidationReport,
    output_dir: str,
    ontology_name: str,
) -> str:
    """
    Generate a detailed import log file documenting what could not be converted.
    
    Args:
        report: The validation report
        output_dir: Directory to write the log file
        ontology_name: Name of the ontology being imported
        
    Returns:
        Path to the generated log file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in ontology_name)
    log_filename = f"import_log_{safe_name}_{timestamp}.json"
    log_path = os.path.join(output_dir, log_filename)
    
    log_data = {
        "ontology_name": ontology_name,
        "import_timestamp": datetime.now().isoformat(),
        "source_file": report.file_path,
        "validation_result": "seamless" if report.can_import_seamlessly else "with_limitations",
        "summary": {
            "total_issues": report.total_issues,
            "errors": report.issues_by_severity.get('error', 0),
            "warnings": report.issues_by_severity.get('warning', 0),
            "info": report.issues_by_severity.get('info', 0),
        },
        "ontology_stats": report.summary,
        "limitations": [],
    }
    
    # Group issues for the log
    for issue in report.issues:
        log_data["limitations"].append({
            "type": issue.category.value,
            "severity": issue.severity.value,
            "description": issue.message,
            "affected_element": issue.uri,
            "impact": issue.details,
            "recommendation": issue.recommendation,
        })
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2)
    
    return log_path
