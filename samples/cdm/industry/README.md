# Industry Accelerator Samples

CDM samples based on [Microsoft Industry Accelerators](https://learn.microsoft.com/en-us/dynamics365/industry/accelerators/overview).

## Overview

Microsoft Industry Accelerators provide standardized data models for specific industries:

| Industry | Directory | Description |
|----------|-----------|-------------|
| Healthcare | `healthcare/` | Patient care and clinical data |
| Financial Services | `financial-services/` | Banking and financial transactions |
| Automotive | `automotive/` | Vehicle sales and service |
| Education | `education/` | Student management and courses |

## Quick Start

### Convert All Industries

```powershell
# Healthcare
python -m src.main convert --format cdm samples/cdm/industry/healthcare/ -o healthcare.json --recursive

# Financial Services  
python -m src.main convert --format cdm samples/cdm/industry/financial-services/ -o banking.json --recursive

# Automotive
python -m src.main convert --format cdm samples/cdm/industry/automotive/ -o automotive.json --recursive

# Education
python -m src.main convert --format cdm samples/cdm/industry/education/ -o education.json --recursive
```

### Validate All

```powershell
python -m src.main validate --format cdm samples/cdm/industry/ --recursive --verbose
```

## Industry Summaries

### Healthcare

Entities for patient care management:

| Entity | Description |
|--------|-------------|
| Patient | Patient demographics and medical identifiers |
| Practitioner | Healthcare providers (doctors, nurses) |
| Encounter | Patient visits and admissions |
| Appointment | Scheduled appointments |

Key relationships: Patient → Encounter, Practitioner → Encounter

### Financial Services

Entities for banking operations:

| Entity | Description |
|--------|-------------|
| Customer | Bank customers and KYC data |
| Account | Bank accounts (checking, savings) |
| Transaction | Financial transactions |
| Loan | Loan products and terms |

Key relationships: Customer → Account → Transaction, Customer → Loan

### Automotive

Entities for dealership operations:

| Entity | Description |
|--------|-------------|
| Vehicle | Vehicle inventory |
| Dealer | Dealership information |
| ServiceAppointment | Service bookings |
| Lead | Sales leads |

Key relationships: Dealer → Vehicle, Vehicle → ServiceAppointment

### Education

Entities for academic institutions:

| Entity | Description |
|--------|-------------|
| Student | Student records |
| Course | Course catalog |
| Enrollment | Course registrations |
| Institution | Educational institutions |

Key relationships: Student → Enrollment → Course, Institution → Course

## Type Mappings

Industry accelerators use semantic types that map to Fabric:

| Semantic Type | Fabric Type | Usage |
|---------------|-------------|-------|
| `mrn` (Medical Record Number) | String | Healthcare |
| `accountNumber` | String | Financial |
| `vin` (Vehicle ID Number) | String | Automotive |
| `studentId` | String | Education |
| `currency`, `money` | Decimal | Financial |
| `date`, `dateTime` | DateTime | All |

## References

- [Healthcare Accelerator](https://learn.microsoft.com/en-us/dynamics365/industry/healthcare/overview)
- [Financial Services Accelerator](https://learn.microsoft.com/en-us/dynamics365/industry/financial-services/overview)
- [Automotive Accelerator](https://learn.microsoft.com/en-us/dynamics365/industry/automotive/overview)
- [Education Accelerator](https://github.com/microsoft/Industry-Accelerator-Education)

## See Also

- [Simple Samples](../simple/) - Basic CDM examples
- [CDM Guide](../../../docs/CDM_GUIDE.md) - Complete CDM documentation
