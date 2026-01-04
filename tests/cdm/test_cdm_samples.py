"""
CDM Sample File Tests.

Tests that validate all CDM sample files can be parsed, validated, and converted.
"""

import pytest
import os
import json
from pathlib import Path

# Add src to path
import sys
src_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from formats.cdm import CDMParser, CDMValidator, CDMToFabricConverter


# Get the samples directory
SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "cdm"


def get_all_cdm_files():
    """Get all CDM files from samples directory."""
    cdm_files = []
    
    for pattern in ["**/*.cdm.json", "**/*.manifest.cdm.json", "**/model.json"]:
        for file_path in SAMPLES_DIR.glob(pattern):
            cdm_files.append(str(file_path))
    
    return cdm_files


def get_manifest_files():
    """Get all manifest files."""
    return [str(p) for p in SAMPLES_DIR.glob("**/*.manifest.cdm.json")]


def get_entity_schema_files():
    """Get all entity schema files (excluding manifests and model.json)."""
    all_cdm = set(SAMPLES_DIR.glob("**/*.cdm.json"))
    manifests = set(SAMPLES_DIR.glob("**/*.manifest.cdm.json"))
    return [str(p) for p in all_cdm - manifests]


def get_model_json_files():
    """Get all model.json files."""
    return [str(p) for p in SAMPLES_DIR.glob("**/model.json")]


# =============================================================================
# Simple Sample Tests
# =============================================================================

@pytest.mark.samples
class TestSimpleSamples:
    """Test simple CDM sample files."""
    
    def test_simple_manifest_exists(self):
        """Simple manifest file exists."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        assert manifest_path.exists(), f"Simple manifest not found at {manifest_path}"
    
    def test_parse_simple_manifest(self):
        """Parse simple manifest."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(manifest_path))
        
        assert result is not None
        assert result.name == "SimpleManifest"
        assert len(result.entities) >= 3  # Person, Contact, Order, OrderLine
    
    def test_validate_simple_manifest(self):
        """Validate simple manifest."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        validator = CDMValidator()
        result = validator.validate(content, str(manifest_path))
        
        assert result.is_valid is True
        assert result.error_count == 0
    
    def test_convert_simple_manifest(self):
        """Convert simple manifest to Fabric types."""
        manifest_path = SAMPLES_DIR / "simple" / "simple.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        assert result is not None
        assert result.success_rate == 100.0
        assert len(result.entity_types) >= 3
    
    @pytest.mark.parametrize("entity_name", ["Person", "Contact", "Order"])
    def test_parse_simple_entity(self, entity_name):
        """Parse simple entity schemas."""
        if entity_name == "Order":
            entity_path = SAMPLES_DIR / "simple" / f"{entity_name}.cdm.json"
        else:
            entity_path = SAMPLES_DIR / "simple" / f"{entity_name}.cdm.json"
        
        with open(entity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(entity_path))
        
        assert result is not None
        assert len(result.entities) >= 1
    
    def test_simple_model_json(self):
        """Parse simple model.json."""
        model_path = SAMPLES_DIR / "simple" / "model.json"
        with open(model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(model_path))
        
        assert result is not None
        assert result.name == "SimpleLegacyModel"


# =============================================================================
# Model.json Sample Tests  
# =============================================================================

@pytest.mark.samples
class TestModelJsonSamples:
    """Test model.json sample files."""
    
    def test_orders_products_model_exists(self):
        """OrdersProducts model.json exists."""
        model_path = SAMPLES_DIR / "model-json" / "OrdersProducts" / "model.json"
        assert model_path.exists()
    
    def test_parse_orders_products_model(self):
        """Parse OrdersProducts model.json."""
        model_path = SAMPLES_DIR / "model-json" / "OrdersProducts" / "model.json"
        with open(model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(model_path))
        
        assert result is not None
        assert result.name == "OrdersProductsModel"
        assert len(result.entities) >= 4  # Customer, Product, Order, OrderDetail, Category
    
    def test_validate_orders_products_model(self):
        """Validate OrdersProducts model.json."""
        model_path = SAMPLES_DIR / "model-json" / "OrdersProducts" / "model.json"
        with open(model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        validator = CDMValidator()
        result = validator.validate(content, str(model_path))
        
        assert result.is_valid is True
    
    def test_convert_orders_products_model(self):
        """Convert OrdersProducts model.json."""
        model_path = SAMPLES_DIR / "model-json" / "OrdersProducts" / "model.json"
        with open(model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(model_path))
        
        assert result.success_rate == 100.0
        assert len(result.entity_types) >= 4


# =============================================================================
# Healthcare Industry Tests
# =============================================================================

@pytest.mark.samples
@pytest.mark.industry
class TestHealthcareSamples:
    """Test Healthcare Industry Accelerator samples."""
    
    def test_healthcare_manifest_exists(self):
        """Healthcare manifest exists."""
        manifest_path = SAMPLES_DIR / "industry" / "healthcare" / "healthcare.manifest.cdm.json"
        assert manifest_path.exists()
    
    def test_parse_healthcare_manifest(self):
        """Parse healthcare manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "healthcare" / "healthcare.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(manifest_path))
        
        assert result is not None
        assert result.name == "HealthcareManifest"
        assert len(result.entities) == 4  # Patient, Practitioner, Encounter, Appointment
    
    def test_validate_healthcare_manifest(self):
        """Validate healthcare manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "healthcare" / "healthcare.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        validator = CDMValidator()
        result = validator.validate(content, str(manifest_path))
        
        assert result.is_valid is True
    
    @pytest.mark.parametrize("entity_name", ["Patient", "Practitioner", "Encounter", "Appointment"])
    def test_parse_healthcare_entity(self, entity_name):
        """Parse healthcare entities."""
        entity_path = SAMPLES_DIR / "industry" / "healthcare" / f"{entity_name}.cdm.json"
        with open(entity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(entity_path))
        
        assert result is not None
        assert len(result.entities) >= 1
        assert result.entities[0].name == entity_name
    
    def test_convert_healthcare_manifest(self):
        """Convert healthcare manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "healthcare" / "healthcare.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=str(manifest_path))
        
        assert result.success_rate == 100.0
        # Should have Patient, Practitioner, Encounter, Appointment
        entity_names = [e.name for e in result.entity_types]
        assert "Patient" in entity_names
        assert "Practitioner" in entity_names


# =============================================================================
# Financial Services Industry Tests
# =============================================================================

@pytest.mark.samples
@pytest.mark.industry
class TestFinancialServicesSamples:
    """Test Financial Services Industry Accelerator samples."""
    
    def test_banking_manifest_exists(self):
        """Banking manifest exists."""
        manifest_path = SAMPLES_DIR / "industry" / "financial-services" / "banking.manifest.cdm.json"
        assert manifest_path.exists()
    
    def test_parse_banking_manifest(self):
        """Parse banking manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "financial-services" / "banking.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(manifest_path))
        
        assert result is not None
        assert result.name == "BankingManifest"
    
    @pytest.mark.parametrize("entity_name", ["Customer", "Account", "Transaction", "Loan"])
    def test_parse_financial_entity(self, entity_name):
        """Parse financial services entities."""
        entity_path = SAMPLES_DIR / "industry" / "financial-services" / f"{entity_name}.cdm.json"
        with open(entity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(entity_path))
        
        assert result is not None
        assert len(result.entities) >= 1


# =============================================================================
# Automotive Industry Tests
# =============================================================================

@pytest.mark.samples
@pytest.mark.industry
class TestAutomotiveSamples:
    """Test Automotive Industry Accelerator samples."""
    
    def test_automotive_manifest_exists(self):
        """Automotive manifest exists."""
        manifest_path = SAMPLES_DIR / "industry" / "automotive" / "automotive.manifest.cdm.json"
        assert manifest_path.exists()
    
    def test_parse_automotive_manifest(self):
        """Parse automotive manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "automotive" / "automotive.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(manifest_path))
        
        assert result is not None
        assert result.name == "AutomotiveManifest"
    
    @pytest.mark.parametrize("entity_name", ["Vehicle", "Dealer", "ServiceAppointment", "Lead"])
    def test_parse_automotive_entity(self, entity_name):
        """Parse automotive entities."""
        entity_path = SAMPLES_DIR / "industry" / "automotive" / f"{entity_name}.cdm.json"
        with open(entity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(entity_path))
        
        assert result is not None


# =============================================================================
# Education Industry Tests
# =============================================================================

@pytest.mark.samples
@pytest.mark.industry
class TestEducationSamples:
    """Test Education Industry Accelerator samples."""
    
    def test_education_manifest_exists(self):
        """Education manifest exists."""
        manifest_path = SAMPLES_DIR / "industry" / "education" / "education.manifest.cdm.json"
        assert manifest_path.exists()
    
    def test_parse_education_manifest(self):
        """Parse education manifest."""
        manifest_path = SAMPLES_DIR / "industry" / "education" / "education.manifest.cdm.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(manifest_path))
        
        assert result is not None
        assert result.name == "EducationManifest"
    
    @pytest.mark.parametrize("entity_name", ["Student", "Course", "Enrollment", "Institution"])
    def test_parse_education_entity(self, entity_name):
        """Parse education entities."""
        entity_path = SAMPLES_DIR / "industry" / "education" / f"{entity_name}.cdm.json"
        with open(entity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, str(entity_path))
        
        assert result is not None


# =============================================================================
# Bulk Sample Tests
# =============================================================================

@pytest.mark.samples
class TestAllSamples:
    """Bulk tests across all sample files."""
    
    @pytest.mark.parametrize("file_path", get_all_cdm_files())
    def test_all_samples_valid_json(self, file_path):
        """All sample files are valid JSON."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not raise
        data = json.loads(content)
        assert isinstance(data, dict)
    
    @pytest.mark.parametrize("file_path", get_all_cdm_files())
    def test_all_samples_parse(self, file_path):
        """All sample files can be parsed."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parser = CDMParser()
        result = parser.parse(content, file_path)
        
        assert result is not None
    
    @pytest.mark.parametrize("file_path", get_all_cdm_files())
    def test_all_samples_validate(self, file_path):
        """All sample files pass validation."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        validator = CDMValidator()
        result = validator.validate(content, file_path)
        
        assert result.is_valid is True, f"Validation failed for {file_path}: {result.error_count} errors"
    
    @pytest.mark.parametrize("manifest_path", get_manifest_files())
    def test_all_manifests_convert(self, manifest_path):
        """All manifest files can be converted."""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        converter = CDMToFabricConverter()
        result = converter.convert(content, source_path=manifest_path)
        
        assert result.success_rate == 100.0, f"Conversion failed for {manifest_path}"
        assert len(result.entity_types) > 0
