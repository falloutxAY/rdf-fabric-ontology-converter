"""Integration tests for RDF to Fabric conversion pipeline.

These tests verify the complete RDF conversion workflow using sample ontologies.
They do NOT require a live Fabric connection - they test the conversion logic only.
"""

import json
import pytest
from pathlib import Path

from src.rdf import parse_ttl_with_result


class TestRDFConversionPipeline:
    """Test end-to-end RDF conversion workflows."""

    @pytest.fixture
    def samples_dir(self) -> Path:
        """Get the samples/rdf directory path for RDF tests."""
        return Path(__file__).parent.parent.parent / "samples" / "rdf"

    def test_foaf_ontology_conversion(self, samples_dir: Path):
        """Test converting the FOAF sample ontology."""
        foaf_path = samples_dir / "sample_foaf_ontology.ttl"
        if not foaf_path.exists():
            pytest.skip("FOAF sample not found")

        content = foaf_path.read_text(encoding="utf-8")
        definition, name, result = parse_ttl_with_result(content)

        # Verify conversion succeeded
        assert definition is not None
        # Definition is API format with 'parts' key
        assert "parts" in definition
        assert result.success_rate > 0

        # Verify result contains the conversion data
        assert len(result.entity_types) > 0 or len(result.relationship_types) > 0

        # Verify JSON is valid
        json_str = json.dumps(definition)
        parsed = json.loads(json_str)
        assert parsed["parts"] == definition["parts"]

    def test_iot_ontology_conversion(self, samples_dir: Path):
        """Test converting the IoT sample ontology."""
        iot_path = samples_dir / "sample_iot_ontology.ttl"
        if not iot_path.exists():
            pytest.skip("IoT sample not found")

        content = iot_path.read_text(encoding="utf-8")
        definition, name, result = parse_ttl_with_result(content)

        # Verify conversion succeeded
        assert definition is not None
        assert len(result.entity_types) > 0
        assert result.success_rate > 0

        # Verify entity types have required fields
        for entity in result.entity_types:
            assert entity.id
            assert entity.name
            assert entity.namespace

    def test_supply_chain_ontology_conversion(self, samples_dir: Path):
        """Test converting the supply chain sample ontology."""
        sc_path = samples_dir / "sample_supply_chain_ontology.ttl"
        if not sc_path.exists():
            pytest.skip("Supply chain sample not found")

        content = sc_path.read_text(encoding="utf-8")
        definition, name, result = parse_ttl_with_result(content)

        # Verify conversion succeeded
        assert definition is not None

        # Verify relationship structure if any exist
        for rel in result.relationship_types:
            assert rel.id
            assert rel.name
            assert rel.source is not None
            assert rel.target is not None
            assert rel.source.entityTypeId
            assert rel.target.entityTypeId

    def test_fibo_ontology_conversion(self, samples_dir: Path):
        """Test converting the FIBO (financial) sample ontology."""
        fibo_path = samples_dir / "sample_fibo_ontology.ttl"
        if not fibo_path.exists():
            pytest.skip("FIBO sample not found")

        content = fibo_path.read_text(encoding="utf-8")
        definition, name, result = parse_ttl_with_result(content)

        # Verify conversion succeeded
        assert definition is not None
        assert result is not None

        # Log any skipped items for inspection
        if result.skipped_items:
            skipped_types = result.skipped_by_type
            print(f"Skipped items by type: {skipped_types}")

    def test_conversion_result_statistics(self, samples_dir: Path):
        """Test that conversion results include proper statistics."""
        iot_path = samples_dir / "sample_iot_ontology.ttl"
        if not iot_path.exists():
            pytest.skip("IoT sample not found")

        content = iot_path.read_text(encoding="utf-8")
        definition, name, result = parse_ttl_with_result(content)

        # Verify ConversionResult attributes
        assert hasattr(result, "entity_types")
        assert hasattr(result, "relationship_types")
        assert hasattr(result, "skipped_items")
        assert hasattr(result, "warnings")
        assert hasattr(result, "success_rate")
        assert hasattr(result, "has_skipped_items")

        # Verify summary generation
        summary = result.get_summary()
        assert isinstance(summary, str)
        assert "Entity Types" in summary or "entity" in summary.lower()

    def test_id_prefix_customization(self, samples_dir: Path):
        """Test that custom ID prefix is applied correctly."""
        iot_path = samples_dir / "sample_iot_ontology.ttl"
        if not iot_path.exists():
            pytest.skip("IoT sample not found")

        content = iot_path.read_text(encoding="utf-8")
        custom_prefix = 9000000000000
        definition, name, result = parse_ttl_with_result(
            content, id_prefix=custom_prefix
        )

        # Verify IDs start with custom prefix
        if result.entity_types:
            first_id = int(result.entity_types[0].id)
            assert first_id >= custom_prefix
            assert first_id < custom_prefix + 1000000000000

    def test_all_samples_convert_without_crash(self, samples_dir: Path):
        """Smoke test: verify all sample TTL files convert without crashing."""
        ttl_files = list(samples_dir.glob("*.ttl"))

        for ttl_file in ttl_files:
            content = ttl_file.read_text(encoding="utf-8")
            try:
                definition, name, result = parse_ttl_with_result(content)
                assert definition is not None, f"Failed: {ttl_file.name}"
            except Exception as e:
                pytest.fail(f"Conversion crashed for {ttl_file.name}: {e}")
