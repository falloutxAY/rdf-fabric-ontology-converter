"""
Consolidated Fabric client tests including API integration and streaming converter.

This module contains all Fabric client-related tests:
- FabricOntologyClient API integration tests
- Streaming RDF converter tests
- Rate limiting and retry behavior
- Long-running operation handling
- Authentication and error handling

Run specific test categories:
    pytest -m integration                          # All integration tests
    pytest tests/core/test_fabric_client.py        # All Fabric client tests
    pytest -k "Streaming" tests/core/test_fabric_client.py  # Streaming tests only
"""

import pytest
import json
import time
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core import (
    FabricOntologyClient,
    FabricConfig,
    FabricAPIError,
    RateLimitConfig,
)
from src.core.platform.fabric_client import TransientAPIError
from src.rdf import (
    StreamingRDFConverter,
    RDFToFabricConverter,
    parse_ttl_streaming,
    parse_ttl_with_result,
    ConversionResult,
    EntityType,
    RelationshipType,
    SkippedItem
)


# =============================================================================
# Constants matching Fabric API specification
# =============================================================================

SAMPLE_WORKSPACE_ID = "cfafbeb1-8037-4d0c-896e-a46fb27ff229"
SAMPLE_ONTOLOGY_ID = "5b218778-e7a5-4d73-8187-f10824047715"
SAMPLE_ONTOLOGY_ID_2 = "3546052c-ae64-4526-b1a8-52af7761426f"
SAMPLE_OPERATION_ID = "0acd697c-1550-43cd-b998-91bfbfbd47c6"
API_BASE_URL = "https://api.fabric.microsoft.com/v1"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_credential():
    """Mock Azure credential that returns a valid token."""
    mock_token = Mock()
    mock_token.token = "mock-access-token-12345"
    mock_token.expires_on = time.time() + 3600
    
    mock_cred = Mock()
    mock_cred.get_token.return_value = mock_token
    return mock_cred


@pytest.fixture
def fabric_config():
    """Create a basic FabricConfig for testing."""
    return FabricConfig(
        workspace_id=SAMPLE_WORKSPACE_ID,
        tenant_id="87654321-4321-4321-4321-cba987654321",
        use_interactive_auth=False,
        rate_limit=RateLimitConfig(enabled=False),
    )


@pytest.fixture
def fabric_config_with_rate_limit():
    """Create a FabricConfig with rate limiting enabled."""
    return FabricConfig(
        workspace_id=SAMPLE_WORKSPACE_ID,
        tenant_id="87654321-4321-4321-4321-cba987654321",
        use_interactive_auth=False,
        rate_limit=RateLimitConfig(enabled=True, requests_per_minute=60, burst=60),
    )


@pytest.fixture
def fabric_client(fabric_config, mock_credential):
    """Create a FabricOntologyClient with mocked credentials."""
    with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_credential):
        client = FabricOntologyClient(fabric_config)
        yield client


@pytest.fixture
def fabric_client_with_rate_limit(fabric_config_with_rate_limit, mock_credential):
    """Create a FabricOntologyClient with rate limiting enabled."""
    with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_credential):
        client = FabricOntologyClient(fabric_config_with_rate_limit)
        yield client


# =============================================================================
# Helper Functions
# =============================================================================

def create_mock_response(
    status_code: int,
    json_data: Dict[str, Any] = None,
    headers: Dict[str, str] = None,
    text: str = ""
) -> Mock:
    """Create a mock requests.Response object."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}
    mock_response.text = text or json.dumps(json_data) if json_data else ""
    
    if json_data is not None:
        mock_response.json.return_value = json_data
    else:
        mock_response.json.side_effect = json.JSONDecodeError("No JSON", "", 0)
    
    return mock_response


def create_ontology_response(
    ontology_id: str = SAMPLE_ONTOLOGY_ID,
    display_name: str = "Ontology 1",
    description: str = "An ontology description.",
    workspace_id: str = SAMPLE_WORKSPACE_ID
) -> Dict[str, Any]:
    """Create an ontology response matching the Fabric API specification."""
    return {
        "id": ontology_id,
        "displayName": display_name,
        "description": description,
        "type": "Ontology",
        "workspaceId": workspace_id
    }


def create_error_response(
    error_code: str,
    message: str,
    request_id: str = "abc123-request-id"
) -> Dict[str, Any]:
    """Create an error response matching the Fabric API specification."""
    return {
        "errorCode": error_code,
        "message": message,
        "requestId": request_id
    }


def create_lro_operation_response(
    status: str,
    percent_complete: int = 0,
    error_message: str = None
) -> Dict[str, Any]:
    """Create an LRO operation status response."""
    response = {
        "status": status,
        "createdTimeUtc": "2023-11-13T22:24:40.477Z",
        "lastUpdatedTimeUtc": "2023-11-13T22:24:41.532Z",
        "percentComplete": percent_complete
    }
    if error_message:
        response["error"] = {"message": error_message}
    return response


# =============================================================================
# FABRIC API INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestListOntologies:
    """Tests for list_ontologies method."""
    
    def test_list_ontologies_success(self, fabric_client):
        """Test successful listing of ontologies."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "value": [
                    create_ontology_response(
                        ontology_id=SAMPLE_ONTOLOGY_ID,
                        display_name="Ontology Name 1",
                        description="An ontology description."
                    ),
                    create_ontology_response(
                        ontology_id=SAMPLE_ONTOLOGY_ID_2,
                        display_name="Ontology Name 2",
                        description="An ontology description."
                    ),
                ]
            }
        )
        
        with patch('requests.request', return_value=mock_response):
            result = fabric_client.list_ontologies()
        
        assert len(result) == 2
        assert result[0]["id"] == SAMPLE_ONTOLOGY_ID
        assert result[0]["type"] == "Ontology"
        assert result[0]["workspaceId"] == SAMPLE_WORKSPACE_ID
        assert result[1]["displayName"] == "Ontology Name 2"
    
    def test_list_ontologies_empty(self, fabric_client):
        """Test listing when no ontologies exist."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={"value": []}
        )
        
        with patch('requests.request', return_value=mock_response):
            result = fabric_client.list_ontologies()
        
        assert result == []
    
    def test_list_ontologies_unauthorized(self, fabric_client):
        """Test listing with invalid credentials (401)."""
        mock_response = create_mock_response(
            status_code=401,
            json_data=create_error_response(
                error_code="Unauthorized",
                message="The caller does not have permission."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.status_code == 401


@pytest.mark.integration
class TestGetOntology:
    """Tests for get_ontology method."""
    
    def test_get_ontology_success(self, fabric_client):
        """Test successful retrieval."""
        mock_response = create_mock_response(
            status_code=200,
            json_data=create_ontology_response(
                ontology_id=SAMPLE_ONTOLOGY_ID,
                display_name="Ontology 1",
                description="An ontology description."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            result = fabric_client.get_ontology(SAMPLE_ONTOLOGY_ID)
        
        assert result["id"] == SAMPLE_ONTOLOGY_ID
        assert result["displayName"] == "Ontology 1"
        assert result["type"] == "Ontology"
        assert result["workspaceId"] == SAMPLE_WORKSPACE_ID
    
    def test_get_ontology_not_found(self, fabric_client):
        """Test retrieval of non-existent ontology (404)."""
        mock_response = create_mock_response(
            status_code=404,
            json_data=create_error_response(
                error_code="ItemNotFound",
                message="The requested item was not found."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.get_ontology("non-existent-id")
        
        assert exc_info.value.status_code == 404


@pytest.mark.integration
class TestCreateOntology:
    """Tests for create_ontology method."""
    
    def test_create_ontology_success_immediate(self, fabric_client):
        """Test successful immediate ontology creation (201)."""
        mock_response = create_mock_response(
            status_code=201,
            json_data=create_ontology_response(
                ontology_id=SAMPLE_ONTOLOGY_ID,
                display_name="Ontology 1",
                description="An ontology description."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            result = fabric_client.create_ontology(
                display_name="Ontology 1",
                description="An ontology description.",
                definition={"parts": []},
                wait_for_completion=False
            )
        
        assert result["id"] == SAMPLE_ONTOLOGY_ID
        assert result["type"] == "Ontology"
    
    def test_create_ontology_lro_success(self, fabric_client):
        """Test ontology creation with long-running operation (202)."""
        location_uri = f"{API_BASE_URL}/workspaces/{SAMPLE_WORKSPACE_ID}/ontologies/{SAMPLE_ONTOLOGY_ID}"
        
        create_response = create_mock_response(
            status_code=202,
            json_data={},
            headers={
                'Location': location_uri,
                'x-ms-operation-id': SAMPLE_OPERATION_ID,
                'Retry-After': '30'
            }
        )
        
        with patch('requests.request', return_value=create_response):
            with patch.object(fabric_client, '_wait_for_operation', return_value={}):
                result = fabric_client.create_ontology(
                    display_name="Ontology 1",
                    description="An ontology description.",
                    definition={"parts": []},
                    wait_for_completion=True
                )
        
        assert result["id"] == SAMPLE_ONTOLOGY_ID
    
    def test_create_ontology_conflict(self, fabric_client):
        """Test creation when ontology already exists (409)."""
        mock_response = create_mock_response(
            status_code=409,
            json_data=create_error_response(
                error_code="ItemDisplayNameAlreadyInUse",
                message="An item with the same name already exists."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.create_ontology(
                    display_name="ExistingOntology",
                    definition={"parts": []}
                )
        
        assert exc_info.value.status_code == 409
    
    def test_create_ontology_validation_error(self, fabric_client):
        """Test creation with invalid payload (400)."""
        mock_response = create_mock_response(
            status_code=400,
            json_data=create_error_response(
                error_code="CorruptedPayload",
                message="The request payload is corrupted."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.create_ontology(
                    display_name="BadOntology",
                    definition={}
                )
        
        assert exc_info.value.status_code == 400


@pytest.mark.integration
class TestUpdateOntologyDefinition:
    """Tests for update_ontology_definition method."""
    
    def test_update_definition_success(self, fabric_client):
        """Test successful definition update (200)."""
        update_response = create_mock_response(
            status_code=200,
            json_data=create_ontology_response(
                ontology_id=SAMPLE_ONTOLOGY_ID,
                display_name="Ontology 1",
                description="Updated ontology."
            )
        )
        
        with patch('requests.request', return_value=update_response):
            result = fabric_client.update_ontology_definition(
                ontology_id=SAMPLE_ONTOLOGY_ID,
                definition={"parts": [{"id": 1, "kind": "EntityType", "name": "NewEntity"}]},
                wait_for_completion=False
            )
        
        assert result["id"] == SAMPLE_ONTOLOGY_ID
        assert result["type"] == "Ontology"


@pytest.mark.integration
class TestDeleteOntology:
    """Tests for delete_ontology method."""
    
    def test_delete_ontology_success(self, fabric_client):
        """Test successful ontology deletion (200)."""
        mock_response = create_mock_response(status_code=200)
        
        with patch('requests.request', return_value=mock_response):
            fabric_client.delete_ontology(SAMPLE_ONTOLOGY_ID)
    
    def test_delete_ontology_not_found(self, fabric_client):
        """Test deletion of non-existent ontology (404)."""
        mock_response = create_mock_response(
            status_code=404,
            json_data=create_error_response(
                error_code="ItemNotFound",
                message="The requested item was not found."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.delete_ontology("non-existent-id")
        
        assert exc_info.value.status_code == 404


@pytest.mark.integration
class TestRateLimitingAndRetry:
    """Tests for rate limiting and retry behavior."""
    
    def test_rate_limit_429_retry(self, fabric_client):
        """Test automatic retry on 429 Too Many Requests."""
        rate_limit_response = create_mock_response(
            status_code=429,
            json_data=create_error_response(
                error_code="TooManyRequests",
                message="Rate limit exceeded."
            ),
            headers={'Retry-After': '1'}
        )
        
        success_response = create_mock_response(
            status_code=200,
            json_data={"value": [create_ontology_response()]}
        )
        
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TransientAPIError(429, retry_after=1, message="Rate limited")
            return success_response
        
        with patch('requests.request', side_effect=side_effect):
            result = fabric_client.list_ontologies()
        
        assert call_count[0] == 2
        assert len(result) == 1
    
    def test_service_unavailable_503_retry(self, fabric_client):
        """Test automatic retry on 503 Service Unavailable."""
        success_response = create_mock_response(
            status_code=200,
            json_data={"value": []}
        )
        
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TransientAPIError(503, retry_after=1, message="Service unavailable")
            return success_response
        
        with patch('requests.request', side_effect=side_effect):
            result = fabric_client.list_ontologies()
        
        assert call_count[0] == 2


@pytest.mark.integration
class TestTimeoutHandling:
    """Tests for request timeout handling."""
    
    def test_request_timeout(self, fabric_client):
        """Test handling of request timeout."""
        import requests as req_lib
        
        with patch('requests.request', side_effect=req_lib.exceptions.Timeout()):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.error_code == 'RequestTimeout'
    
    def test_connection_error(self, fabric_client):
        """Test handling of connection error."""
        import requests as req_lib
        
        with patch('requests.request', side_effect=req_lib.exceptions.ConnectionError()):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.error_code == 'ConnectionError'


@pytest.mark.integration
class TestAuthentication:
    """Tests for authentication handling."""
    
    def test_token_refresh_on_expiry(self, fabric_config):
        """Test that token is refreshed when expired."""
        expired_token = Mock()
        expired_token.token = "expired-token"
        expired_token.expires_on = time.time() - 100
        
        new_token = Mock()
        new_token.token = "new-valid-token"
        new_token.expires_on = time.time() + 3600
        
        mock_credential = Mock()
        mock_credential.get_token.side_effect = [expired_token, new_token]
        
        with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_credential):
            client = FabricOntologyClient(fabric_config)
            
            mock_response = create_mock_response(
                status_code=200,
                json_data={"value": []}
            )
            
            with patch('requests.request', return_value=mock_response) as mock_req:
                client.list_ontologies()
                assert mock_credential.get_token.called
    
    def test_authentication_failure_raises_error(self, fabric_config):
        """Test that authentication failure raises error."""
        mock_credential = Mock()
        mock_credential.get_token.side_effect = Exception("Auth failed")
        
        with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_credential):
            client = FabricOntologyClient(fabric_config)
            
            with pytest.raises(FabricAPIError) as exc_info:
                client.list_ontologies()
            
            assert exc_info.value.status_code == 401


@pytest.mark.integration
class TestErrorResponseHandling:
    """Tests for various error response handling."""
    
    def test_invalid_json_response(self, fabric_client):
        """Test handling of invalid JSON in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "not valid json"
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.error_code == 'InvalidResponse'
    
    def test_server_error_500(self, fabric_client):
        """Test handling of 500 Internal Server Error."""
        mock_response = create_mock_response(
            status_code=500,
            json_data=create_error_response(
                error_code="InternalError",
                message="An unexpected error occurred."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.status_code == 500
    
    def test_forbidden_403(self, fabric_client):
        """Test handling of 403 Forbidden."""
        mock_response = create_mock_response(
            status_code=403,
            json_data=create_error_response(
                error_code="Forbidden",
                message="The caller does not have permission."
            )
        )
        
        with patch('requests.request', return_value=mock_response):
            with pytest.raises(FabricAPIError) as exc_info:
                fabric_client.list_ontologies()
        
        assert exc_info.value.status_code == 403


@pytest.mark.integration
class TestRateLimiterIntegration:
    """Tests for rate limiter integration with client."""
    
    def test_rate_limiter_acquires_before_request(self, fabric_client_with_rate_limit):
        """Test that rate limiter is called before each request."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={"value": []}
        )
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(
                fabric_client_with_rate_limit.rate_limiter,
                'acquire',
                wraps=fabric_client_with_rate_limit.rate_limiter.acquire
            ) as mock_acquire:
                fabric_client_with_rate_limit.list_ontologies()
                assert mock_acquire.called
    
    def test_rate_limiter_statistics_tracked(self, fabric_client_with_rate_limit):
        """Test that rate limiter statistics are tracked."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={"value": []}
        )
        
        with patch('requests.request', return_value=mock_response):
            for _ in range(3):
                fabric_client_with_rate_limit.list_ontologies()
            
            stats = fabric_client_with_rate_limit.get_rate_limit_statistics()
            assert stats['total_requests'] == 3


@pytest.mark.integration
class TestRequestHeaders:
    """Tests for request header handling."""
    
    def test_authorization_header_included(self, fabric_client):
        """Test that Authorization header is included."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={"value": []}
        )
        
        with patch('requests.request', return_value=mock_response) as mock_req:
            fabric_client.list_ontologies()
            
            call_args = mock_req.call_args
            headers = call_args.kwargs.get('headers', {})
            assert 'Authorization' in headers
            assert headers['Authorization'].startswith('Bearer ')
    
    def test_content_type_header_for_post(self, fabric_client):
        """Test that Content-Type header is set for POST."""
        mock_response = create_mock_response(
            status_code=201,
            json_data=create_ontology_response()
        )
        
        with patch('requests.request', return_value=mock_response) as mock_req:
            fabric_client.create_ontology(
                display_name="Ontology 1",
                definition={"parts": []},
                wait_for_completion=False
            )
            
            call_args = mock_req.call_args
            headers = call_args.kwargs.get('headers', {})
            assert headers.get('Content-Type') == 'application/json'


@pytest.mark.integration
class TestConfigurationValidation:
    """Tests for configuration validation."""
    
    def test_empty_workspace_id_raises_error(self):
        """Test that empty workspace_id raises error."""
        config = FabricConfig(
            workspace_id="",
            tenant_id="test-tenant"
        )
        
        with pytest.raises(ValueError) as exc_info:
            FabricOntologyClient(config)
        
        assert "workspace_id" in str(exc_info.value).lower()
    
    def test_placeholder_workspace_id_raises_error(self):
        """Test that placeholder workspace_id raises error."""
        config = FabricConfig(
            workspace_id="YOUR_WORKSPACE_ID",
            tenant_id="test-tenant"
        )
        
        with pytest.raises(ValueError) as exc_info:
            FabricOntologyClient(config)
        
        assert "workspace" in str(exc_info.value).lower()
    
    def test_invalid_workspace_id_format_warns(self, mock_credential, caplog):
        """Test that invalid workspace_id format logs warning."""
        config = FabricConfig(
            workspace_id="not-a-valid-guid",
            tenant_id="test-tenant",
            rate_limit=RateLimitConfig(enabled=False)
        )
        
        with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_credential):
            import logging
            with caplog.at_level(logging.WARNING):
                client = FabricOntologyClient(config)
            
            assert any("guid" in record.message.lower() for record in caplog.records)


@pytest.mark.integration
class TestLongRunningOperations:
    """Tests for long-running operation handling."""
    
    def test_lro_timeout(self, fabric_client):
        """Test LRO timeout after maximum polling attempts."""
        with patch.object(
            fabric_client,
            '_wait_for_operation',
            side_effect=FabricAPIError(504, 'OperationTimeout', 'Operation timed out.')
        ):
            location_uri = f"{API_BASE_URL}/operations/{SAMPLE_OPERATION_ID}"
            create_response = create_mock_response(
                status_code=202,
                headers={
                    'Location': location_uri,
                    'x-ms-operation-id': SAMPLE_OPERATION_ID,
                    'Retry-After': '30'
                }
            )
            
            with patch('requests.request', return_value=create_response):
                with pytest.raises(FabricAPIError) as exc_info:
                    fabric_client.create_ontology(
                        display_name="TimeoutTest",
                        definition={"parts": []},
                        wait_for_completion=True
                    )
                
                assert exc_info.value.error_code == 'OperationTimeout'
    
    def test_lro_failure(self, fabric_client):
        """Test LRO failure handling when operation fails."""
        with patch.object(
            fabric_client,
            '_wait_for_operation',
            side_effect=FabricAPIError(500, 'OperationFailed', 'Operation failed.')
        ):
            location_uri = f"{API_BASE_URL}/operations/{SAMPLE_OPERATION_ID}"
            create_response = create_mock_response(
                status_code=202,
                headers={
                    'Location': location_uri,
                    'x-ms-operation-id': SAMPLE_OPERATION_ID,
                    'Retry-After': '30'
                }
            )
            
            with patch('requests.request', return_value=create_response):
                with pytest.raises(FabricAPIError) as exc_info:
                    fabric_client.create_ontology(
                        display_name="FailTest",
                        definition={"parts": []},
                        wait_for_completion=True
                    )
                
                assert exc_info.value.error_code == 'OperationFailed'


# =============================================================================
# STREAMING CONVERTER TESTS
# =============================================================================

@pytest.mark.unit
class TestStreamingRDFConverterBasic:
    """Test basic StreamingRDFConverter functionality."""
    
    def test_init_default_values(self):
        """Test converter initialization with default values."""
        converter = StreamingRDFConverter()
        
        assert converter.id_prefix == 1000000000000
        assert converter.batch_size == StreamingRDFConverter.DEFAULT_BATCH_SIZE
        assert converter.loose_inference is False
        assert converter.id_counter == 0
        assert len(converter.entity_types) == 0
        assert len(converter.relationship_types) == 0
    
    def test_init_custom_values(self):
        """Test converter initialization with custom values."""
        converter = StreamingRDFConverter(
            id_prefix=5000000000000,
            batch_size=5000,
            loose_inference=True
        )
        
        assert converter.id_prefix == 5000000000000
        assert converter.batch_size == 5000
        assert converter.loose_inference is True
    
    def test_reset_state(self):
        """Test state reset between conversions."""
        converter = StreamingRDFConverter()
        
        converter.id_counter = 100
        converter.entity_types['test'] = Mock()
        converter.skipped_items.append(Mock())
        
        converter._reset_state()
        
        assert converter.id_counter == 0
        assert len(converter.entity_types) == 0
        assert len(converter.skipped_items) == 0
    
    def test_generate_id(self):
        """Test unique ID generation."""
        converter = StreamingRDFConverter(id_prefix=1000)
        
        id1 = converter._generate_id()
        id2 = converter._generate_id()
        id3 = converter._generate_id()
        
        assert id1 == "1001"
        assert id2 == "1002"
        assert id3 == "1003"
    
    def test_uri_to_name_fragment(self):
        """Test name extraction from URI with fragment."""
        from rdflib import URIRef
        converter = StreamingRDFConverter()
        
        uri = URIRef("http://example.org/ontology#PersonClass")
        name = converter._uri_to_name(uri)
        
        assert name == "PersonClass"
    
    def test_uri_to_name_path(self):
        """Test name extraction from URI with path."""
        from rdflib import URIRef
        converter = StreamingRDFConverter()
        
        uri = URIRef("http://example.org/ontology/PersonClass")
        name = converter._uri_to_name(uri)
        
        assert name == "PersonClass"
    
    def test_uri_to_name_special_chars(self):
        """Test name cleaning for special characters."""
        from rdflib import URIRef
        converter = StreamingRDFConverter()
        
        uri = URIRef("http://example.org/ontology#Person-Class.Name")
        name = converter._uri_to_name(uri)
        
        assert name == "Person_Class_Name"
    
    def test_uri_to_name_starts_with_number(self):
        """Test name cleaning when starting with number."""
        from rdflib import URIRef
        converter = StreamingRDFConverter()
        
        uri = URIRef("http://example.org/ontology#123Entity")
        name = converter._uri_to_name(uri)
        
        assert name.startswith("E_")


@pytest.mark.unit
class TestStreamingParserWithFiles:
    """Test streaming parser with actual TTL files."""
    
    @pytest.fixture
    def simple_ttl_content(self):
        """Simple ontology for basic tests."""
        return """
        @prefix : <http://example.org/ontology#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Person a owl:Class .
        :Organization a owl:Class .
        
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
    
    @pytest.fixture
    def temp_ttl_file(self, simple_ttl_content):
        """Create a temporary TTL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(simple_ttl_content)
            temp_path = f.name
        
        yield temp_path
        
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_parse_simple_ontology(self, temp_ttl_file):
        """Test parsing a simple ontology file."""
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_ttl_file)
        
        assert isinstance(result, ConversionResult)
        assert len(result.entity_types) == 2
        assert len(result.relationship_types) == 1
        assert result.triple_count > 0
    
    def test_entity_types_extracted(self, temp_ttl_file):
        """Test that entity types are correctly extracted."""
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_ttl_file)
        
        entity_names = {e.name for e in result.entity_types}
        assert "Person" in entity_names
        assert "Organization" in entity_names
    
    def test_data_properties_extracted(self, temp_ttl_file):
        """Test that data properties are correctly assigned to entities."""
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_ttl_file)
        
        person_entity = next((e for e in result.entity_types if e.name == "Person"), None)
        assert person_entity is not None
        
        prop_names = {p.name for p in person_entity.properties}
        assert "name" in prop_names
        assert "age" in prop_names
    
    def test_relationships_extracted(self, temp_ttl_file):
        """Test that relationships are correctly extracted."""
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(temp_ttl_file)
        
        assert len(result.relationship_types) == 1
        rel = result.relationship_types[0]
        assert rel.name == "worksFor"
    
    def test_progress_callback_called(self, temp_ttl_file):
        """Test that progress callback is called during parsing."""
        converter = StreamingRDFConverter()
        progress_values = []
        
        def progress_callback(n):
            progress_values.append(n)
        
        result = converter.parse_ttl_streaming(
            temp_ttl_file,
            progress_callback=progress_callback
        )
        
        assert len(progress_values) >= 1
        assert progress_values[-1] == result.triple_count
    
    def test_file_not_found_raises(self):
        """Test that FileNotFoundError is raised for missing files."""
        converter = StreamingRDFConverter()
        
        with pytest.raises(FileNotFoundError):
            converter.parse_ttl_streaming("/nonexistent/path/file.ttl")
    
    def test_invalid_ttl_raises(self):
        """Test that ValueError is raised for invalid TTL content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
            f.write("this is not valid turtle syntax {{{{")
            temp_path = f.name
        
        try:
            converter = StreamingRDFConverter()
            with pytest.raises(ValueError, match="Invalid RDF/TTL"):
                converter.parse_ttl_streaming(temp_path)
        finally:
            os.unlink(temp_path)


@pytest.mark.unit
class TestStreamingVsStandardConverter:
    """Compare streaming converter output with standard converter."""
    
    @pytest.fixture
    def sample_ttl_content(self):
        """Sample ontology for comparison tests."""
        return """
        @prefix : <http://example.org/test#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Animal a owl:Class .
        :Dog a owl:Class ;
            rdfs:subClassOf :Animal .
        :Cat a owl:Class ;
            rdfs:subClassOf :Animal .
        
        :name a owl:DatatypeProperty ;
            rdfs:domain :Animal ;
            rdfs:range xsd:string .
        
        :age a owl:DatatypeProperty ;
            rdfs:domain :Animal ;
            rdfs:range xsd:integer .
        
        :chases a owl:ObjectProperty ;
            rdfs:domain :Dog ;
            rdfs:range :Cat .
        """
    
    def test_same_entity_count(self, sample_ttl_content):
        """Test same entity count between converters."""
        standard = RDFToFabricConverter()
        standard_entities, _ = standard.parse_ttl(sample_ttl_content)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(sample_ttl_content)
            temp_path = f.name
        
        try:
            streaming = StreamingRDFConverter()
            result = streaming.parse_ttl_streaming(temp_path)
            
            assert len(result.entity_types) == len(standard_entities)
        finally:
            os.unlink(temp_path)
    
    def test_same_entity_names(self, sample_ttl_content):
        """Test same entity names between converters."""
        standard = RDFToFabricConverter()
        standard_entities, _ = standard.parse_ttl(sample_ttl_content)
        standard_names = {e.name for e in standard_entities}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(sample_ttl_content)
            temp_path = f.name
        
        try:
            streaming = StreamingRDFConverter()
            result = streaming.parse_ttl_streaming(temp_path)
            streaming_names = {e.name for e in result.entity_types}
            
            assert streaming_names == standard_names
        finally:
            os.unlink(temp_path)
    
    def test_same_relationship_count(self, sample_ttl_content):
        """Test same relationship count between converters."""
        standard = RDFToFabricConverter()
        _, standard_rels = standard.parse_ttl(sample_ttl_content)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(sample_ttl_content)
            temp_path = f.name
        
        try:
            streaming = StreamingRDFConverter()
            result = streaming.parse_ttl_streaming(temp_path)
            
            assert len(result.relationship_types) == len(standard_rels)
        finally:
            os.unlink(temp_path)


@pytest.mark.unit
class TestParseTTLStreamingFunction:
    """Test the parse_ttl_streaming convenience function."""
    
    @pytest.fixture
    def temp_ontology_file(self):
        """Create a temp ontology file."""
        content = """
        @prefix : <http://example.org/test#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        :Product a owl:Class .
        :productName a owl:DatatypeProperty ;
            rdfs:domain :Product ;
            rdfs:range xsd:string .
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        yield temp_path
        
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_returns_tuple(self, temp_ontology_file):
        """Test that function returns tuple."""
        definition, name, result = parse_ttl_streaming(temp_ontology_file)
        
        assert isinstance(definition, dict)
        assert isinstance(name, str)
        assert isinstance(result, ConversionResult)
    
    def test_definition_has_parts(self, temp_ontology_file):
        """Test that definition has parts array."""
        definition, _, _ = parse_ttl_streaming(temp_ontology_file)
        
        assert 'parts' in definition
        assert isinstance(definition['parts'], list)
    
    def test_name_derived_from_filename(self, temp_ontology_file):
        """Test that ontology name is derived from filename."""
        _, name, _ = parse_ttl_streaming(temp_ontology_file)
        
        assert name
        assert name[0].isalpha()
    
    def test_custom_batch_size(self, temp_ontology_file):
        """Test custom batch size parameter."""
        definition, _, result = parse_ttl_streaming(
            temp_ontology_file,
            batch_size=100
        )
        
        assert isinstance(result, ConversionResult)
    
    def test_invalid_file_raises(self):
        """Test that invalid file path raises error."""
        with pytest.raises(FileNotFoundError):
            parse_ttl_streaming("/nonexistent/file.ttl")


@pytest.mark.unit
class TestCancellationSupport:
    """Test cancellation token support in streaming converter."""
    
    @pytest.fixture
    def large_ttl_file(self):
        """Create a larger ontology for cancellation tests."""
        lines = [
            "@prefix : <http://example.org/test#> .",
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            ""
        ]
        
        for i in range(50):
            lines.append(f":Class{i} a owl:Class .")
        
        for i in range(50):
            lines.append(f":prop{i} a owl:DatatypeProperty ;")
            lines.append(f"    rdfs:domain :Class{i % 50} ;")
            lines.append(f"    rdfs:range xsd:string .")
        
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        yield temp_path
        
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_cancellation_token_checked(self, large_ttl_file):
        """Test that cancellation token is checked during parsing."""
        from src.core import CancellationToken
        
        token = CancellationToken()
        check_count = [0]
        
        original_throw = token.throw_if_cancelled
        def counting_throw():
            check_count[0] += 1
            original_throw()
        token.throw_if_cancelled = counting_throw
        
        converter = StreamingRDFConverter()
        converter.parse_ttl_streaming(large_ttl_file, cancellation_token=token)
        
        assert check_count[0] > 0
    
    def test_pre_cancelled_token_raises(self, large_ttl_file):
        """Test that pre-cancelled token raises immediately."""
        from src.core import CancellationToken, OperationCancelledException
        
        token = CancellationToken()
        token.cancel()
        
        converter = StreamingRDFConverter()
        
        with pytest.raises(OperationCancelledException):
            converter.parse_ttl_streaming(large_ttl_file, cancellation_token=token)


@pytest.mark.unit
class TestSkippedItemTracking:
    """Test skipped item tracking in streaming converter."""
    
    @pytest.fixture
    def ttl_with_incomplete_properties(self):
        """TTL with properties missing domain/range."""
        return """
        @prefix : <http://example.org/test#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Person a owl:Class .
        
        :missingRange a owl:ObjectProperty ;
            rdfs:domain :Person .
        
        :missingDomain a owl:ObjectProperty ;
            rdfs:range :Person .
        
        :missingBoth a owl:ObjectProperty .
        """
    
    def test_skipped_items_tracked(self, ttl_with_incomplete_properties):
        """Test that skipped items are tracked."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(ttl_with_incomplete_properties)
            temp_path = f.name
        
        try:
            converter = StreamingRDFConverter()
            result = converter.parse_ttl_streaming(temp_path)
            
            assert len(result.skipped_items) > 0
            
            skipped_names = {item.name for item in result.skipped_items}
            assert "missingRange" in skipped_names or "missingDomain" in skipped_names
        finally:
            os.unlink(temp_path)


@pytest.mark.unit
class TestSubclassHandling:
    """Test subclass (inheritance) handling in streaming converter."""
    
    @pytest.fixture
    def ttl_with_inheritance(self):
        """TTL with class inheritance."""
        return """
        @prefix : <http://example.org/test#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        
        :Animal a owl:Class .
        :Mammal a owl:Class ;
            rdfs:subClassOf :Animal .
        :Dog a owl:Class ;
            rdfs:subClassOf :Mammal .
        """
    
    def test_parent_relationships_set(self, ttl_with_inheritance):
        """Test that parent relationships are correctly set."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as f:
            f.write(ttl_with_inheritance)
            temp_path = f.name
        
        try:
            converter = StreamingRDFConverter()
            result = converter.parse_ttl_streaming(temp_path)
            
            entities_by_name = {e.name: e for e in result.entity_types}
            
            assert "Animal" in entities_by_name
            assert "Mammal" in entities_by_name
            assert "Dog" in entities_by_name
            
            animal = entities_by_name["Animal"]
            mammal = entities_by_name["Mammal"]
            dog = entities_by_name["Dog"]
            
            assert animal.baseEntityTypeId is None
            assert mammal.baseEntityTypeId == animal.id
            assert dog.baseEntityTypeId == mammal.id
        finally:
            os.unlink(temp_path)


@pytest.mark.samples
class TestSampleOntologiesStreaming:
    """Test streaming converter with sample ontology files."""
    
    @pytest.fixture
    def samples_dir(self):
        """Get path to samples/rdf directory for RDF tests."""
        samples = ROOT_DIR / "samples" / "rdf"
        if not samples.exists():
            pytest.skip("samples/rdf directory not found")
        return samples
    
    def test_supply_chain_ontology(self, samples_dir):
        """Test streaming parser with supply chain sample."""
        ttl_file = samples_dir / "sample_supply_chain_ontology.ttl"
        if not ttl_file.exists():
            pytest.skip("supply chain sample not found")
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(str(ttl_file))
        
        assert isinstance(result, ConversionResult)
        assert len(result.entity_types) > 0
        assert result.triple_count > 0
    
    def test_iot_ontology(self, samples_dir):
        """Test streaming parser with IoT sample."""
        ttl_file = samples_dir / "sample_iot_ontology.ttl"
        if not ttl_file.exists():
            pytest.skip("IoT sample not found")
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(str(ttl_file))
        
        assert isinstance(result, ConversionResult)
        assert len(result.entity_types) > 0
    
    def test_foaf_ontology(self, samples_dir):
        """Test streaming parser with FOAF sample."""
        ttl_file = samples_dir / "sample_foaf_ontology.ttl"
        if not ttl_file.exists():
            pytest.skip("FOAF sample not found")
        
        converter = StreamingRDFConverter()
        result = converter.parse_ttl_streaming(str(ttl_file))
        
        assert isinstance(result, ConversionResult)
        assert result.success_rate > 0


@pytest.mark.unit
class TestStreamingThreshold:
    """Test streaming threshold constant."""
    
    def test_threshold_value(self):
        """Test that streaming threshold is set appropriately."""
        assert StreamingRDFConverter.STREAMING_THRESHOLD_MB >= 50
        assert StreamingRDFConverter.STREAMING_THRESHOLD_MB <= 500
    
    def test_default_batch_size(self):
        """Test default batch size is reasonable."""
        assert StreamingRDFConverter.DEFAULT_BATCH_SIZE >= 1000
        assert StreamingRDFConverter.DEFAULT_BATCH_SIZE <= 100000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
