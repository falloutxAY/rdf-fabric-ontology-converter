# RDF/OWL → Microsoft Fabric Ontology: Mapping Challenges and Non‑1:1 Scenarios

Convertors from RDF/OWL (TTL) to Microsoft Fabric Ontology necessarily simplify certain constructs. RDF/OWL is highly expressive and designed for open‑world, inference‑driven knowledge representation, while Fabric Ontology targets business‑friendly models optimized for data products and analytics. This document explains why conversions are not 1:1, what information can be lost or transformed, and how to mitigate.

## What changes between RDF/OWL and Fabric Ontology?

- Semantics vs structure:
  - RDF/OWL uses description logic and inference (e.g., RDFS/OWL entailments). Many semantics are implicit and only materialize under reasoning.
  - Fabric Ontology encodes explicit classes, properties, and relationships for downstream data use; it does not fully support RDF/OWL constructs.
- Expressivity vs implementability:
  - RDF/OWL supports complex class expressions and property axioms.
  - Fabric Ontology APIs typically provide a constrained type system and relationship model without full OWL semantics.

## Common sources of non‑1:1 mapping (potential loss)

1. Complex class expressions
   - `owl:intersectionOf`, `owl:complementOf`, `owl:oneOf` (enumerations), nested expressions, and blank‑node encodings.
   - Outcome: Often flattened or skipped; exact semantics may be lost.

2. Property restrictions
   - `owl:Restriction` (e.g., `someValuesFrom`, `allValuesFrom`, `hasValue`, min/max/exact cardinality, qualified cardinality).
   - Outcome: Usually not represented; cardinality semantics and constraints are lost.

3. Property characteristics
   - Functional/inverse‑functional, symmetric, transitive, reflexive/irreflexive, asymmetric.
   - Outcome: These are semantic constraints; typically not preserved.

4. Property chains and advanced axioms
   - `owl:propertyChainAxiom`, `owl:equivalentProperty`, `owl:disjointProperty`.
   - Outcome: Not represented; inferable relationships are not materialized.

5. Class axioms
   - `owl:equivalentClass`, `owl:disjointWith`.
   - Outcome: Not carried over; identity/disjointness semantics are lost.

6. Imports and external dependencies
   - `owl:imports` pull in external vocabularies/signatures.
   - Outcome: Unless merged beforehand, dependent semantics are missing in a single TTL file.

7. Implicit signatures
   - Properties without explicit `rdfs:domain`/`rdfs:range` or pointing to classes not declared locally.
   - Outcome: Converter skips such properties to maintain predictable, explicit models.

8. Datatypes and shapes
   - Exotic XSD datatypes, RDF lists, reification, SHACL constraints and validation rules.
   - Outcome: Unsupported datatypes may be mapped to string; shapes and validation are not preserved.

9. Individuals and annotations
   - Named individuals, `owl:sameAs`, annotation properties (labels, comments) vs operational semantics.
   - Outcome: Individuals may be out‑of‑scope; annotations may be partially preserved or ignored depending on tooling.

## Current converter behavior (summary)

- Classes and properties:
  - Declared classes are imported.
  - Datatype properties map to Fabric attributes when their `rdfs:domain` resolves to declared classes.
  - Object properties become Fabric relationships for each resolvable domain–range pair.
- `owl:unionOf` support:
  - Domain and range unions are resolved; each pair yields a distinct relationship type.
- Datatype mapping:
  - Common XSDs are mapped (e.g., string, boolean, integer, decimal, date, dateTime, anyURI, dateTimeStamp, time).
  - Unions or unfamiliar datatypes may conservatively map to `String`.
- Strict semantics:
  - No heuristics; properties without explicit, resolvable `rdfs:domain`/`rdfs:range` are skipped.

## FOAF and similar vocabularies

Some FOAF properties lack explicit domain/range in a single file or depend on external vocabularies. In practice, this yields conversion warnings and round‑trip differences. Example classes and properties that commonly surface issues (observed during testing):

- Skipped object properties due to unresolved signatures: `page`, `depicts`, `topic_interest`, `based_near`, `logo`, `made`, `maker`, `depiction`, `isPrimaryTopicOf`, `primaryTopic`.
- Datatype properties reported as lost: `homepage`, `name` (depending on local declarations and unions).

To improve preservation:
- Add explicit `rdfs:domain` and `rdfs:range` for the needed properties.
- Declare referenced FOAF classes locally or merge FOAF core with your domain ontology.
- Avoid unsupported OWL restrictions unless you extend the converter.

### FOAF strict‑friendly checklist (practical steps)

- Identify required FOAF classes and declare them locally:
  - Common: `foaf:Person`, `foaf:Agent`, `foaf:Organization`, `foaf:Document`, `foaf:Image`, `foaf:Project`.
- Add explicit signatures for the properties you intend to preserve:
  - Examples:
    - `foaf:name` — `rdfs:domain foaf:Person` (or Agents) and `rdfs:range xsd:string`.
    - `foaf:homepage` — `rdfs:domain foaf:Agent` and `rdfs:range xsd:anyURI`.
    - `foaf:depicts`/`foaf:depiction` — choose domains/ranges like `foaf:Image` ↔ `foaf:Agent` (or `foaf:Person`).
    - `foaf:based_near`, `foaf:topic_interest`, `foaf:page`, `foaf:logo`, `foaf:maker`/`foaf:made`, `foaf:primaryTopic`/`foaf:isPrimaryTopicOf` — add explicit `rdfs:domain`/`rdfs:range` and declare target classes locally (e.g., `foaf:Document`, `foaf:Project`).
- Prefer simple constructs:
  - Avoid `owl:Restriction` (e.g., `someValuesFrom`, cardinalities) in converted segments.
  - If unions are needed, use `owl:unionOf` on classes and declare all members.
- Align datatypes with supported mappings:
  - Use common XSDs (e.g., `xsd:string`, `xsd:anyURI`, `xsd:dateTime`, `xsd:boolean`).
- Validate and iterate:
  - Run `roundtrip --save-export` and `compare --verbose` to inspect differences.
  - Set logging to `DEBUG` in `src/config.json` to trace decisions.
  - Address warnings by adding/adjusting property signatures and class declarations.

## Why round‑trip TTL ↔ Fabric ↔ TTL can differ

- Semantic compression: OWL axioms and reasoning effects are not fully representable in Fabric models.
- Normalization: The converter may split union‑implied relationships into multiple explicit edges.
- Skipping unconstrained properties: Without explicit signatures, conversion remains conservative.
- Datatype fallback: Some datatypes are generalized to strings to ensure operability.

## Mitigations and best practices

- Provide explicit property signatures:
  - Ensure `rdfs:domain`/`rdfs:range` resolve to declared classes.
  - Use `owl:unionOf` for class unions; declare all members.
- Merge required vocabularies:
  - If your TTL relies on external ontologies, import and materialize needed class/property declarations into a single file.
- Keep constructs simple:
  - Avoid complex restrictions and chains if the target platform will not use a reasoner.
- Validate iteratively:
  - Use `roundtrip --save-export` and `compare --verbose` to inspect differences.
- Log for insight:
  - Set `logging.level` to `DEBUG` in `src/config.json` to trace decisions.

## Known warnings reference

- "Skipping property … due to unresolved domain/range"
  - Cause: `rdfs:domain`/`rdfs:range` missing or point to classes not declared locally.
  - Fix: Declare the classes; add explicit `rdfs:domain`/`rdfs:range`; use `owl:unionOf` if needed.

- "Unresolved class target …"
  - Cause: A referenced class URI is not found among declared classes in the TTL being converted.
  - Fix: Declare the class locally or merge in the vocabulary that defines it.

- "Unknown XSD datatype … defaulting to String"
  - Cause: Datatype not covered by the converter’s mapping.
  - Fix: Use a supported XSD datatype or extend mappings; for unions of datatypes, expect conservative `String` mapping.

- "Round‑trip differences: lost datatype/object properties"
  - Cause: Properties were skipped during conversion (missing signatures) or normalized differently (e.g., unions expanded into multiple relationships).
  - Fix: Add explicit signatures; verify class declarations; run `compare --verbose` to pinpoint gaps.

- "Unsupported OWL construct … skipping restriction"
  - Cause: `owl:Restriction` or advanced axioms not implemented.
  - Fix: Flatten to explicit properties/relationships with signatures; avoid complex OWL in converted segments.

## References and further reading

- RDF and OWL standards: W3C specifications
- RDFLib documentation: https://github.com/RDFLib/rdflib
- Microsoft Fabric documentation: https://learn.microsoft.com/fabric/
- Project docs:
  - `docs/ERROR_HANDLING_SUMMARY.md`
  - `docs/TROUBLESHOOTING.md`
  - `docs/TESTING.md`

---

This document is informational and reflects practical constraints observed during conversion. Behavior may evolve as Fabric APIs and the converter add capabilities. 