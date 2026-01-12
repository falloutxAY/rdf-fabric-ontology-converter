"""
CLI helper utilities.

This module provides shared utilities for CLI commands including:
- Configuration loading
- Logging setup
- Path resolution
"""

import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, Literal, Tuple, List

try:  # Prefer absolute import when running from project root
    from src.constants import LoggingConfig
except ImportError:  # pragma: no cover - fallback when running as package
    from ...constants import LoggingConfig  # type: ignore

# Type alias for log levels
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class JSONFormatter(logging.Formatter):
    """A lightweight JSON formatter for structured logging."""

    _RESERVED_FIELDS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - custom JSON body
        timestamp = datetime.utcfromtimestamp(record.created).strftime(
            LoggingConfig.JSON_DATE_FORMAT
        )
        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        # Include any extra fields supplied via LoggerAdapter/extra
        for key, value in record.__dict__.items():
            if key in self._RESERVED_FIELDS or key.startswith("_"):
                continue
            if key in payload:
                continue
            try:
                json.dumps(value)  # Validate serializable
                payload[key] = value
            except TypeError:
                payload[key] = str(value)

        return json.dumps(payload, ensure_ascii=False)


_MANAGED_HANDLERS: List[Handler] = []
_LOGGING_SIGNATURE: Optional[Tuple[Any, ...]] = None
_LAST_LOG_FILE: Optional[str] = None


def _ensure_utf8_stdout() -> None:
    """Ensure stdout can handle UTF-8 characters on Windows."""
    if sys.platform == 'win32':
        # Try to set console to UTF-8 mode
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, TypeError):
            # Fallback for older Python versions
            try:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer, encoding='utf-8', errors='replace'
                )
            except AttributeError:
                pass  # Not a TTY, let it be


# Initialize UTF-8 output on module load
_ensure_utf8_stdout()


def get_default_config_path() -> str:
    """Get the default configuration file path.
    
    Returns:
        Path to the default config.json file in the project root directory.
    """
    # Look for config.json in the project root (where config.sample.json lives)
    # Path: src/app/cli/helpers.py -> src/app/cli -> src/app -> src -> project root
    cli_dir = Path(__file__).parent
    project_root = cli_dir.parent.parent.parent
    return str(project_root / "config.json")


def _clear_managed_handlers() -> None:
    """Remove handlers that were added by this module."""
    global _MANAGED_HANDLERS
    root_logger = logging.getLogger()
    for handler in _MANAGED_HANDLERS:
        try:
            root_logger.removeHandler(handler)
            handler.close()
        except Exception:
            continue
    _MANAGED_HANDLERS = []


def _coerce_positive_int(value: Any, default: int) -> int:
    """Convert config-provided values to positive integers."""
    try:
        numeric = int(value)
        return numeric if numeric > 0 else default
    except (TypeError, ValueError):
        return default


def _create_file_handler(
    path: str,
    rotation_enabled: bool,
    max_bytes: int,
    backup_count: int
) -> Handler:
    """Create a file or rotating file handler."""
    if rotation_enabled and max_bytes > 0:
        return RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=max(backup_count, 1),
            encoding='utf-8'
        )
    return logging.FileHandler(path, encoding='utf-8')


def setup_logging(
    level: LogLevel = LoggingConfig.DEFAULT_LOG_LEVEL,
    log_file: Optional[str] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
    include_console: bool = True,
) -> Optional[str]:
    """
    Setup logging configuration with fallback locations.
    
    If the primary log file location fails (permission denied, disk full, etc.),
    attempts to write to fallback locations in order:
    1. Requested location
    2. System temp directory
    3. User home directory
    4. Console-only (final fallback)
    
    Args:
        level: Legacy log level override (kept for backward compatibility).
        log_file: Legacy log file override.
        config: Optional logging configuration dictionary.
        include_console: If False, skip adding a console handler.
        
    Returns:
        The actual log file path used, or None if logging to console only.
    """
    global _LOGGING_SIGNATURE, _LAST_LOG_FILE

    config_dict = dict(config or {})

    resolved_level = str(config_dict.get('level', level or LoggingConfig.DEFAULT_LOG_LEVEL))
    log_level = getattr(logging, resolved_level.upper(), logging.INFO)

    config_file = config_dict.get('file') or config_dict.get('log_file')
    file_path = log_file if log_file is not None else config_file
    
    format_style = str(config_dict.get('format', LoggingConfig.DEFAULT_FORMAT_STYLE)).lower()
    if format_style not in LoggingConfig.SUPPORTED_FORMATS:
        format_style = LoggingConfig.DEFAULT_FORMAT_STYLE
    if config_dict.get('structured'):
        format_style = 'json'
    structured = format_style == 'json'

    text_pattern = config_dict.get('pattern') or config_dict.get('text_pattern')
    format_string = text_pattern or LoggingConfig.LOG_FORMAT
    date_format = config_dict.get('date_format', LoggingConfig.DATE_FORMAT)

    formatter: logging.Formatter
    if structured:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(fmt=format_string, datefmt=date_format)

    rotation_cfg = config_dict.get('rotation') if isinstance(config_dict.get('rotation'), dict) else {}
    rotation_enabled = rotation_cfg.get('enabled')
    if rotation_enabled is None:
        rotation_enabled = bool(file_path) and LoggingConfig.ROTATION_ENABLED
    max_mb = rotation_cfg.get('max_mb', LoggingConfig.MAX_LOG_FILE_MB)
    backup_count = rotation_cfg.get('backup_count', LoggingConfig.LOG_BACKUP_COUNT)
    max_bytes = _coerce_positive_int(max_mb, LoggingConfig.MAX_LOG_FILE_MB) * 1024 * 1024
    backup_count = _coerce_positive_int(backup_count, LoggingConfig.LOG_BACKUP_COUNT)

    signature = (
        log_level,
        file_path,
        format_style,
        include_console,
        rotation_enabled,
        max_bytes,
        backup_count,
    )

    if _LOGGING_SIGNATURE == signature and _MANAGED_HANDLERS:
        return _LAST_LOG_FILE

    handlers: List[Handler] = []
    actual_log_file = None
    
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    if file_path:
        log_filename = os.path.basename(file_path) or "rdf_converter.log"
        fallback_locations = [
            file_path,
            os.path.join(tempfile.gettempdir(), log_filename),
            os.path.join(Path.home(), log_filename),
        ]
        file_handler = None
        for fallback_path in fallback_locations:
            try:
                log_dir = os.path.dirname(fallback_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                file_handler = _create_file_handler(
                    fallback_path,
                    rotation_enabled=bool(rotation_enabled),
                    max_bytes=max_bytes,
                    backup_count=backup_count,
                )
                file_handler.setFormatter(formatter)
                handlers.append(file_handler)
                actual_log_file = fallback_path
                if fallback_path != file_path:
                    print(f"Note: Using fallback log file: {fallback_path}")
                break
            except PermissionError:
                print(f"  Could not create log at {fallback_path}: Permission denied")
                continue
            except OSError as exc:
                print(f"  Could not create log at {fallback_path}: {exc}")
                continue
            except Exception as exc:
                print(f"  Unexpected error creating log at {fallback_path}: {exc}")
                continue
        if not file_handler:
            print("Warning: Could not write log file to any location")
            print(f"  Requested: {file_path}")
            print(f"  Attempted fallbacks: {', '.join(fallback_locations[1:])}")
            print("  Logging to console only")

    if not handlers:
        # As a failsafe, ensure we still have console output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    _clear_managed_handlers()
    root_logger = logging.getLogger()
    logging.captureWarnings(True)
    root_logger.setLevel(log_level)

    for handler in handlers:
        root_logger.addHandler(handler)
        _MANAGED_HANDLERS.append(handler)

    _LOGGING_SIGNATURE = signature
    _LAST_LOG_FILE = actual_log_file

    logger = logging.getLogger(__name__)
    if actual_log_file:
        logger.info(f"Logging to: {actual_log_file}")

    return actual_log_file


def load_config(config_path: str, strict_security: bool = False) -> Dict[str, Any]:
    """
    Load configuration from a JSON file with security validation.
    
    Security features:
    - Validates file path to prevent traversal attacks
    - Rejects symlinks
    - Optionally restricts to current working directory (when strict_security=True)
    - Validates JSON structure
    
    Args:
        config_path: Path to the configuration file.
        strict_security: If True, enforce config file is within cwd (default: False).
        
    Returns:
        Dictionary containing the configuration.
        
    Raises:
        ValueError: If config_path is empty or file contains invalid JSON.
        FileNotFoundError: If the configuration file doesn't exist.
        PermissionError: If the file cannot be read or is a symlink.
        IOError: If there's an error reading the file.
    """
    # Import InputValidator here to avoid circular imports
    from src.rdf import InputValidator
    
    if not config_path:
        raise ValueError("config_path cannot be empty")
    
    # Validate config path - use strict_security to control cwd restriction
    try:
        if strict_security:
            validated_path = InputValidator.validate_config_file_path(config_path)
        else:
            # Less strict validation: allow config files from any location
            # but still validate traversal, extension, existence
            validated_path = InputValidator.validate_file_path(
                config_path,
                allowed_extensions=['.json'],
                check_exists=True,
                check_readable=True,
                restrict_to_cwd=False,
                reject_symlinks=True
            )
    except ValueError as e:
        if "outside" in str(e).lower():
            raise ValueError(
                f"Configuration file must be in current working directory: {config_path}\n"
                f"Please move config.json to the working directory or adjust the path."
            )
        raise
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create a config.json file or specify one with --config"
        )
    except PermissionError as e:
        if "symlink" in str(e).lower():
            raise PermissionError(
                f"Symlinks are not allowed for configuration files: {config_path}\n"
                f"Please use the actual file path instead."
            )
        raise PermissionError(f"Cannot read configuration file: {e}")
    
    try:
        with open(validated_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in configuration file {validated_path} at line {e.lineno}, column {e.colno}: {e.msg}"
        )
    except UnicodeDecodeError as e:
        raise ValueError(f"File encoding error in {validated_path}: {e}")
    except Exception as e:
        raise IOError(f"Error loading configuration file: {e}")
    
    if not isinstance(config, dict):
        raise ValueError(f"Configuration file must contain a JSON object, got {type(config)}")
    
    # Warn if credentials are in plaintext
    fabric_config = config.get('fabric', {})
    if fabric_config.get('client_secret'):
        print("\n⚠️  WARNING: client_secret found in configuration file!")
        print("   For production, use:")
        print("   - Azure Key Vault")
        print("   - Environment variables (set FABRIC_CLIENT_SECRET)")
        print("   - Managed Identity (recommended)\n")
    
    return config


def print_header(title: str, width: int = 60) -> None:
    """Print a formatted header with the given title.
    
    Args:
        title: The title to display in the header.
        width: Total width of the header line.
    """
    print("\n" + "=" * width)
    print(title)
    print("=" * width)


def print_footer(width: int = 60) -> None:
    """Print a footer line.
    
    Args:
        width: Total width of the footer line.
    """
    print("=" * width + "\n")


def format_count_summary(
    items: Dict[str, int],
    prefix: str = "  "
) -> str:
    """Format a dictionary of counts for display.
    
    Args:
        items: Dictionary mapping item names to counts.
        prefix: Prefix string for each line.
        
    Returns:
        Formatted multi-line string.
    """
    lines = []
    for name, count in sorted(items.items(), key=lambda x: -x[1]):
        lines.append(f"{prefix}{name}: {count}")
    return "\n".join(lines)


def confirm_action(
    prompt: str,
    default: bool = False
) -> bool:
    """
    Prompt the user for confirmation.
    
    Args:
        prompt: The prompt message to display.
        default: Default value if user just presses Enter.
        
    Returns:
        True if user confirmed, False otherwise.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    response = input(f"{prompt} {suffix}: ").strip().lower()
    
    if not response:
        return default
    
    return response in ('y', 'yes')


def resolve_dtdl_converter_modes(args: Any) -> Tuple[Any, Any]:
    """Resolve DTDL converter mode enums from CLI arguments.

    Args:
        args: Argument namespace or object with component_mode/command_mode attributes.

    Returns:
        Tuple of (ComponentMode, CommandMode) enums.
    """
    from formats.dtdl import ComponentMode, CommandMode  # Local import to avoid cycles

    component_mode_value = getattr(args, 'component_mode', ComponentMode.SKIP.value)
    command_mode_value = getattr(args, 'command_mode', CommandMode.SKIP.value)

    try:
        component_mode = ComponentMode(component_mode_value)
    except ValueError as exc:  # pragma: no cover - argparse should prevent this
        raise ValueError(f"Unsupported component mode: {component_mode_value}") from exc

    try:
        command_mode = CommandMode(command_mode_value)
    except ValueError as exc:  # pragma: no cover - argparse should prevent this
        raise ValueError(f"Unsupported command mode: {command_mode_value}") from exc

    return component_mode, command_mode
