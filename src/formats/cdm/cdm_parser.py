"""
CDM Parser.

This module provides parsing functionality for CDM (Common Data Model) files,
including manifest files, entity schema files, and legacy model.json files.

Supported file types:
- *.manifest.cdm.json - CDM manifest (entry point)
- *.cdm.json - CDM entity schema definitions
- model.json - Legacy model format

Usage:
    from formats.cdm.cdm_parser import CDMParser
    
    parser = CDMParser()
    
    # Parse a manifest file
    manifest = parser.parse_file("model.manifest.cdm.json")
    
    # Parse content string
    manifest = parser.parse(json_content)
    
    # Parse a folder containing CDM files
    manifest = parser.parse_folder("/path/to/cdm/folder")
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .cdm_models import (
    CDMAttribute,
    CDMEntity,
    CDMManifest,
    CDMRelationship,
    CDMTrait,
    CDMTraitArgument,
)

logger = logging.getLogger(__name__)


class CDMParseError(Exception):
    """Exception raised when CDM parsing fails."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[str] = None):
        self.file_path = file_path
        self.details = details
        super().__init__(message)


class CDMParser:
    """
    Parse CDM manifest and entity schema documents.
    
    Supports:
    - *.manifest.cdm.json (manifest files)
    - *.cdm.json (entity schema files)
    - model.json (legacy format)
    
    The parser resolves entity references and loads related schema files
    from the same folder structure.
    
    Example:
        >>> parser = CDMParser()
        >>> manifest = parser.parse_file("sales.manifest.cdm.json")
        >>> for entity in manifest.entities:
        ...     print(entity.name)
    """
    
    def __init__(self, resolve_references: bool = True, max_depth: int = 10):
        """
        Initialize the CDM parser.
        
        Args:
            resolve_references: Whether to resolve and load referenced entities.
            max_depth: Maximum depth for resolving nested references.
        """
        self.resolve_references = resolve_references
        self.max_depth = max_depth
        self._loaded_paths: Set[str] = set()
        self._base_path: Optional[str] = None
    
    def parse(self, content: str, file_path: Optional[str] = None) -> CDMManifest:
        """
        Parse CDM content string.
        
        Automatically detects the document type (manifest, entity schema,
        or model.json) and parses accordingly.
        
        Args:
            content: JSON string containing CDM content.
            file_path: Optional path for error messages and reference resolution.
            
        Returns:
            CDMManifest containing parsed entities and relationships.
            
        Raises:
            CDMParseError: If content cannot be parsed.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise CDMParseError(
                f"Invalid JSON: {e}",
                file_path=file_path,
                details=str(e)
            )
        
        # Determine document type and parse
        doc_type = self._detect_document_type(data, file_path)
        
        if doc_type == "manifest":
            return self._parse_manifest_data(data, file_path)
        elif doc_type == "model_json":
            return self._parse_model_json_data(data, file_path)
        else:
            return self._parse_entity_schema_data(data, file_path)
    
    def parse_file(self, file_path: str) -> CDMManifest:
        """
        Parse a CDM file.
        
        Args:
            file_path: Path to the CDM file to parse.
            
        Returns:
            CDMManifest containing parsed entities and relationships.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            CDMParseError: If content cannot be parsed.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"CDM file not found: {file_path}")
        
        if path.is_dir():
            return self.parse_folder(file_path)
        
        # Set base path for reference resolution
        self._base_path = str(path.parent)
        self._loaded_paths = {str(path.resolve())}
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse(content, file_path)
    
    def parse_folder(self, folder_path: str) -> CDMManifest:
        """
        Parse a CDM folder, looking for manifest or model.json.
        
        Args:
            folder_path: Path to folder containing CDM files.
            
        Returns:
            CDMManifest containing all entities found.
            
        Raises:
            CDMParseError: If no valid CDM files found.
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            raise FileNotFoundError(f"CDM folder not found: {folder_path}")
        
        if not folder.is_dir():
            raise CDMParseError(f"Not a directory: {folder_path}")
        
        self._base_path = str(folder)
        self._loaded_paths = set()
        
        # Look for manifest files first
        manifest_files = list(folder.glob("*.manifest.cdm.json"))
        if manifest_files:
            return self.parse_file(str(manifest_files[0]))
        
        # Look for model.json
        model_json = folder / "model.json"
        if model_json.exists():
            return self.parse_file(str(model_json))
        
        # Fallback: collect all .cdm.json files
        cdm_files = list(folder.glob("*.cdm.json"))
        if cdm_files:
            all_entities: List[CDMEntity] = []
            for cdm_file in cdm_files:
                if str(cdm_file.resolve()) not in self._loaded_paths:
                    self._loaded_paths.add(str(cdm_file.resolve()))
                    with open(cdm_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    data = json.loads(content)
                    entities = self._parse_entity_schema_data(data, str(cdm_file))
                    all_entities.extend(entities.entities)
            
            return CDMManifest(
                name=folder.name,
                entities=all_entities,
                source_path=folder_path
            )
        
        raise CDMParseError(f"No CDM files found in folder: {folder_path}")
    
    def _detect_document_type(self, data: Any, file_path: Optional[str]) -> str:
        """
        Detect the type of CDM document.
        
        Args:
            data: Parsed JSON data.
            file_path: Optional file path for detection hints.
            
        Returns:
            Document type: "manifest", "model_json", or "entity_schema".
        """
        # Check file extension hints
        if file_path:
            path_lower = file_path.lower()
            if path_lower.endswith('.manifest.cdm.json'):
                return "manifest"
            if path_lower.endswith('model.json'):
                return "model_json"
        
        # Check content structure
        if isinstance(data, dict):
            # Manifest indicators
            if "manifestName" in data or "entities" in data and "jsonSchemaSemanticVersion" in data:
                if "definitions" not in data:  # Not an entity schema
                    return "manifest"
            
            # model.json indicators
            if data.get("$schema", "").endswith("model.json") or "model" in str(data.get("name", "")).lower():
                if "entities" in data and isinstance(data["entities"], list):
                    first_entity = data["entities"][0] if data["entities"] else {}
                    if "$type" in first_entity or "attributes" in first_entity:
                        return "model_json"
            
            # Entity schema indicators
            if "definitions" in data:
                return "entity_schema"
            
            # Legacy model.json with specific structure
            if "entities" in data and "name" in data:
                if "jsonSchemaSemanticVersion" not in data:
                    return "model_json"
        
        return "entity_schema"
    
    def _parse_manifest_data(self, data: Dict[str, Any], file_path: Optional[str]) -> CDMManifest:
        """
        Parse CDM manifest JSON data.
        
        Args:
            data: Parsed manifest JSON.
            file_path: Source file path.
            
        Returns:
            Parsed CDMManifest.
        """
        manifest_name = data.get("manifestName", data.get("folderName", "unknown"))
        schema_version = data.get("jsonSchemaSemanticVersion", "1.0.0")
        
        # Parse imports
        imports = []
        for imp in data.get("imports", []):
            if isinstance(imp, dict):
                imports.append(imp.get("corpusPath", ""))
            elif isinstance(imp, str):
                imports.append(imp)
        
        # Parse entities
        entities: List[CDMEntity] = []
        for entity_ref in data.get("entities", []):
            parsed_entities = self._resolve_entity_reference(entity_ref, file_path)
            entities.extend(parsed_entities)
        
        # Parse relationships
        relationships: List[CDMRelationship] = []
        for rel_data in data.get("relationships", []):
            rel = self._parse_relationship(rel_data)
            if rel:
                relationships.append(rel)
        
        # Parse sub-manifests
        sub_manifests = []
        for sub in data.get("subManifests", []):
            if isinstance(sub, dict):
                sub_manifests.append(sub.get("manifestPath", sub.get("definition", "")))
            elif isinstance(sub, str):
                sub_manifests.append(sub)
        
        return CDMManifest(
            name=manifest_name,
            entities=entities,
            relationships=relationships,
            sub_manifests=sub_manifests,
            schema_version=schema_version,
            source_path=file_path,
            imports=imports
        )
    
    def _parse_model_json_data(self, data: Dict[str, Any], file_path: Optional[str]) -> CDMManifest:
        """
        Parse legacy model.json format.
        
        Args:
            data: Parsed model.json JSON.
            file_path: Source file path.
            
        Returns:
            Parsed CDMManifest.
        """
        model_name = data.get("name", "model")
        version = data.get("version", "1.0")
        
        entities: List[CDMEntity] = []
        relationships: List[CDMRelationship] = []
        
        for entity_data in data.get("entities", []):
            entity = self._parse_model_json_entity(entity_data)
            if entity:
                entities.append(entity)
        
        # Extract relationships from entity references
        for entity_data in data.get("entities", []):
            entity_name = entity_data.get("name", "")
            for attr in entity_data.get("attributes", []):
                if "attributeReference" in attr:
                    ref = attr["attributeReference"]
                    if isinstance(ref, dict):
                        rel = CDMRelationship(
                            from_entity=entity_name,
                            from_attribute=attr.get("name", ""),
                            to_entity=ref.get("entityName", ""),
                            to_attribute=ref.get("attributeName", "")
                        )
                        relationships.append(rel)
        
        return CDMManifest(
            name=model_name,
            entities=entities,
            relationships=relationships,
            schema_version=version,
            source_path=file_path
        )
    
    def _parse_model_json_entity(self, data: Dict[str, Any]) -> Optional[CDMEntity]:
        """
        Parse an entity from model.json format.
        
        Args:
            data: Entity data from model.json.
            
        Returns:
            Parsed CDMEntity or None.
        """
        entity_name = data.get("name", data.get("$name"))
        if not entity_name:
            return None
        
        description = data.get("description")
        
        attributes: List[CDMAttribute] = []
        for attr_data in data.get("attributes", []):
            attr = self._parse_model_json_attribute(attr_data)
            if attr:
                attributes.append(attr)
        
        return CDMEntity(
            name=entity_name,
            description=description,
            attributes=attributes
        )
    
    def _parse_model_json_attribute(self, data: Dict[str, Any]) -> Optional[CDMAttribute]:
        """
        Parse an attribute from model.json format.
        
        Args:
            data: Attribute data from model.json.
            
        Returns:
            Parsed CDMAttribute or None.
        """
        attr_name = data.get("name", data.get("$name"))
        if not attr_name:
            return None
        
        # Map model.json dataType to CDM dataType
        data_type = data.get("dataType", "string")
        if isinstance(data_type, dict):
            data_type = data_type.get("dataType", "string")
        
        return CDMAttribute(
            name=attr_name,
            data_type=data_type,
            description=data.get("description"),
            is_nullable=data.get("isNullable", True),
            maximum_length=data.get("maximumLength"),
            display_name=data.get("displayName")
        )
    
    def _parse_entity_schema_data(self, data: Dict[str, Any], file_path: Optional[str]) -> CDMManifest:
        """
        Parse CDM entity schema (.cdm.json) format.
        
        Args:
            data: Parsed entity schema JSON.
            file_path: Source file path.
            
        Returns:
            CDMManifest containing parsed entities.
        """
        schema_version = data.get("jsonSchemaSemanticVersion", "1.0.0")
        
        entities: List[CDMEntity] = []
        
        # Parse definitions
        for definition in data.get("definitions", []):
            entity = self._parse_entity_definition(definition, file_path)
            if entity:
                entities.append(entity)
        
        # Handle single entity document (no definitions array)
        if not entities and "entityName" in data:
            entity = self._parse_entity_definition(data, file_path)
            if entity:
                entities.append(entity)
        
        manifest_name = Path(file_path).stem if file_path else "schema"
        
        return CDMManifest(
            name=manifest_name,
            entities=entities,
            schema_version=schema_version,
            source_path=file_path
        )
    
    def _parse_entity_definition(self, data: Dict[str, Any], file_path: Optional[str]) -> Optional[CDMEntity]:
        """
        Parse a single entity definition.
        
        Args:
            data: Entity definition data.
            file_path: Source file path.
            
        Returns:
            Parsed CDMEntity or None.
        """
        entity_name = data.get("entityName")
        if not entity_name:
            return None
        
        # Parse extends
        extends_entity = data.get("extendsEntity")
        if isinstance(extends_entity, dict):
            extends_entity = extends_entity.get("entityReference", extends_entity.get("source"))
        
        # Parse attributes
        attributes: List[CDMAttribute] = []
        for attr_data in data.get("hasAttributes", []):
            parsed_attrs = self._parse_attribute(attr_data)
            attributes.extend(parsed_attrs)
        
        # Parse exhibited traits
        exhibited_traits = self._parse_traits(data.get("exhibitsTraits", []))
        
        return CDMEntity(
            name=entity_name,
            description=data.get("description"),
            extends_entity=extends_entity,
            attributes=attributes,
            exhibited_traits=exhibited_traits,
            source_path=file_path,
            display_name=data.get("displayName"),
            version=data.get("version")
        )
    
    def _parse_attribute(self, data: Union[Dict[str, Any], str]) -> List[CDMAttribute]:
        """
        Parse an attribute definition.
        
        Handles both simple attributes and attribute groups.
        
        Args:
            data: Attribute data (dict or string reference).
            
        Returns:
            List of parsed CDMAttributes.
        """
        # Handle string reference
        if isinstance(data, str):
            return [CDMAttribute(name=data, data_type="string")]
        
        # Handle attribute group expansion
        if "attributeGroupReference" in data:
            # Attribute groups should be expanded - for now return empty
            # In a full implementation, we would resolve the group
            logger.debug(f"Skipping attribute group reference: {data.get('attributeGroupReference')}")
            return []
        
        # Handle entity attribute (relationship indicator)
        if "entity" in data or "entityReference" in data:
            # This represents a relationship, not a simple attribute
            entity_ref = data.get("entity", data.get("entityReference"))
            if isinstance(entity_ref, dict):
                entity_ref = entity_ref.get("source", entity_ref.get("entityName", ""))
            
            return [CDMAttribute(
                name=data.get("name", "entityRef"),
                data_type="entity",
                description=data.get("description"),
                purpose=data.get("purpose")
            )]
        
        # Handle type attribute (foreign key pattern)
        if "attributeReference" in data:
            ref = data["attributeReference"]
            return [CDMAttribute(
                name=data.get("name", ref if isinstance(ref, str) else ref.get("name", "ref")),
                data_type="string",  # FK references are typically string IDs
                description=data.get("description")
            )]
        
        # Standard attribute
        attr_name = data.get("name")
        if not attr_name:
            return []
        
        # Handle dataType that can be string or object
        data_type = data.get("dataType", "string")
        if isinstance(data_type, dict):
            data_type = data_type.get("dataType", "string")
        
        applied_traits = self._parse_traits(data.get("appliedTraits", []))
        
        # Extract purpose
        purpose = data.get("purpose")
        if isinstance(purpose, dict):
            purpose = purpose.get("purposeReference")
        
        # Extract maximum length from traits
        max_length = data.get("maximumLength")
        if max_length is None:
            for trait in applied_traits:
                if trait.trait_reference == "is.constrained.length":
                    for arg in trait.arguments:
                        if arg.name == "maximumLength" and arg.value:
                            try:
                                max_length = int(arg.value)
                            except (ValueError, TypeError):
                                pass
        
        return [CDMAttribute(
            name=attr_name,
            data_type=data_type,
            description=data.get("description"),
            applied_traits=applied_traits,
            purpose=purpose,
            is_nullable=data.get("isNullable", True),
            maximum_length=max_length,
            display_name=data.get("displayName"),
            source_ordering=data.get("sourceOrdering")
        )]
    
    def _parse_traits(self, traits_data: List[Any]) -> List[CDMTrait]:
        """
        Parse trait references.
        
        Args:
            traits_data: List of trait references.
            
        Returns:
            List of parsed CDMTraits.
        """
        traits: List[CDMTrait] = []
        
        for trait_data in traits_data:
            if isinstance(trait_data, str):
                traits.append(CDMTrait(trait_reference=trait_data))
            elif isinstance(trait_data, dict):
                trait_ref = trait_data.get("traitReference", trait_data.get("traitName", ""))
                arguments: List[CDMTraitArgument] = []
                
                for arg in trait_data.get("arguments", []):
                    if isinstance(arg, dict):
                        arguments.append(CDMTraitArgument(
                            name=arg.get("name"),
                            value=arg.get("value")
                        ))
                    else:
                        arguments.append(CDMTraitArgument(value=arg))
                
                traits.append(CDMTrait(
                    trait_reference=trait_ref,
                    arguments=arguments
                ))
        
        return traits
    
    def _parse_relationship(self, data: Dict[str, Any]) -> Optional[CDMRelationship]:
        """
        Parse a relationship definition.
        
        Args:
            data: Relationship data from manifest.
            
        Returns:
            Parsed CDMRelationship or None.
        """
        from_entity = data.get("fromEntity", "")
        from_attr = data.get("fromEntityAttribute", "")
        to_entity = data.get("toEntity", "")
        to_attr = data.get("toEntityAttribute", "")
        
        if not (from_entity and to_entity):
            return None
        
        traits = self._parse_traits(data.get("exhibitsTraits", []))
        name = data.get("name")
        
        return CDMRelationship(
            from_entity=from_entity,
            from_attribute=from_attr,
            to_entity=to_entity,
            to_attribute=to_attr,
            name=name,
            traits=traits
        )
    
    def _resolve_entity_reference(
        self, 
        entity_ref: Union[Dict[str, Any], str],
        manifest_path: Optional[str]
    ) -> List[CDMEntity]:
        """
        Resolve an entity reference from a manifest.
        
        Args:
            entity_ref: Entity reference (path or inline definition).
            manifest_path: Path to the manifest file.
            
        Returns:
            List of resolved CDMEntities.
        """
        if isinstance(entity_ref, str):
            # String reference - try to resolve file
            if self.resolve_references and self._base_path:
                return self._load_entity_from_path(entity_ref)
            return []
        
        # Dictionary reference
        entity_type = entity_ref.get("type", entity_ref.get("$type", ""))
        
        # Inline/local entity
        if entity_type.lower() in ("localentity", "local"):
            entity_path = entity_ref.get("entityPath", entity_ref.get("entityDeclaration", ""))
            entity_name = entity_ref.get("entityName", "")
            
            # If there's a path, try to load it
            if entity_path and self.resolve_references and self._base_path:
                entities = self._load_entity_from_path(entity_path)
                if entities:
                    return entities
            
            # Create placeholder entity from reference
            if entity_name:
                return [CDMEntity(name=entity_name)]
            
            # Extract entity name from path
            if entity_path:
                # Format: "Folder/Entity.cdm.json/EntityName"
                parts = entity_path.split("/")
                if len(parts) >= 1:
                    name = parts[-1]
                    return [CDMEntity(name=name, source_path=entity_path)]
        
        # Referenced entity
        if entity_type.lower() == "referencedentity":
            entity_name = entity_ref.get("entityName", "")
            if entity_name:
                return [CDMEntity(name=entity_name)]
        
        return []
    
    def _load_entity_from_path(self, entity_path: str) -> List[CDMEntity]:
        """
        Load entity from a corpus path.
        
        Args:
            entity_path: CDM corpus path (e.g., "Folder/Entity.cdm.json/EntityName").
            
        Returns:
            List of loaded CDMEntities.
        """
        if not self._base_path:
            return []
        
        # Parse corpus path format: "Folder/File.cdm.json/EntityName"
        parts = entity_path.split("/")
        
        # Find the .cdm.json file part
        file_parts = []
        entity_name_from_path = None
        
        for i, part in enumerate(parts):
            file_parts.append(part)
            if part.endswith(".cdm.json"):
                if i + 1 < len(parts):
                    entity_name_from_path = parts[i + 1]
                break
        
        if not file_parts:
            return []
        
        # Construct file path
        file_path = os.path.join(self._base_path, *file_parts)
        
        # Check if already loaded (prevent circular references)
        resolved_path = str(Path(file_path).resolve())
        if resolved_path in self._loaded_paths:
            return []
        
        if not os.path.exists(file_path):
            logger.debug(f"Entity file not found: {file_path}")
            return []
        
        self._loaded_paths.add(resolved_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            data = json.loads(content)
            manifest = self._parse_entity_schema_data(data, file_path)
            
            # Filter to specific entity if named
            if entity_name_from_path:
                return [e for e in manifest.entities if e.name == entity_name_from_path]
            
            return manifest.entities
        
        except Exception as e:
            logger.warning(f"Failed to load entity from {file_path}: {e}")
            return []
