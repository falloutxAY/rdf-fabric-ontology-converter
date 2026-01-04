"""
Export command for exporting ontologies from Fabric to TTL format.
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from ..base import BaseCommand
from ...helpers import (
    load_config,
    get_default_config_path,
    setup_logging,
)


logger = logging.getLogger(__name__)


class ExportCommand(BaseCommand):
    """
    Export an ontology from Fabric to TTL format (RDF only).
    
    Usage:
        export <ontology_id> [options]
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the export command."""
        from rdf import InputValidator, FabricToTTLConverter
        from core import FabricConfig, FabricOntologyClient, FabricAPIError
        
        config_path = args.config or get_default_config_path()
        
        try:
            config_data = load_config(config_path)
            setup_logging(config=config_data.get('logging', {}))
        except Exception as e:
            print(f"✗ {e}")
            return 1
        
        try:
            fabric_config = FabricConfig.from_dict(config_data)
        except Exception as e:
            print(f"✗ Configuration error: {e}")
            return 1
        
        client = FabricOntologyClient(fabric_config)
        ontology_id = args.ontology_id
        
        print(f"✓ Exporting ontology {ontology_id} to TTL...")
        
        try:
            ontology_info = client.get_ontology(ontology_id)
            definition = client.get_ontology_definition(ontology_id)
            
            if not definition:
                print("✗ Failed to get ontology definition")
                return 1
            
            fabric_definition = {
                "displayName": ontology_info.get("displayName", "exported_ontology"),
                "description": ontology_info.get("description", ""),
                "definition": definition
            }
            
            converter = FabricToTTLConverter()
            ttl_content = converter.convert(fabric_definition)
            
            if args.output:
                output_path = args.output
            else:
                safe_name = ontology_info.get("displayName", ontology_id).replace(" ", "_")
                output_path = f"{safe_name}_exported.ttl"
            
            try:
                validated_output = InputValidator.validate_output_file_path(
                    output_path, allowed_extensions=['.ttl', '.rdf', '.owl']
                )
            except Exception as e:
                print(f"✗ Invalid output path: {e}")
                return 1
            
            with open(validated_output, 'w', encoding='utf-8') as f:
                f.write(ttl_content)
            
            print(f"✓ Exported to: {validated_output}")
            print(f"  Ontology Name: {ontology_info.get('displayName', 'Unknown')}")
            print(f"  Parts: {len(definition.get('parts', []))}")
            
            return 0
            
        except FabricAPIError as e:
            print(f"✗ API Error: {e}")
            return 1
        except Exception as e:
            print(f"✗ Export failed: {e}")
            return 1
