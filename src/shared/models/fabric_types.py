"""
Fabric Ontology data types.

This module defines the core data structures that represent Microsoft Fabric
Ontology entities and relationships. These classes map directly to the
Fabric Ontology API schema.

Reference:
    https://learn.microsoft.com/en-us/rest/api/fabric/ontology
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EntityTypeProperty:
    """
    Represents a property of an entity type in Fabric Ontology.
    
    Attributes:
        id: Unique identifier for the property (numeric string).
        name: Display name of the property.
        valueType: Fabric data type (String, Boolean, DateTime, BigInt, Double, etc.).
        is_timeseries: Whether this is a timeseries property (from eventhouse).
        redefines: ID of parent property being redefined (for inheritance).
        baseTypeNamespaceType: Namespace type of the base property.
    
    Example:
        >>> prop = EntityTypeProperty(
        ...     id="1000000001",
        ...     name="temperature",
        ...     valueType="Double",
        ...     is_timeseries=True
        ... )
        >>> prop.to_dict()
        {'id': '1000000001', 'name': 'temperature', 'valueType': 'Double'}
    """
    id: str
    name: str
    valueType: str
    is_timeseries: bool = False
    redefines: Optional[str] = None
    baseTypeNamespaceType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Fabric API dictionary format."""
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "valueType": self.valueType,
        }
        if self.redefines:
            result["redefines"] = self.redefines
        if self.baseTypeNamespaceType:
            result["baseTypeNamespaceType"] = self.baseTypeNamespaceType
        return result


@dataclass
class EntityType:
    """
    Represents an entity type in Fabric Ontology.
    
    Entity types are the primary building blocks of an ontology, representing
    classes of real-world objects (e.g., Machine, Product, Sensor).
    
    Attributes:
        id: Unique identifier (numeric string, typically 13 digits).
        name: Display name of the entity type.
        namespace: Ontology namespace (default: "usertypes").
        namespaceType: Type of namespace (default: "Custom").
        visibility: Visibility setting (default: "Visible").
        baseEntityTypeId: ID of parent entity type (for inheritance).
        entityIdParts: List of property IDs that form the entity's identity.
        displayNamePropertyId: ID of property used for display name.
        properties: List of regular properties.
        timeseriesProperties: List of time-series properties (telemetry).
    
    Example:
        >>> entity = EntityType(
        ...     id="1000000000001",
        ...     name="Machine",
        ...     properties=[
        ...         EntityTypeProperty("1000000001", "serialNumber", "String")
        ...     ]
        ... )
    """
    id: str
    name: str
    namespace: str = "usertypes"
    namespaceType: str = "Custom"
    visibility: str = "Visible"
    baseEntityTypeId: Optional[str] = None
    entityIdParts: List[str] = field(default_factory=list)
    displayNamePropertyId: Optional[str] = None
    properties: List[EntityTypeProperty] = field(default_factory=list)
    timeseriesProperties: List[EntityTypeProperty] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Fabric API dictionary format."""
        result: Dict[str, Any] = {
            "id": self.id,
            "namespace": self.namespace,
            "name": self.name,
            "namespaceType": self.namespaceType,
            "visibility": self.visibility,
            "baseEntityTypeId": self.baseEntityTypeId,
        }
        if self.entityIdParts:
            result["entityIdParts"] = self.entityIdParts
        if self.displayNamePropertyId:
            result["displayNamePropertyId"] = self.displayNamePropertyId
        if self.properties:
            result["properties"] = [p.to_dict() for p in self.properties]
        if self.timeseriesProperties:
            result["timeseriesProperties"] = [p.to_dict() for p in self.timeseriesProperties]
        return result


@dataclass
class RelationshipEnd:
    """
    Represents one end (source or target) of a relationship.
    
    Attributes:
        entityTypeId: ID of the entity type at this end of the relationship.
    """
    entityTypeId: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Fabric API dictionary format."""
        return {"entityTypeId": self.entityTypeId}


@dataclass
class RelationshipType:
    """
    Represents a relationship type in Fabric Ontology.
    
    Relationship types define connections between entity types
    (e.g., "Machine produces Product", "Sensor monitors Machine").
    
    Attributes:
        id: Unique identifier (numeric string).
        name: Display name of the relationship.
        source: The source end of the relationship.
        target: The target end of the relationship.
        namespace: Ontology namespace (default: "usertypes").
        namespaceType: Type of namespace (default: "Custom").
    
    Example:
        >>> rel = RelationshipType(
        ...     id="2000000000001",
        ...     name="produces",
        ...     source=RelationshipEnd("1000000000001"),  # Machine
        ...     target=RelationshipEnd("1000000000002"),  # Product
        ... )
    """
    id: str
    name: str
    source: RelationshipEnd
    target: RelationshipEnd
    namespace: str = "usertypes"
    namespaceType: str = "Custom"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Fabric API dictionary format."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "name": self.name,
            "namespaceType": self.namespaceType,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
        }
