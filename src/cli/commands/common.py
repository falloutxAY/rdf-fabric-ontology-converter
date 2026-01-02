"""
Common CLI commands.

This module contains commands that are shared across formats:
- ListCommand: List ontologies in the workspace
- GetCommand: Get ontology details
- DeleteCommand: Delete an ontology
- TestCommand: Test with sample ontology
- CompareCommand: Compare two TTL files
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Ensure src directory is in path for late imports
_src_dir = str(Path(__file__).parent.parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from .base import BaseCommand, print_conversion_summary

try:
    from ..helpers import (
        load_config,
        get_default_config_path,
        setup_logging,
        print_header,
        print_footer,
        confirm_action,
    )
except ImportError:
    from cli.helpers import (
        load_config,
        get_default_config_path,
        setup_logging,
        print_header,
        print_footer,
        confirm_action,
    )


logger = logging.getLogger(__name__)


class ListCommand(BaseCommand):
    """List all ontologies in the workspace."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the list command."""
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        
        config_path = args.config or get_default_config_path()
        config_data = load_config(config_path)
        fabric_config = FabricConfig.from_dict(config_data)
        
        log_config = config_data.get('logging', {})
        setup_logging(config=log_config)
        
        client = FabricOntologyClient(fabric_config)
        
        try:
            ontologies = client.list_ontologies()
            
            if not ontologies:
                print("No ontologies found in the workspace.")
                return 0
            
            print(f"\nFound {len(ontologies)} ontologies:\n")
            print(f"{'ID':<40} {'Name':<30} {'Description':<40}")
            print("-" * 110)
            
            for ont in ontologies:
                ont_id = ont.get('id', 'Unknown')
                name = ont.get('displayName', 'Unknown')[:30]
                desc = (ont.get('description', '') or '')[:40]
                print(f"{ont_id:<40} {name:<30} {desc:<40}")
            
            return 0
            
        except FabricAPIError as e:
            logger.error(f"Fabric API error: {e}")
            print(f"Error: {e.message}")
            return 1


class GetCommand(BaseCommand):
    """Get details of a specific ontology."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the get command."""
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        
        config_path = args.config or get_default_config_path()
        config_data = load_config(config_path)
        fabric_config = FabricConfig.from_dict(config_data)
        
        log_config = config_data.get('logging', {})
        setup_logging(config=log_config)
        
        client = FabricOntologyClient(fabric_config)
        
        try:
            ontology = client.get_ontology(args.ontology_id)
            print("\nOntology Details:")
            print(json.dumps(ontology, indent=2))
            
            if args.with_definition:
                print("\nOntology Definition:")
                definition = client.get_ontology_definition(args.ontology_id)
                print(json.dumps(definition, indent=2))
            
            return 0
            
        except FabricAPIError as e:
            logger.error(f"Fabric API error: {e}")
            print(f"Error: {e.message}")
            return 1


class DeleteCommand(BaseCommand):
    """Delete an ontology."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the delete command."""
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        
        config_path = args.config or get_default_config_path()
        config_data = load_config(config_path)
        fabric_config = FabricConfig.from_dict(config_data)
        
        log_config = config_data.get('logging', {})
        setup_logging(config=log_config)
        
        client = FabricOntologyClient(fabric_config)
        
        if not args.force:
            if not confirm_action(f"Are you sure you want to delete ontology {args.ontology_id}?"):
                print("Cancelled.")
                return 0
        
        try:
            client.delete_ontology(args.ontology_id)
            print(f"Successfully deleted ontology {args.ontology_id}")
            return 0
            
        except FabricAPIError as e:
            logger.error(f"Fabric API error: {e}")
            print(f"Error: {e.message}")
            return 1


class TestCommand(BaseCommand):
    """Test the program with a sample ontology."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the test command."""
        from rdf_converter import InputValidator, parse_ttl_content
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        
        config_path = args.config or get_default_config_path()
        if os.path.exists(config_path):
            config_data = load_config(config_path)
            log_config = config_data.get('logging', {})
            setup_logging(config=log_config)
        else:
            self.setup_logging_from_config()
            config_data = None
        
        # Find sample TTL file
        script_dir = Path(__file__).parent.parent.parent  # Go up from commands/ to src/
        candidate_paths = [
            script_dir.parent / "samples" / "sample_supply_chain_ontology.ttl",
            Path.cwd() / "samples" / "sample_supply_chain_ontology.ttl",
            script_dir / "samples" / "sample_supply_chain_ontology.ttl",
        ]
        sample_ttl = next((p for p in candidate_paths if p.exists()), None)
        
        if not sample_ttl:
            print("Error: Sample TTL file not found in expected locations:")
            for p in candidate_paths:
                print(f"  - {p}")
            return 1
        
        print(f"Testing with sample ontology: {sample_ttl}\n")
        
        try:
            validated_path = InputValidator.validate_input_ttl_path(str(sample_ttl))
        except (ValueError, FileNotFoundError, PermissionError) as e:
            print(f"Error validating sample file: {e}")
            return 1
        
        with open(validated_path, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
        
        definition, ontology_name = parse_ttl_content(ttl_content)
        
        print(f"Ontology Name: {ontology_name}")
        print(f"Number of definition parts: {len(definition['parts'])}")
        print("\nDefinition Parts:")
        for part in definition['parts']:
            print(f"  - {part['path']}")
        
        print("\n--- Full Definition (JSON) ---\n")
        print(json.dumps(definition, indent=2))
        
        # Test Fabric connection if configured
        if config_data and os.path.exists(config_path):
            fabric_config = FabricConfig.from_dict(config_data)
            
            if fabric_config.workspace_id and fabric_config.workspace_id != "YOUR_WORKSPACE_ID":
                print("\n--- Testing Fabric Connection ---\n")
                client = FabricOntologyClient(fabric_config)
                
                try:
                    ontologies = client.list_ontologies()
                    print(f"Successfully connected to Fabric. Found {len(ontologies)} existing ontologies.")
                    
                    if args.upload_test:
                        print("\nUploading test ontology...")
                        result = client.create_ontology(
                            display_name="Test_Manufacturing_Ontology",
                            description="Test ontology from RDF import tool",
                            definition=definition,
                        )
                        print(f"Successfully created test ontology: {result.get('id')}")
                    
                    return 0
                    
                except FabricAPIError as e:
                    print(f"Fabric API error: {e.message}")
                    return 1
            else:
                print("\nNote: Configure workspace_id in config.json to test Fabric connection.")
        else:
            print(f"\nNote: Create {config_path} to test Fabric connection.")
        
        return 0


class CompareCommand(BaseCommand):
    """Compare two TTL files for semantic equivalence."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the compare command."""
        from rdf_converter import InputValidator
        from fabric_to_ttl import compare_ontologies
        
        self.setup_logging_from_config()
        
        ttl_file1 = args.ttl_file1
        ttl_file2 = args.ttl_file2
        
        try:
            allow_up = getattr(args, 'allow_relative_up', False)
            validated_path1 = InputValidator.validate_input_ttl_path(ttl_file1, allow_relative_up=allow_up)
            validated_path2 = InputValidator.validate_input_ttl_path(ttl_file2, allow_relative_up=allow_up)
        except ValueError as e:
            err = str(e).lower()
            if ("outside current directory" in err or "outside working directory" in err) and allow_up:
                print("✗ Path resolves outside the current directory")
                print(f"  {e}")
                print("\n  Relative up is only allowed within the current directory when using --allow-relative-up.")
                print("  Tip: cd into the target folder or provide an absolute path inside the workspace.")
                return 1
            else:
                print(f"Error: Invalid TTL file path: {e}")
                return 1
        except FileNotFoundError as e:
            print(f"Error: TTL file not found: {e}")
            return 1
        except PermissionError as e:
            print(f"Error: {e}")
            return 1
        
        try:
            with open(validated_path1, 'r', encoding='utf-8') as f:
                ttl_content1 = f.read()
            with open(validated_path2, 'r', encoding='utf-8') as f:
                ttl_content2 = f.read()
        except Exception as e:
            print(f"Error reading TTL files: {e}")
            return 1
        
        print(f"Comparing:")
        print(f"  File 1: {validated_path1}")
        print(f"  File 2: {validated_path2}")
        print()
        
        comparison = compare_ontologies(ttl_content1, ttl_content2)
        
        if comparison["is_equivalent"]:
            print("✓ Ontologies are semantically EQUIVALENT")
        else:
            print("✗ Ontologies are NOT equivalent")
        
        print()
        print(f"Classes: {comparison['classes']['count1']} vs {comparison['classes']['count2']}")
        if comparison['classes']['only_in_first']:
            print(f"  Only in file 1: {comparison['classes']['only_in_first']}")
        if comparison['classes']['only_in_second']:
            print(f"  Only in file 2: {comparison['classes']['only_in_second']}")
        
        print(f"Datatype Properties: {comparison['datatype_properties']['count1']} vs {comparison['datatype_properties']['count2']}")
        if comparison['datatype_properties']['only_in_first']:
            print(f"  Only in file 1: {comparison['datatype_properties']['only_in_first']}")
        if comparison['datatype_properties']['only_in_second']:
            print(f"  Only in file 2: {comparison['datatype_properties']['only_in_second']}")
        
        print(f"Object Properties: {comparison['object_properties']['count1']} vs {comparison['object_properties']['count2']}")
        if comparison['object_properties']['only_in_first']:
            print(f"  Only in file 1: {comparison['object_properties']['only_in_first']}")
        if comparison['object_properties']['only_in_second']:
            print(f"  Only in file 2: {comparison['object_properties']['only_in_second']}")
        
        if args.verbose:
            print()
            print("Detailed comparison results:")
            serializable = {}
            for key, value in comparison.items():
                if isinstance(value, set):
                    serializable[key] = list(value)
                else:
                    serializable[key] = value
            print(json.dumps(serializable, indent=2))
        
        return 0 if comparison["is_equivalent"] else 1
