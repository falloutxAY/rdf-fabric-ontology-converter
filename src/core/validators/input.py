"""
Input validation utilities for the RDF/DTDL Fabric Ontology Converter.

This module provides centralized input validation with consistent error messages for:
- TTL content validation
- File path validation with security checks
- Parameter type and value checking

Security features:
- Path traversal detection (../ sequences)
- Symlink detection and warning
- Extension validation
- Directory boundary awareness

Usage:
    from core.validators.input import InputValidator
    
    # Validate file path with security checks
    validated_path = InputValidator.validate_file_path(
        path, 
        allowed_extensions=['.ttl', '.rdf'],
        check_exists=True
    )
    
    # Validate TTL content
    content = InputValidator.validate_ttl_content(content)
"""

import os
import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class InputValidator:
    """
    Centralized input validation for RDF converter public methods.
    
    Provides consistent validation with clear error messages for:
    - TTL content validation
    - File path validation with security checks
    - Parameter type and value checking
    
    Security features:
    - Path traversal detection (../ sequences)
    - Symlink detection and warning
    - Extension validation
    - Directory boundary awareness
    """
    
    # Allowed extensions for different file types
    TTL_EXTENSIONS = [
        '.ttl',
        '.rdf',
        '.owl',
        '.n3',
        '.nt',
        '.nq',
        '.nquads',
        '.trig',
        '.trix',
        '.jsonld',
        '.xml',
        '.hext',
        '.html',
        '.xhtml',
        '.htm',
    ]
    JSON_EXTENSIONS = ['.json']
    OUTPUT_EXTENSIONS = ['.ttl', '.json', '.txt', '.md']
    
    @staticmethod
    def validate_ttl_content(content: Any) -> str:
        """
        Validate TTL content parameter.
        
        Args:
            content: Content to validate (should be non-empty string)
            
        Returns:
            Validated content string
            
        Raises:
            ValueError: If content is None or empty
            TypeError: If content is not a string
        """
        if content is None:
            raise ValueError("TTL content cannot be None")
        
        if not isinstance(content, str):
            raise TypeError(f"TTL content must be string, got {type(content).__name__}")
        
        if not content.strip():
            raise ValueError("TTL content cannot be empty or whitespace-only")
        
        return content
    
    @staticmethod
    def _check_path_traversal(path_str: str) -> None:
        """
        Check for path traversal attempts.
        
        Args:
            path_str: Path string to check
            
        Raises:
            ValueError: If path traversal detected
        """
        # Normalize separators for consistent checking
        normalized = path_str.replace('\\', '/')
        
        # Check for obvious traversal patterns
        traversal_patterns = ['../', '..\\', '/..', '\\..']
        for pattern in traversal_patterns:
            if pattern in path_str or pattern in normalized:
                raise ValueError(
                    f"Path traversal detected in path: {path_str}. "
                    f"Paths containing '..' are not allowed for security reasons."
                )
        
        # Also check if resolved path contains '..' components
        try:
            path_obj = Path(path_str)
            # Check each component
            for part in path_obj.parts:
                if part == '..':
                    raise ValueError(
                        f"Path traversal detected in path: {path_str}. "
                        f"Paths containing '..' components are not allowed."
                    )
        except Exception:
            pass  # If Path parsing fails, let later validation catch it
    
    @staticmethod
    def _check_symlink(path_obj: Path, strict: bool = False) -> None:
        """
        Check if path is a symlink.
        
        Args:
            path_obj: Path object to check
            strict: If True, raise exception on symlink; if False, log warning
            
        Raises:
            ValueError: If symlink detected and strict mode enabled
        """
        try:
            if path_obj.is_symlink():
                msg = (
                    f"Security error: Symlink detected: {path_obj}. "
                    f"Symlinks are not allowed for security reasons. "
                    f"Please use the actual file path instead."
                )
                if strict:
                    raise ValueError(msg)
                else:
                    logger.warning(msg)
        except OSError:
            # Some systems may raise OSError when checking symlinks
            if strict:
                raise ValueError(f"Cannot verify symlink status for: {path_obj}")
            pass  # Ignore errors in symlink detection in non-strict mode
    
    @staticmethod
    def _check_directory_boundary(path_obj: Path, warn_only: bool = True) -> None:
        """
        Check if path is outside current working directory.
        
        Args:
            path_obj: Resolved absolute path to check
            warn_only: If True, only log warning; if False, raise exception
        """
        try:
            cwd = Path.cwd().resolve()
            path_obj.relative_to(cwd)
        except ValueError:
            msg = f"Path is outside current directory: {path_obj}"
            if warn_only:
                logger.warning(msg + " (this may be intentional for absolute paths)")
            else:
                raise ValueError(msg + ". Access to paths outside working directory is restricted.")
    
    @classmethod
    def validate_file_path(
        cls, 
        path: Any, 
        allowed_extensions: Optional[List[str]] = None,
        check_exists: bool = True,
        check_readable: bool = True,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate file path for security and correctness.
        
        Security checks performed:
        - Path traversal detection (../)
        - Symlink detection (configurable: warning or hard reject)
        - Directory boundary check (optional enforcement)
        - Extension validation (optional)
        
        Args:
            path: Path to validate (should be non-empty string)
            allowed_extensions: List of allowed extensions (e.g., ['.ttl', '.rdf'])
            check_exists: Whether to verify file exists
            check_readable: Whether to verify file is readable
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks; if False, warn only
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object (resolved to absolute path)
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, traversal detected, or symlink found (if reject_symlinks=True)
            FileNotFoundError: If file doesn't exist (when check_exists=True)
            PermissionError: If file is not readable (when check_readable=True)
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal BEFORE resolving
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                # Also check parts for '..'
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    # Fall back to strict traversal check
                    pass
        if not allow_relative_up:
            # Original strict check
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks (strict by default for input files)
        cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            # Enforce that relative-up stays within cwd
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Existence check
        if check_exists:
            if not path_obj.exists():
                raise FileNotFoundError(f"File not found: {path_obj}")
            
            if not path_obj.is_file():
                raise ValueError(f"Path is not a file: {path_obj}")
        
        # Extension validation
        if allowed_extensions:
            # Normalize extensions to lowercase with leading dot
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Readability check
        if check_readable and check_exists:
            if not os.access(path_obj, os.R_OK):
                raise PermissionError(f"File is not readable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_input_ttl_path(
        cls, 
        path: Any, 
        restrict_to_cwd: bool = False, 
        reject_symlinks: bool = True, 
        allow_relative_up: bool = False
    ) -> Path:
        """
        Validate input TTL/RDF file path.
        
        Convenience method with TTL-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to TTL file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.TTL_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_input_json_path(
        cls, 
        path: Any, 
        restrict_to_cwd: bool = False, 
        reject_symlinks: bool = True, 
        allow_relative_up: bool = False
    ) -> Path:
        """
        Validate input JSON file path.
        
        Convenience method with JSON-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to JSON file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_output_file_path(
        cls, 
        path: Any,
        allowed_extensions: Optional[List[str]] = None,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate output file path for writing.
        
        Similar to validate_file_path but:
        - Does not require file to exist
        - Validates parent directory exists and is writable
        
        Args:
            path: Path for output file
            allowed_extensions: List of allowed extensions
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception if output target is symlink
            allow_relative_up: If True, allow '..' but enforce path stays within cwd
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, or traversal detected
            PermissionError: If parent directory is not writable
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    pass
        if not allow_relative_up:
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks if file exists
        if path_obj.exists():
            cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Extension validation
        if allowed_extensions:
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Check parent directory exists and is writable
        parent_dir = path_obj.parent
        if not parent_dir.exists():
            raise ValueError(f"Parent directory does not exist: {parent_dir}")
        
        if not os.access(parent_dir, os.W_OK):
            raise PermissionError(f"Cannot write to directory: {parent_dir}")
        
        # If file exists, check it's writable
        if path_obj.exists() and not os.access(path_obj, os.W_OK):
            raise PermissionError(f"File exists but is not writable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_config_file_path(cls, path: Any) -> Path:
        """
        Validate configuration file path.
        
        Configuration files have stricter validation:
        - Must be JSON
        - Must be readable
        - Must be in safe location (within cwd)
        - Symlinks are rejected
        
        Args:
            path: Path to config file
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is invalid or outside current directory
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable or symlink detected
        """
        validated_path = cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=True,  # Strict: config must be in cwd
            reject_symlinks=True   # Hard reject symlinks
        )
        
        return validated_path
    
    @staticmethod
    def validate_id_prefix(prefix: Any) -> int:
        """
        Validate ID prefix parameter.
        
        Args:
            prefix: Prefix to validate (should be non-negative integer)
            
        Returns:
            Validated prefix integer
            
        Raises:
            TypeError: If prefix is not an integer
            ValueError: If prefix is negative
        """
        if not isinstance(prefix, int):
            raise TypeError(f"ID prefix must be integer, got {type(prefix).__name__}")
        
        if prefix < 0:
            raise ValueError(f"ID prefix must be non-negative, got {prefix}")
        
        return prefix
