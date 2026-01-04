# Healthcare Industry Accelerator Samples

This directory contains CDM samples based on Microsoft's Healthcare Industry Accelerator.

## Overview

The Healthcare Accelerator provides FHIR-aligned data models for healthcare scenarios.

## Entities

| Entity | Description |
|--------|-------------|
| `Patient.cdm.json` | Patient demographics and information |
| `Practitioner.cdm.json` | Healthcare practitioner information |
| `Encounter.cdm.json` | Patient encounters/visits |
| `Appointment.cdm.json` | Scheduled appointments |

## Usage

```bash
# Validate healthcare manifest
python -m src.main validate --format cdm samples/cdm/industry/healthcare/healthcare.manifest.cdm.json

# Convert healthcare entities to Fabric
python -m src.main convert --format cdm samples/cdm/industry/healthcare/ -o output/healthcare/
```

## Resources

- [Healthcare Accelerator Documentation](https://learn.microsoft.com/en-us/dynamics365/industry/accelerators/health-overview)
- [FHIR Standard](https://hl7.org/fhir/)
