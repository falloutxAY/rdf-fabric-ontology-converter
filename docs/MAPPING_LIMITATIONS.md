# RDF/OWL → Fabric Ontology: Mapping Limitations

RDF/OWL is highly expressive with inference-driven semantics, while Fabric Ontology targets business-friendly models for data products. Conversions are **not 1:1** — complex OWL constructs are simplified or skipped.

## Pre-flight Validation

Validate TTL files before import to identify compatibility issues:

```powershell
# Quick validation
python src/main.py validate samples/sample_foaf_ontology.ttl --verbose

# Save detailed report
python src/main.py validate samples/sample_foaf_ontology.ttl --output report.json
```

**Upload with validation** (automatic):
```powershell
python src/main.py upload my_ontology.ttl --name "MyOntology"
# Creates import_log_<name>_<timestamp>.json in logs/ if issues detected

# Skip validation: --skip-validation or --force
```

## What's Lost or Transformed

| OWL/RDF Construct | Fabric Conversion | Impact |
|-------------------|-------------------|--------|
| **Property restrictions** (`owl:Restriction`, cardinality) | Skipped | Constraints not enforced |
| **Property characteristics** (transitive, symmetric, functional) | Not preserved | Semantic behavior lost |
| **Complex class expressions** (`owl:intersectionOf`, `owl:complementOf`) | Flattened | Exact semantics simplified |
| **Class axioms** (`owl:equivalentClass`, `owl:disjointWith`) | Skipped | Identity/disjointness lost |
| **Property chains** (`owl:propertyChainAxiom`) | Not materialized | Inferable relationships missing |
| **Imports** (`owl:imports`) | Must be merged | External dependencies unresolved |
| **Implicit signatures** (no `rdfs:domain`/`rdfs:range`) | Skipped | Properties without explicit types ignored |
| **Exotic datatypes** | Map to String | Type precision reduced |
| **Individuals** (`owl:sameAs`) | Out of scope | Instance data not converted |
| **SHACL constraints** | Not preserved | Validation rules lost |

## Converter Behavior

**What's supported:**
- Declared classes → Entity types
- Datatype properties → Attributes (when domain resolves)
- Object properties → Relationships (for each domain-range pair)
- `owl:unionOf`, `owl:intersectionOf`, `owl:complementOf`, `owl:oneOf` (classes extracted)
- Common XSD types: string, boolean, integer, decimal, date, dateTime, anyURI, dateTimeStamp, time
- Cycle detection and depth limiting (max 10) for nested blank nodes

**Strict semantics:**
- Properties **require** explicit `rdfs:domain` and `rdfs:range` pointing to declared classes
- No heuristics for missing signatures

## Common Warnings & Fixes

| Warning | Fix |
|---------|-----|
| "Skipping property due to unresolved domain/range" | Add explicit `rdfs:domain`/`rdfs:range` and declare all referenced classes locally |
| "Unresolved class target" | Declare the class in your TTL or merge the external vocabulary |
| "Unknown XSD datatype, defaulting to String" | Use supported XSD types or accept String fallback |
| "Unsupported OWL construct" | Flatten restrictions to explicit properties with signatures |

## Working with External Vocabularies (e.g., FOAF)

Many vocabularies like FOAF have properties without explicit domain/range or depend on external definitions. **Result:** Skipped properties and round-trip differences.

**To preserve properties:**
1. **Declare classes locally:**
   ```turtle
   foaf:Person a owl:Class .
   foaf:Agent a owl:Class .
   foaf:Document a owl:Class .
   ```

2. **Add explicit signatures:**
   ```turtle
   foaf:name rdfs:domain foaf:Person ; rdfs:range xsd:string .
   foaf:homepage rdfs:domain foaf:Agent ; rdfs:range xsd:anyURI .
   foaf:knows rdfs:domain foaf:Person ; rdfs:range foaf:Person .
   ```

3. **Use `owl:unionOf` for multiple domains/ranges:**
   ```turtle
   foaf:name rdfs:domain [ owl:unionOf (foaf:Person foaf:Organization) ] .
   ```

## Best Practices

✅ **Provide explicit signatures** — Always declare `rdfs:domain` and `rdfs:range` for properties  
✅ **Declare all referenced classes** — Don't rely on external ontologies unless merged  
✅ **Use supported XSD types** — string, boolean, integer, decimal, date, dateTime, anyURI  
✅ **Avoid complex OWL** — Restrictions, property chains, and cardinality constraints aren't preserved  
✅ **Validate iteratively** — Use `upload`, `export`, and `compare --verbose` to verify round-trips  
✅ **Enable debug logging** — Set `logging.level` to `DEBUG` in `src/config.json`

## Round-Trip Differences

TTL → Fabric → TTL conversions may differ due to:
- **Semantic compression** — OWL axioms and inference not fully representable
- **Normalization** — Unions expanded into multiple explicit relationships
- **Conservative skipping** — Properties without explicit signatures omitted
- **Datatype fallback** — Unsupported types mapped to String

## Additional Resources

- [RDFLib documentation](https://github.com/RDFLib/rdflib)
- [Microsoft Fabric documentation](https://learn.microsoft.com/fabric/)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [TESTING.md](TESTING.md) - Test suite

---

*Behavior may evolve as Fabric APIs and converter capabilities expand.*
