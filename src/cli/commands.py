"""
CLI command handlers.

This module contains command classes that orchestrate the execution of CLI commands.
Each command class follows the Command pattern and has a single responsibility:
coordinating between validators, converters, and API clients.

The command classes are intentionally thin - they delegate actual work to
the appropriate domain modules (rdf_converter, fabric_client, etc.).
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from .helpers import (
    load_config,
    get_default_config_path,
    setup_logging,
    print_header,
    print_footer,
    confirm_action,
)


try:  # Prefer absolute import when repository root is on sys.path
    from models import ConversionResult
    from models.base import ConverterProtocol
    from constants import ExitCode
except ImportError:  # pragma: no cover - fallback when running as package
    from ..models import ConversionResult  # type: ignore
    from ..models.base import ConverterProtocol  # type: ignore
    from ..constants import ExitCode  # type: ignore


logger = logging.getLogger(__name__)


# ============================================================================
# Helper Utilities
# ============================================================================

def print_conversion_summary(result: ConversionResult, heading: Optional[str] = None) -> None:
    """Print a consistent summary for any converter result."""
    if heading:
        print_header(heading)
    print(result.get_summary())
    if heading:
        print_footer()


# ============================================================================
# Protocols for Dependency Injection
# ============================================================================

class IValidator(Protocol):
    """Protocol for TTL validation."""
    
    def validate(self, content: str, file_path: str) -> Any:
        """Validate TTL content."""
        ...


class IConverter(ConverterProtocol, Protocol):
    """Alias for the shared converter protocol."""
    ...


class IFabricClient(Protocol):
    """Protocol for Fabric API operations."""
    
    def list_ontologies(self) -> list:
        """List all ontologies."""
        ...
    
    def get_ontology(self, ontology_id: str) -> dict:
        """Get ontology by ID."""
        ...
    
    def get_ontology_definition(self, ontology_id: str) -> dict:
        """Get ontology definition."""
        ...
    
    def create_or_update_ontology(
        self,
        display_name: str,
        description: str,
        definition: dict,
        wait_for_completion: bool = True,
        cancellation_token: Any = None
    ) -> dict:
        """Create or update an ontology."""
        ...
    
    def delete_ontology(self, ontology_id: str) -> None:
        """Delete an ontology."""
        ...


# ============================================================================
# Base Command Class
# ============================================================================

class BaseCommand(ABC):
    """
    Base class for CLI commands.
    
    Provides common functionality like configuration loading and logging setup.
    Subclasses should implement the execute() method.
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        validator: Optional[IValidator] = None,
        converter: Optional[IConverter] = None,
        client: Optional[IFabricClient] = None,
    ):
        """
        Initialize the command.
        
        Args:
            config_path: Path to configuration file.
            validator: Optional validator instance (for dependency injection).
            converter: Optional converter instance (for dependency injection).
            client: Optional Fabric client instance (for dependency injection).
        """
        self.config_path = config_path or get_default_config_path()
        self._validator = validator
        self._converter = converter
        self._client = client
        self._config: Optional[Dict[str, Any]] = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Lazy-load configuration."""
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config
    
    def get_validator(self) -> IValidator:
        """Get or create validator instance."""
        if self._validator is None:
            from preflight_validator import PreflightValidator
            self._validator = PreflightValidator()
        return self._validator
    
    def get_client(self) -> IFabricClient:
        """Get or create Fabric client instance."""
        if self._client is None:
            from fabric_client import FabricConfig, FabricOntologyClient
            fabric_config = FabricConfig.from_dict(self.config)
            self._client = FabricOntologyClient(fabric_config)
        return self._client
    
    def setup_logging_from_config(self, allow_missing: bool = True) -> None:
        """Setup logging configuration, falling back gracefully if config is absent."""
        log_config: Dict[str, Any] = {}

        if self._config is not None:
            log_config = self._config.get('logging', {})
        else:
            config_path = Path(self.config_path)
            if config_path.exists() or not allow_missing:
                try:
                    config_data = load_config(self.config_path)
                    self._config = config_data
                    log_config = config_data.get('logging', {})
                except FileNotFoundError:
                    if not allow_missing:
                        raise
                except Exception as exc:
                    if not allow_missing:
                        raise
                    print(f"Warning: Could not load logging configuration: {exc}")

        setup_logging(config=log_config)
    
    @abstractmethod
    def execute(self, args: Any) -> int:
        """
        Execute the command.
        
        Args:
            args: Parsed command-line arguments.
            
        Returns:
            Exit code (0 for success, non-zero for error).
        """
        pass


# ============================================================================
# Command Implementations
# ============================================================================

class ValidateCommand(BaseCommand):
    """Validate a TTL file for Fabric Ontology compatibility."""
    
    def execute(self, args: Any) -> int:
        """Execute the validate command."""
        from rdf_converter import InputValidator
        from preflight_validator import validate_ttl_content
        
        self.setup_logging_from_config()
        
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
    
    def execute(self, args: Any) -> int:
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


class ListCommand(BaseCommand):
    """List all ontologies in the workspace."""
    
    def execute(self, args: Any) -> int:
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
    
    def execute(self, args: Any) -> int:
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
    
    def execute(self, args: Any) -> int:
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
    
    def execute(self, args: Any) -> int:
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
        script_dir = Path(__file__).parent.parent  # Go up from cli/ to src/
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


class ConvertCommand(BaseCommand):
    """Convert TTL to Fabric Ontology definition without uploading."""
    
    def execute(self, args: Any) -> int:
        """Execute the convert command."""
        from rdf_converter import (
            InputValidator, parse_ttl_with_result, parse_ttl_streaming,
            StreamingRDFConverter
        )
        
        self.setup_logging_from_config()
        
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


class ExportCommand(BaseCommand):
    """Export an ontology from Fabric to TTL format."""
    
    def execute(self, args: Any) -> int:
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


class CompareCommand(BaseCommand):
    """Compare two TTL files for semantic equivalence."""
    
    def execute(self, args: Any) -> int:
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


# ============================================================================
# DTDL Command Classes
# ============================================================================

class DTDLValidateCommand(BaseCommand):
    """Command to validate DTDL files."""
    
    def execute(self, args) -> int:
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
        
        if validation_result.errors:
            print(f"Found {len(validation_result.errors)} validation errors:")
            for error in validation_result.errors[:10]:
                print(f"  - [{error.level.value}] {error.element_id}: {error.message}")
            return 1
        
        if validation_result.warnings:
            print(f"Found {len(validation_result.warnings)} warnings:")
            for warning in validation_result.warnings[:10]:
                print(f"  - {warning.element_id}: {warning.message}")
        
        print("✓ Validation successful!")
        
        if getattr(args, 'verbose', False):
            print("\nInterface Summary:")
            for interface in result.interfaces[:20]:
                print(f"  {interface.name} ({interface.dtmi})")
                print(f"    Properties: {len(interface.properties)}, "
                      f"Telemetries: {len(interface.telemetries)}, "
                      f"Relationships: {len(interface.relationships)}")
        
        return 0


class DTDLConvertCommand(BaseCommand):
    """Command to convert DTDL to Fabric format."""
    
    def execute(self, args) -> int:
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
    
    def execute(self, args) -> int:
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
            config_path = getattr(args, 'config', None) or str(Path(__file__).parent.parent / "config.json")
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
