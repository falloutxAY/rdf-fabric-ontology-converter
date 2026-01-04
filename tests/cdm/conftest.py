"""
CDM test configuration and shared fixtures.
"""

import pytest
import sys
import os

# Ensure src is in path
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import fixtures from __init__.py
from . import (
    simple_manifest,
    manifest_with_relationships,
    simple_entity_schema,
    entity_with_all_types,
    entity_with_inheritance,
    entity_with_traits,
    model_json,
    invalid_json,
    missing_entity_name,
    duplicate_entity_names,
    unknown_data_types,
)

# Re-export fixtures
__all__ = [
    'simple_manifest',
    'manifest_with_relationships',
    'simple_entity_schema',
    'entity_with_all_types',
    'entity_with_inheritance',
    'entity_with_traits',
    'model_json',
    'invalid_json',
    'missing_entity_name',
    'duplicate_entity_names',
    'unknown_data_types',
]
