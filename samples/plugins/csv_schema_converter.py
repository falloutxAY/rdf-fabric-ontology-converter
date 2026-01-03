"""
Sample CSV Schema Plugin for Fabric Ontology Converter.

This is a sample plugin demonstrating how to create a custom format converter
for the Fabric Ontology Converter. It converts CSV schema definitions
(describing entity types and their properties) to Fabric Ontology format.

CSV Format:
    The expected CSV format has the following columns:
    - entity_name: Name of the entity type
    - property_name: Name of the property
    - property_type: Data type (String, Integer, Float, Boolean, DateTime)
    - is_id: Whether this property is an identifier (true/false)
    - description: Optional description

Example CSV:
    entity_name,property_name,property_type,is_id,description
    Machine,serial_number,String,true,Unique serial number
    Machine,manufacturer,String,false,Manufacturer name
    Machine,model,String,false,Model name
    Machine,install_date,DateTime,false,Installation date
    Sensor,sensor_id,String,true,Unique sensor ID
    Sensor,sensor_type,String,false,Type of sensor
    Sensor,machine_id,String,false,Associated machine ID

Usage:
    # Register the plugin
    from src.core.plugins import PluginRegistry
    from samples.plugins.csv_schema_converter import CSVSchemaConverter
    
    PluginRegistry.register_converter(CSVSchemaConverter())
    
    # Use the plugin
    converter = PluginRegistry.get_converter("csvschema")
    result = converter.convert("schema.csv")

Entry Point Registration:
    Add to pyproject.toml:
    
    [project.entry-points."fabric_ontology.converters"]
    csvschema = "samples.plugins.csv_schema_converter:CSVSchemaConverter"
"""

import csv
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Import from the main package
try:
    from src.core.plugins import (
        FormatConverter,
        ConversionContext,
        ConversionOutput,
        ConversionStatus,
    )
    from src.models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
    )
except ImportError:
    # Fallback for direct import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.core.plugins import (
        FormatConverter,
        ConversionContext,
        ConversionOutput,
        ConversionStatus,
    )
    from src.models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
    )

logger = logging.getLogger(__name__)


# Type mapping from CSV types to Fabric types
CSV_TO_FABRIC_TYPE: Dict[str, str] = {
    "string": "String",
    "text": "String",
    "varchar": "String",
    "integer": "BigInt",
    "int": "BigInt",
    "bigint": "BigInt",
    "smallint": "BigInt",
    "float": "Double",
    "double": "Double",
    "decimal": "Double",
    "numeric": "Double",
    "real": "Double",
    "boolean": "Boolean",
    "bool": "Boolean",
    "datetime": "DateTime",
    "timestamp": "DateTime",
    "date": "DateTime",
    "time": "DateTime",
}


class CSVSchemaConverter(FormatConverter):
    """
    Converts CSV schema definitions to Fabric Ontology format.
    
    This is a sample plugin demonstrating the plugin interface. It shows how to:
    - Define format metadata (format_name, file_extensions, etc.)
    - Implement the convert() method
    - Generate entity types and properties
    - Handle conversion errors and warnings
    - Report progress through callbacks
    
    Attributes:
        format_name: "csvschema" - identifier for the CSV schema format.
        file_extensions: [".csv"] - supported file extensions.
        format_description: Human-readable description.
    """
    
    # Required plugin metadata
    format_name = "csvschema"
    file_extensions = [".csv"]
    format_description = "CSV Schema Definition to Fabric Ontology converter"
    version = "1.0.0"
    author = "Sample Plugin Author"
    
    # Configuration
    DEFAULT_NAMESPACE = "usertypes"
    ID_BASE = 1000000000000  # Starting ID for generated entities
    PROPERTY_ID_BASE = 1000000001  # Starting ID for properties
    
    def __init__(self) -> None:
        """Initialize the CSV schema converter."""
        self._current_entity_id = self.ID_BASE
        self._current_property_id = self.PROPERTY_ID_BASE
    
    def convert(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ConversionOutput:
        """
        Convert CSV schema to Fabric Ontology format.
        
        Args:
            source: CSV content - can be:
                - str: File path or CSV content string
                - Path: Path to CSV file
                - bytes: Raw CSV content
            context: Optional conversion context with config and callbacks.
            **options: Additional options:
                - namespace: Override default namespace
                - include_relationships: Try to infer relationships from _id columns
                - skip_header: Number of header rows to skip (default: 1)
        
        Returns:
            ConversionOutput with entity types and any warnings/errors.
        
        Example using core infrastructure:
            # Create context with core features enabled
            context = ConversionContext.create_with_defaults(
                enable_rate_limiter=True,
                enable_circuit_breaker=True,
                enable_cancellation=True,
                enable_memory_manager=True,
            )
            
            converter = CSVSchemaConverter()
            result = converter.convert("schema.csv", context=context)
        """
        output = ConversionOutput()
        self._reset_ids()
        
        namespace = options.get("namespace", self.DEFAULT_NAMESPACE)
        include_relationships = options.get("include_relationships", True)
        skip_header = options.get("skip_header", 1)
        
        try:
            # Check memory availability if memory manager is configured
            if context and not context.check_memory("CSV conversion"):
                output.status = ConversionStatus.FAILED
                output.errors.append("Insufficient memory for conversion")
                return output
            
            # Validate input if validator is configured
            if context and isinstance(source, (str, Path)):
                source_path = str(source)
                if Path(source_path).exists():
                    context.validate_input(source_path)
            
            # Parse the CSV content
            rows = self._parse_csv(source, skip_header)
            
            if not rows:
                output.status = ConversionStatus.FAILED
                output.errors.append("No data rows found in CSV")
                return output
            
            # Group rows by entity name
            entities_data = self._group_by_entity(rows)
            total_entities = len(entities_data)
            
            # Convert each entity
            for idx, (entity_name, properties) in enumerate(entities_data.items()):
                if context:
                    # Report progress
                    context.report_progress(idx + 1, total_entities, f"Converting {entity_name}")
                    
                    # Check for cancellation (supports both callback and token)
                    if context.is_cancelled():
                        output.status = ConversionStatus.PARTIAL
                        output.warnings.append("Conversion cancelled by user")
                        break
                    
                    # Alternative: throw exception on cancellation
                    # context.throw_if_cancelled()
                
                entity_type = self._create_entity_type(entity_name, properties, namespace)
                output.entity_types.append(entity_type)
            
            # Optionally infer relationships from _id columns
            if include_relationships:
                relationships = self._infer_relationships(output.entity_types)
                output.relationship_types.extend(relationships)
            
            # Update statistics
            output.statistics = {
                "row_count": len(rows),
                "entity_count": len(output.entity_types),
                "relationship_count": len(output.relationship_types),
                "property_count": sum(len(e.properties) for e in output.entity_types),
            }
            
            if output.warnings:
                output.status = ConversionStatus.PARTIAL
            else:
                output.status = ConversionStatus.SUCCESS
                
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(f"CSV conversion failed: {str(e)}")
            logger.error(f"CSV conversion error: {e}", exc_info=True)
        
        return output
    
    def can_convert(self, source: Union[str, Path]) -> bool:
        """
        Check if this converter can handle the given source.
        
        Performs content-based detection by checking for expected CSV structure.
        
        Args:
            source: File path to check.
        
        Returns:
            True if the file appears to be a CSV schema definition.
        """
        # First check extension
        if isinstance(source, (str, Path)):
            path = Path(source) if isinstance(source, str) else source
            if path.suffix.lower() != '.csv':
                return False
            
            # Try to detect CSV schema content
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().lower()
                    # Check for expected columns
                    return (
                        'entity_name' in first_line and 
                        'property_name' in first_line and
                        'property_type' in first_line
                    )
            except Exception:
                pass
        
        return False
    
    def _reset_ids(self) -> None:
        """Reset ID counters for a new conversion."""
        self._current_entity_id = self.ID_BASE
        self._current_property_id = self.PROPERTY_ID_BASE
    
    def _next_entity_id(self) -> str:
        """Generate the next entity ID."""
        entity_id = str(self._current_entity_id)
        self._current_entity_id += 1
        return entity_id
    
    def _next_property_id(self) -> str:
        """Generate the next property ID."""
        prop_id = str(self._current_property_id)
        self._current_property_id += 1
        return prop_id
    
    def _parse_csv(
        self, 
        source: Union[str, Path, bytes], 
        skip_header: int
    ) -> List[Dict[str, str]]:
        """
        Parse CSV content into a list of row dictionaries.
        
        Args:
            source: CSV content or file path.
            skip_header: Number of header rows already parsed.
        
        Returns:
            List of dictionaries, one per data row.
        """
        rows: List[Dict[str, str]] = []
        
        # Get content as string
        if isinstance(source, bytes):
            content = source.decode('utf-8')
            lines = content.splitlines()
        elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
            with open(source, 'r', encoding='utf-8', newline='') as f:
                content = f.read()
            lines = content.splitlines()
        else:
            # Assume string content
            lines = source.splitlines()
        
        if not lines:
            return rows
        
        # Parse with csv module
        reader = csv.DictReader(lines)
        for row in reader:
            # Normalize keys to lowercase
            normalized = {k.lower().strip(): v.strip() for k, v in row.items()}
            rows.append(normalized)
        
        return rows
    
    def _group_by_entity(
        self, 
        rows: List[Dict[str, str]]
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Group CSV rows by entity name.
        
        Args:
            rows: List of row dictionaries.
        
        Returns:
            Dictionary mapping entity names to their property rows.
        """
        entities: Dict[str, List[Dict[str, str]]] = {}
        
        for row in rows:
            entity_name = row.get('entity_name', '').strip()
            if not entity_name:
                continue
            
            if entity_name not in entities:
                entities[entity_name] = []
            entities[entity_name].append(row)
        
        return entities
    
    def _create_entity_type(
        self,
        entity_name: str,
        property_rows: List[Dict[str, str]],
        namespace: str
    ) -> EntityType:
        """
        Create an EntityType from CSV property rows.
        
        Args:
            entity_name: Name of the entity.
            property_rows: List of property definitions.
            namespace: Namespace for the entity.
        
        Returns:
            EntityType with properties.
        """
        entity = EntityType(
            id=self._next_entity_id(),
            name=entity_name,
            namespace=namespace,
            namespaceType="Custom",
            visibility="Visible",
        )
        
        id_properties: List[str] = []
        
        for row in property_rows:
            prop_name = row.get('property_name', '').strip()
            prop_type = row.get('property_type', 'String').strip().lower()
            is_id = row.get('is_id', '').strip().lower() in ('true', 'yes', '1')
            
            if not prop_name:
                continue
            
            # Map type to Fabric type
            fabric_type = CSV_TO_FABRIC_TYPE.get(prop_type, "String")
            
            prop = EntityTypeProperty(
                id=self._next_property_id(),
                name=prop_name,
                valueType=fabric_type,
            )
            entity.properties.append(prop)
            
            # Track ID properties
            if is_id:
                id_properties.append(prop.id)
        
        # Set entityIdParts if we have ID properties
        if id_properties:
            entity.entityIdParts = id_properties
            # Use first ID property as display name
            entity.displayNamePropertyId = id_properties[0]
        
        return entity
    
    def _infer_relationships(
        self, 
        entity_types: List[EntityType]
    ) -> List[RelationshipType]:
        """
        Infer relationships from properties ending in '_id'.
        
        If an entity has a property like 'machine_id', and there's a 'Machine'
        entity, we infer a relationship.
        
        Args:
            entity_types: List of entity types.
        
        Returns:
            List of inferred relationship types.
        """
        relationships: List[RelationshipType] = []
        
        # Build lookup of entity names to IDs
        entity_lookup = {e.name.lower(): e.id for e in entity_types}
        
        rel_id_base = 2000000000000
        
        for entity in entity_types:
            for prop in entity.properties:
                # Check for _id suffix
                if prop.name.lower().endswith('_id'):
                    # Extract potential entity name
                    target_name = prop.name[:-3]  # Remove '_id'
                    target_name_lower = target_name.lower()
                    
                    # Check if target entity exists
                    if target_name_lower in entity_lookup:
                        target_id = entity_lookup[target_name_lower]
                        
                        # Create relationship
                        rel = RelationshipType(
                            id=str(rel_id_base),
                            name=f"has_{target_name}",
                            namespace="usertypes",
                            namespaceType="Custom",
                            source=RelationshipEnd(entityTypeId=entity.id),
                            target=RelationshipEnd(entityTypeId=target_id),
                        )
                        relationships.append(rel)
                        rel_id_base += 1
        
        return relationships


class CSVSchemaValidator:
    """
    Sample validator for CSV schema files.
    
    This demonstrates how to create a FormatValidator plugin.
    """
    
    format_name = "csvschema"
    file_extensions = [".csv"]
    format_description = "CSV Schema Definition validator"
    version = "1.0.0"
    
    REQUIRED_COLUMNS = {'entity_name', 'property_name', 'property_type'}
    
    def validate(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> Dict[str, Any]:
        """
        Validate a CSV schema file.
        
        Returns:
            Dictionary with is_valid, errors, warnings, and info.
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
        }
        
        try:
            # Read content
            if isinstance(source, bytes):
                content = source.decode('utf-8')
            elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
                with open(source, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = source
            
            lines = content.splitlines()
            if not lines:
                result["is_valid"] = False
                result["errors"].append("Empty CSV file")
                return result
            
            # Check header
            reader = csv.DictReader(lines)
            header = {col.lower().strip() for col in reader.fieldnames or []}
            
            missing = self.REQUIRED_COLUMNS - header
            if missing:
                result["is_valid"] = False
                result["errors"].append(f"Missing required columns: {', '.join(missing)}")
            
            # Validate rows
            row_count = 0
            entity_names = set()
            
            for idx, row in enumerate(reader, start=2):
                row_count += 1
                entity_name = row.get('entity_name', '').strip()
                prop_name = row.get('property_name', '').strip()
                prop_type = row.get('property_type', '').strip().lower()
                
                if not entity_name:
                    result["warnings"].append(f"Row {idx}: Missing entity_name")
                else:
                    entity_names.add(entity_name)
                
                if not prop_name:
                    result["warnings"].append(f"Row {idx}: Missing property_name")
                
                if prop_type and prop_type not in CSV_TO_FABRIC_TYPE:
                    result["warnings"].append(
                        f"Row {idx}: Unknown property_type '{prop_type}', will default to String"
                    )
            
            result["info"].append(f"Found {row_count} property definitions")
            result["info"].append(f"Found {len(entity_names)} unique entities")
            
        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"Validation failed: {str(e)}")
        
        return result


# Example usage
if __name__ == "__main__":
    # Create sample CSV content
    sample_csv = """entity_name,property_name,property_type,is_id,description
Machine,serial_number,String,true,Unique serial number
Machine,manufacturer,String,false,Manufacturer name
Machine,model,String,false,Model name
Machine,install_date,DateTime,false,Installation date
Machine,status,String,false,Current status
Sensor,sensor_id,String,true,Unique sensor ID
Sensor,sensor_type,String,false,Type of sensor
Sensor,machine_id,String,false,Associated machine ID
Sensor,last_reading,Float,false,Last sensor reading
Reading,reading_id,String,true,Reading identifier
Reading,sensor_id,String,false,Sensor that took reading
Reading,value,Float,false,Reading value
Reading,timestamp,DateTime,false,Time of reading
"""
    
    # Test the converter
    converter = CSVSchemaConverter()
    result = converter.convert(sample_csv, include_relationships=True)
    
    print(f"Conversion Status: {result.status.value}")
    print(f"Entity Types: {len(result.entity_types)}")
    print(f"Relationships: {len(result.relationship_types)}")
    
    for entity in result.entity_types:
        print(f"\n  Entity: {entity.name}")
        print(f"    ID: {entity.id}")
        print(f"    Properties: {len(entity.properties)}")
        for prop in entity.properties:
            print(f"      - {prop.name} ({prop.valueType})")
    
    for rel in result.relationship_types:
        print(f"\n  Relationship: {rel.name}")
        print(f"    Source: {rel.source.entityTypeId}")
        print(f"    Target: {rel.target.entityTypeId}")
