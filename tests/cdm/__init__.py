"""
CDM test fixtures and configuration.

This module provides test fixtures for CDM format testing.
"""

import pytest

# =============================================================================
# CDM Manifest Fixtures
# =============================================================================

SIMPLE_MANIFEST = """{
    "manifestName": "TestManifest",
    "jsonSchemaSemanticVersion": "1.0.0",
    "entities": [
        {
            "type": "LocalEntity",
            "entityName": "Person",
            "entityPath": "Person.cdm.json/Person"
        }
    ],
    "relationships": []
}"""

MANIFEST_WITH_RELATIONSHIPS = """{
    "manifestName": "SalesManifest",
    "jsonSchemaSemanticVersion": "1.0.0",
    "entities": [
        {
            "type": "LocalEntity",
            "entityName": "Customer",
            "entityPath": "Customer.cdm.json/Customer"
        },
        {
            "type": "LocalEntity",
            "entityName": "Order",
            "entityPath": "Order.cdm.json/Order"
        }
    ],
    "relationships": [
        {
            "fromEntity": "Order/Order.cdm.json/Order",
            "fromEntityAttribute": "customerId",
            "toEntity": "Customer/Customer.cdm.json/Customer",
            "toEntityAttribute": "customerId",
            "exhibitsTraits": [
                {
                    "traitReference": "means.relationship.verbPhrase",
                    "arguments": [{"value": "placedBy"}]
                }
            ]
        }
    ]
}"""


# =============================================================================
# CDM Entity Schema Fixtures
# =============================================================================

SIMPLE_ENTITY_SCHEMA = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "imports": [
        {"corpusPath": "/foundations.cdm.json"}
    ],
    "definitions": [
        {
            "entityName": "Person",
            "extendsEntity": "CdmEntity",
            "description": "A person entity",
            "hasAttributes": [
                {
                    "name": "personId",
                    "dataType": "string",
                    "appliedTraits": ["means.identity.entityId"],
                    "purpose": "identifiedBy"
                },
                {
                    "name": "fullName",
                    "dataType": "name",
                    "appliedTraits": ["means.identity.person.fullName"],
                    "purpose": "namedBy"
                },
                {
                    "name": "email",
                    "dataType": "email",
                    "description": "Contact email address"
                },
                {
                    "name": "age",
                    "dataType": "integer"
                },
                {
                    "name": "isActive",
                    "dataType": "boolean"
                }
            ]
        }
    ]
}"""

ENTITY_WITH_ALL_TYPES = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "entityName": "TypeTest",
            "hasAttributes": [
                {"name": "stringAttr", "dataType": "string"},
                {"name": "intAttr", "dataType": "integer"},
                {"name": "int64Attr", "dataType": "int64"},
                {"name": "doubleAttr", "dataType": "double"},
                {"name": "floatAttr", "dataType": "float"},
                {"name": "decimalAttr", "dataType": "decimal"},
                {"name": "boolAttr", "dataType": "boolean"},
                {"name": "dateAttr", "dataType": "date"},
                {"name": "dateTimeAttr", "dataType": "dateTime"},
                {"name": "guidAttr", "dataType": "GUID"},
                {"name": "nameAttr", "dataType": "name"},
                {"name": "emailAttr", "dataType": "email"},
                {"name": "phoneAttr", "dataType": "phone"},
                {"name": "urlAttr", "dataType": "url"},
                {"name": "currencyAttr", "dataType": "currency"},
                {"name": "yearAttr", "dataType": "year"}
            ]
        }
    ]
}"""

ENTITY_WITH_INHERITANCE = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "entityName": "BaseEntity",
            "hasAttributes": [
                {"name": "id", "dataType": "string", "purpose": "identifiedBy"},
                {"name": "createdOn", "dataType": "dateTime"}
            ]
        },
        {
            "entityName": "DerivedEntity",
            "extendsEntity": "BaseEntity",
            "hasAttributes": [
                {"name": "derivedField", "dataType": "string"}
            ]
        }
    ]
}"""

ENTITY_WITH_TRAITS = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "entityName": "Product",
            "exhibitsTraits": [
                "is.CDM.entityVersion",
                {
                    "traitReference": "is.localized.describedAs",
                    "arguments": [{"value": "Product information"}]
                }
            ],
            "hasAttributes": [
                {
                    "name": "productCode",
                    "dataType": "string",
                    "appliedTraits": [
                        "means.identity.entityId",
                        {
                            "traitReference": "is.constrained.length",
                            "arguments": [
                                {"name": "maximumLength", "value": 50}
                            ]
                        }
                    ]
                },
                {
                    "name": "price",
                    "dataType": "decimal",
                    "appliedTraits": ["means.measurement.currency"]
                }
            ]
        }
    ]
}"""


# =============================================================================
# Legacy model.json Fixtures
# =============================================================================

MODEL_JSON = """{
    "name": "TestModel",
    "version": "1.0",
    "entities": [
        {
            "$type": "LocalEntity",
            "name": "Product",
            "description": "Product catalog",
            "attributes": [
                {"name": "productId", "dataType": "string"},
                {"name": "productName", "dataType": "string"},
                {"name": "price", "dataType": "decimal"},
                {"name": "quantity", "dataType": "integer"}
            ]
        },
        {
            "$type": "LocalEntity",
            "name": "Category",
            "attributes": [
                {"name": "categoryId", "dataType": "string"},
                {"name": "categoryName", "dataType": "string"}
            ]
        }
    ]
}"""


# =============================================================================
# Invalid Content Fixtures
# =============================================================================

INVALID_JSON = """{ invalid json content """

MISSING_ENTITY_NAME = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "hasAttributes": [
                {"name": "field1", "dataType": "string"}
            ]
        }
    ]
}"""

DUPLICATE_ENTITY_NAMES = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {"entityName": "DuplicateEntity", "hasAttributes": []},
        {"entityName": "DuplicateEntity", "hasAttributes": []}
    ]
}"""

UNKNOWN_DATA_TYPES = """{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "entityName": "UnknownTypes",
            "hasAttributes": [
                {"name": "customType", "dataType": "myCustomType"},
                {"name": "binaryType", "dataType": "binary"}
            ]
        }
    ]
}"""


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def simple_manifest():
    """Simple CDM manifest for testing."""
    return SIMPLE_MANIFEST


@pytest.fixture
def manifest_with_relationships():
    """CDM manifest with relationships."""
    return MANIFEST_WITH_RELATIONSHIPS


@pytest.fixture
def simple_entity_schema():
    """Simple CDM entity schema."""
    return SIMPLE_ENTITY_SCHEMA


@pytest.fixture
def entity_with_all_types():
    """Entity with all supported data types."""
    return ENTITY_WITH_ALL_TYPES


@pytest.fixture
def entity_with_inheritance():
    """Entity demonstrating inheritance."""
    return ENTITY_WITH_INHERITANCE


@pytest.fixture
def entity_with_traits():
    """Entity with various traits."""
    return ENTITY_WITH_TRAITS


@pytest.fixture
def model_json():
    """Legacy model.json format."""
    return MODEL_JSON


@pytest.fixture
def invalid_json():
    """Invalid JSON content."""
    return INVALID_JSON


@pytest.fixture
def missing_entity_name():
    """Entity missing required name."""
    return MISSING_ENTITY_NAME


@pytest.fixture
def duplicate_entity_names():
    """Duplicate entity names."""
    return DUPLICATE_ENTITY_NAMES


@pytest.fixture
def unknown_data_types():
    """Entity with unknown data types."""
    return UNKNOWN_DATA_TYPES
