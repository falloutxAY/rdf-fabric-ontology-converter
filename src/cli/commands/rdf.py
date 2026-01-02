"""
RDF/TTL CLI commands.

This module contains commands for RDF/TTL file operations:
- ValidateCommand: Validate a TTL file for Fabric compatibility
- UploadCommand: Upload a TTL file to Fabric Ontology
- ConvertCommand: Convert TTL to Fabric format without uploading
- ExportCommand: Export an ontology from Fabric to TTL format
"""

import argparse
import json
import logging
import os
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


# ============================================================================
# Helper Functions for Batch Processing
# ============================================================================

def find_ttl_files(directory: Path, recursive: bool = False) -> List[Path]:
    """
    Find all TTL files in a directory.
    
    Args:
        directory: Directory to search
        recursive: Whether to search recursively
        
    Returns:
        List of paths to TTL files
    """
    pattern = "**/*.ttl" if recursive else "*.ttl"
    files = list(directory.glob(pattern))
    
    # Also check for .rdf and .owl extensions
    for ext in [".rdf", ".owl"]:
        ext_pattern = f"**/*{ext}" if recursive else f"*{ext}"
        files.extend(directory.glob(ext_pattern))
    
    return sorted(set(files))


def print_batch_progress(current: int, total: int, filename: str) -> None:
    """Print progress for batch operations."""
    print(f"[{current}/{total}] Processing: {filename}")


def print_batch_summary(
    successes: List[str],
    failures: List[Tuple[str, str]],
    operation: str
) -> None:
    """
    Print summary of batch operation results.
    
    Args:
        successes: List of successfully processed files
        failures: List of (filename, error) tuples for failed files
        operation: Name of the operation (e.g., "validate", "convert")
    """
    total = len(successes) + len(failures)
    print(f"\n{'='*60}")
    print(f"BATCH {operation.upper()} SUMMARY")
    print(f"{'='*60}")
    print(f"Total files: {total}")
    print(f"Successful: {len(successes)}")
    print(f"Failed: {len(failures)}")
    
    if failures:
        print(f"\nFailed files:")
        for filename, error in failures:
            print(f"  ✗ {filename}: {error}")
    
    if successes:
        print(f"\nSuccessful files:")
        for filename in successes[:10]:  # Show first 10
            print(f"  ✓ {filename}")
        if len(successes) > 10:
            print(f"  ... and {len(successes) - 10} more")


class ValidateCommand(BaseCommand):
    """Validate a TTL file for Fabric Ontology compatibility."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the validate command."""
        from rdf_converter import InputValidator
        from preflight_validator import validate_ttl_content
        
        self.setup_logging_from_config()
        
        ttl_path = Path(args.ttl_file)
        
        # Check if this is a directory and --recursive is set
        if ttl_path.is_dir():
            if not getattr(args, 'recursive', False):
                print(f"✗ '{ttl_path}' is a directory. Use --recursive to process all TTL files.")
                return 1
            return self._execute_batch_validate(args, ttl_path)
        
        # Single file validation
        return self._execute_single_validate(args)
    
    def _execute_single_validate(self, args: argparse.Namespace) -> int:
        """Execute validation for a single file."""
        from rdf_converter import InputValidator
        from preflight_validator import validate_ttl_content
        
        ttl_file = args.ttl_file
        
        # Validate TTL file path with enhanced error messages
        try:
            allow_up = getattr(args, 'allow_relative_up', False)
            validated_path = InputValidator.validate_input_ttl_path(ttl_file, allow_relative_up=allow_up)
        except ValueError as e:
            err = str(e).lower()
            if "symlink" in err:
                print("✗ Security Error: Symlinks are not allowed")
                print(f"  {e}")
                print("\n  Please provide the actual file path instead of a symlink.")
                return 1
            elif "traversal" in err:
                print("✗ Security Error: Path traversal detected")
                print(f"  {e}")
                print("\n  Paths with '..' are not allowed for security reasons.")
                return 1
            elif ("outside current directory" in err or "outside working directory" in err) and allow_up:
                print("✗ Path resolves outside the current directory")
                print(f"  {e}")
                print("\n  Relative up is only allowed within the current directory when using --allow-relative-up.")
                print("  Tip: cd into the target folder or provide an absolute path inside the workspace.")
                return 1
            else:
                print(f"✗ Invalid file path: {e}")
                return 1
        except FileNotFoundError:
            print(f"✗ File not found: {ttl_file}")
            print(f"  Please verify the path exists and is correct.")
            return 1
        except PermissionError:
            print(f"✗ Permission denied: Cannot read file: {ttl_file}")
            print(f"  Please check file permissions.")
            return 1
        
        print(f"✓ Validating TTL file: {validated_path}\n")
        
        try:
            with open(validated_path, 'r', encoding='utf-8') as f:
                ttl_content = f.read()
        except UnicodeDecodeError as e:
            print(f"✗ Encoding error: File is not valid UTF-8")
            print(f"  {e}")
            return 1
        except Exception as e:
            print(f"✗ Error reading TTL file: {e}")
            return 1
        
        # Run validation
        report = validate_ttl_content(ttl_content, str(validated_path))
        
        # Display results
        self._display_results(report, args.verbose)
        
        # Save report if requested
        if args.output:
            report.save_to_file(args.output)
            print(f"\nDetailed report saved to: {args.output}")
        elif args.save_report:
            output_path = str(Path(ttl_file).with_suffix('.validation.json'))
            report.save_to_file(output_path)
            print(f"\nDetailed report saved to: {output_path}")
        
        # Return appropriate exit code
        if report.can_import_seamlessly:
            return 0
        elif report.issues_by_severity.get('error', 0) > 0:
            return 2  # Errors present
        else:
            return 1  # Only warnings
    
    def _execute_batch_validate(self, args: argparse.Namespace, directory: Path) -> int:
        """Execute validation for all TTL files in a directory."""
        from rdf_converter import InputValidator
        from preflight_validator import validate_ttl_content
        
        recursive = getattr(args, 'recursive', False)
        ttl_files = find_ttl_files(directory, recursive=recursive)
        
        if not ttl_files:
            print(f"✗ No TTL files found in '{directory}'")
            if not recursive:
                print("  Tip: Use --recursive to search subdirectories")
            return 1
        
        print(f"Found {len(ttl_files)} TTL file(s) to validate\n")
        
        successes: List[str] = []
        failures: List[Tuple[str, str]] = []
        all_reports = []
        
        for i, ttl_file in enumerate(ttl_files, 1):
            print_batch_progress(i, len(ttl_files), ttl_file.name)
            
            try:
                validated_path = InputValidator.validate_input_ttl_path(str(ttl_file))
                
                with open(validated_path, 'r', encoding='utf-8') as f:
                    ttl_content = f.read()
                
                report = validate_ttl_content(ttl_content, str(validated_path))
                all_reports.append((ttl_file.name, report))
                
                if report.can_import_seamlessly:
                    successes.append(str(ttl_file))
                    print(f"  ✓ Valid")
                else:
                    errors = report.issues_by_severity.get('error', 0)
                    warnings = report.issues_by_severity.get('warning', 0)
                    if errors > 0:
                        failures.append((str(ttl_file), f"{errors} errors, {warnings} warnings"))
                        print(f"  ✗ {errors} errors, {warnings} warnings")
                    else:
                        successes.append(str(ttl_file))
                        print(f"  ⚠ {warnings} warnings")
                        
            except Exception as e:
                failures.append((str(ttl_file), str(e)))
                print(f"  ✗ Error: {e}")
        
        # Print summary
        print_batch_summary(successes, failures, "validation")
        
        # Save combined report if requested
        if args.output:
            combined_report = {
                "total_files": len(ttl_files),
                "successful": len(successes),
                "failed": len(failures),
                "reports": [
                    {"file": name, "summary": report.to_dict()} 
                    for name, report in all_reports
                ]
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(combined_report, f, indent=2)
            print(f"\nCombined report saved to: {args.output}")
        
        return 0 if not failures else 1
    
    def _display_results(self, report: Any, verbose: bool) -> None:
        """Display validation results."""
        if verbose:
            print(report.get_human_readable_summary())
        else:
            print_header("VALIDATION RESULT")
            
            if report.can_import_seamlessly:
                print("✓ This ontology can be imported SEAMLESSLY.")
                print("  No significant conversion issues detected.")
            else:
                print("✗ Issues detected that may affect conversion quality.")
                print()
                print(f"Total Issues: {report.total_issues}")
                print(f"  - Errors:   {report.issues_by_severity.get('error', 0)}")
                print(f"  - Warnings: {report.issues_by_severity.get('warning', 0)}")
                print(f"  - Info:     {report.issues_by_severity.get('info', 0)}")
            
            print()
            print("Ontology Statistics:")
            print(f"  Triples: {report.summary.get('total_triples', 0)}")
            print(f"  Classes: {report.summary.get('declared_classes', 0)}")
            print(f"  Properties: {report.summary.get('declared_properties', 0)}")
            
            if report.issues and not report.can_import_seamlessly:
                print()
                print("Issue Categories:")
                for category, count in sorted(report.issues_by_category.items(), key=lambda x: -x[1]):
                    print(f"  - {category.replace('_', ' ').title()}: {count}")


class UploadCommand(BaseCommand):
    """Upload an RDF TTL file to Fabric Ontology."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the upload command."""
        from rdf_converter import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter
        )
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        from preflight_validator import validate_ttl_content, generate_import_log, IssueSeverity
        from cancellation import (
            setup_cancellation_handler, restore_default_handler,
            OperationCancelledException
        )
        
        ttl_path = Path(args.ttl_file)
        
        # Check if this is a directory and --recursive is set
        if ttl_path.is_dir():
            if not getattr(args, 'recursive', False):
                print(f"✗ '{ttl_path}' is a directory. Use --recursive to process all TTL files.")
                return 1
            return self._execute_batch_upload(args, ttl_path)
        
        # Single file upload
        return self._execute_single_upload(args)
    
    def _execute_single_upload(self, args: argparse.Namespace) -> int:
        """Execute upload for a single file."""
        from rdf_converter import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter
        )
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        from preflight_validator import validate_ttl_content, generate_import_log, IssueSeverity
        from cancellation import (
            setup_cancellation_handler, restore_default_handler,
            OperationCancelledException
        )
        
        # Setup cancellation handler
        cancellation_token = setup_cancellation_handler(
            message="\n⚠️  Cancellation requested. Cleaning up..."
        )
        
        created_ontology_id = None
        validation_report = None
        
        def cleanup_on_cancel():
            if created_ontology_id:
                logger.info(f"Cancellation cleanup: partial ontology may exist: {created_ontology_id}")
                print(f"\n⚠️  Partial ontology may have been created: {created_ontology_id}")
                print("   You may want to delete it manually if the upload was incomplete.")
        
        cancellation_token.register_callback(cleanup_on_cancel)
        
        try:
            # Load and validate configuration
            config_path = args.config or get_default_config_path()
            try:
                config_data = load_config(config_path)
            except FileNotFoundError as e:
                print(f"✗ {e}")
                return 1
            except PermissionError as e:
                print(f"✗ {e}")
                return 1
            except ValueError as e:
                print(f"✗ {e}")
                return 1
            
            fabric_config = FabricConfig.from_dict(config_data)
            
            if not fabric_config.workspace_id or fabric_config.workspace_id == "YOUR_WORKSPACE_ID":
                print("✗ Configuration Error: Please configure your Fabric workspace_id in config.json")
                return 1
            
            # Setup logging
            log_config = config_data.get('logging', {})
            setup_logging(config=log_config)
            
            # Validate and read TTL file with enhanced error handling
            ttl_file = args.ttl_file
            try:
                allow_up = getattr(args, 'allow_relative_up', False)
                validated_path = InputValidator.validate_input_ttl_path(ttl_file, allow_relative_up=allow_up)
            except ValueError as e:
                err = str(e).lower()
                if "symlink" in err:
                    print("✗ Security Error: Symlinks are not allowed")
                    print(f"  {e}")
                    print("\n  Please provide the actual file path instead of a symlink.")
                    return 1
                elif "traversal" in err:
                    print("✗ Security Error: Path traversal detected")
                    print(f"  {e}")
                    print("\n  Paths with '..' are not allowed for security reasons.")
                    return 1
                elif ("outside current directory" in err or "outside working directory" in err) and allow_up:
                    print("✗ Path resolves outside the current directory")
                    print(f"  {e}")
                    print("\n  Relative up is only allowed within the current directory when using --allow-relative-up.")
                    print("  Tip: cd into the target folder or provide an absolute path inside the workspace.")
                    return 1
                else:
                    print(f"✗ Invalid file path: {e}")
                    return 1
            except FileNotFoundError:
                print(f"✗ File not found: {ttl_file}")
                print(f"  Please verify the path exists and is correct.")
                return 1
            except PermissionError:
                print(f"✗ Permission denied: Cannot read file: {ttl_file}")
                print(f"  Please check file permissions.")
                return 1
            
            logger.info(f"Parsing TTL file: {validated_path}")
            
            try:
                with open(validated_path, 'r', encoding='utf-8') as f:
                    ttl_content = f.read()
            except UnicodeDecodeError as e:
                print(f"✗ Encoding error: File is not valid UTF-8")
                print(f"  {e}")
                print("\nTry converting the file to UTF-8 encoding")
                return 1
            except Exception as e:
                print(f"✗ Error reading TTL file: {e}")
                return 1
            
            if not ttl_content.strip():
                print(f"✗ Error: TTL file is empty: {ttl_file}")
                return 1
            
            # Pre-flight validation
            if not args.skip_validation:
                validation_report = self._run_validation(
                    ttl_content, ttl_file, args, validated_path
                )
                if validation_report is None:
                    return 0  # User cancelled
            
            # Convert TTL to Fabric format
            id_prefix = config_data.get('ontology', {}).get('id_prefix', 1000000000000)
            force_memory = getattr(args, 'force_memory', False)
            use_streaming = getattr(args, 'streaming', False)
            
            # Check file size for streaming suggestion
            file_size_mb = validated_path.stat().st_size / (1024 * 1024)
            if file_size_mb > StreamingRDFConverter.STREAMING_THRESHOLD_MB and not use_streaming:
                print(f"⚠️  Large file detected ({file_size_mb:.1f} MB). Consider using --streaming.")
            
            try:
                definition, extracted_name, conversion_result = self._convert_ttl(
                    ttl_content, validated_path, id_prefix, force_memory, 
                    use_streaming, cancellation_token
                )
            except ValueError as e:
                logger.error(f"Invalid TTL content: {e}")
                print(f"Error: Invalid RDF/TTL content: {e}")
                return 1
            except MemoryError as e:
                logger.error(f"Insufficient memory to parse TTL file: {e}")
                print(f"\nError: {e}")
                print("\nTip: Use --streaming for memory-efficient processing of large files.")
                return 1
            except Exception as e:
                logger.error(f"Failed to parse TTL file: {e}", exc_info=True)
                print(f"Error parsing TTL file: {e}")
                return 1
            
            # Display conversion summary
            print_conversion_summary(conversion_result, heading="CONVERSION SUMMARY")
            
            # Confirm if items were skipped
            if conversion_result.has_skipped_items and not args.force:
                print("⚠ Some items were skipped during conversion.")
                for item_type, count in conversion_result.skipped_by_type.items():
                    print(f"  - {item_type}s skipped: {count}")
                print()
                if not confirm_action("Do you want to proceed with the upload anyway?"):
                    print("Upload cancelled.")
                    return 0
            
            if not definition or 'parts' not in definition or not definition['parts']:
                print("Error: Generated definition is invalid or empty")
                return 1
            
            # Upload to Fabric
            ontology_name = args.name or extracted_name
            description = args.description or f"Imported from {os.path.basename(ttl_file)}"
            
            logger.info(f"Ontology name: {ontology_name}")
            logger.info(f"Definition has {len(definition['parts'])} parts")
            
            client = FabricOntologyClient(fabric_config)
            
            try:
                result = client.create_or_update_ontology(
                    display_name=ontology_name,
                    description=description,
                    definition=definition,
                    wait_for_completion=True,
                    cancellation_token=cancellation_token,
                )
                
                created_ontology_id = result.get('id')
                
                print(f"Successfully processed ontology '{ontology_name}'")
                print(f"Ontology ID: {result.get('id', 'Unknown')}")
                print(f"Workspace ID: {result.get('workspaceId', fabric_config.workspace_id)}")
                
                # Generate import log if validation had issues
                if validation_report and not validation_report.can_import_seamlessly:
                    log_dir = log_config.get('file', 'logs/app.log')
                    log_dir = os.path.dirname(log_dir) or 'logs'
                    log_path = generate_import_log(validation_report, log_dir, ontology_name)
                    print(f"\nImport log saved to: {log_path}")
                
                return 0
                
            except FabricAPIError as e:
                logger.error(f"Fabric API error: {e}")
                print(f"Error: {e.message}")
                if e.error_code == "ItemDisplayNameAlreadyInUse":
                    print("Hint: Use --update to update an existing ontology, or choose a different name with --name")
                return 1
        
        except OperationCancelledException:
            print("\n✗ Upload cancelled by user.")
            return 130  # Standard exit code for SIGINT
        
        finally:
            restore_default_handler()
    
    def _execute_batch_upload(self, args: argparse.Namespace, directory: Path) -> int:
        """Execute upload for all TTL files in a directory."""
        from rdf_converter import InputValidator, parse_ttl_with_result
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        
        # Load configuration first
        config_path = args.config or get_default_config_path()
        try:
            config_data = load_config(config_path)
        except Exception as e:
            print(f"✗ Error loading config: {e}")
            return 1
        
        fabric_config = FabricConfig.from_dict(config_data)
        if not fabric_config.workspace_id or fabric_config.workspace_id == "YOUR_WORKSPACE_ID":
            print("✗ Configuration Error: Please configure your Fabric workspace_id in config.json")
            return 1
        
        recursive = getattr(args, 'recursive', False)
        ttl_files = find_ttl_files(directory, recursive=recursive)
        
        if not ttl_files:
            print(f"✗ No TTL files found in '{directory}'")
            return 1
        
        print(f"Found {len(ttl_files)} TTL file(s) to upload\n")
        
        # Confirm batch operation
        if not args.force:
            if not confirm_action(f"Upload {len(ttl_files)} files to Fabric?"):
                print("Upload cancelled.")
                return 0
        
        successes: List[str] = []
        failures: List[Tuple[str, str]] = []
        id_prefix = config_data.get('ontology', {}).get('id_prefix', 1000000000000)
        client = FabricOntologyClient(fabric_config)
        
        for i, ttl_file in enumerate(ttl_files, 1):
            print_batch_progress(i, len(ttl_files), ttl_file.name)
            
            try:
                validated_path = InputValidator.validate_input_ttl_path(str(ttl_file))
                
                with open(validated_path, 'r', encoding='utf-8') as f:
                    ttl_content = f.read()
                
                definition, extracted_name, conversion_result = parse_ttl_with_result(
                    ttl_content, id_prefix
                )
                
                # Generate ontology name from filename
                ontology_name = args.name or extracted_name or ttl_file.stem
                description = args.description or f"Batch imported from {ttl_file.name}"
                
                result = client.create_or_update_ontology(
                    display_name=ontology_name,
                    description=description,
                    definition=definition,
                    wait_for_completion=True,
                )
                
                successes.append(str(ttl_file))
                print(f"  ✓ Uploaded as '{ontology_name}' (ID: {result.get('id', 'N/A')})")
                
            except Exception as e:
                failures.append((str(ttl_file), str(e)))
                print(f"  ✗ Error: {e}")
        
        # Print summary
        print_batch_summary(successes, failures, "upload")
        
        return 0 if not failures else 1
    
    def _run_validation(
        self, ttl_content: str, ttl_file: str, args: Any, validated_path: Path
    ) -> Any:
        """Run pre-flight validation."""
        from preflight_validator import validate_ttl_content, IssueSeverity
        
        print_header("PRE-FLIGHT VALIDATION")
        
        validation_report = validate_ttl_content(ttl_content, ttl_file)
        
        if validation_report.can_import_seamlessly:
            print("✓ Ontology can be imported seamlessly.")
            print(f"  Classes: {validation_report.summary.get('declared_classes', 0)}")
            print(f"  Properties: {validation_report.summary.get('declared_properties', 0)}")
        else:
            print("⚠ Issues detected that may affect conversion quality:\n")
            print(f"  Errors:   {validation_report.issues_by_severity.get('error', 0)}")
            print(f"  Warnings: {validation_report.issues_by_severity.get('warning', 0)}")
            print(f"  Info:     {validation_report.issues_by_severity.get('info', 0)}")
            print()
            
            # Show top issues
            warning_issues = [
                i for i in validation_report.issues 
                if i.severity in (IssueSeverity.ERROR, IssueSeverity.WARNING)
            ]
            if warning_issues:
                print("Key issues:")
                for issue in warning_issues[:5]:
                    icon = "✗" if issue.severity == IssueSeverity.ERROR else "⚠"
                    print(f"  {icon} {issue.message}")
                if len(warning_issues) > 5:
                    print(f"  ... and {len(warning_issues) - 5} more warnings/errors")
            
            print()
            
            if not args.force:
                print("Some RDF/OWL constructs cannot be fully represented in Fabric Ontology.")
                if not confirm_action("Do you want to proceed with the import anyway?"):
                    print("Import cancelled.")
                    if args.save_validation_report:
                        report_path = str(Path(ttl_file).with_suffix('.validation.json'))
                        validation_report.save_to_file(report_path)
                        print(f"Validation report saved to: {report_path}")
                    return None
        
        print_footer()
        return validation_report
    
    def _convert_ttl(
        self, ttl_content: str, validated_path: Path, id_prefix: int,
        force_memory: bool, use_streaming: bool, cancellation_token: Any
    ) -> tuple:
        """Convert TTL to Fabric format."""
        from rdf_converter import parse_ttl_with_result, parse_ttl_streaming
        
        if use_streaming:
            print(f"Using streaming mode for conversion...")
            pbar = None
            progress_callback = None
            try:
                from tqdm import tqdm
                pbar = tqdm(desc="Processing ontology", unit=" triples", dynamic_ncols=True, total=0)
                
                def progress_callback(n: int) -> None:
                    if pbar is not None:
                        pbar.total = n if n > 0 else None
                        pbar.n = n
                        pbar.refresh()
            except ImportError:
                pass
            
            try:
                return parse_ttl_streaming(
                    str(validated_path),
                    id_prefix=id_prefix,
                    progress_callback=progress_callback,
                    cancellation_token=cancellation_token
                )
            finally:
                if pbar is not None:
                    pbar.close()
        else:
            return parse_ttl_with_result(
                ttl_content, id_prefix, force_large_file=force_memory
            )


class ConvertCommand(BaseCommand):
    """Convert TTL to Fabric Ontology definition without uploading."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the convert command."""
        from rdf_converter import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter
        )
        
        self.setup_logging_from_config()
        
        ttl_path = Path(args.ttl_file)
        
        # Check if this is a directory and --recursive is set
        if ttl_path.is_dir():
            if not getattr(args, 'recursive', False):
                print(f"✗ '{ttl_path}' is a directory. Use --recursive to process all TTL files.")
                return 1
            return self._execute_batch_convert(args, ttl_path)
        
        # Single file conversion
        return self._execute_single_convert(args)
    
    def _execute_single_convert(self, args: argparse.Namespace) -> int:
        """Execute conversion for a single file."""
        from rdf_converter import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter
        )
        
        ttl_file = args.ttl_file
        
        try:
            allow_up = getattr(args, 'allow_relative_up', False)
            validated_path = InputValidator.validate_input_ttl_path(ttl_file, allow_relative_up=allow_up)
        except ValueError as e:
            err = str(e).lower()
            if "symlink" in err:
                print("✗ Security Error: Symlinks are not allowed")
                print(f"  {e}")
                return 1
            elif "traversal" in err:
                print("✗ Security Error: Path traversal detected")
                print(f"  {e}")
                return 1
            elif ("outside current directory" in err or "outside working directory" in err) and allow_up:
                print("✗ Path resolves outside the current directory")
                print(f"  {e}")
                print("\n  Relative up is only allowed within the current directory when using --allow-relative-up.")
                print("  Tip: cd into the target folder or provide an absolute path inside the workspace.")
                return 1
            else:
                print(f"✗ Invalid file path: {e}")
                return 1
        except FileNotFoundError:
            print(f"✗ File not found: {ttl_file}")
            return 1
        except PermissionError:
            print(f"✗ Permission denied: Cannot read file: {ttl_file}")
            return 1
        
        print(f"✓ Converting TTL file: {validated_path}")
        
        force_memory = getattr(args, 'force_memory', False)
        use_streaming = getattr(args, 'streaming', False)
        
        # Check file size
        file_size_mb = validated_path.stat().st_size / (1024 * 1024)
        if file_size_mb > StreamingRDFConverter.STREAMING_THRESHOLD_MB and not use_streaming:
            print(f"⚠️  Large file detected ({file_size_mb:.1f} MB). Consider using --streaming.")
        
        try:
            if use_streaming:
                print(f"Using streaming mode (batch processing)...")
                pbar = None
                progress_callback = None
                try:
                    from tqdm import tqdm
                    pbar = tqdm(desc="Processing ontology", unit=" triples", dynamic_ncols=True, total=0)
                    
                    def progress_callback(n: int) -> None:
                        if pbar is not None:
                            pbar.total = n if n > 0 else None
                            pbar.n = n
                            pbar.refresh()
                except ImportError:
                    pass
                
                try:
                    definition, ontology_name, conversion_result = parse_ttl_streaming(
                        str(validated_path),
                        progress_callback=progress_callback
                    )
                finally:
                    if pbar is not None:
                        pbar.close()
            else:
                try:
                    with open(validated_path, 'r', encoding='utf-8') as f:
                        ttl_content = f.read()
                except UnicodeDecodeError as e:
                    print(f"✗ Encoding error: File is not valid UTF-8")
                    print(f"  {e}")
                    print("\nTry converting the file to UTF-8 encoding")
                    return 1
                except Exception as e:
                    print(f"✗ Error reading TTL file: {e}")
                    return 1
                
                definition, ontology_name, conversion_result = parse_ttl_with_result(
                    ttl_content, force_large_file=force_memory
                )
        except ValueError as e:
            print(f"✗ Invalid RDF/TTL content: {e}")
            return 1
        except MemoryError as e:
            print(f"\n✗ {e}")
            print("\nTip: Use --streaming for memory-efficient processing of large files.")
            return 1
        except Exception as e:
            print(f"Error parsing TTL file: {e}")
            return 1
        
        # Display summary
        print("\n" + conversion_result.get_summary())
        
        output = {
            "displayName": ontology_name,
            "description": f"Converted from {validated_path.name}",
            "definition": definition,
            "conversionResult": conversion_result.to_dict()
        }
        
        output_path = args.output or str(validated_path.with_suffix('.json'))
        
        try:
            validated_output = InputValidator.validate_output_file_path(
                output_path, allowed_extensions=['.json']
            )
        except ValueError as e:
            print(f"Error: Invalid output path: {e}")
            return 1
        except PermissionError as e:
            print(f"Error: {e}")
            return 1
        
        try:
            with open(validated_output, 'w', encoding='utf-8') as f:
                json.dump(output, indent=2, fp=f)
        except PermissionError:
            print(f"Error: Permission denied writing to {validated_output}")
            return 1
        except Exception as e:
            print(f"Error writing output file: {e}")
            return 1
        
        print(f"\nSaved Fabric Ontology definition to: {validated_output}")
        print(f"Ontology Name: {ontology_name}")
        print(f"Definition Parts: {len(definition['parts'])}")
        
        if conversion_result.has_skipped_items:
            print(f"⚠ Skipped Items: {len(conversion_result.skipped_items)}")
            print("  See conversionResult in output file for details.")
        
        return 0
    
    def _execute_batch_convert(self, args: argparse.Namespace, directory: Path) -> int:
        """Execute conversion for all TTL files in a directory."""
        from rdf_converter import InputValidator, parse_ttl_with_result
        
        recursive = getattr(args, 'recursive', False)
        ttl_files = find_ttl_files(directory, recursive=recursive)
        
        if not ttl_files:
            print(f"✗ No TTL files found in '{directory}'")
            return 1
        
        print(f"Found {len(ttl_files)} TTL file(s) to convert\n")
        
        successes: List[str] = []
        failures: List[Tuple[str, str]] = []
        output_dir = Path(args.output) if args.output else directory
        
        # Create output directory if needed
        if args.output:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, ttl_file in enumerate(ttl_files, 1):
            print_batch_progress(i, len(ttl_files), ttl_file.name)
            
            try:
                validated_path = InputValidator.validate_input_ttl_path(str(ttl_file))
                
                with open(validated_path, 'r', encoding='utf-8') as f:
                    ttl_content = f.read()
                
                definition, ontology_name, conversion_result = parse_ttl_with_result(ttl_content)
                
                output = {
                    "displayName": ontology_name,
                    "description": f"Converted from {ttl_file.name}",
                    "definition": definition,
                    "conversionResult": conversion_result.to_dict()
                }
                
                output_file = output_dir / f"{ttl_file.stem}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2)
                
                successes.append(str(ttl_file))
                print(f"  ✓ Saved to {output_file}")
                
            except Exception as e:
                failures.append((str(ttl_file), str(e)))
                print(f"  ✗ Error: {e}")
        
        # Print summary
        print_batch_summary(successes, failures, "conversion")
        
        return 0 if not failures else 1


class ExportCommand(BaseCommand):
    """Export an ontology from Fabric to TTL format."""
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the export command."""
        from rdf_converter import InputValidator
        from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
        from fabric_to_ttl import FabricToTTLConverter
        
        config_path = args.config or get_default_config_path()
        
        # Load and validate configuration with enhanced error handling
        try:
            config_data = load_config(config_path)
            log_config = config_data.get('logging', {})
            setup_logging(config=log_config)
        except FileNotFoundError as e:
            print(f"✗ {e}")
            return 1
        except PermissionError as e:
            print(f"✗ {e}")
            return 1
        except ValueError as e:
            print(f"✗ {e}")
            return 1
        
        try:
            fabric_config = FabricConfig.from_dict(config_data)
        except ValueError as e:
            print(f"✗ Configuration error: {e}")
            return 1
        except Exception as e:
            print(f"✗ Failed to load configuration: {e}")
            return 1
        
        client = FabricOntologyClient(fabric_config)
        ontology_id = args.ontology_id
        
        print(f"✓ Exporting ontology {ontology_id} to TTL format...")
        
        try:
            ontology_info = client.get_ontology(ontology_id)
            definition = client.get_ontology_definition(ontology_id)
            
            if not definition:
                print("✗ Error: Failed to get ontology definition")
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
            except ValueError as e:
                print(f"Error: Invalid output path: {e}")
                return 1
            except PermissionError as e:
                print(f"Error: {e}")
                return 1
            
            with open(validated_output, 'w', encoding='utf-8') as f:
                f.write(ttl_content)
            
            print(f"Successfully exported ontology to: {validated_output}")
            print(f"Ontology Name: {ontology_info.get('displayName', 'Unknown')}")
            print(f"Parts in definition: {len(definition.get('parts', []))}")
            
            return 0
            
        except FabricAPIError as e:
            logger.error(f"API Error: {e}")
            return 1
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return 1
