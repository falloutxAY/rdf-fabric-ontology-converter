"""
DTDL CLI commands.

This module contains commands for DTDL file operations:
- DTDLValidateCommand: Validate DTDL files
- DTDLConvertCommand: Convert DTDL to Fabric format
- DTDLImportCommand: Import DTDL to Fabric Ontology (validate + convert + upload)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

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


class DTDLValidateCommand(BaseCommand):
    """Command to validate DTDL files."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute DTDL validation."""
        from pathlib import Path
        
        # Import DTDL modules
        try:
            from dtdl.dtdl_parser import DTDLParser, ParseError
            from dtdl.dtdl_validator import DTDLValidator
        except ImportError:
            print("Error: DTDL module not found. Ensure src/dtdl/ exists.")
            return 1
        
        path = Path(args.path)
        parser = DTDLParser()
        validator = DTDLValidator()
        
        print(f"Validating DTDL at: {path}")
        
        try:
            if path.is_file():
                result = parser.parse_file(str(path))
            elif path.is_dir():
                recursive = getattr(args, 'recursive', False)
                result = parser.parse_directory(str(path), recursive=recursive)
            else:
                print(f"Error: Path does not exist: {path}")
                return 2
        except ParseError as e:
            print(f"Parse error: {e}")
            return 2
        except Exception as e:
            print(f"Unexpected error parsing: {e}")
            return 2
        
        if result.errors:
            print(f"Found {len(result.errors)} parse errors:")
            for error in result.errors[:10]:
                print(f"  - {error}")
            if not getattr(args, 'continue_on_error', False):
                return 2
        
        print(f"Parsed {len(result.interfaces)} interfaces")
        
        # Validate
        validation_result = validator.validate(result.interfaces)
        
        # Build report data
        report_data = {
            "path": str(path),
            "interfaces_parsed": len(result.interfaces),
            "parse_errors": result.errors,
            "validation_errors": [
                {"level": e.level.value, "element_id": e.element_id, "message": e.message}
                for e in validation_result.errors
            ],
            "validation_warnings": [
                {"level": w.level.value, "element_id": w.element_id, "message": w.message}
                for w in validation_result.warnings
            ],
            "is_valid": len(validation_result.errors) == 0,
            "interfaces": [
                {
                    "name": i.name,
                    "dtmi": i.dtmi,
                    "properties": len(i.properties),
                    "telemetries": len(i.telemetries),
                    "relationships": len(i.relationships),
                    "commands": len(i.commands),
                    "components": len(i.components),
                }
                for i in result.interfaces
            ]
        }
        
        if validation_result.errors:
            print(f"Found {len(validation_result.errors)} validation errors:")
            for error in validation_result.errors[:10]:
                print(f"  - [{error.level.value}] {error.element_id}: {error.message}")
            exit_code = 1
        else:
            if validation_result.warnings:
                print(f"Found {len(validation_result.warnings)} warnings:")
                for warning in validation_result.warnings[:10]:
                    print(f"  - {warning.element_id}: {warning.message}")
            
            print("✓ Validation successful!")
            exit_code = 0
        
        if getattr(args, 'verbose', False):
            print("\nInterface Summary:")
            for interface in result.interfaces[:20]:
                print(f"  {interface.name} ({interface.dtmi})")
                print(f"    Properties: {len(interface.properties)}, "
                      f"Telemetries: {len(interface.telemetries)}, "
                      f"Relationships: {len(interface.relationships)}")
        
        # Save report if requested
        output_path = getattr(args, 'output', None)
        save_report = getattr(args, 'save_report', False)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)
            print(f"\nValidation report saved to: {output_path}")
        elif save_report:
            auto_path = f"{path}.validation.json" if path.is_file() else f"{path.name}.validation.json"
            with open(auto_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)
            print(f"\nValidation report saved to: {auto_path}")
        
        return exit_code


class DTDLConvertCommand(BaseCommand):
    """Command to convert DTDL to Fabric format."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute DTDL conversion."""
        from pathlib import Path
        import json
        
        # Import DTDL modules
        try:
            from dtdl.dtdl_parser import DTDLParser
            from dtdl.dtdl_validator import DTDLValidator
            from dtdl.dtdl_converter import DTDLToFabricConverter
        except ImportError:
            print("Error: DTDL module not found. Ensure src/dtdl/ exists.")
            return 1
        
        path = Path(args.path)
        
        # Parse
        print(f"Parsing DTDL files from: {path}")
        parser = DTDLParser()
        
        try:
            if path.is_file():
                result = parser.parse_file(str(path))
            else:
                recursive = getattr(args, 'recursive', False)
                result = parser.parse_directory(str(path), recursive=recursive)
        except Exception as e:
            print(f"Parse error: {e}")
            return 2
        
        if result.errors:
            print(f"Parse errors: {len(result.errors)}")
            return 2
        
        print(f"Parsed {len(result.interfaces)} interfaces")
        
        # Validate
        validator = DTDLValidator()
        validation_result = validator.validate(result.interfaces)
        
        if validation_result.errors:
            print(f"Validation errors: {len(validation_result.errors)}")
            for error in validation_result.errors[:5]:
                print(f"  - {error.message}")
            return 1
        
        # Convert
        converter = DTDLToFabricConverter(
            namespace=getattr(args, 'namespace', 'usertypes'),
            flatten_components=getattr(args, 'flatten_components', False),
        )
        
        conversion_result = converter.convert(result.interfaces)
        ontology_name = getattr(args, 'ontology_name', None) or path.stem
        definition = converter.to_fabric_definition(conversion_result, ontology_name)
        
        # Save output
        output_path = Path(getattr(args, 'output', None) or f"{ontology_name}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)
        
        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        print(f"  Output: {output_path}")
        
        # Save mapping if requested
        if getattr(args, 'save_mapping', False):
            mapping_path = output_path.with_suffix('.mapping.json')
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(converter.get_dtmi_mapping(), f, indent=2)
            print(f"  DTMI mapping: {mapping_path}")
        
        return 0


class DTDLImportCommand(BaseCommand):
    """Command to import DTDL to Fabric Ontology (validate + convert + upload)."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute DTDL import pipeline."""
        from pathlib import Path
        import json
        
        # Import DTDL modules
        try:
            from dtdl.dtdl_parser import DTDLParser
            from dtdl.dtdl_validator import DTDLValidator
            from dtdl.dtdl_converter import DTDLToFabricConverter
        except ImportError:
            print("Error: DTDL module not found. Ensure src/dtdl/ exists.")
            return 1
        
        path = Path(args.path)
        ontology_name = getattr(args, 'ontology_name', None) or path.stem
        
        print(f"=== DTDL Import: {path} ===")
        
        # Step 1: Parse
        print("\nStep 1: Parsing DTDL files...")
        parser = DTDLParser()
        
        try:
            if path.is_file():
                result = parser.parse_file(str(path))
            else:
                recursive = getattr(args, 'recursive', False)
                result = parser.parse_directory(str(path), recursive=recursive)
        except Exception as e:
            print(f"  ✗ Parse error: {e}")
            return 2
        
        if result.errors:
            print(f"  ✗ Parse errors: {len(result.errors)}")
            for error in result.errors[:5]:
                print(f"    - {error}")
            return 2
        
        print(f"  ✓ Parsed {len(result.interfaces)} interfaces")
        
        # Step 2: Validate
        print("\nStep 2: Validating...")
        validator = DTDLValidator()
        validation_result = validator.validate(result.interfaces)
        
        if validation_result.errors:
            print(f"  ✗ Validation errors: {len(validation_result.errors)}")
            for error in validation_result.errors[:5]:
                print(f"    - {error.message}")
            return 1
        
        print("  ✓ Validation passed")
        
        # Step 3: Convert
        print("\nStep 3: Converting to Fabric format...")
        converter = DTDLToFabricConverter(
            namespace=getattr(args, 'namespace', 'usertypes'),
            flatten_components=getattr(args, 'flatten_components', False),
        )
        
        conversion_result = converter.convert(result.interfaces)
        definition = converter.to_fabric_definition(conversion_result, ontology_name)
        
        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        
        # Step 4: Upload (or dry-run)
        if getattr(args, 'dry_run', False):
            print("\nStep 4: Dry run - saving to file...")
            output_path = Path(getattr(args, 'output', None) or f"{ontology_name}_fabric.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(definition, f, indent=2)
            print(f"  ✓ Definition saved to: {output_path}")
        else:
            print("\nStep 4: Uploading to Fabric...")
            
            try:
                from fabric_client import FabricOntologyClient, FabricConfig
            except ImportError:
                print("  ✗ Could not import FabricOntologyClient")
                return 1
            
            # Load config
            config_path = getattr(args, 'config', None) or str(Path(__file__).parent.parent.parent / "config.json")
            try:
                config = FabricConfig.from_file(config_path)
            except FileNotFoundError:
                print(f"  ✗ Config file not found: {config_path}")
                return 1
            except Exception as e:
                print(f"  ✗ Error loading config: {e}")
                return 1
            
            client = FabricOntologyClient(config)
            
            try:
                result = client.create_ontology(
                    display_name=ontology_name,
                    description=f"Imported from DTDL: {path.name}",
                    definition=definition
                )
                ontology_id = result.get('id') if isinstance(result, dict) else result
                print(f"  ✓ Upload successful! Ontology ID: {ontology_id}")
            except Exception as e:
                print(f"  ✗ Upload failed: {e}")
                return 1
        
        print("\n=== Import complete ===")
        return 0
