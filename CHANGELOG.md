# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- **DTDL v4 Support**: Full implementation of DTDL version 4 specification features:
  - New `DTDLScaledDecimal` model class for high-precision decimal values
  - New primitive schema types: `byte`, `bytes`, `decimal`, `short`, `uuid`
  - Unsigned integer types: `unsignedByte`, `unsignedShort`, `unsignedInteger`, `unsignedLong`
  - Geospatial schema DTMIs with version 4 suffix
  - Support for `nullable` property on CommandRequest and CommandResponse
  - Updated limits: inheritance depth (12) and complex schema depth (8)
- Shared `src/models/` package with Fabric data classes and converter protocol.
- Community documentation: CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, and CHANGELOG.
- Standards compliance review docs in `review/`.
- New DTDL v4 test suite with 13 comprehensive tests
- **Documentation Structure**: Created consistent documentation with Table of Contents
  - New `docs/RDF_GUIDE.md` parallel to `docs/DTDL_GUIDE.md`
  - Added TOCs to all major docs (API, COMMANDS, CONFIGURATION, TESTING, TROUBLESHOOTING)
  - Renamed MAPPING_LIMITATIONS.md title to clarify it covers both RDF and DTDL
  - Clarified purpose: Format guides have brief limitation summaries, MAPPING_LIMITATIONS.md is the comprehensive reference

### Changed
- **Package Reorganization**: Consolidated folder structure for consistency
  - RDF components moved from `src/converters/` to `src/rdf/` (parallel to `src/dtdl/`)
  - `preflight_validator.py` and `fabric_to_ttl.py` moved into `src/rdf/`
  - `fabric_client.py` moved into `src/core/` (shared infrastructure)
  - Removed duplicate `cancellation.py`, `circuit_breaker.py`, `rate_limiter.py` from `src/` root
  - Removed redundant `src/formats/` package
- **Samples Reorganization**: Consistent folder structure with format-specific subfolders
  - Created `samples/rdf/` for all RDF/TTL ontology samples
  - Moved `samples/sample_*.ttl` files to `samples/rdf/`
  - Consolidated samples from `review/samples/` into main samples folder
  - DTDL samples remain in `samples/dtdl/`
  - Mixed-format use case examples stay in `samples/manufacturingMedical/`
- Updated import paths throughout codebase to use new package structure
- RDF and DTDL converters now import shared models to avoid duplication.
- `DTDLPrimitiveSchema` enum now includes all v4 primitive types including `scaledDecimal`
- Type mapper updated to handle `DTDLScaledDecimal` schema type
- Parser updated to recognize `scaledDecimal` string schema references

### Fixed
- None yet.

## [1.0.0] - 2025-12-01
### Added
- Initial open-source release of RDF & DTDL to Microsoft Fabric import tooling.
