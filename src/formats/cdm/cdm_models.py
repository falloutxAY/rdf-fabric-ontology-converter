"""
CDM Data Models.

This module defines the data structures for representing parsed CDM
(Common Data Model) content. These models provide a format-agnostic
intermediate representation between CDM JSON files and Fabric Ontology.

Models:
- CDMTrait: CDM trait with semantic meaning
- CDMTraitArgument: Argument for a trait
- CDMAttribute: Entity attribute definition
- CDMEntity: Entity definition with attributes
- CDMRelationship: Relationship between entities
- CDMManifest: Top-level manifest with entities and relationships
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class CDMPurpose(Enum):
    """
    Standard CDM attribute purposes.
    
    Purposes define the role an attribute plays within an entity.
    """
    IDENTIFIED_BY = "identifiedBy"
    NAMED_BY = "namedBy"
    HAS_A = "hasA"
    ORDERED_BY = "orderedBy"
    REPRESENTS_STATE_WITH = "representsStateWith"
    QUALIFIED_BY = "qualifiedBy"
    UNKNOWN = "unknown"


@dataclass
class CDMTraitArgument:
    """
    Represents an argument for a CDM trait.
    
    Traits can have named arguments that provide additional
    configuration or semantic information.
    
    Attributes:
        name: Optional argument name.
        value: The argument value (string, number, or complex).
    """
    name: Optional[str] = None
    value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result: Dict[str, Any] = {}
        if self.name:
            result["name"] = self.name
        if self.value is not None:
            result["value"] = self.value
        return result


@dataclass
class CDMTrait:
    """
    Represents a CDM trait (semantic annotation).
    
    Traits provide semantic meaning to entities and attributes:
    - `is.dataFormat.integer` - Data format traits
    - `means.identity.entityId` - Semantic meaning traits
    - `is.constrained.length` - Constraint traits
    
    Attributes:
        trait_reference: Full trait name or reference path.
        arguments: List of trait arguments.
    """
    trait_reference: str
    arguments: List[CDMTraitArgument] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        if not self.arguments:
            return {"traitReference": self.trait_reference}
        return {
            "traitReference": self.trait_reference,
            "arguments": [arg.to_dict() for arg in self.arguments]
        }
    
    @property
    def is_data_format(self) -> bool:
        """Check if this is a data format trait."""
        return self.trait_reference.startswith("is.dataFormat.")
    
    @property
    def is_semantic(self) -> bool:
        """Check if this is a semantic meaning trait."""
        return self.trait_reference.startswith("means.")
    
    @property
    def is_constraint(self) -> bool:
        """Check if this is a constraint trait."""
        return self.trait_reference.startswith("is.constrained.")


@dataclass
class CDMAttribute:
    """
    Represents a CDM entity attribute.
    
    Attributes define the properties of an entity, including their
    data types, constraints, and semantic meaning through traits.
    
    Attributes:
        name: Attribute name (required).
        data_type: CDM data type (string, integer, etc.).
        description: Human-readable description.
        applied_traits: List of traits applied to this attribute.
        purpose: Role of attribute (identifiedBy, namedBy, etc.).
        is_nullable: Whether the attribute can be null.
        maximum_length: Maximum string length (if applicable).
        display_name: Friendly display name.
        source_ordering: Original ordering in source file.
    """
    name: str
    data_type: str = "string"
    description: Optional[str] = None
    applied_traits: List[CDMTrait] = field(default_factory=list)
    purpose: Optional[str] = None
    is_nullable: bool = True
    maximum_length: Optional[int] = None
    display_name: Optional[str] = None
    source_ordering: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result: Dict[str, Any] = {
            "name": self.name,
            "dataType": self.data_type,
        }
        if self.description:
            result["description"] = self.description
        if self.applied_traits:
            result["appliedTraits"] = [t.to_dict() for t in self.applied_traits]
        if self.purpose:
            result["purpose"] = self.purpose
        if not self.is_nullable:
            result["isNullable"] = self.is_nullable
        if self.maximum_length is not None:
            result["maximumLength"] = self.maximum_length
        if self.display_name:
            result["displayName"] = self.display_name
        return result
    
    @property
    def is_primary_key(self) -> bool:
        """Check if attribute is marked as primary key."""
        pk_traits = [
            "means.identity.entityId",
            "is.identifiedBy",
        ]
        for trait in self.applied_traits:
            if trait.trait_reference in pk_traits:
                return True
        return self.purpose == "identifiedBy"
    
    @property
    def is_display_name(self) -> bool:
        """Check if attribute is marked as display name."""
        name_traits = [
            "means.identity.name",
            "means.identity.person.fullName",
        ]
        for trait in self.applied_traits:
            if trait.trait_reference in name_traits:
                return True
        return self.purpose == "namedBy"


@dataclass
class CDMEntity:
    """
    Represents a CDM entity definition.
    
    Entities are the primary building blocks of a CDM schema,
    representing classes of real-world objects (Customer, Product, etc.).
    
    Attributes:
        name: Entity name (required).
        description: Human-readable description.
        extends_entity: Parent entity name for inheritance.
        attributes: List of entity attributes.
        exhibited_traits: Traits applied to the entity itself.
        source_path: Path to the source file.
        display_name: Friendly display name.
        version: Entity schema version.
    """
    name: str
    description: Optional[str] = None
    extends_entity: Optional[str] = None
    attributes: List[CDMAttribute] = field(default_factory=list)
    exhibited_traits: List[CDMTrait] = field(default_factory=list)
    source_path: Optional[str] = None
    display_name: Optional[str] = None
    version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result: Dict[str, Any] = {
            "entityName": self.name,
        }
        if self.description:
            result["description"] = self.description
        if self.extends_entity:
            result["extendsEntity"] = self.extends_entity
        if self.attributes:
            result["hasAttributes"] = [a.to_dict() for a in self.attributes]
        if self.exhibited_traits:
            result["exhibitsTraits"] = [t.to_dict() for t in self.exhibited_traits]
        if self.display_name:
            result["displayName"] = self.display_name
        return result
    
    @property
    def primary_key_attributes(self) -> List[CDMAttribute]:
        """Get attributes marked as primary keys."""
        return [attr for attr in self.attributes if attr.is_primary_key]
    
    @property
    def display_name_attribute(self) -> Optional[CDMAttribute]:
        """Get the attribute marked as display name."""
        for attr in self.attributes:
            if attr.is_display_name:
                return attr
        return None


@dataclass
class CDMRelationship:
    """
    Represents a CDM relationship between entities.
    
    Relationships define connections between entities, typically
    through foreign key relationships.
    
    Attributes:
        name: Optional relationship name.
        from_entity: Source entity path (entity that has the FK).
        from_attribute: Foreign key attribute name.
        to_entity: Target entity path (entity being referenced).
        to_attribute: Target key attribute name.
        traits: Traits applied to the relationship.
    """
    from_entity: str
    from_attribute: str
    to_entity: str
    to_attribute: str
    name: Optional[str] = None
    traits: List[CDMTrait] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result: Dict[str, Any] = {
            "fromEntity": self.from_entity,
            "fromEntityAttribute": self.from_attribute,
            "toEntity": self.to_entity,
            "toEntityAttribute": self.to_attribute,
        }
        if self.name:
            result["name"] = self.name
        if self.traits:
            result["exhibitsTraits"] = [t.to_dict() for t in self.traits]
        return result
    
    @property
    def relationship_name(self) -> str:
        """
        Get relationship name, generating one if not provided.
        
        Uses verb phrase trait if available, otherwise generates
        from entity names.
        """
        if self.name:
            return self.name
        
        # Check for verb phrase trait
        for trait in self.traits:
            if trait.trait_reference == "means.relationship.verbPhrase":
                for arg in trait.arguments:
                    if arg.value:
                        return str(arg.value)
        
        # Generate from entity names
        from_name = self.from_entity.split("/")[-1].split(".")[0]
        to_name = self.to_entity.split("/")[-1].split(".")[0]
        return f"{from_name}_to_{to_name}"
    
    @property
    def from_entity_name(self) -> str:
        """Extract entity name from from_entity path."""
        # Handle paths like "Sales/Sales.cdm.json/Sales"
        parts = self.from_entity.split("/")
        return parts[-1] if parts else self.from_entity
    
    @property
    def to_entity_name(self) -> str:
        """Extract entity name from to_entity path."""
        parts = self.to_entity.split("/")
        return parts[-1] if parts else self.to_entity


@dataclass
class CDMManifest:
    """
    Represents a CDM manifest (top-level document).
    
    Manifests are the entry point for CDM folders, listing all
    entities, relationships, and sub-manifests.
    
    Attributes:
        name: Manifest name.
        entities: List of parsed entities.
        relationships: List of parsed relationships.
        sub_manifests: Paths to sub-manifests.
        schema_version: CDM JSON schema version.
        source_path: Path to the source manifest file.
        imports: List of corpus path imports.
    """
    name: str
    entities: List[CDMEntity] = field(default_factory=list)
    relationships: List[CDMRelationship] = field(default_factory=list)
    sub_manifests: List[str] = field(default_factory=list)
    schema_version: str = "1.0.0"
    source_path: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "manifestName": self.name,
            "jsonSchemaSemanticVersion": self.schema_version,
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "subManifests": self.sub_manifests,
        }
    
    @property
    def entity_count(self) -> int:
        """Get total number of entities."""
        return len(self.entities)
    
    @property
    def relationship_count(self) -> int:
        """Get total number of relationships."""
        return len(self.relationships)
    
    def get_entity_by_name(self, name: str) -> Optional[CDMEntity]:
        """
        Find entity by name.
        
        Args:
            name: Entity name to search for.
            
        Returns:
            CDMEntity if found, None otherwise.
        """
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None
    
    def get_entity_names(self) -> List[str]:
        """Get list of all entity names."""
        return [entity.name for entity in self.entities]
