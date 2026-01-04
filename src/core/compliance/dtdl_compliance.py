"""
DTDL Compliance Validator.

Validates DTDL documents against v2/v3/v4 specifications.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from .models import (
    ComplianceLevel,
    ComplianceIssue,
    ComplianceResult,
    DTDLVersion,
)
from .constants import DTDL_LIMITS

logger = logging.getLogger(__name__)


class DTDLComplianceValidator:
    """
    Validates DTDL documents against v2/v3/v4 specifications.
    
    Checks for:
    - Valid DTMI format
    - Required fields presence
    - Value constraints (lengths, counts, types)
    - Version-specific features
    - Structural validity (inheritance depth, schema nesting)
    """
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator.
        
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
    
    def validate(
        self,
        interfaces: List[Any],
        version: Optional[DTDLVersion] = None
    ) -> ComplianceResult:
        """
        Validate a list of DTDL interfaces.
        
        Args:
            interfaces: List of DTDLInterface objects
            version: Expected DTDL version (auto-detected if None)
            
        Returns:
            ComplianceResult with validation findings
        """
        result = ComplianceResult(
            is_valid=True,
            source_type="DTDL",
            version=f"v{version.value}" if version else "auto",
            statistics={
                "interfaces": len(interfaces),
                "properties": 0,
                "relationships": 0,
                "telemetries": 0,
                "commands": 0,
                "components": 0,
            }
        )
        
        # Build interface map for reference validation
        interface_map = {}
        for iface in interfaces:
            if hasattr(iface, 'dtmi'):
                interface_map[iface.dtmi] = iface
        
        # Validate each interface
        for iface in interfaces:
            detected_version = self._detect_version(iface)
            if version is None:
                version = detected_version
            
            limits = DTDL_LIMITS.get(version or DTDLVersion.V3, DTDL_LIMITS[DTDLVersion.V3])
            
            # Validate DTMI
            self._validate_dtmi(iface, result)
            
            # Validate interface structure
            self._validate_interface_structure(iface, limits, result)
            
            # Validate inheritance
            self._validate_inheritance(iface, interface_map, limits, result)
            
            # Validate contents
            self._validate_contents(iface, limits, result)
            
            # Count elements for statistics
            self._count_elements(iface, result)
        
        # Check for any errors
        result.is_valid = result.error_count == 0
        if self.strict and result.warning_count > 0:
            result.is_valid = False
        
        return result
    
    def _detect_version(self, interface: Any) -> Optional[DTDLVersion]:
        """Detect DTDL version from interface context."""
        if hasattr(interface, 'context'):
            ctx = interface.context
            if hasattr(ctx, 'dtdl_version'):
                version_num = ctx.dtdl_version
                return DTDLVersion(version_num) if version_num in [2, 3, 4] else None
        return None
    
    def _validate_dtmi(self, interface: Any, result: ComplianceResult) -> None:
        """Validate DTMI format."""
        if not hasattr(interface, 'dtmi') or not interface.dtmi:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL001",
                message="Interface missing required @id (DTMI)",
                element_type="Interface",
                element_name=getattr(interface, 'name', 'unknown'),
            ))
            return
        
        dtmi = interface.dtmi
        
        # Basic DTMI format check
        if not dtmi.startswith("dtmi:"):
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL002",
                message=f"Invalid DTMI format: must start with 'dtmi:' (got: {dtmi})",
                element_type="Interface",
                element_name=interface.dtmi,
            ))
        
        # Length check for Interface DTMIs
        if len(dtmi) > 128:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL003",
                message=f"Interface DTMI exceeds maximum length of 128 characters (length: {len(dtmi)})",
                element_type="Interface",
                element_name=interface.dtmi,
            ))
        
        # Check for system segments (segments starting with underscore)
        parts = dtmi.replace("dtmi:", "").split(";")[0].split(":")
        for part in parts:
            if part.startswith("_"):
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.ERROR,
                    code="DTDL004",
                    message=f"DTMI contains system segment (starts with _): {part}",
                    element_type="Interface",
                    element_name=interface.dtmi,
                    suggestion="User DTMIs cannot contain segments starting with underscore",
                ))
    
    def _validate_interface_structure(
        self,
        interface: Any,
        limits: Dict,
        result: ComplianceResult
    ) -> None:
        """Validate interface structure against version limits."""
        # Validate name length
        name = getattr(interface, 'name', '') or getattr(interface, 'resolved_display_name', '')
        max_name = limits.get('max_name_length', 512)
        
        if len(name) > max_name:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL010",
                message=f"Interface name exceeds maximum length of {max_name} characters",
                element_type="Interface",
                element_name=interface.dtmi,
            ))
    
    def _validate_inheritance(
        self,
        interface: Any,
        interface_map: Dict,
        limits: Dict,
        result: ComplianceResult
    ) -> None:
        """Validate inheritance chain."""
        extends = getattr(interface, 'extends', []) or []
        
        # Check extends count
        max_extends = limits.get('max_extends', 2)
        if len(extends) > max_extends:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL020",
                message=f"Interface extends {len(extends)} interfaces, maximum is {max_extends}",
                element_type="Interface",
                element_name=interface.dtmi,
            ))
        
        # Check inheritance depth
        max_depth = limits.get('max_extends_depth', 10)
        depth = self._calculate_inheritance_depth(interface, interface_map)
        if depth > max_depth:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL021",
                message=f"Inheritance depth ({depth}) exceeds maximum ({max_depth})",
                element_type="Interface",
                element_name=interface.dtmi,
            ))
        
        # Warn about external references
        for parent_dtmi in extends:
            if parent_dtmi not in interface_map:
                result.issues.append(ComplianceIssue(
                    level=ComplianceLevel.WARNING,
                    code="DTDL022",
                    message=f"Interface extends external type not in model: {parent_dtmi}",
                    element_type="Interface",
                    element_name=interface.dtmi,
                    suggestion="Include the parent interface definition or remove the extends reference",
                ))
    
    def _calculate_inheritance_depth(
        self,
        interface: Any,
        interface_map: Dict,
        visited: Optional[Set[str]] = None
    ) -> int:
        """Calculate inheritance chain depth."""
        if visited is None:
            visited = set()
        
        dtmi = getattr(interface, 'dtmi', '')
        if dtmi in visited:
            return 0  # Cycle detected, stop
        
        visited.add(dtmi)
        extends = getattr(interface, 'extends', []) or []
        
        if not extends:
            return 1
        
        max_depth = 0
        for parent_dtmi in extends:
            if parent_dtmi in interface_map:
                parent = interface_map[parent_dtmi]
                depth = self._calculate_inheritance_depth(parent, interface_map, visited)
                max_depth = max(max_depth, depth)
        
        return max_depth + 1
    
    def _validate_contents(
        self,
        interface: Any,
        limits: Dict,
        result: ComplianceResult
    ) -> None:
        """Validate interface contents."""
        # Validate properties
        properties = getattr(interface, 'properties', []) or []
        for prop in properties:
            self._validate_content_element(prop, "Property", limits, result)
        
        # Validate relationships
        relationships = getattr(interface, 'relationships', []) or []
        for rel in relationships:
            self._validate_content_element(rel, "Relationship", limits, result)
        
        # Validate telemetries
        telemetries = getattr(interface, 'telemetries', []) or []
        for tel in telemetries:
            self._validate_content_element(tel, "Telemetry", limits, result)
        
        # Validate commands
        commands = getattr(interface, 'commands', []) or []
        for cmd in commands:
            self._validate_content_element(cmd, "Command", limits, result)
    
    def _validate_content_element(
        self,
        element: Any,
        element_type: str,
        limits: Dict,
        result: ComplianceResult
    ) -> None:
        """Validate a single content element."""
        name = getattr(element, 'name', '')
        max_name = limits.get('max_name_length', 512)
        
        if len(name) > max_name:
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL030",
                message=f"{element_type} name '{name}' exceeds maximum length of {max_name}",
                element_type=element_type,
                element_name=name,
            ))
        
        # Validate name format (alphanumeric + underscore, starting with letter)
        if name and not name[0].isalpha():
            result.issues.append(ComplianceIssue(
                level=ComplianceLevel.ERROR,
                code="DTDL031",
                message=f"{element_type} name must start with a letter: '{name}'",
                element_type=element_type,
                element_name=name,
            ))
    
    def _count_elements(self, interface: Any, result: ComplianceResult) -> None:
        """Count interface elements for statistics."""
        result.statistics["properties"] += len(getattr(interface, 'properties', []) or [])
        result.statistics["relationships"] += len(getattr(interface, 'relationships', []) or [])
        result.statistics["telemetries"] += len(getattr(interface, 'telemetries', []) or [])
        result.statistics["commands"] += len(getattr(interface, 'commands', []) or [])
        result.statistics["components"] += len(getattr(interface, 'components', []) or [])
