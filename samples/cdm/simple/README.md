# Simple CDM Samples

Basic CDM examples demonstrating core concepts for learning and testing.

## Files

| File | Type | Description |
|------|------|-------------|
| `Person.cdm.json` | Entity | Basic entity with string, integer, boolean, date attributes |
| `Contact.cdm.json` | Entity | Entity with semantic types (email, phone, address) |
| `Order.cdm.json` | Entity | Multi-entity file with Order and OrderLine |
| `simple.manifest.cdm.json` | Manifest | References all entities with relationships |
| `model.json` | Legacy | model.json format example |

## Entity Descriptions

### Person.cdm.json

A basic person entity with common attributes:

| Attribute | Data Type | Description |
|-----------|-----------|-------------|
| `personId` | guid | Unique identifier |
| `firstName` | name | Person's first name |
| `lastName` | name | Person's last name |
| `fullName` | name | Full name |
| `dateOfBirth` | date | Birth date |
| `age` | integer | Age in years |
| `isActive` | boolean | Active status |
| `createdDate` | dateTime | Record creation date |
| `modifiedDate` | dateTime | Last modification date |

### Contact.cdm.json

Entity demonstrating semantic types for contact information:

| Attribute | Data Type | Description |
|-----------|-----------|-------------|
| `contactId` | guid | Unique identifier |
| `emailAddress` | email | Primary email |
| `phoneNumber` | phone | Primary phone |
| `streetAddress` | address | Street address |
| `city` | city | City name |
| `stateProvince` | string | State or province |
| `postalCode` | postalCode | Postal/ZIP code |
| `country` | country | Country name |
| `websiteUrl` | url | Website URL |

### Order.cdm.json

Multi-entity file with parent-child relationship:

**Order Entity:**
| Attribute | Data Type | Description |
|-----------|-----------|-------------|
| `orderId` | guid | Order identifier |
| `customerId` | guid | Reference to customer |
| `orderDate` | dateTime | Order timestamp |
| `totalAmount` | decimal | Order total |
| `currency` | currency | Currency code |
| `status` | string | Order status |

**OrderLine Entity:**
| Attribute | Data Type | Description |
|-----------|-----------|-------------|
| `orderLineId` | guid | Line item identifier |
| `orderId` | guid | Parent order reference |
| `productId` | guid | Product reference |
| `quantity` | integer | Quantity ordered |
| `unitPrice` | decimal | Price per unit |
| `lineTotal` | decimal | Line item total |

### model.json (Legacy Format)

Demonstrates the legacy model.json format used by Azure Data Lake:

**Entities:**
- `Product` - Product catalog with name, description, price
- `Category` - Product categories
- `Supplier` - Supplier information

## Relationships

The manifest defines these relationships:

| From Entity | From Attribute | To Entity | To Attribute |
|-------------|----------------|-----------|--------------|
| Contact | personId | Person | personId |
| Order | customerId | Person | personId |
| OrderLine | orderId | Order | orderId |
| OrderLine | productId | Product | productId |

## Usage

### Validate

```powershell
# Validate single entity
python -m src.main validate --format cdm samples/cdm/simple/Person.cdm.json

# Validate manifest
python -m src.main validate --format cdm samples/cdm/simple/simple.manifest.cdm.json

# Validate all files
python -m src.main validate --format cdm samples/cdm/simple/ --recursive
```

### Convert

```powershell
# Convert single entity
python -m src.main convert --format cdm samples/cdm/simple/Person.cdm.json -o person.json

# Convert manifest (all entities + relationships)
python -m src.main convert --format cdm samples/cdm/simple/simple.manifest.cdm.json -o simple.json

# Convert legacy model.json
python -m src.main convert --format cdm samples/cdm/simple/model.json -o model_output.json
```

### Upload to Fabric

```powershell
python -m src.main upload --format cdm samples/cdm/simple/simple.manifest.cdm.json --ontology-name SimpleOntology
```

## Expected Output

Converting `Person.cdm.json` produces:

```json
{
  "entity_types": [
    {
      "name": "Person",
      "namespace": "usertypes",
      "namespaceType": "Custom",
      "properties": [
        { "name": "personId", "valueType": "String" },
        { "name": "firstName", "valueType": "String" },
        { "name": "lastName", "valueType": "String" },
        { "name": "fullName", "valueType": "String" },
        { "name": "dateOfBirth", "valueType": "DateTime" },
        { "name": "age", "valueType": "BigInt" },
        { "name": "isActive", "valueType": "Boolean" },
        { "name": "createdDate", "valueType": "DateTime" },
        { "name": "modifiedDate", "valueType": "DateTime" }
      ]
    }
  ]
}
```

## See Also

- [CDM Guide](../../../docs/CDM_GUIDE.md) - Complete CDM documentation
- [Industry Samples](../industry/) - Complex industry-specific samples
