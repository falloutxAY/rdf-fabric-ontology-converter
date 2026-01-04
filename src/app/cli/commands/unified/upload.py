"""
Unified upload command supporting both RDF and DTDL formats.
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseCommand, print_conversion_summary
from ...format import Format
from ...helpers import (
    load_config,
    get_default_config_path,
    setup_logging,
    print_header,
    print_footer,
    confirm_action,
    resolve_dtdl_converter_modes,
)


logger = logging.getLogger(__name__)


def _get_dtdl_converter_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    """Build consistent kwargs for DTDL converter configuration."""
    namespace = getattr(args, 'namespace', 'usertypes')
    component_mode, command_mode = resolve_dtdl_converter_modes(args)
    return {
        "namespace": namespace,
        "component_mode": component_mode,
        "command_mode": command_mode,
    }


class UploadCommand(BaseCommand):
    """
    Unified upload command supporting both RDF and DTDL formats.
    
    Usage:
        upload --format rdf <path> [options]
        upload --format dtdl <path> [options]
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute upload based on the specified format."""
        fmt = Format(args.format)
        
        if fmt == Format.RDF:
            return self._upload_rdf(args)
        elif fmt == Format.DTDL:
            return self._upload_dtdl(args)
        else:
            print(f"✗ Unsupported format: {fmt}")
            return 1
    
    def _upload_rdf(
        self,
        args: argparse.Namespace,
        *,
        rdf_format_override: Optional[str] = None,
        format_label: str = "RDF",
        directory_extensions: Optional[List[str]] = None,
    ) -> int:
        """Delegate to RDF/JSON-LD upload logic."""
        from rdf import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter, validate_ttl_content, IssueSeverity,
            RDFGraphParser,
        )
        from core import FabricConfig, FabricOntologyClient, FabricAPIError
        from core import setup_cancellation_handler, restore_default_handler, OperationCancelledException
        
        cancellation_token = setup_cancellation_handler(message="\n⚠️  Cancellation requested...")
        
        try:
            config_path = args.config or get_default_config_path()
            try:
                config_data = load_config(config_path)
            except Exception as e:
                print(f"✗ {e}")
                return 1
            
            fabric_config = FabricConfig.from_dict(config_data)
            if not fabric_config.workspace_id or fabric_config.workspace_id == "YOUR_WORKSPACE_ID":
                print("✗ Please configure workspace_id in config.json")
                return 1
            
            setup_logging(config=config_data.get('logging', {}))
            
            label = format_label or "RDF"
            path = Path(args.path)
            
            if path.is_dir():
                if not getattr(args, 'recursive', False):
                    print(f"✗ '{path}' is a directory. Use --recursive.")
                    return 1
                return self._upload_rdf_batch(
                    args,
                    path,
                    config_data,
                    fabric_config,
                    rdf_format_override=rdf_format_override,
                    format_label=label,
                    extensions=directory_extensions,
                )
            
            try:
                allow_up = getattr(args, 'allow_relative_up', False)
                validated_path = InputValidator.validate_input_ttl_path(str(path), allow_relative_up=allow_up)
            except (ValueError, FileNotFoundError, PermissionError) as e:
                print(f"✗ {e}")
                return 1
            format_hint = rdf_format_override or RDFGraphParser.infer_format_from_path(validated_path)
            
            with open(validated_path, 'r', encoding='utf-8') as f:
                ttl_content = f.read()
            
            if not ttl_content.strip():
                print(f"✗ File is empty: {path}")
                return 1
            
            # Pre-flight validation
            validation_report = None
            if not args.skip_validation:
                print_header("PRE-FLIGHT VALIDATION")
                validation_report = validate_ttl_content(
                    ttl_content,
                    str(path),
                    rdf_format=format_hint,
                )
                if validation_report.can_import_seamlessly:
                    print("✓ Ontology can be imported seamlessly.")
                else:
                    print(f"⚠ Issues detected: {validation_report.total_issues}")
                    if not args.force:
                        if not confirm_action("Proceed anyway?"):
                            print("Upload cancelled.")
                            return 0
                print_footer()
            
            # Convert
            id_prefix = config_data.get('ontology', {}).get('id_prefix', 1000000000000)
            force_memory = getattr(args, 'force_memory', False)
            use_streaming = getattr(args, 'streaming', False)
            
            if use_streaming:
                definition, extracted_name, conversion_result = parse_ttl_streaming(
                    str(validated_path),
                    id_prefix=id_prefix,
                    cancellation_token=cancellation_token,
                    rdf_format=format_hint,
                )
            else:
                definition, extracted_name, conversion_result = parse_ttl_with_result(
                    ttl_content,
                    id_prefix,
                    force_large_file=force_memory,
                    rdf_format=format_hint,
                    source_path=str(validated_path),
                )
            
            print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
            
            if conversion_result.has_skipped_items and not args.force:
                print("⚠ Some items were skipped.")
                if not confirm_action("Proceed with upload?"):
                    print("Upload cancelled.")
                    return 0
            
            # Dry-run check
            if args.dry_run:
                output_path = args.output or f"{extracted_name or 'output'}_fabric.json"
                output = {
                    "displayName": args.ontology_name or extracted_name,
                    "description": args.description or f"Converted from {path.name}",
                    "definition": definition,
                }
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2)
                print(f"\n✓ Dry-run: saved to {output_path}")
                return 0
            
            # Upload
            ontology_name = args.ontology_name or extracted_name
            description = args.description or f"Imported from {os.path.basename(str(path))}"
            
            client = FabricOntologyClient(fabric_config)
            
            try:
                result = client.create_or_update_ontology(
                    display_name=ontology_name,
                    description=description,
                    definition=definition,
                    wait_for_completion=True,
                    cancellation_token=cancellation_token,
                )
                print(f"✓ Successfully uploaded '{ontology_name}'")
                print(f"  Ontology ID: {result.get('id', 'Unknown')}")
                return 0
            except FabricAPIError as e:
                print(f"✗ Fabric API error: {e.message}")
                if e.error_code == "ItemDisplayNameAlreadyInUse":
                    print("  Hint: Use --update to update existing ontology.")
                return 1
        
        except OperationCancelledException:
            print("\n✗ Upload cancelled.")
            return 130
        finally:
            restore_default_handler()
    
    def _upload_rdf_batch(
        self,
        args: argparse.Namespace,
        directory: Path,
        config_data: dict,
        fabric_config,
        *,
        rdf_format_override: Optional[str] = None,
        format_label: str = "RDF",
        extensions: Optional[List[str]] = None,
    ) -> int:
        """Upload all RDF/JSON-LD files in a directory."""
        from rdf import InputValidator, parse_ttl_with_result, RDFGraphParser
        from core import FabricOntologyClient
        
        ext_list = extensions or getattr(InputValidator, 'TTL_EXTENSIONS', ['.ttl'])
        files = set()
        for ext in ext_list:
            pattern = f"**/*{ext}" if args.recursive else f"*{ext}"
            files.update(directory.glob(pattern))
        files = sorted(files)
        
        if not files:
            print(f"✗ No RDF files found in '{directory}'")
            return 1
        
        print(f"Found {len(files)} {format_label} file(s) to upload\n")
        
        if not args.force:
            if not confirm_action(f"Upload {len(files)} files to Fabric?"):
                print("Upload cancelled.")
                return 0
        
        successes, failures = [], []
        id_prefix = config_data.get('ontology', {}).get('id_prefix', 1000000000000)
        client = FabricOntologyClient(fabric_config)
        
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {f.name}")
            try:
                validated_path = InputValidator.validate_input_ttl_path(str(f))
                with open(validated_path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                format_hint = rdf_format_override or RDFGraphParser.infer_format_from_path(validated_path)
                definition, extracted_name, _ = parse_ttl_with_result(
                    content,
                    id_prefix,
                    rdf_format=format_hint,
                    source_path=str(validated_path),
                )
                ontology_name = args.ontology_name or extracted_name or f.stem
                description = args.description or f"Batch imported from {f.name}"
                result = client.create_or_update_ontology(
                    display_name=ontology_name,
                    description=description,
                    definition=definition,
                    wait_for_completion=True,
                )
                successes.append(str(f))
                print(f"  ✓ ID: {result.get('id', 'N/A')}")
            except Exception as e:
                failures.append((str(f), str(e)))
                print(f"  ✗ {e}")
        
        print(f"\n{'='*60}")
        print(f"BATCH UPLOAD SUMMARY ({format_label})")
        print(f"{'='*60}")
        print(f"Total: {len(files)}, Successful: {len(successes)}, Failed: {len(failures)}")
        
        return 0 if not failures else 1
    
    def _upload_dtdl(self, args: argparse.Namespace) -> int:
        """Delegate to DTDL upload logic."""
        try:
            from dtdl.dtdl_parser import DTDLParser
            from dtdl.dtdl_validator import DTDLValidator
            from dtdl.dtdl_converter import DTDLToFabricConverter
        except ImportError:
            print("✗ DTDL module not found.")
            return 1
        
        path = Path(args.path)
        ontology_name = args.ontology_name or path.stem
        use_streaming = getattr(args, 'streaming', False)
        force_memory = getattr(args, 'force_memory', False)

        if path.is_file():
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > 100 and not use_streaming and not force_memory:
                print(f"⚠️  Large file detected ({file_size_mb:.1f} MB). Consider using --streaming.")

        if use_streaming:
            return self._upload_dtdl_streaming(args, path, ontology_name)
        
        print(f"=== DTDL Upload: {path} ===")
        
        # Parse
        print("\nStep 1: Parsing...")
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
            return 2
        
        print(f"  ✓ Parsed {len(result.interfaces)} interfaces")
        
        # Validate
        print("\nStep 2: Validating...")
        validator = DTDLValidator()
        validation_result = validator.validate(result.interfaces)
        
        if validation_result.errors:
            print(f"  ✗ Validation errors: {len(validation_result.errors)}")
            if not args.force:
                return 1
        
        print("  ✓ Validation passed")
        
        # Convert
        print("\nStep 3: Converting...")
        converter = DTDLToFabricConverter(**_get_dtdl_converter_kwargs(args))
        
        conversion_result = converter.convert(result.interfaces)
        definition = converter.to_fabric_definition(conversion_result, ontology_name)
        
        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        
        # Dry-run or upload
        if args.dry_run:
            print("\nStep 4: Dry run - saving to file...")
            output_path = Path(args.output or f"{ontology_name}_fabric.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(definition, f, indent=2)
            print(f"  ✓ Saved to: {output_path}")
        else:
            print("\nStep 4: Uploading...")
            
            try:
                from core import FabricOntologyClient, FabricConfig
            except ImportError:
                print("  ✗ Could not import FabricOntologyClient")
                return 1
            
            config_path = args.config or get_default_config_path()
            try:
                config = FabricConfig.from_file(config_path)
            except Exception as e:
                print(f"  ✗ Config error: {e}")
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
        
        print("\n=== Upload complete ===")
        return 0

    def _upload_dtdl_streaming(
        self,
        args: argparse.Namespace,
        path: Path,
        ontology_name: str
    ) -> int:
        """Upload DTDL models using streaming conversion."""
        try:
            from core.streaming import DTDLStreamAdapter, StreamConfig
        except ImportError:
            print("✗ Streaming module not available.")
            return 1

        converter_kwargs = _get_dtdl_converter_kwargs(args)
        config = StreamConfig(chunk_size=10000, memory_threshold_mb=100.0, enable_progress=True)
        adapter = DTDLStreamAdapter(
            config=config,
            ontology_name=ontology_name,
            namespace=converter_kwargs["namespace"],
            component_mode=converter_kwargs["component_mode"],
            command_mode=converter_kwargs["command_mode"],
        )

        def progress(n: int) -> None:
            if n % 1000 == 0:
                print(f"  Processed {n:,} items...")

        try:
            result = adapter.convert_streaming(
                str(path),
                progress_callback=progress,
            )
        except Exception as exc:
            print(f"✗ Streaming error: {exc}")
            return 1

        if not result.success:
            error_message = result.error_message or "unknown error"
            print(f"✗ Streaming failed: {error_message}")
            return 1

        payload = result.data or {}
        definition = payload.get("definition")
        conversion_result = payload.get("conversion_result")

        if definition is None:
            print("✗ Streaming adapter did not return a Fabric definition.")
            return 1

        if conversion_result is not None:
            print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")

        print(result.stats.get_summary())

        if args.dry_run:
            print("\nDry run - saving to file...")
            output_path = Path(args.output or f"{ontology_name}_fabric.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(definition, f, indent=2)
            print(f"  ✓ Saved to: {output_path}")
            return 0

        print("\nUploading to Fabric...")

        try:
            from core import FabricOntologyClient, FabricConfig
        except ImportError:
            print("  ✗ Could not import FabricOntologyClient")
            return 1

        config_path = args.config or get_default_config_path()
        try:
            config = FabricConfig.from_file(config_path)
        except Exception as exc:
            print(f"  ✗ Config error: {exc}")
            return 1

        client = FabricOntologyClient(config)

        try:
            result = client.create_ontology(
                display_name=ontology_name,
                description=f"Imported from DTDL: {path.name}",
                definition=definition,
            )
            ontology_id = result.get('id') if isinstance(result, dict) else result
            print(f"  ✓ Upload successful! Ontology ID: {ontology_id}")
        except Exception as exc:
            print(f"  ✗ Upload failed: {exc}")
            return 1

        print("\n=== Upload complete ===")
        return 0
