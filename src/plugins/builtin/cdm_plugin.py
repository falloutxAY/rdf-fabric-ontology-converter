"""
CDM Plugin.

This module provides the CDM (Common Data Model) plugin for the
RDF-DTDL-Fabric Ontology Converter. It wraps the CDM format components
as a unified plugin interface.

Usage:
    from plugins.builtin.cdm_plugin import CDMPlugin
    
    plugin = CDMPlugin()
    
    # Get parser, validator, converter
    parser = plugin.get_parser()
    validator = plugin.get_validator()
    converter = plugin.get_converter()
    
    # Check if file is CDM
    if plugin.can_handle_file("model.manifest.cdm.json"):
        # Process file
        pass
"""

import json
from typing import Any, Dict, List, Optional, Set

from plugins.base import OntologyPlugin


class CDMPlugin(OntologyPlugin):
    """
    Common Data Model (CDM) plugin.
    
    Supports:
    - CDM manifest files (*.manifest.cdm.json)
    - CDM entity schema files (*.cdm.json)
    - Legacy model.json files
    
    Compatible with:
    - Dynamics 365 / Dataverse schemas
    - Power Platform CDM folders
    - Azure Data Lake CDM folders
    - Industry Accelerators (Healthcare, Financial Services, etc.)
    """
    
    @property
    def format_name(self) -> str:
        """Return the internal format identifier."""
        return "cdm"
    
    @property
    def display_name(self) -> str:
        """Return the human-readable format name."""
        return "CDM (Common Data Model)"
    
    @property
    def file_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {".cdm.json", ".manifest.cdm.json", ".json"}
    
    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "1.0.0"
    
    @property
    def author(self) -> str:
        """Return the plugin author."""
        return "Fabric Ontology Converter Team"
    
    @property
    def description(self) -> str:
        """Return the plugin description."""
        return (
            "Common Data Model (CDM) format plugin. Supports CDM manifests, "
            "entity schemas, and legacy model.json format. Compatible with "
            "Dynamics 365, Power Platform, and Industry Accelerators."
        )
    
    @property
    def dependencies(self) -> List[str]:
        """Return required dependencies (standard library only)."""
        return []  # Uses standard library JSON
    
    def get_parser(self) -> Any:
        """
        Return CDM parser instance.
        
        Returns:
            CDMParser instance.
        """
        try:
            from formats.cdm import CDMParser
            return CDMParser()
        except ImportError as e:
            raise ImportError(f"CDM modules not available: {e}")
    
    def get_validator(self) -> Any:
        """
        Return CDM validator instance.
        
        Returns:
            CDMValidator instance.
        """
        try:
            from formats.cdm import CDMValidator
            return CDMValidator()
        except ImportError as e:
            raise ImportError(f"CDM modules not available: {e}")
    
    def get_converter(self) -> Any:
        """
        Return CDM converter instance.
        
        Returns:
            CDMToFabricConverter instance.
        """
        try:
            from formats.cdm import CDMToFabricConverter
            return CDMToFabricConverter()
        except ImportError as e:
            raise ImportError(f"CDM modules not available: {e}")
    
    def get_type_mappings(self) -> Dict[str, str]:
        """
        Return CDM to Fabric type mappings.
        
        Returns:
            Dictionary mapping CDM types to Fabric types.
        """
        try:
            from formats.cdm import CDM_TYPE_MAPPINGS, CDM_SEMANTIC_TYPE_MAPPINGS
            mappings = CDM_TYPE_MAPPINGS.copy()
            mappings.update(CDM_SEMANTIC_TYPE_MAPPINGS)
            return mappings
        except ImportError:
            return {}
    
    def can_handle_file(self, file_path: str) -> bool:
        """
        Check if this plugin can handle the given file.
        
        Args:
            file_path: Path to file to check.
            
        Returns:
            True if this plugin can handle the file.
        """
        path_lower = file_path.lower()
        
        # Definite CDM files
        if path_lower.endswith('.cdm.json'):
            return True
        if path_lower.endswith('.manifest.cdm.json'):
            return True
        if path_lower.endswith('model.json'):
            return True
        
        # Check JSON files for CDM content
        if path_lower.endswith('.json'):
            return self._looks_like_cdm(file_path)
        
        return False
    
    def _looks_like_cdm(self, file_path: str) -> bool:
        """
        Heuristic check if JSON file contains CDM content.
        
        Args:
            file_path: Path to JSON file.
            
        Returns:
            True if file appears to be CDM content.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read first 4KB for quick check
                content = f.read(4096)
            
            data = json.loads(content)
            
            if isinstance(data, dict):
                # CDM manifest indicators
                if "manifestName" in data:
                    return True
                if "jsonSchemaSemanticVersion" in data:
                    return True
                if "definitions" in data and isinstance(data.get("definitions"), list):
                    return True
                
                # model.json indicators
                if "entities" in data and "name" in data:
                    entities = data.get("entities", [])
                    if entities and isinstance(entities[0], dict):
                        if "$type" in entities[0] or "attributes" in entities[0]:
                            return True
            
            return False
            
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError):
            return False
    
    def register_cli_arguments(self, parser: Any) -> None:
        """
        Register CDM-specific CLI arguments.
        
        Args:
            parser: Argument parser to add arguments to.
        """
        parser.add_argument(
            "--cdm-resolve-references",
            action="store_true",
            default=True,
            help="Resolve entity references from external files (default: True)"
        )
        parser.add_argument(
            "--cdm-flatten-inheritance",
            action="store_true",
            default=True,
            help="Flatten inherited attributes into entities (default: True)"
        )
        parser.add_argument(
            "--cdm-include-model-json",
            action="store_true",
            default=True,
            help="Support legacy model.json format (default: True)"
        )
    
    def detect_cdm_document_type(self, content: str) -> Optional[str]:
        """
        Detect the type of CDM document from content.
        
        Args:
            content: JSON string content.
            
        Returns:
            Document type: "manifest", "entity_schema", "model_json", or None.
        """
        try:
            data = json.loads(content)
            
            if isinstance(data, dict):
                # Manifest
                if "manifestName" in data:
                    return "manifest"
                if "jsonSchemaSemanticVersion" in data and "entities" in data:
                    if "definitions" not in data:
                        return "manifest"
                
                # Entity schema
                if "definitions" in data:
                    return "entity_schema"
                if "entityName" in data:
                    return "entity_schema"
                
                # model.json
                if "entities" in data and "name" in data:
                    return "model_json"
            
            return None
            
        except json.JSONDecodeError:
            return None


# Export
__all__ = ["CDMPlugin"]
