# Model.json Samples

Legacy `model.json` format examples for backward compatibility with Azure Data Lake.

## Overview

The `model.json` format is an older CDM format used by:
- Azure Data Lake Storage (ADLS)
- Power BI dataflows
- Azure Synapse Analytics

## Files

| Directory | Description |
|-----------|-------------|
| `OrdersProducts/` | Complete e-commerce model with customers, orders, products |

## OrdersProducts Model

A complete e-commerce data model demonstrating the legacy format.

### Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| `Customer` | Customer records | customerId, firstName, lastName, email, phone |
| `Product` | Product catalog | productId, productName, description, price, category |
| `Order` | Customer orders | orderId, customerId, orderDate, totalAmount, status |
| `OrderDetail` | Order line items | orderDetailId, orderId, productId, quantity, unitPrice |
| `Category` | Product categories | categoryId, categoryName, description |

### Relationships

```
Customer ──┬── Order
           └── OrderDetail ──── Product
                              │
Category ─────────────────────┘
```

## Format Comparison

### model.json (Legacy)

```json
{
    "name": "MyModel",
    "version": "1.0",
    "entities": [
        {
            "name": "Product",
            "attributes": [
                { "name": "productId", "dataType": "string" }
            ]
        }
    ]
}
```

### *.cdm.json (Modern)

```json
{
    "jsonSchemaSemanticVersion": "1.0.0",
    "definitions": [
        {
            "entityName": "Product",
            "hasAttributes": [
                { "name": "productId", "dataType": "guid" }
            ]
        }
    ]
}
```

## Usage

### Validate

```powershell
python -m src.main validate --format cdm samples/cdm/model-json/OrdersProducts/model.json
```

### Convert

```powershell
python -m src.main convert --format cdm samples/cdm/model-json/OrdersProducts/model.json -o orders.json
```

### Upload

```powershell
python -m src.main upload --format cdm samples/cdm/model-json/OrdersProducts/ --ontology-name ECommerce
```

## Limitations

The legacy format has some limitations compared to modern `.cdm.json`:

| Feature | model.json | *.cdm.json |
|---------|------------|------------|
| Traits | ❌ Not supported | ✅ Full support |
| Inheritance | ❌ Not supported | ✅ `extendsEntity` |
| Attribute groups | ❌ Not supported | ✅ Supported |
| Semantic types | Limited | Full support |
| Relationships | Via attributes | Explicit in manifest |

## See Also

- [Simple Samples](../simple/) - Modern CDM format examples
- [CDM Guide](../../../docs/CDM_GUIDE.md) - Complete CDM documentation
