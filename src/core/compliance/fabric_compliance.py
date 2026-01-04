"""
Fabric Compliance Checker.

Validates ontologies against Microsoft Fabric API limits.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .models import (
    ComplianceLevel,
    ComplianceIssue,
    ComplianceResult,
)

if TYPE_CHECKING:
    from rdflib import Graph

logger = logging.getLogger(__name__)


# Fabric API limits
FABRIC_LIMITS = {
    "max_ontology_size_mb": 10,
    "max_entities_per_ontology": 1000,
    "max_properties_per_entity": 100,
    "max_relationships_per_entity": 50,
    "max_name_length": 256,
    "max_description_length": 4000,
    "max_batch_size": 100,
}


class FabricComplianceChecker:
    """
    Checks ontology compliance with Microsoft Fabric API limits.
    
    Validates against:
    - Entity count limits
    - Property limits per entity
    - Relationship limits
    - Name/description length limits
    - Overall size constraints
    """
    
    def __init__(self, strict: bool = False):
        """
        Initialize checker.
        
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
        self.limits = FABRIC_LIMITS.copy()
    
    def check(
        self,
        entity_types: List[Any],
        relationship_types: List[Any]
    ) -> ComplianceResult:
        """
        Check Fabric ontology definition compliance.
        
        Args:
            entity_types: List of EntityType objects
            relationship_types: List of RelationshipType objects
            
        Returns:
            ComplianceResult with findings
        """
        # Import Fabric limits
        try:
            from ...constants import FabricLimits
        except ImportError:
            try:
                from constants import FabricLimits
            except ImportError:
                # Use local limits as fallback
                FabricLimits = type('FabricLimits', (), {
                    'MAX_ENTITY_NAME_LENGTH': 256,
                    'MAX_ENTITY_TYPES': 1000,
                    'MAX_RELATIONSHIP_TYPES': 500,
                    'MAX_PROPERTIES_PER_ENTITY': 100,
                    'MAX_PROPERTY_NAME_LENGTH': 256,
                })
        
        result = ComplianceResult(
            is_valid=True,
            source_type="Fabric IQ Ontology",
            statistics={
                "entity_types": len(entity_types),
                "relationship_types": len(relationship_types),
                "total_properties": 0,
            }
        )
        
        entity_ids = {e.id for e in entity_types}
        
        for entity in entity_types:
            # Check name length
            if len(entity.name) > FabricLimits.MAX_ENTITY_NAME_LENGTH:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.ERROR,
                    code="FAB001",
                    message=f"Entity name exceeds {FabricLimits.MAX_ENTITY_NAME_LENGTH} characters",
                    element_type="EntityType",
                    element_name=entity.name,
                ))
            
            # Check parent reference validity
            if entity.baseEntityTypeId and entity.baseEntityTypeId not in entity_ids:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.ERROR,
                    code="FAB002",
                    message=f"Entity references non-existent parent: {entity.baseEntityTypeId}",
                    element_type="EntityType",
                    element_name=entity.name,
                ))
            
            # Check property count
            prop_count = len(entity.properties) + len(getattr(entity, 'timeseriesProperties', []))
            result.statistics["total_properties"] += prop_count
            
            if prop_count > FabricLimits.MAX_PROPERTIES_PER_ENTITY:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.WARNING,
                    code="FAB003",
                    message=f"Entity has {prop_count} properties, exceeds recommended {FabricLimits.MAX_PROPERTIES_PER_ENTITY}",
                    element_type="EntityType",
                    element_name=entity.name,
                ))
            
            # Validate properties
            for prop in entity.properties:
                if len(prop.name) > FabricLimits.MAX_PROPERTY_NAME_LENGTH:
                    result.issues.append(ComplianceIssue(
                        level=ComplianceLevel.ERROR,
                        code="FAB010",
                        message=f"Property name exceeds {FabricLimits.MAX_PROPERTY_NAME_LENGTH} characters",
                        element_type="Property",
                        element_name=prop.name,
                    ))
        
        # Check totals
        if len(entity_types) > FabricLimits.MAX_ENTITY_TYPES:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="FAB020",
                message=f"Ontology has {len(entity_types)} entity types, exceeds recommended {FabricLimits.MAX_ENTITY_TYPES}",
            ))
        
        if len(relationship_types) > FabricLimits.MAX_RELATIONSHIP_TYPES:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="FAB021",
                message=f"Ontology has {len(relationship_types)} relationships, exceeds recommended {FabricLimits.MAX_RELATIONSHIP_TYPES}",
            ))
        
        result.is_valid = result.error_count == 0
        return result
    
    def check_dtdl(self, interfaces: List[Any]) -> ComplianceResult:
        """
        Check DTDL interfaces for Fabric compliance.
        
        Args:
            interfaces: List of DTDLInterface objects
            
        Returns:
            ComplianceResult with findings
        """
        result = ComplianceResult(
            is_valid=True,
            source_type="DTDL",
            version="Fabric API",
            statistics={
                "total_entities": len(interfaces),
                "total_properties": 0,
                "total_relationships": 0,
            }
        )
        
        # Check entity count
        if len(interfaces) > self.limits["max_entities_per_ontology"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="FAB001",
                message=f"Ontology has {len(interfaces)} entities, exceeds Fabric limit of {self.limits['max_entities_per_ontology']}",
                element_type="Ontology",
                element_name="global",
                suggestion="Split ontology into multiple smaller ontologies",
            ))
        
        # Check each interface
        for iface in interfaces:
            self._check_interface(iface, result)
        
        result.is_valid = result.error_count == 0
        if self.strict and result.warning_count > 0:
            result.is_valid = False
        
        return result
    
    def check_rdf(self, graph: "Graph") -> ComplianceResult:
        """
        Check RDF graph for Fabric compliance.
        
        Args:
            graph: RDFLib Graph
            
        Returns:
            ComplianceResult with findings
        """
        from rdflib import OWL, RDF, RDFS
        
        result = ComplianceResult(
            is_valid=True,
            source_type="RDF/OWL",
            version="Fabric API",
            statistics={
                "total_entities": 0,
                "total_properties": 0,
                "total_relationships": 0,
            }
        )
        
        # Count entities (classes)
        classes = set(graph.subjects(RDF.type, OWL.Class))
        classes.update(graph.subjects(RDF.type, RDFS.Class))
        result.statistics["total_entities"] = len(classes)
        
        if len(classes) > self.limits["max_entities_per_ontology"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="FAB001",
                message=f"Ontology has {len(classes)} classes, exceeds Fabric limit of {self.limits['max_entities_per_ontology']}",
                element_type="Ontology",
                element_name="global",
                suggestion="Split ontology into multiple smaller ontologies",
            ))
        
        # Check property counts per class
        object_props = set(graph.subjects(RDF.type, OWL.ObjectProperty))
        datatype_props = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
        all_props = object_props | datatype_props
        
        result.statistics["total_properties"] = len(datatype_props)
        result.statistics["total_relationships"] = len(object_props)
        
        # Check properties per class
        for cls in classes:
            self._check_class_properties(cls, all_props, graph, result)
        
        result.is_valid = result.error_count == 0
        if self.strict and result.warning_count > 0:
            result.is_valid = False
        
        return result
    
    def _check_interface(self, interface: Any, result: ComplianceResult) -> None:
        """Check a single DTDL interface."""
        dtmi = getattr(interface, 'dtmi', 'unknown')
        name = getattr(interface, 'name', '') or getattr(interface, 'resolved_display_name', '')
        
        # Check name length
        if len(name) > self.limits["max_name_length"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="FAB010",
                message=f"Interface name exceeds Fabric limit of {self.limits['max_name_length']} characters",
                element_type="Interface",
                element_name=dtmi,
                suggestion=f"Shorten name to {self.limits['max_name_length']} characters or less",
            ))
        
        # Check description length
        description = getattr(interface, 'description', '') or ''
        if len(description) > self.limits["max_description_length"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="FAB011",
                message=f"Description exceeds Fabric limit of {self.limits['max_description_length']} characters",
                element_type="Interface",
                element_name=dtmi,
                suggestion="Description will be truncated during upload",
            ))
        
        # Check property count
        properties = getattr(interface, 'properties', []) or []
        result.statistics["total_properties"] += len(properties)
        
        if len(properties) > self.limits["max_properties_per_entity"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="FAB012",
                message=f"Interface has {len(properties)} properties, exceeds limit of {self.limits['max_properties_per_entity']}",
                element_type="Interface",
                element_name=dtmi,
                suggestion="Split interface into multiple interfaces",
            ))
        
        # Check relationship count
        relationships = getattr(interface, 'relationships', []) or []
        result.statistics["total_relationships"] += len(relationships)
        
        if len(relationships) > self.limits["max_relationships_per_entity"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="FAB013",
                message=f"Interface has {len(relationships)} relationships, exceeds limit of {self.limits['max_relationships_per_entity']}",
                element_type="Interface",
                element_name=dtmi,
                suggestion="Consider consolidating relationships or splitting interface",
            ))
    
    def _check_class_properties(
        self,
        cls: Any,
        all_props: set,
        graph: "Graph",
        result: ComplianceResult
    ) -> None:
        """Check property counts for a class."""
        from rdflib import RDFS, OWL, RDF
        
        class_name = self._get_local_name(cls)
        
        # Find properties with this class as domain
        prop_count = 0
        rel_count = 0
        
        for prop in all_props:
            domains = list(graph.objects(prop, RDFS.domain))
            if cls in domains:
                if (prop, RDF.type, OWL.ObjectProperty) in graph:
                    rel_count += 1
                else:
                    prop_count += 1
        
        if prop_count > self.limits["max_properties_per_entity"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="FAB020",
                message=f"Class '{class_name}' has {prop_count} datatype properties, exceeds limit",
                element_type="Class",
                element_name=class_name,
                suggestion="Split class into multiple classes",
            ))
        
        if rel_count > self.limits["max_relationships_per_entity"]:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.WARNING,
                code="FAB021",
                message=f"Class '{class_name}' has {rel_count} object properties, exceeds limit",
                element_type="Class",
                element_name=class_name,
                suggestion="Consider consolidating object properties",
            ))
    
    def _get_local_name(self, uri: Any) -> str:
        """Extract local name from URI."""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        elif "/" in uri_str:
            return uri_str.split("/")[-1]
        return uri_str
