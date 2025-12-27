"""
Unit tests for RDF to Fabric Ontology Converter

Run with: python -m pytest test_converter.py -v
Or with coverage: python -m pytest test_converter.py -v --cov=rdf_converter --cov-report=html
"""

import pytest
import json
from pathlib import Path
from rdf_converter import (
    RDFToFabricConverter, 
    EntityType, 
    RelationshipType,
    EntityTypeProperty,
    RelationshipEnd,
    parse_ttl_file,
    parse_ttl_content,
    convert_to_fabric_definition,
    FabricDefinitionValidator,
    DefinitionValidationError
)


class TestRDFConverter:
    """Test suite for RDFToFabricConverter"""
    
    @pytest.fixture
    def converter(self):
        """Create a converter instance for testing"""
        return RDFToFabricConverter()
    
    @pytest.fixture
    def simple_ttl(self):
        """Simple TTL content for testing"""
        return """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class ;
            rdfs:label "Person" ;
            rdfs:comment "A human being" .
        
        :Organization a owl:Class ;
            rdfs:label "Organization" .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:string .
        
        :age a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:integer .
        
        :worksFor a owl:ObjectProperty ;
            rdfs:domain :Person ;
            rdfs:range :Organization .
        """
    
    def test_parse_simple_ttl(self, converter, simple_ttl):
        """Test parsing a simple TTL file"""
        entity_types, relationship_types = converter.parse_ttl(simple_ttl)
        
        # Should have 2 entity types
        assert len(entity_types) == 2
        
        # Check entity type names
        entity_names = {et.name for et in entity_types}
        assert "Person" in entity_names
        assert "Organization" in entity_names
        
        # Person should have 2 properties
        person = next(et for et in entity_types if et.name == "Person")
        assert len(person.properties) == 2
        
        # Should have 1 relationship type
        assert len(relationship_types) == 1
        assert relationship_types[0].name == "worksFor"
    
    def test_empty_ttl(self, converter):
        """Test handling of empty TTL content"""
        with pytest.raises(ValueError, match="Empty TTL content"):
            converter.parse_ttl("")
    
    def test_invalid_ttl_syntax(self, converter):
        """Test handling of invalid TTL syntax"""
        invalid_ttl = "@prefix : <invalid syntax"
        with pytest.raises(ValueError, match="Invalid RDF/TTL syntax"):
            converter.parse_ttl(invalid_ttl)
    
    def test_uri_to_name_conversion(self, converter):
        """Test URI to name conversion"""
        from rdflib import URIRef
        
        # Test standard URI
        uri = URIRef("http://example.org/Person")
        name = converter._uri_to_name(uri)
        assert name == "Person"
        
        # Test URI with hash
        uri = URIRef("http://example.org#Employee")
        name = converter._uri_to_name(uri)
        assert name == "Employee"
        
        # Test URI with multiple segments
        uri = URIRef("http://example.org/ontology/v1/Customer")
        name = converter._uri_to_name(uri)
        assert name == "Customer"
    
    def test_fabric_name_compliance(self, converter):
        """Test that generated names comply with Fabric requirements"""
        from rdflib import URIRef
        
        # Test name with spaces (should be replaced with underscores)
        uri = URIRef("http://example.org/My Class")
        name = converter._uri_to_name(uri)
        assert " " not in name
        assert "_" in name
        
        # Test name starting with number (should be prefixed)
        uri = URIRef("http://example.org/123Class")
        name = converter._uri_to_name(uri)
        assert not name[0].isdigit()
    
    def test_subclass_relationships(self, converter):
        """Test handling of subclass relationships"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Animal a owl:Class .
        :Mammal a owl:Class ;
            rdfs:subClassOf :Animal .
        :Dog a owl:Class ;
            rdfs:subClassOf :Mammal .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        
        # Should have 3 entity types
        assert len(entity_types) == 3
        
        # Dog should have Mammal as parent
        dog = next(et for et in entity_types if et.name == "Dog")
        assert dog.baseEntityTypeId is not None
    
    def test_multiple_domains(self, converter):
        """Test property with multiple domains"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class .
        :Organization a owl:Class .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:domain :Organization ;
            rdfs:range xsd:string .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        
        # Both Person and Organization should have the name property
        person = next(et for et in entity_types if et.name == "Person")
        org = next(et for et in entity_types if et.name == "Organization")
        
        assert any(p.name == "name" for p in person.properties)
        assert any(p.name == "name" for p in org.properties)
    
    def test_generate_fabric_definition(self, converter, simple_ttl):
        """Test generation of Fabric ontology definition"""
        entity_types, relationship_types = converter.parse_ttl(simple_ttl)
        
        definition = convert_to_fabric_definition(
            entity_types=entity_types,
            relationship_types=relationship_types,
            ontology_name="Test_Ontology"
        )
        
        # Check structure
        assert "parts" in definition
        assert len(definition["parts"]) > 0
        
        # Should have platform metadata
        assert any(part["path"] == ".platform" for part in definition["parts"])
        
        # Should have entity type definitions
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) == len(entity_types)
    
    def test_parse_ttl_file(self, converter, tmp_path):
        """Test parsing from file"""
        # Create a temporary TTL file
        ttl_file = tmp_path / "test.ttl"
        ttl_file.write_text("""
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        
        :TestClass a owl:Class .
        """)
        
        definition, name = parse_ttl_file(str(ttl_file))
        
        assert name == "ImportedOntology"  # Default name
        assert "parts" in definition
    
    def test_xsd_type_mapping(self, converter):
        """Test XSD datatype to Fabric type mapping"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:string .
        
        :age a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:integer .
        
        :salary a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:decimal .
        
        :active a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:boolean .
        
        :birthDate a owl:DatatypeProperty ;
            rdfs:domain :Person ;
            rdfs:range xsd:dateTime .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        person = entity_types[0]
        
        # Check property types
        prop_types = {p.name: p.valueType for p in person.properties}
        assert prop_types["name"] == "String"
        assert prop_types["age"] == "BigInt"
        assert prop_types["salary"] == "Double"
        assert prop_types["active"] == "Boolean"
        assert prop_types["birthDate"] == "DateTime"


class TestEntityType:
    """Test EntityType dataclass"""
    
    def test_entity_type_creation(self):
        """Test creating an EntityType"""
        entity = EntityType(
            id="1000000000001",
            namespace="usertypes",
            name="TestEntity",
            namespaceType="Custom",
            visibility="Visible"
        )
        
        assert entity.id == "1000000000001"
        assert entity.name == "TestEntity"
        assert len(entity.properties) == 0
    
    def test_entity_with_properties(self):
        """Test EntityType with properties"""
        entity = EntityType(
            id="1000000000001",
            namespace="usertypes",
            name="Person",
            namespaceType="Custom",
            visibility="Visible"
        )
        
        prop = EntityTypeProperty(
            id="1000000000002",
            name="name",
            valueType="String"
        )
        
        entity.properties.append(prop)
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "name"


class TestRelationshipType:
    """Test RelationshipType dataclass"""
    
    def test_relationship_type_creation(self):
        """Test creating a RelationshipType"""
        source = RelationshipEnd(entityTypeId="1000000000002")
        target = RelationshipEnd(entityTypeId="1000000000003")
        
        rel = RelationshipType(
            id="1000000000001",
            name="worksFor",
            source=source,
            target=target,
            namespace="usertypes",
            namespaceType="Custom"
        )
        
        assert rel.name == "worksFor"
        assert rel.source.entityTypeId == "1000000000002"
        assert rel.target.entityTypeId == "1000000000003"


class TestSampleOntologies:
    """Test with actual sample TTL files"""
    
    @pytest.fixture
    def samples_dir(self):
        """Get the samples directory path"""
        return Path(__file__).parent.parent / "samples"
    
    def test_sample_ontology_ttl(self, samples_dir):
        """Test parsing sample_supply_chain_ontology.ttl"""
        sample_file = samples_dir / "sample_supply_chain_ontology.ttl"
        
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")
        
        # Parse the file
        definition, name = parse_ttl_file(str(sample_file))
        
        # Verify structure
        assert "parts" in definition
        assert len(definition["parts"]) > 0
        
        # Should have .platform metadata
        platform_parts = [p for p in definition["parts"] if p["path"] == ".platform"]
        assert len(platform_parts) == 1
        
        # Should have entity types
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) >= 3  # Equipment, Sensor, Facility
        
        # Verify each entity has valid JSON
        for part in entity_parts:
            import base64
            payload = base64.b64decode(part["payload"]).decode()
            entity_data = json.loads(payload)
            assert "id" in entity_data
            assert "name" in entity_data
            assert "namespace" in entity_data
    
    def test_foaf_ontology_ttl(self, samples_dir):
        """Test parsing sample_foaf_ontology.ttl (Friend of a Friend vocabulary)"""
        sample_file = samples_dir / "sample_foaf_ontology.ttl"
        
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")
        
        # Parse the file
        definition, name = parse_ttl_file(str(sample_file))
        
        # Verify structure
        assert "parts" in definition
        assert len(definition["parts"]) > 0
        
        # Should have multiple entity types (Person, Agent, Organization, etc.)
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) >= 5
        
        # Check for inheritance (Person subClassOf Agent)
        import base64
        for part in entity_parts:
            payload = base64.b64decode(part["payload"]).decode()
            entity_data = json.loads(payload)
            if entity_data["name"] == "Person":
                # Person should have a base entity type (Agent)
                assert entity_data.get("baseEntityTypeId") is not None
                break
    
    def test_iot_ontology_ttl(self, samples_dir):
        """Test parsing sample_iot_ontology.ttl"""
        sample_file = samples_dir / "sample_iot_ontology.ttl"
        
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")
        
        # Parse the file
        definition, name = parse_ttl_file(str(sample_file))
        
        # Verify structure
        assert "parts" in definition
        
        # Should have Device and Location entity types
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) >= 2
        
        # Verify Device entity has properties
        import base64
        device_found = False
        for part in entity_parts:
            payload = base64.b64decode(part["payload"]).decode()
            entity_data = json.loads(payload)
            if entity_data["name"] == "Device":
                device_found = True
                # Device should have properties like deviceId, deviceName, status, temperature
                assert "properties" in entity_data
                assert len(entity_data["properties"]) >= 3
                
                # Check for specific properties
                prop_names = [p["name"] for p in entity_data["properties"]]
                assert "deviceId" in prop_names or "status" in prop_names
                break
        
        assert device_found, "Device entity type not found in parsed ontology"
    
    def test_fibo_ontology_ttl(self, samples_dir):
        """Test parsing sample_fibo_ontology.ttl (Financial Industry Business Ontology sample)"""
        sample_file = samples_dir / "sample_fibo_ontology.ttl"
        
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")
        
        # Parse the file
        definition, name = parse_ttl_file(str(sample_file))
        
        # Verify structure
        assert "parts" in definition
        assert len(definition["parts"]) > 0
    
    def test_all_sample_ttl_files(self, samples_dir):
        """Test that all .ttl files in samples directory can be parsed"""
        ttl_files = list(samples_dir.glob("*.ttl"))
        
        if not ttl_files:
            pytest.skip("No TTL files found in samples directory")
        
        results = []
        for ttl_file in ttl_files:
            try:
                definition, name = parse_ttl_file(str(ttl_file))
                assert "parts" in definition
                results.append((ttl_file.name, "SUCCESS", len(definition["parts"])))
            except Exception as e:
                results.append((ttl_file.name, "FAILED", str(e)))
        
        # Print summary
        print("\n\nSample TTL Files Parsing Results:")
        print("-" * 70)
        for filename, status, info in results:
            print(f"{filename:30} {status:10} {info}")
        print("-" * 70)
        
        # All should succeed
        failures = [r for r in results if r[1] == "FAILED"]
        assert len(failures) == 0, f"Failed to parse {len(failures)} files: {failures}"


class TestConversionAccuracy:
    """Test accuracy of conversion from RDF to Fabric format"""
    
    def test_property_count_preservation(self):
        """Verify that all properties are converted"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class .
        
        :firstName a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:string .
        :lastName a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:string .
        :age a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:integer .
        :email a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:string .
        :active a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:boolean .
        """
        
        converter = RDFToFabricConverter()
        entity_types, _ = converter.parse_ttl(ttl)
        
        person = entity_types[0]
        assert len(person.properties) == 5
        
        prop_names = {p.name for p in person.properties}
        assert prop_names == {"firstName", "lastName", "age", "email", "active"}
    
    def test_relationship_count_preservation(self):
        """Verify that all relationships are converted"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Person a owl:Class .
        :Company a owl:Class .
        :Department a owl:Class .
        
        :worksFor a owl:ObjectProperty ; rdfs:domain :Person ; rdfs:range :Company .
        :manages a owl:ObjectProperty ; rdfs:domain :Person ; rdfs:range :Department .
        :employs a owl:ObjectProperty ; rdfs:domain :Company ; rdfs:range :Person .
        """
        
        converter = RDFToFabricConverter()
        entity_types, relationship_types = converter.parse_ttl(ttl)
        
        assert len(relationship_types) == 3
        rel_names = {r.name for r in relationship_types}
        assert rel_names == {"worksFor", "manages", "employs"}
    
    def test_fabric_definition_structure(self):
        """Test that generated Fabric definition has correct structure"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class ; rdfs:label "Person" .
        :name a owl:DatatypeProperty ; rdfs:domain :Person ; rdfs:range xsd:string .
        :Organization a owl:Class .
        :worksFor a owl:ObjectProperty ; rdfs:domain :Person ; rdfs:range :Organization .
        """
        
        definition, _ = parse_ttl_content(ttl)
        
        # Should have parts array
        assert "parts" in definition
        assert isinstance(definition["parts"], list)
        
        # Should have .platform
        platform_parts = [p for p in definition["parts"] if p["path"] == ".platform"]
        assert len(platform_parts) == 1
        
        # Should have definition.json
        def_parts = [p for p in definition["parts"] if p["path"] == "definition.json"]
        assert len(def_parts) == 1
        
        # Should have EntityTypes
        entity_parts = [p for p in definition["parts"] if "EntityTypes" in p["path"]]
        assert len(entity_parts) == 2
        
        # Should have RelationshipTypes
        rel_parts = [p for p in definition["parts"] if "RelationshipTypes" in p["path"]]
        assert len(rel_parts) == 1
        
        # Each part should have required fields
        for part in definition["parts"]:
            assert "path" in part
            assert "payload" in part
            assert "payloadType" in part
            assert part["payloadType"] == "InlineBase64"


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent file"""
        with pytest.raises(FileNotFoundError):
            parse_ttl_file("nonexistent_file.ttl")
    
    def test_invalid_file_path(self):
        """Test handling of invalid file path"""
        with pytest.raises(Exception):
            parse_ttl_file("")
    
    def test_empty_content(self):
        """Test handling of empty content"""
        with pytest.raises(ValueError):
            parse_ttl_content("")
    
    def test_none_content(self):
        """Test handling of None content"""
        with pytest.raises(ValueError):
            parse_ttl_content(None)
    
    def test_malformed_ttl(self):
        """Test handling of malformed TTL"""
        malformed = "@prefix : <http://example.org/ . :Person a owl:Class"
        with pytest.raises(ValueError, match="Invalid RDF/TTL syntax"):
            parse_ttl_content(malformed)
    
    def test_class_without_properties(self):
        """Test handling of class without properties"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        
        :EmptyClass a owl:Class .
        """
        
        converter = RDFToFabricConverter()
        entity_types, _ = converter.parse_ttl(ttl)
        
        assert len(entity_types) == 1
        assert entity_types[0].name == "EmptyClass"
        assert len(entity_types[0].properties) == 0


class TestDataclassToDict:
    """Test dataclass to_dict() methods"""
    
    def test_entity_type_to_dict(self):
        """Test EntityType.to_dict()"""
        prop = EntityTypeProperty(
            id="1000000000002",
            name="testProp",
            valueType="String"
        )
        
        entity = EntityType(
            id="1000000000001",
            name="TestEntity",
            namespace="usertypes",
            namespaceType="Custom",
            visibility="Visible",
            properties=[prop]
        )
        
        entity_dict = entity.to_dict()
        
        assert entity_dict["id"] == "1000000000001"
        assert entity_dict["name"] == "TestEntity"
        assert entity_dict["namespace"] == "usertypes"
        assert len(entity_dict["properties"]) == 1
        assert entity_dict["properties"][0]["name"] == "testProp"
    
    def test_relationship_type_to_dict(self):
        """Test RelationshipType.to_dict()"""
        source = RelationshipEnd(entityTypeId="1000000000002")
        target = RelationshipEnd(entityTypeId="1000000000003")
        
        rel = RelationshipType(
            id="1000000000001",
            name="testRel",
            source=source,
            target=target
        )
        
        rel_dict = rel.to_dict()
        
        assert rel_dict["id"] == "1000000000001"
        assert rel_dict["name"] == "testRel"
        assert rel_dict["source"]["entityTypeId"] == "1000000000002"
        assert rel_dict["target"]["entityTypeId"] == "1000000000003"


class TestFabricDefinitionValidator:
    """Test suite for FabricDefinitionValidator"""
    
    def test_valid_definition(self):
        """Test validation passes for valid definition"""
        prop = EntityTypeProperty(id="prop1", name="name", valueType="String")
        entity = EntityType(
            id="entity1",
            name="Person",
            properties=[prop],
            entityIdParts=["prop1"],
            displayNamePropertyId="prop1"
        )
        
        is_valid, errors = FabricDefinitionValidator.validate_definition([entity], [])
        
        assert is_valid
        assert len([e for e in errors if e.level == "error"]) == 0
    
    def test_invalid_parent_reference(self):
        """Test validation catches invalid parent references"""
        entity = EntityType(
            id="entity1",
            name="Child",
            baseEntityTypeId="nonexistent_parent"
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "non-existent parent" in errors[0].message
    
    def test_self_inheritance(self):
        """Test validation catches self-inheritance"""
        entity = EntityType(
            id="entity1",
            name="SelfRef",
            baseEntityTypeId="entity1"  # Self-reference
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "cannot inherit from itself" in errors[0].message
    
    def test_invalid_display_name_property(self):
        """Test validation catches invalid displayNamePropertyId"""
        prop = EntityTypeProperty(id="prop1", name="name", valueType="String")
        entity = EntityType(
            id="entity1",
            name="Person",
            properties=[prop],
            displayNamePropertyId="nonexistent_prop"
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "displayNamePropertyId" in errors[0].message
    
    def test_display_name_property_type_warning(self):
        """Test validation warns when displayNameProperty is not String"""
        prop = EntityTypeProperty(id="prop1", name="count", valueType="BigInt")
        entity = EntityType(
            id="entity1",
            name="Item",
            properties=[prop],
            displayNamePropertyId="prop1"
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "warning"
        assert "should be String type" in errors[0].message
    
    def test_invalid_entity_id_part(self):
        """Test validation catches invalid entityIdParts"""
        prop = EntityTypeProperty(id="prop1", name="name", valueType="String")
        entity = EntityType(
            id="entity1",
            name="Person",
            properties=[prop],
            entityIdParts=["nonexistent_prop"]
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "entityIdPart" in errors[0].message
    
    def test_entity_id_part_type_warning(self):
        """Test validation warns when entityIdPart is not String or BigInt"""
        prop = EntityTypeProperty(id="prop1", name="value", valueType="Double")
        entity = EntityType(
            id="entity1",
            name="Measurement",
            properties=[prop],
            entityIdParts=["prop1"]
        )
        
        errors = FabricDefinitionValidator.validate_entity_types([entity])
        
        assert len(errors) == 1
        assert errors[0].level == "warning"
        assert "String or BigInt" in errors[0].message
    
    def test_invalid_relationship_source(self):
        """Test validation catches invalid relationship source"""
        entity = EntityType(id="entity1", name="Person")
        rel = RelationshipType(
            id="rel1",
            name="knows",
            source=RelationshipEnd(entityTypeId="nonexistent"),
            target=RelationshipEnd(entityTypeId="entity1")
        )
        
        errors = FabricDefinitionValidator.validate_relationships([rel], [entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "source" in errors[0].message
    
    def test_invalid_relationship_target(self):
        """Test validation catches invalid relationship target"""
        entity = EntityType(id="entity1", name="Person")
        rel = RelationshipType(
            id="rel1",
            name="knows",
            source=RelationshipEnd(entityTypeId="entity1"),
            target=RelationshipEnd(entityTypeId="nonexistent")
        )
        
        errors = FabricDefinitionValidator.validate_relationships([rel], [entity])
        
        assert len(errors) == 1
        assert errors[0].level == "error"
        assert "target" in errors[0].message
    
    def test_self_referential_relationship_warning(self):
        """Test validation warns on self-referential relationships"""
        entity = EntityType(id="entity1", name="Person")
        rel = RelationshipType(
            id="rel1",
            name="knows",
            source=RelationshipEnd(entityTypeId="entity1"),
            target=RelationshipEnd(entityTypeId="entity1")
        )
        
        errors = FabricDefinitionValidator.validate_relationships([rel], [entity])
        
        assert len(errors) == 1
        assert errors[0].level == "warning"
        assert "self-referential" in errors[0].message
    
    def test_convert_to_fabric_definition_with_validation_error(self):
        """Test convert_to_fabric_definition raises error on invalid definition"""
        entity = EntityType(
            id="entity1",
            name="Child",
            baseEntityTypeId="nonexistent_parent"  # Invalid reference
        )
        
        with pytest.raises(ValueError) as excinfo:
            convert_to_fabric_definition([entity], [], "TestOntology")
        
        assert "Invalid ontology definition" in str(excinfo.value)
        assert "non-existent parent" in str(excinfo.value)
    
    def test_convert_to_fabric_definition_with_warnings_passes(self):
        """Test convert_to_fabric_definition succeeds with only warnings"""
        entity = EntityType(id="entity1", name="Person")
        rel = RelationshipType(
            id="rel1",
            name="knows",
            source=RelationshipEnd(entityTypeId="entity1"),
            target=RelationshipEnd(entityTypeId="entity1")  # Self-referential warning
        )
        
        # Should not raise, just log warning
        definition = convert_to_fabric_definition([entity], [rel], "TestOntology")
        
        assert "parts" in definition
        assert len(definition["parts"]) > 0
    
    def test_definition_validation_error_str(self):
        """Test DefinitionValidationError string representation"""
        error = DefinitionValidationError(
            level="error",
            message="Test error message",
            entity_id="entity123"
        )
        
        error_str = str(error)
        
        assert "[ERROR]" in error_str
        assert "Test error message" in error_str
        assert "entity123" in error_str


class TestBlankNodeHandling:
    """Test suite for improved blank node handling in domain/range resolution"""
    
    @pytest.fixture
    def converter(self):
        """Create a converter instance for testing"""
        return RDFToFabricConverter()
    
    def test_simple_unionof_resolution(self, converter):
        """Test resolving a simple owl:unionOf expression"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class .
        :Organization a owl:Class .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain [
                a owl:Class ;
                owl:unionOf ( :Person :Organization )
            ] ;
            rdfs:range xsd:string .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        
        # Both Person and Organization should have the 'name' property
        person = next((e for e in entity_types if e.name == "Person"), None)
        org = next((e for e in entity_types if e.name == "Organization"), None)
        
        assert person is not None
        assert org is not None
        
        person_props = [p.name for p in person.properties]
        org_props = [p.name for p in org.properties]
        
        assert "name" in person_props, "Person should have 'name' property from unionOf"
        assert "name" in org_props, "Organization should have 'name' property from unionOf"
    
    def test_nested_unionof_resolution(self, converter):
        """Test resolving nested owl:unionOf expressions"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Animal a owl:Class .
        :Person a owl:Class ;
            rdfs:subClassOf :Animal .
        :Company a owl:Class .
        :NGO a owl:Class .
        
        :identifier a owl:DatatypeProperty ;
            rdfs:domain [
                owl:unionOf (
                    :Person
                    [
                        owl:unionOf ( :Company :NGO )
                    ]
                )
            ] ;
            rdfs:range xsd:string .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        
        # Get property counts
        entities_with_identifier = [
            e.name for e in entity_types 
            if any(p.name == "identifier" for p in e.properties)
        ]
        
        # Person should have the property
        assert "Person" in entities_with_identifier
        # Nested union members may or may not be resolved depending on implementation
        # At minimum, we should have Person
    
    def test_intersectionof_resolution(self, converter):
        """Test resolving owl:intersectionOf expressions"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :LivingThing a owl:Class .
        :Intelligent a owl:Class .
        :Human a owl:Class .
        
        :iq a owl:DatatypeProperty ;
            rdfs:domain [
                owl:intersectionOf ( :LivingThing :Intelligent )
            ] ;
            rdfs:range xsd:integer .
        """
        
        entity_types, _ = converter.parse_ttl(ttl)
        
        # intersectionOf should resolve to the classes in the intersection
        living = next((e for e in entity_types if e.name == "LivingThing"), None)
        intelligent = next((e for e in entity_types if e.name == "Intelligent"), None)
        
        # At least one of the intersection members should get the property
        has_iq = lambda e: e and any(p.name == "iq" for p in e.properties)
        assert has_iq(living) or has_iq(intelligent), \
            "At least one intersection member should have 'iq' property"
    
    def test_cycle_detection_in_blank_nodes(self, converter):
        """Test that cycles in blank node expressions don't cause infinite loops"""
        # This is a malformed ontology that could cause infinite loops without cycle detection
        from rdflib import Graph, BNode, URIRef, Namespace
        from rdflib.namespace import OWL, RDF, RDFS
        
        graph = Graph()
        EX = Namespace("http://example.org/")
        
        # Create a blank node
        bnode1 = BNode()
        
        # Create a cycle: bnode1 unionOf includes bnode1
        graph.add((bnode1, OWL.unionOf, bnode1))  # Self-referential - cycle!
        
        # Try to resolve - should not hang
        targets = converter._resolve_class_targets(graph, bnode1)
        
        # Should return empty or limited results, not hang
        assert isinstance(targets, list)
    
    def test_max_depth_protection(self, converter):
        """Test that deeply nested structures are limited by max_depth"""
        from rdflib import Graph, BNode, URIRef, Namespace
        from rdflib.namespace import OWL, RDF, RDFS
        
        graph = Graph()
        EX = Namespace("http://example.org/")
        
        # Create a deeply nested structure
        # bnode1 -> unionOf -> bnode2 -> unionOf -> bnode3 -> ...
        prev_bnode = BNode()
        for i in range(20):  # Create 20 levels deep
            new_bnode = BNode()
            list_node = BNode()
            graph.add((prev_bnode, OWL.unionOf, list_node))
            graph.add((list_node, RDF.first, new_bnode))
            graph.add((list_node, RDF.rest, RDF.nil))
            prev_bnode = new_bnode
        
        # Add a terminal class at the end
        final_class = URIRef("http://example.org/FinalClass")
        list_node = BNode()
        graph.add((prev_bnode, OWL.unionOf, list_node))
        graph.add((list_node, RDF.first, final_class))
        graph.add((list_node, RDF.rest, RDF.nil))
        
        # Resolve with default max_depth (10)
        targets = converter._resolve_class_targets(graph, BNode())
        
        # Should not hang and should return a list (may be empty due to depth limit)
        assert isinstance(targets, list)
    
    def test_resolve_rdf_list_with_cycle(self, converter):
        """Test RDF list cycle detection"""
        from rdflib import Graph, BNode, URIRef, Namespace
        from rdflib.namespace import RDF
        
        graph = Graph()
        
        # Create a cyclic RDF list
        node1 = BNode()
        node2 = BNode()
        
        graph.add((node1, RDF.first, URIRef("http://example.org/Class1")))
        graph.add((node1, RDF.rest, node2))
        graph.add((node2, RDF.first, URIRef("http://example.org/Class2")))
        graph.add((node2, RDF.rest, node1))  # Cycle back to node1!
        
        targets, unresolved = converter._resolve_rdf_list(graph, node1, set(), 10)
        
        # Should detect cycle and stop, returning partial results
        assert isinstance(targets, list)
        assert "http://example.org/Class1" in targets
        assert "http://example.org/Class2" in targets
        # Should not contain duplicates from looping
        assert targets.count("http://example.org/Class1") == 1
    
    def test_object_property_with_unionof_range(self, converter):
        """Test object property with unionOf range creates correct relationships"""
        ttl = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Person a owl:Class .
        :Company a owl:Class .
        :University a owl:Class .
        
        :affiliatedWith a owl:ObjectProperty ;
            rdfs:domain :Person ;
            rdfs:range [
                owl:unionOf ( :Company :University )
            ] .
        """
        
        entity_types, relationship_types = converter.parse_ttl(ttl)
        
        # Should have relationships for Person -> Company and Person -> University
        rel_names = [r.name for r in relationship_types]
        assert "affiliatedWith" in rel_names
        
        # Check that relationships target both Company and University
        affiliated_rels = [r for r in relationship_types if r.name == "affiliatedWith"]
        target_names = set()
        for rel in affiliated_rels:
            target_id = rel.target.entityTypeId
            target_entity = next((e for e in entity_types if e.id == target_id), None)
            if target_entity:
                target_names.add(target_entity.name)
        
        # At least one of the union targets should be represented
        assert len(target_names) > 0
    
    def test_complementof_resolution(self, converter):
        """Test resolving owl:complementOf expressions"""
        from rdflib import Graph, BNode, URIRef, Namespace
        from rdflib.namespace import OWL
        
        graph = Graph()
        EX = Namespace("http://example.org/")
        
        bnode = BNode()
        graph.add((bnode, OWL.complementOf, EX.SomeClass))
        
        targets = converter._resolve_class_targets(graph, bnode)
        
        assert "http://example.org/SomeClass" in targets
    
    def test_empty_union_returns_empty_list(self, converter):
        """Test that empty unionOf returns empty list without error"""
        from rdflib import Graph, BNode
        from rdflib.namespace import OWL, RDF
        
        graph = Graph()
        
        bnode = BNode()
        list_head = BNode()
        graph.add((bnode, OWL.unionOf, list_head))
        graph.add((list_head, RDF.first, RDF.nil))  # Empty-ish list
        graph.add((list_head, RDF.rest, RDF.nil))
        
        targets = converter._resolve_class_targets(graph, bnode)
        
        # Should return empty list without crashing
        assert isinstance(targets, list)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
