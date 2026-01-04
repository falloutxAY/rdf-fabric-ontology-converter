# Financial Services Industry Accelerator Samples

This directory contains CDM samples based on Microsoft's Financial Services Industry Accelerator.

## Overview

The Financial Services Accelerator provides data models for banking and financial services scenarios.

## Entities

| Entity | Description |
|--------|-------------|
| `Customer.cdm.json` | Banking customer information |
| `Account.cdm.json` | Bank account details |
| `Transaction.cdm.json` | Financial transactions |
| `Loan.cdm.json` | Loan and credit products |

## Usage

```bash
# Validate financial services manifest
python -m src.main validate --format cdm samples/cdm/industry/financial-services/banking.manifest.cdm.json

# Convert to Fabric format
python -m src.main convert --format cdm samples/cdm/industry/financial-services/ -o output/financial/
```

## Resources

- [Financial Services Accelerator](https://learn.microsoft.com/en-us/dynamics365/industry/accelerators/financial-services)
