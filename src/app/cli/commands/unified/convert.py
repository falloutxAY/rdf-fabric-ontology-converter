"""
Unified convert command supporting both RDF and DTDL formats.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseCommand, print_conversion_summary
from ...format import Format
from ...helpers import resolve_dtdl_converter_modes


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


class ConvertCommand(BaseCommand):
    """
    Unified convert command supporting both RDF and DTDL formats.
    
    Usage:
        convert --format rdf <path> [options]
        convert --format dtdl <path> [options]
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute conversion based on the specified format."""
        fmt = Format(args.format)
        
        if fmt == Format.RDF:
            return self._convert_rdf(args)
        elif fmt == Format.DTDL:
            return self._convert_dtdl(args)
        elif fmt == Format.CDM:
            return self._convert_cdm(args)
        else:
            print(f"✗ Unsupported format: {fmt}")
            return 1
    
    def _convert_rdf(
        self,
        args: argparse.Namespace,
        *,
        rdf_format_override: Optional[str] = None,
        format_label: str = "RDF",
        directory_extensions: Optional[List[str]] = None,
    ) -> int:
        """Delegate to RDF/JSON-LD conversion logic."""
        from src.rdf import (
            InputValidator,
            parse_ttl_with_result,
            parse_ttl_streaming,
            StreamingRDFConverter,
            RDFGraphParser,
        )
        
        self.setup_logging_from_config()
        label = format_label or "RDF"
        
        path = Path(args.path)
        
        if path.is_dir():
            if not getattr(args, 'recursive', False):
                print(f"✗ '{path}' is a directory. Use --recursive to process all files.")
                return 1
            return self._convert_rdf_batch(
                args,
                path,
                rdf_format_override=rdf_format_override,
                format_label=label,
                extensions=directory_extensions,
            )
        
        try:
            allow_up = getattr(args, 'allow_relative_up', False)
            validated_path = InputValidator.validate_input_ttl_path(str(path), allow_relative_up=allow_up)
        except (ValueError, FileNotFoundError, PermissionError) as e:
            print(f"✗ Invalid file path: {e}")
            return 1
        
        print(f"✓ Converting {label} file: {validated_path}")

        format_hint = rdf_format_override or RDFGraphParser.infer_format_from_path(validated_path)
        
        force_memory = getattr(args, 'force_memory', False)
        use_streaming = getattr(args, 'streaming', False)
        
        file_size_mb = validated_path.stat().st_size / (1024 * 1024)
        if file_size_mb > StreamingRDFConverter.STREAMING_THRESHOLD_MB and not use_streaming:
            print(f"⚠️  Large file ({file_size_mb:.1f} MB). Consider using --streaming.")
        
        try:
            if use_streaming:
                print("Using streaming mode...")
                definition, ontology_name, conversion_result = parse_ttl_streaming(
                    str(validated_path),
                    rdf_format=format_hint,
                )
            else:
                with open(validated_path, 'r', encoding='utf-8') as f:
                    ttl_content = f.read()
                definition, ontology_name, conversion_result = parse_ttl_with_result(
                    ttl_content,
                    force_large_file=force_memory,
                    rdf_format=format_hint,
                    source_path=str(validated_path),
                )
        except ValueError as e:
            print(f"✗ Invalid RDF content: {e}")
            return 1
        except MemoryError as e:
            print(f"✗ {e}\n\nTip: Use --streaming for large files.")
            return 1
        except Exception as e:
            print(f"✗ Error parsing file: {e}")
            return 1
        
        print("\n" + conversion_result.get_summary())
        
        output = {
            "displayName": args.ontology_name or ontology_name,
            "description": args.description or f"Converted from {validated_path.name}",
            "definition": definition,
            "conversionResult": conversion_result.to_dict()
        }
        
        output_path = args.output or str(validated_path.with_suffix('.json'))
        
        try:
            validated_output = InputValidator.validate_output_file_path(output_path, allowed_extensions=['.json'])
            with open(validated_output, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
        except Exception as e:
            print(f"✗ Error writing output: {e}")
            return 1
        
        print(f"\nSaved to: {validated_output}")
        return 0
    
    def _convert_rdf_batch(
        self,
        args: argparse.Namespace,
        directory: Path,
        *,
        rdf_format_override: Optional[str] = None,
        format_label: str = "RDF",
        extensions: Optional[List[str]] = None,
    ) -> int:
        """Convert all RDF/JSON-LD files in a directory."""
        from src.rdf import InputValidator, parse_ttl_with_result, RDFGraphParser
        
        ext_list = extensions or getattr(InputValidator, 'TTL_EXTENSIONS', ['.ttl'])
        files = set()
        for ext in ext_list:
            pattern = f"**/*{ext}" if args.recursive else f"*{ext}"
            files.update(directory.glob(pattern))
        files = sorted(files)
        
        if not files:
            print(f"✗ No RDF files found in '{directory}'")
            return 1
        
        print(f"Found {len(files)} {format_label} file(s) to convert\n")
        
        successes, failures = [], []
        output_dir = Path(args.output) if args.output else directory
        if args.output:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {f.name}")
            try:
                validated_path = InputValidator.validate_input_ttl_path(str(f))
                with open(validated_path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                format_hint = rdf_format_override or RDFGraphParser.infer_format_from_path(validated_path)
                definition, ontology_name, conversion_result = parse_ttl_with_result(
                    content,
                    rdf_format=format_hint,
                    source_path=str(validated_path),
                )
                output = {
                    "displayName": ontology_name,
                    "description": f"Converted from {f.name}",
                    "definition": definition,
                    "conversionResult": conversion_result.to_dict()
                }
                output_file = output_dir / f"{f.stem}.json"
                with open(output_file, 'w', encoding='utf-8') as fp:
                    json.dump(output, fp, indent=2)
                successes.append(str(f))
                print(f"  ✓ {output_file}")
            except Exception as e:
                failures.append((str(f), str(e)))
                print(f"  ✗ {e}")
        
        print(f"\n{'='*60}")
        print(f"BATCH CONVERSION SUMMARY ({format_label})")
        print(f"{'='*60}")
        print(f"Total: {len(files)}, Successful: {len(successes)}, Failed: {len(failures)}")
        
        return 0 if not failures else 1
    
    def _convert_dtdl(self, args: argparse.Namespace) -> int:
        """Delegate to DTDL conversion logic."""
        try:
            from dtdl.dtdl_parser import DTDLParser
            from dtdl.dtdl_validator import DTDLValidator
            from dtdl.dtdl_converter import DTDLToFabricConverter
        except ImportError:
            print("✗ DTDL module not found.")
            return 1
        
        path = Path(args.path)
        use_streaming = getattr(args, 'streaming', False)
        
        if use_streaming:
            return self._convert_dtdl_streaming(args, path)
        
        print(f"Parsing DTDL from: {path}")
        parser = DTDLParser()
        
        try:
            if path.is_file():
                result = parser.parse_file(str(path))
            else:
                recursive = getattr(args, 'recursive', False)
                result = parser.parse_directory(str(path), recursive=recursive)
        except Exception as e:
            print(f"✗ Parse error: {e}")
            return 2
        
        if result.errors:
            print(f"✗ Parse errors: {len(result.errors)}")
            return 2
        
        print(f"Parsed {len(result.interfaces)} interfaces")
        
        validator = DTDLValidator()
        validation_result = validator.validate(result.interfaces)
        
        if validation_result.errors:
            print(f"✗ Validation errors: {len(validation_result.errors)}")
            for err in validation_result.errors[:5]:
                print(f"  - {err.message}")
            return 1
        
        converter = DTDLToFabricConverter(**_get_dtdl_converter_kwargs(args))
        
        conversion_result = converter.convert(result.interfaces)
        ontology_name = args.ontology_name or path.stem
        definition = converter.to_fabric_definition(conversion_result, ontology_name)
        
        output_path = Path(args.output or f"{ontology_name}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)
        
        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        print(f"  Output: {output_path}")
        
        if getattr(args, 'save_mapping', False):
            mapping_path = output_path.with_suffix('.mapping.json')
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(converter.get_dtmi_mapping(), f, indent=2)
            print(f"  DTMI mapping: {mapping_path}")
        
        return 0
    
    def _convert_dtdl_streaming(self, args: argparse.Namespace, path: Path) -> int:
        """Convert DTDL using streaming mode."""
        try:
            from core.streaming import DTDLStreamAdapter, StreamConfig
        except ImportError:
            print("✗ Streaming module not available.")
            return 1
        
        print("Using streaming mode...")

        converter_kwargs = _get_dtdl_converter_kwargs(args)
        ontology_name = args.ontology_name or path.stem
        
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
        except Exception as e:
            print(f"✗ Streaming error: {e}")
            return 1

        if not result.success:
            error_message = result.error_message or "unknown error"
            print(f"✗ Streaming failed: {error_message}")
            return 1

        payload = result.data or {}
        definition = payload.get("definition")
        conversion_result = payload.get("conversion_result")

        if definition is None or conversion_result is None:
            print("✗ Streaming adapter did not return a Fabric definition.")
            return 1

        output_path = Path(args.output or f"{ontology_name}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)

        print("Streaming conversion complete!")
        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        print(result.stats.get_summary())
        print(f"  Output: {output_path}")

        if getattr(args, 'save_mapping', False) and payload.get("dtmi_mapping"):
            mapping_path = output_path.with_suffix('.mapping.json')
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(payload["dtmi_mapping"], f, indent=2)
            print(f"  DTMI mapping: {mapping_path}")

        return 0

    def _convert_cdm(self, args: argparse.Namespace) -> int:
        """Delegate to CDM conversion logic."""
        try:
            from src.formats.cdm import CDMParser, CDMValidator, CDMToFabricConverter
            from src.formats.rdf.rdf_converter import convert_to_fabric_definition
        except ImportError as exc:
            print(f"✗ CDM modules not available: {exc}")
            return 1

        path = Path(args.path)

        if not path.exists():
            print(f"✗ Path does not exist: {path}")
            return 2

        print(f"Parsing CDM from: {path}")
        parser = CDMParser()

        try:
            if path.is_file():
                manifest = parser.parse_file(str(path))
            elif path.is_dir():
                # Look for manifest files in directory
                manifest_files = list(path.glob("*.manifest.cdm.json")) + list(path.glob("model.json"))
                if not manifest_files:
                    print(f"✗ No CDM manifest files found in '{path}'")
                    return 2
                manifest = parser.parse_file(str(manifest_files[0]))
                print(f"Using manifest: {manifest_files[0].name}")
            else:
                print(f"✗ Path does not exist: {path}")
                return 2
        except Exception as e:
            print(f"✗ Parse error: {e}")
            return 2

        print(f"Parsed {len(manifest.entities)} entities")

        # Validate using validate_manifest for pre-parsed objects
        validator = CDMValidator()
        validation_result = validator.validate_manifest(manifest)

        if not validation_result.is_valid:
            print(f"✗ Validation errors: {validation_result.error_count}")
            from src.shared.utilities.validation import Severity
            for err in validation_result.get_issues_by_severity(Severity.ERROR)[:5]:
                print(f"  - {err.message}")
            return 1

        # Convert
        namespace = getattr(args, 'namespace', 'usertypes')
        converter = CDMToFabricConverter(namespace=namespace)

        conversion_result = converter.convert_manifest(manifest)
        ontology_name = args.ontology_name or manifest.name or path.stem

        # Build Fabric definition using the shared function
        definition = convert_to_fabric_definition(
            conversion_result.entity_types,
            conversion_result.relationship_types,
            ontology_name,
            skip_validation=True,  # Already validated via CDMValidator
        )

        output_path = Path(args.output or f"{ontology_name}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)

        print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
        print(f"  Output: {output_path}")

        return 0
