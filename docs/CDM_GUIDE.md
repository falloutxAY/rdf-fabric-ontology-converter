# CDM (Common Data Model) to Fabric Ontology Guide

Convert Microsoft Common Data Model (CDM) schemas to Microsoft Fabric Ontology format.

## Overview

The **Common Data Model (CDM)** is a shared data language for business and analytical applications. It provides standardized, extensible data schemas that allow applications to share data consistently.

CDM is used across:
- **Microsoft Dynamics 365** - Customer engagement, finance, operations
- **Power Platform** - Power Apps, Power BI, Power Automate
- **Azure Synapse Analytics** - Data lake storage format
- **Industry Accelerators** - Healthcare, Financial Services, Automotive, Education

## Supported Formats

| File Type | Extension | Description |
|-----------|-----------|-------------|
| Manifest | `*.manifest.cdm.json` | Collection of entities with relationships |
| Entity Schema | `*.cdm.json` | Single entity definition |
| Model.json | `model.json` | Legacy format (Azure Data Lake) |

## Quick Start

```powershell
# Validate CDM manifest
python -m src.main validate --format cdm samples/cdm/simple/simple.manifest.cdm.json --verbose

# Convert to Fabric format
python -m src.main convert --format cdm samples/cdm/simple/simple.manifest.cdm.json --output fabric.json

# Upload to Fabric
python -m src.main upload --format cdm samples/cdm/industry/healthcare/ --ontology-name HealthcareOntology --recursive

# Convert single entity file
python -m src.main convert --format cdm samples/cdm/simple/Person.cdm.json --output person.json
```

## Mapping Reference

### ✅ Fully Supported

| CDM Concept | Fabric Mapping |
|-------------|----------------|
| Entity (`entityName`) | EntityType (`name`) |
| Entity description | EntityType (`description`) |
| Attribute (`hasAttributes`) | EntityTypeProperty (`properties`) |
| Attribute name | EntityTypeProperty (`name`) |
| Attribute description | EntityTypeProperty (`description`) |
| Relationship (manifest) | RelationshipType |
| Entity inheritance (`extendsEntity`) | `baseEntityTypeId` |

### Type Mapping

| CDM Data Type | Fabric Type | Notes |
|---------------|-------------|-------|
| `string`, `char`, `text` | String | |
| `integer`, `int`, `int32`, `int64` | BigInt | |
| `smallInteger`, `bigInteger`, `byte` | BigInt | |
| `float`, `double`, `real` | Double | |
| `decimal`, `numeric`, `money` | Decimal | |
| `boolean`, `bool` | Boolean | |
| `date`, `dateTime`, `time` | DateTime | |
| `dateTimeOffset`, `timestamp` | DateTime | |
| `guid`, `uuid` | String | GUID as string |
| `binary`, `varbinary` | String | Base64 encoded |
| `json`, `object` | String | Serialized JSON |
| `array`, `list` | String | JSON array string |

### Semantic Type Mapping

CDM semantic types (from traits) are mapped to appropriate Fabric types:

| CDM Semantic Type | Fabric Type | Notes |
|-------------------|-------------|-------|
| `name`, `fullName`, `firstName`, `lastName` | String | Person names |
| `email`, `phone`, `url` | String | Contact info |
| `address`, `city`, `country`, `postalCode` | String | Geographic |
| `currency`, `currencyCode` | String | Financial |
| `latitude`, `longitude` | Double | Geospatial |
| `age`, `year` | BigInt | Temporal |
| `image`, `photo` | String | Binary as base64 |

### Relationship Mapping

| CDM Relationship | Fabric Mapping |
|------------------|----------------|
| `fromEntity` | `sourceEntityTypeId` |
| `fromEntityAttribute` | `sourceEntityTypePropertyId` |
| `toEntity` | `targetEntityTypeId` |
| `toEntityAttribute` | `targetEntityTypePropertyId` |
| `exhibitsTraits` | Ignored (metadata only) |

### ⚠️ Limited Support

| Feature | Behavior |
|---------|----------|
| Attribute groups | Expanded inline |
| Multiple inheritance | First parent only |
| Complex traits | Mapped to simple types |
| Reference resolution | Local references only |
| Partition data | Schema only (data ignored) |

### ❌ Not Supported (Skipped)

- **Data partitions** - Only schema is converted
- **Data partition patterns** - Schema only
- **Import statements** - Cross-manifest imports
- **Corpus references** - External entity references
- **Trait definitions** - Traits used for type mapping only
- **Attribute context** - Structural metadata
- **Attribute resolution guidance** - Internal CDM hints

## CDM Document Types

### 1. Manifest Files (*.manifest.cdm.json)

Manifests are the primary entry point for CDM schemas. They define:
- A collection of entities
- Relationships between entities
- Sub-manifests (nested manifests)

```json
{
    "jsonSchemaSemanticVersion": "1.0.0",
    "manifestName": "MyManifest",
    "entities": [
        {
            "entityName": "Customer",
            "entityPath": "Customer.cdm.json/Customer"
        },
        {
            "entityName": "Order",
            "entityPath": "Order.cdm.json/Order"
        }
    ],
    "relationships": [
        {
            "fromEntity": "Order.cdm.json/Order",
            "fromEntityAttribute": "customerId",
            "toEntity": "Customer.cdm.json/Customer",
            "toEntityAttribute": "customerId"
        }
    ]
}
```

### 2. Entity Schema Files (*.cdm.json)

Entity schemas define the structure of a single entity:

```json
{
    "jsonSchemaSemanticVersion": "1.0.0",
    "imports": [
        { "corpusPath": "cdm:/foundations.cdm.json" }
    ],
    "definitions": [
        {
            "entityName": "Customer",
            "extendsEntity": "CdmEntity",
            "description": "Customer information",
            "hasAttributes": [
                {
                    "name": "customerId",
                    "dataType": "guid",
                    "appliedTraits": ["is.dataFormat.guid"]
                },
                {
                    "name": "fullName",
                    "dataType": "name",
                    "description": "Customer's full name"
                },
                {
                    "name": "emailAddress",
                    "dataType": "email"
                }
            ]
        }
    ]
}
```

### 3. Model.json (Legacy Format)

The legacy format used by Azure Data Lake:

```json
{
    "name": "MyModel",
    "version": "1.0",
    "entities": [
        {
            "name": "Product",
            "description": "Product catalog",
            "attributes": [
                {
                    "name": "productId",
                    "dataType": "string"
                },
                {
                    "name": "price",
                    "dataType": "decimal"
                }
            ]
        }
    ]
}
```

## Example Conversions

### Simple Entity

**Input (Person.cdm.json):**
```json
{
    "definitions": [{
        "entityName": "Person",
        "hasAttributes": [
            { "name": "personId", "dataType": "guid" },
            { "name": "firstName", "dataType": "name" },
            { "name": "lastName", "dataType": "name" },
            { "name": "birthDate", "dataType": "date" },
            { "name": "isActive", "dataType": "boolean" }
        ]
    }]
}
```

**Output (Fabric EntityType):**
```json
{
    "name": "Person",
    "namespace": "usertypes",
    "namespaceType": "Custom",
    "properties": [
        { "name": "personId", "valueType": "String" },
        { "name": "firstName", "valueType": "String" },
        { "name": "lastName", "valueType": "String" },
        { "name": "birthDate", "valueType": "DateTime" },
        { "name": "isActive", "valueType": "Boolean" }
    ]
}
```

### Healthcare Industry Entity

**Input (Patient.cdm.json):**
```json
{
    "definitions": [{
        "entityName": "Patient",
        "hasAttributes": [
            { "name": "patientId", "dataType": "guid" },
            { "name": "mrn", "dataType": "string" },
            { "name": "firstName", "dataType": "name" },
            { "name": "lastName", "dataType": "name" },
            { "name": "dateOfBirth", "dataType": "date" },
            { "name": "gender", "dataType": "string" },
            { "name": "primaryPhoneNumber", "dataType": "phone" },
            { "name": "primaryEmailAddress", "dataType": "email" }
        ]
    }]
}
```

**Output:**
- EntityType: `Patient`
- Properties: `patientId` (String), `mrn` (String), `firstName` (String), `lastName` (String), `dateOfBirth` (DateTime), `gender` (String), `primaryPhoneNumber` (String), `primaryEmailAddress` (String)

## Validation Checks

The CDM validator performs these checks:

### Syntax Validation
- ✓ Valid JSON format
- ✓ Required fields present (`entityName` or `name`)
- ✓ Schema version compatibility

### Structure Validation
- ✓ Entity definitions well-formed
- ✓ Attribute definitions complete
- ✓ Relationship references valid

### Semantic Validation
- ✓ Data types recognized
- ✓ Entity references resolvable (local)
- ✓ No circular inheritance

### Fabric Compatibility
- ✓ Property names valid (alphanumeric, underscore)
- ✓ Name lengths within limits
- ✓ No reserved words

## Industry Accelerators

The converter includes samples from Microsoft Industry Accelerators:

### Healthcare
```powershell
python -m src.main convert --format cdm samples/cdm/industry/healthcare/ -o healthcare.json --recursive
```
Entities: Patient, Practitioner, Encounter, Appointment

### Financial Services
```powershell
python -m src.main convert --format cdm samples/cdm/industry/financial-services/ -o banking.json --recursive
```
Entities: Customer, Account, Transaction, Loan

### Automotive
```powershell
python -m src.main convert --format cdm samples/cdm/industry/automotive/ -o automotive.json --recursive
```
Entities: Vehicle, Dealer, ServiceAppointment, Lead

### Education
```powershell
python -m src.main convert --format cdm samples/cdm/industry/education/ -o education.json --recursive
```
Entities: Student, Course, Enrollment, Institution

## Troubleshooting

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid JSON` | Malformed CDM file | Check JSON syntax |
| `No entities found` | Empty or invalid manifest | Verify `entities` array exists |
| `Unknown data type` | Unrecognized CDM type | Maps to String (with warning) |
| `Missing entityName` | Incomplete entity definition | Add `entityName` field |
| `Circular inheritance` | Entity extends itself | Fix entity hierarchy |

### Warnings

| Warning | Meaning |
|---------|---------|
| `Unknown type mapped to String` | CDM type not in mapping table |
| `Trait not processed` | Complex trait skipped |
| `Relationship target not found` | Reference entity missing |
| `Attribute group expanded` | Group converted to flat attributes |

### Debug Mode

Enable verbose logging for troubleshooting:

```powershell
python -m src.main validate --format cdm input.cdm.json --verbose --log-level DEBUG
```

## Configuration

In `config.json`:

```json
{
    "cdm": {
        "strict_validation": true,
        "resolve_references": false,
        "expand_attribute_groups": true,
        "default_namespace": "usertypes"
    }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `strict_validation` | `true` | Fail on unknown types |
| `resolve_references` | `false` | Resolve entity references |
| `expand_attribute_groups` | `true` | Flatten attribute groups |
| `default_namespace` | `"usertypes"` | Default Fabric namespace |

## CLI Commands

### Validate
```powershell
# Single file
python -m src.main validate --format cdm file.cdm.json

# Directory (recursive)
python -m src.main validate --format cdm samples/cdm/ --recursive

# With verbose output
python -m src.main validate --format cdm file.cdm.json --verbose
```

### Convert
```powershell
# Convert manifest
python -m src.main convert --format cdm manifest.cdm.json --output result.json

# Convert directory
python -m src.main convert --format cdm samples/cdm/healthcare/ --output healthcare.json --recursive

# Dry run (validate only)
python -m src.main convert --format cdm file.cdm.json --dry-run
```

### Upload
```powershell
# Upload with auto-generated name
python -m src.main upload --format cdm samples/cdm/simple/

# Upload with specific ontology name
python -m src.main upload --format cdm samples/cdm/ --ontology-name MyCDMOntology
```

## References

- [Common Data Model Documentation](https://learn.microsoft.com/en-us/common-data-model/)
- [CDM SDK Technical Guide](https://learn.microsoft.com/en-us/common-data-model/sdk/overview)
- [CDM Manifest Reference](https://learn.microsoft.com/en-us/common-data-model/sdk/manifest)
- [Industry Accelerators Overview](https://learn.microsoft.com/en-us/dynamics365/industry/accelerators/overview)
- [CDM GitHub Repository](https://github.com/microsoft/CDM)
- [Microsoft Fabric Ontology API](https://learn.microsoft.com/en-us/fabric/)

## See Also

- [DTDL Guide](DTDL_GUIDE.md) - Digital Twins Definition Language conversion
- [RDF Guide](RDF_GUIDE.md) - RDF/OWL ontology conversion
- [Plugin Guide](PLUGIN_GUIDE.md) - Creating custom format plugins
- [CLI Commands](CLI_COMMANDS.md) - Complete command reference
