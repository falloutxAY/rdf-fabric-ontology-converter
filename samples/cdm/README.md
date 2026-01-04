# CDM (Common Data Model) Samples

This directory contains CDM sample files for testing and demonstrating the CDM format plugin.

## Directory Structure

```
samples/cdm/
├── README.md                      # This file
├── simple/                        # Basic examples for learning
│   ├── Person.cdm.json           # Simple entity with attributes
│   ├── Contact.cdm.json          # Entity with more attributes
│   ├── Order.cdm.json            # Entity with relationships
│   ├── simple.manifest.cdm.json  # Manifest file
│   └── model.json                # Legacy format example
│
├── model-json/                    # model.json format examples
│   └── OrdersProducts/
│       └── model.json            # Complete model.json example
│
└── industry/                      # Industry Accelerator samples
    ├── healthcare/               # Healthcare entities
    ├── financial-services/       # Financial services entities
    ├── automotive/               # Automotive entities
    └── education/                # Education entities
```

## Sample Types

### Simple Samples (`simple/`)

Basic CDM examples demonstrating core concepts:

| File | Description |
|------|-------------|
| `Person.cdm.json` | Basic entity with string, integer, boolean attributes |
| `Contact.cdm.json` | Entity with semantic types (email, phone, address) |
| `Order.cdm.json` | Entity demonstrating relationships |
| `simple.manifest.cdm.json` | Manifest referencing all simple entities |
| `model.json` | Legacy model.json format |

### Model.json Samples (`model-json/`)

Legacy model.json format examples for backward compatibility testing.

### Industry Accelerator Samples (`industry/`)

Samples based on Microsoft's Industry Accelerators:

| Industry | Entities | Description |
|----------|----------|-------------|
| Healthcare | Patient, Practitioner, Encounter, Appointment | FHIR-aligned healthcare entities |
| Financial Services | Customer, Account, Transaction, Loan | Banking and financial entities |
| Automotive | Vehicle, Dealer, ServiceAppointment, Lead | Automotive industry entities |
| Education | Student, Course, Enrollment, Institution | Higher education entities |

## Usage Examples

### Validate CDM Files

```bash
# Validate a manifest
python -m src.main validate --format cdm samples/cdm/simple/simple.manifest.cdm.json

# Validate an entity schema
python -m src.main validate --format cdm samples/cdm/simple/Person.cdm.json

# Validate model.json
python -m src.main validate --format cdm samples/cdm/model-json/OrdersProducts/model.json
```

### Convert CDM to Fabric

```bash
# Convert manifest and all entities
python -m src.main convert --format cdm samples/cdm/simple/simple.manifest.cdm.json -o output/

# Convert industry accelerator
python -m src.main convert --format cdm samples/cdm/industry/healthcare/ -o output/healthcare/
```

### Upload to Fabric

```bash
# Upload CDM entities to Fabric
python -m src.main upload --format cdm samples/cdm/simple/simple.manifest.cdm.json
```

## CDM Document Types

### Manifest (`.manifest.cdm.json`)

Entry point that lists entities and relationships:

```json
{
    "manifestName": "MyManifest",
    "jsonSchemaSemanticVersion": "1.0.0",
    "entities": [
        {
            "type": "LocalEntity",
            "entityName": "Person",
            "entityPath": "Person.cdm.json/Person"
        }
    ],
    "relationships": [...]
}
```

### Entity Schema (`.cdm.json`)

Entity definitions with attributes:

```json
{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [{
        "entityName": "Person",
        "hasAttributes": [
            {"name": "personId", "dataType": "string"},
            {"name": "fullName", "dataType": "name"}
        ]
    }]
}
```

### model.json (Legacy)

Flat JSON format for simple scenarios:

```json
{
    "name": "MyModel",
    "version": "1.0",
    "entities": [
        {
            "name": "Product",
            "attributes": [
                {"name": "productId", "dataType": "string"}
            ]
        }
    ]
}
```

## Type Mappings

| CDM Type | Fabric Type |
|----------|-------------|
| `string`, `char` | `String` |
| `integer`, `int64`, `bigInteger` | `BigInt` |
| `double`, `float` | `Double` |
| `decimal` | `Decimal` |
| `boolean` | `Boolean` |
| `dateTime`, `date`, `time` | `DateTime` |
| `GUID`, `uuid` | `String` |
| Semantic types (email, phone, etc.) | Mapped primitive |

## Resources

- [CDM GitHub Repository](https://github.com/microsoft/CDM)
- [CDM Documentation](https://docs.microsoft.com/en-us/common-data-model/)
- [Industry Accelerators](https://docs.microsoft.com/en-us/dynamics365/industry/accelerators/)
- [CDM JSON Schema](https://raw.githubusercontent.com/microsoft/CDM/master/schemaDocuments/schema.cdm.json)
