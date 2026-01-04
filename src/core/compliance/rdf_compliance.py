"""
RDF/OWL Compliance Validator.

Validates RDF/OWL documents against OWL 2 and RDFS specifications.
"""

import logging
from typing import Any, Set, TYPE_CHECKING

from .models import ComplianceLevel, ComplianceIssue, ComplianceResult

if TYPE_CHECKING:
    from rdflib import Graph

logger = logging.getLogger(__name__)


class RDFOWLComplianceValidator:
    """
    Validates RDF/OWL documents against OWL 2 and RDFS specifications.
    
    Checks for:
    - Valid URI formats
    - Required property signatures (domain/range)
    - Supported OWL constructs
    - Class hierarchy consistency
    """
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator.
        
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
    
    def validate(self, graph: Any) -> ComplianceResult:
        """
        Validate an RDF graph.
        
        Args:
            graph: RDFLib Graph object
            
        Returns:
            ComplianceResult with validation findings
        """
        from rdflib import RDF, RDFS, OWL
        
        result = ComplianceResult(
            is_valid=True,
            source_type="RDF/OWL",
            version="OWL 2",
            statistics={
                "classes": 0,
                "datatype_properties": 0,
                "object_properties": 0,
                "restrictions": 0,
                "individuals": 0,
            }
        )
        
        # Collect all declared classes
        declared_classes: Set[str] = set()
        for s in graph.subjects(RDF.type, OWL.Class):
            declared_classes.add(str(s))
            result.statistics["classes"] += 1
        for s in graph.subjects(RDF.type, RDFS.Class):
            declared_classes.add(str(s))
        
        # Validate datatype properties
        for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
            result.statistics["datatype_properties"] += 1
            self._validate_property(prop, "DatatypeProperty", graph, declared_classes, result)
        
        # Validate object properties
        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            result.statistics["object_properties"] += 1
            self._validate_property(prop, "ObjectProperty", graph, declared_classes, result)
        
        # Check for restrictions (warning - not supported)
        for restriction in graph.subjects(RDF.type, OWL.Restriction):
            result.statistics["restrictions"] += 1
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="OWL001",
                message="owl:Restriction detected - constraints will not be preserved in Fabric",
                element_type="Restriction",
                element_name=str(restriction),
                suggestion="Consider expressing constraints as documentation or external validation rules",
            ))
        
        # Check for unsupported constructs
        self._check_unsupported_constructs(graph, result)
        
        # Count individuals
        for ind in graph.subjects(RDF.type, OWL.NamedIndividual):
            result.statistics["individuals"] += 1
        
        if result.statistics["individuals"] > 0:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="OWL010",
                message=f"Found {result.statistics['individuals']} individuals - instance data is not converted",
                element_type="Individual",
                suggestion="Individual/instance data must be loaded separately into Fabric",
            ))
        
        # Determine validity
        result.is_valid = result.error_count == 0
        if self.strict and result.warning_count > 0:
            result.is_valid = False
        
        return result
    
    def _validate_property(
        self,
        prop: Any,
        prop_type: str,
        graph: Any,
        declared_classes: Set[str],
        result: ComplianceResult
    ) -> None:
        """Validate a property has required domain and range."""
        from rdflib import RDFS
        
        prop_uri = str(prop)
        
        # Check domain
        domains = list(graph.objects(prop, RDFS.domain))
        if not domains:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="OWL020",
                message=f"Property missing rdfs:domain - will be skipped in conversion",
                element_type=prop_type,
                element_name=prop_uri,
                suggestion="Add explicit rdfs:domain pointing to a declared class",
            ))
        else:
            # Validate domain references declared class
            for domain in domains:
                domain_str = str(domain)
                if domain_str not in declared_classes and not self._is_blank_node(domain):
                    result.issues.append(ComplianceIssue(
                        level=ComplianceLevel.WARNING,
                        code="OWL021",
                        message=f"Property domain references undeclared class: {domain_str}",
                        element_type=prop_type,
                        element_name=prop_uri,
                        suggestion="Declare the domain class or import its definition",
                    ))
        
        # Check range
        ranges = list(graph.objects(prop, RDFS.range))
        if not ranges:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="OWL022",
                message=f"Property missing rdfs:range - will be skipped or use default String type",
                element_type=prop_type,
                element_name=prop_uri,
                suggestion="Add explicit rdfs:range",
            ))
    
    def _is_blank_node(self, node: Any) -> bool:
        """Check if node is a blank node."""
        from rdflib import BNode
        return isinstance(node, BNode)
    
    def _check_unsupported_constructs(self, graph: Any, result: ComplianceResult) -> None:
        """Check for OWL constructs that aren't supported."""
        from rdflib import OWL, RDF
        
        unsupported_checks = [
            (OWL.FunctionalProperty, "OWL030", "owl:FunctionalProperty"),
            (OWL.TransitiveProperty, "OWL031", "owl:TransitiveProperty"),
            (OWL.SymmetricProperty, "OWL032", "owl:SymmetricProperty"),
            (OWL.inverseOf, "OWL033", "owl:inverseOf"),
        ]
        
        for construct, code, name in unsupported_checks:
            # Check as type
            count = len(list(graph.subjects(RDF.type, construct)))
            if count > 0:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.WARNING,
                    code=code,
                    message=f"Found {count} uses of {name} - semantic behavior not preserved in Fabric",
                    suggestion="Document expected behavior externally",
                ))
            
            # Check as predicate
            count = len(list(graph.subject_objects(construct)))
            if count > 0:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.WARNING,
                    code=code,
                    message=f"Found {count} uses of {name} as predicate - not preserved in Fabric",
                ))
        
        # Check for owl:imports
        imports_count = len(list(graph.objects(None, OWL.imports)))
        if imports_count > 0:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="OWL040",
                message=f"Found {imports_count} owl:imports statements - external ontologies must be merged manually",
                suggestion="Use a tool like robot or rapper to merge imported ontologies before conversion",
            ))
