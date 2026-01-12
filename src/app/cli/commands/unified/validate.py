"""
Unified validate command supporting both RDF and DTDL formats.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseCommand
from ...format import Format
from ...helpers import setup_logging


logger = logging.getLogger(__name__)


class ValidateCommand(BaseCommand):
    """
    Unified validate command supporting both RDF and DTDL formats.
    
    Usage:
        validate --format rdf <path> [options]
        validate --format dtdl <path> [options]
    """

    RDF_BATCH_EXTENSIONS: List[str] = [
        ".ttl", ".rdf", ".owl", ".nt", ".n3", ".xml", ".trig",
        ".nq", ".nquads", ".trix", ".hext", ".jsonld",
        ".html", ".xhtml", ".htm",
    ]
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute validation based on the specified format."""
        fmt = Format(args.format)
        
        if fmt == Format.RDF:
            return self._validate_rdf(args)
        elif fmt == Format.DTDL:
            return self._validate_dtdl(args)
        elif fmt == Format.CDM:
            return self._validate_cdm(args)
        else:
            print(f"✗ Unsupported format: {fmt}")
            return 1
    
    def _validate_rdf(
        self,
        args: argparse.Namespace,
        *,
        rdf_format_override: Optional[str] = None,
        format_label: str = "RDF",
        directory_extensions: Optional[List[str]] = None,
    ) -> int:
        """Delegate to RDF/JSON-LD validation logic."""
        from src.rdf import InputValidator, PreflightValidator, RDFGraphParser

        self.setup_logging_from_config()
        label = format_label or "RDF"
        allow_up = getattr(args, 'allow_relative_up', False)
        force = getattr(args, 'force', False)

        def _validate_file(file_path: Path, report_target: Optional[Path]) -> int:
            try:
                validated_str = InputValidator.validate_input_ttl_path(
                    str(file_path),
                    allow_relative_up=allow_up,
                )
                validated_path = Path(validated_str)
            except (ValueError, FileNotFoundError, PermissionError) as exc:
                print(f"✗ {exc}")
                return 1

            try:
                with open(validated_path, 'r', encoding='utf-8') as handle:
                    ttl_content = handle.read()
            except OSError as exc:
                print(f"✗ Error reading file: {exc}")
                return 1

            if not ttl_content.strip():
                print(f"✗ File is empty: {validated_path}")
                return 1

            format_hint = rdf_format_override or RDFGraphParser.infer_format_from_path(validated_path)
            validator = PreflightValidator()
            report = validator.validate(
                ttl_content,
                file_path=str(validated_path),
                rdf_format=format_hint,
                source_path=str(validated_path),
            )

            print(report.get_human_readable_summary())

            if report_target:
                report_target.parent.mkdir(parents=True, exist_ok=True)
                with open(report_target, 'w', encoding='utf-8') as handle:
                    json.dump(report.to_dict(), handle, indent=2)
                print(f"Report saved to: {report_target}")

            errors = report.issues_by_severity.get('error', 0)
            warnings = report.issues_by_severity.get('warning', 0)

            if errors:
                if force:
                    print("⚠ Validation completed with errors (forced to continue).")
                    return 0
                print("✗ Validation completed with errors.")
                return 1

            if warnings:
                print("⚠ Validation completed with warnings.")
            else:
                print("✓ Validation successful!")

            return 0

        path = Path(args.path)
        extensions = directory_extensions or self.RDF_BATCH_EXTENSIONS

        if path.is_dir():
            if not getattr(args, 'recursive', False):
                print(f"✗ '{path}' is a directory. Use --recursive to process all files.")
                return 1

            files = set()
            for ext in extensions:
                pattern = f"**/*{ext}" if args.recursive else f"*{ext}"
                files.update(path.glob(pattern))
            files = sorted(files)

            if not files:
                print(f"✗ No {label} files found in '{path}'")
                return 1

            output_dir: Optional[Path] = None
            if args.output:
                output_dir = Path(args.output)
                output_dir.mkdir(parents=True, exist_ok=True)

            failures = 0
            for file_path in files:
                print(f"\n--- Validating {file_path} ---")
                target = None
                if output_dir:
                    target = output_dir / f"{file_path.stem}.validation.json"
                elif args.save_report:
                    target = Path(f"{file_path}.validation.json")
                result = _validate_file(Path(file_path), target)
                if result != 0:
                    failures += 1

            if failures:
                print(f"\n✗ {failures} file(s) failed validation.")
                return 1

            print(f"\n✓ All {len(files)} {label} file(s) validated.")
            return 0

        report_target: Optional[Path] = None
        if args.output:
            report_target = Path(args.output)
        elif args.save_report:
            report_target = Path(f"{path}.validation.json")

        return _validate_file(path, report_target)

    def _validate_dtdl(self, args: argparse.Namespace) -> int:
        """Validate DTDL models."""
        try:
            from dtdl.dtdl_parser import DTDLParser, ParseError
            from dtdl.dtdl_validator import DTDLValidator
        except ImportError as exc:
            print(f"✗ DTDL modules not available: {exc}")
            return 1

        path = Path(args.path)
        parser = DTDLParser()
        validator = DTDLValidator()

        try:
            if path.is_file():
                result = parser.parse_file(str(path))
            elif path.is_dir():
                recursive = getattr(args, 'recursive', False)
                result = parser.parse_directory(str(path), recursive=recursive)
            else:
                print(f"✗ Path does not exist: {path}")
                return 2
        except ParseError as exc:
            print(f"✗ Parse error: {exc}")
            return 2
        except Exception as exc:
            print(f"✗ Unexpected error: {exc}")
            return 2

        if result.errors:
            print(f"Found {len(result.errors)} parse errors:")
            for err in result.errors[:10]:
                print(f"  - {err}")
            if not getattr(args, 'continue_on_error', False):
                return 2

        print(f"Parsed {len(result.interfaces)} interfaces")

        validation_result = validator.validate(result.interfaces)

        report_data = {
            "path": str(path),
            "interfaces_parsed": len(result.interfaces),
            "parse_errors": result.errors,
            "validation_errors": [
                {"level": e.level.value, "dtmi": e.dtmi, "message": e.message}
                for e in validation_result.errors
            ],
            "validation_warnings": [
                {"level": w.level.value, "dtmi": w.dtmi, "message": w.message}
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
            ],
        }

        if validation_result.errors:
            print(f"Found {len(validation_result.errors)} validation errors:")
            for err in validation_result.errors[:10]:
                print(f"  - [{err.level.value}] {err.dtmi or 'unknown'}: {err.message}")
            exit_code = 1
        else:
            if validation_result.warnings:
                print(f"Found {len(validation_result.warnings)} warnings:")
                for warn in validation_result.warnings[:10]:
                    print(f"  - {warn.dtmi or 'unknown'}: {warn.message}")
            print("✓ Validation successful!")
            exit_code = 0

        if getattr(args, 'verbose', False):
            print("\nInterface Summary:")
            for iface in result.interfaces[:20]:
                print(f"  {iface.name} ({iface.dtmi})")
                print(
                    f"    Props: {len(iface.properties)}, Telemetry: {len(iface.telemetries)}, "
                    f"Rels: {len(iface.relationships)}"
                )

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as handle:
                json.dump(report_data, handle, indent=2)
            print(f"\nReport saved to: {args.output}")
        elif args.save_report:
            auto_path = f"{path}.validation.json" if path.is_file() else f"{path.name}.validation.json"
            with open(auto_path, 'w', encoding='utf-8') as handle:
                json.dump(report_data, handle, indent=2)
            print(f"\nReport saved to: {auto_path}")

        return exit_code

    def _validate_cdm(self, args: argparse.Namespace) -> int:
        """Validate CDM manifest and entity files."""
        try:
            from src.formats.cdm import CDMParser, CDMValidator
            from src.shared.utilities.validation import Severity
        except ImportError as exc:
            print(f"✗ CDM modules not available: {exc}")
            return 1

        path = Path(args.path)

        if not path.exists():
            print(f"✗ Path does not exist: {path}")
            return 2

        parser = CDMParser()
        validator = CDMValidator()

        try:
            if path.is_file():
                manifest = parser.parse_file(str(path))
            elif path.is_dir():
                # Look for manifest files in directory
                manifest_files = list(path.glob("*.manifest.cdm.json")) + list(path.glob("model.json"))
                if not manifest_files:
                    print(f"✗ No CDM manifest files found in '{path}'")
                    return 2
                # Parse first manifest found
                manifest = parser.parse_file(str(manifest_files[0]))
                print(f"Using manifest: {manifest_files[0].name}")
            else:
                print(f"✗ Path does not exist: {path}")
                return 2
        except Exception as exc:
            print(f"✗ Parse error: {exc}")
            return 2

        print(f"Parsed CDM manifest: {manifest.name}")
        print(f"  Entities: {len(manifest.entities)}")

        # Use validate_manifest for pre-parsed manifest objects
        validation_result = validator.validate_manifest(manifest)

        # Get errors and warnings using the proper interface
        errors = validation_result.get_issues_by_severity(Severity.ERROR)
        warnings = validation_result.get_issues_by_severity(Severity.WARNING)

        report_data = {
            "path": str(path),
            "manifest_name": manifest.name,
            "entities_parsed": len(manifest.entities),
            "validation_errors": [
                {"severity": str(e.severity.value), "code": str(e.category.value), "message": e.message}
                for e in errors
            ],
            "validation_warnings": [
                {"severity": str(w.severity.value), "code": str(w.category.value), "message": w.message}
                for w in warnings
            ],
            "is_valid": validation_result.is_valid,
            "entities": [
                {
                    "name": e.name,
                    "attributes": len(e.attributes),
                }
                for e in manifest.entities
            ],
        }

        if errors:
            print(f"Found {len(errors)} validation errors:")
            for err in errors[:10]:
                print(f"  - [{err.severity.value}] {err.category.value}: {err.message}")
            exit_code = 1
        else:
            if warnings:
                print(f"Found {len(warnings)} warnings:")
                for warn in warnings[:10]:
                    print(f"  - {warn.category.value}: {warn.message}")
            print("✓ Validation successful!")
            exit_code = 0

        if getattr(args, 'verbose', False):
            print("\nEntity Summary:")
            for entity in manifest.entities[:20]:
                print(f"  {entity.name}")
                print(f"    Attributes: {len(entity.attributes)}")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as handle:
                json.dump(report_data, handle, indent=2)
            print(f"\nReport saved to: {args.output}")
        elif getattr(args, 'save_report', False):
            auto_path = f"{path}.validation.json" if path.is_file() else f"{path.name}.validation.json"
            with open(auto_path, 'w', encoding='utf-8') as handle:
                json.dump(report_data, handle, indent=2)
            print(f"\nReport saved to: {auto_path}")

        return exit_code
