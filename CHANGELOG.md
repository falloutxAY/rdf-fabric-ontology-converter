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

### Changed
- RDF and DTDL converters now import shared models to avoid duplication.
- `DTDLPrimitiveSchema` enum now includes all v4 primitive types including `scaledDecimal`
- Type mapper updated to handle `DTDLScaledDecimal` schema type
- Parser updated to recognize `scaledDecimal` string schema references

### Fixed
- None yet.

## [1.0.0] - 2025-12-01
### Added
- Initial open-source release of RDF & DTDL to Microsoft Fabric import tooling.
