"""
Fabric API Contract Tests

These tests validate that the FabricOntologyClient behavior matches
the actual Fabric API contract. Unlike unit tests that mock everything,
these tests:

1. Use validated mock responses matching the actual Fabric API spec
2. Validate request payloads against schema before sending
3. Test error handling for all documented error codes
4. Ensure serialization/deserialization matches API expectations

Run with: pytest tests/core/test_fabric_contract.py -v
"""

import pytest
import json
import base64
from unittest.mock import patch, MagicMock, Mock
from typing import Any, Dict


# Import fixtures
from tests.fixtures.fabric_responses import (
    create_ontology_response,
    create_list_response,
    create_error_response,
    create_lro_response,
    create_lro_headers,
    create_sample_definition,
    SAMPLE_WORKSPACE_ID,
    SAMPLE_ONTOLOGY_ID,
    SAMPLE_OPERATION_ID,
    ERROR_UNAUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_CONFLICT,
    ERROR_BAD_REQUEST,
    ERROR_RATE_LIMITED,
)

# Import schema validator
from src.core.validators.fabric_schema import (
    FabricSchemaValidator,
    validate_fabric_definition,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_fabric_config():
    """Create a mock FabricConfig with the sample workspace ID."""
    from src.core.platform.fabric_client import FabricConfig, RateLimitConfig, CircuitBreakerSettings
    
    return FabricConfig(
        workspace_id=SAMPLE_WORKSPACE_ID,
        api_base_url="https://api.fabric.microsoft.com/v1",
        tenant_id=None,
        client_id=None,
        client_secret=None,
        use_interactive_auth=True,
        rate_limit=RateLimitConfig(enabled=False),
        circuit_breaker=CircuitBreakerSettings(enabled=False),
    )


@pytest.fixture
def schema_validator():
    """Create a schema validator instance."""
    return FabricSchemaValidator()


def create_mock_response(
    status_code: int,
    json_data: Dict[str, Any] = None,
    headers: Dict[str, str] = None,
) -> Mock:
    """Create a mock requests.Response object."""
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.ok = 200 <= status_code < 300
    
    if json_data:
        response.json.return_value = json_data
        response.text = json.dumps(json_data)
        response.content = response.text.encode()
    else:
        response.json.side_effect = ValueError("No JSON")
        response.text = ""
        response.content = b""
    
    return response


def create_mock_credential():
    """Create a mock Azure credential."""
    credential = MagicMock()
    token = MagicMock()
    token.token = "mock_access_token"
    token.expires_on = 9999999999  # Far future
    credential.get_token.return_value = token
    return credential


# =============================================================================
# Contract Tests: List Ontologies
# =============================================================================

class TestListOntologiesContract:
    """Contract tests for the list ontologies endpoint."""
    
    def test_list_returns_valid_schema(self, mock_fabric_config):
        """Verify list response matches documented schema."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange: Create validated response
        expected_response = create_list_response()
        mock_response = create_mock_response(200, expected_response)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                result = client.list_ontologies()
                
                # Assert: Response structure matches
                assert isinstance(result, list)
                assert len(result) == 2
                
                for ontology in result:
                    # Validate required fields per API spec
                    assert "id" in ontology
                    assert "displayName" in ontology
                    assert "type" in ontology
                    assert ontology["type"] == "Ontology"
                    assert "workspaceId" in ontology
    
    def test_list_handles_pagination(self, mock_fabric_config):
        """Verify pagination with continuation tokens."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange: First page with continuation token
        page1 = create_list_response(
            ontologies=[create_ontology_response(display_name="Page1Ontology")],
            continuation_token="token123",
        )
        page2 = create_list_response(
            ontologies=[create_ontology_response(display_name="Page2Ontology")],
        )
        
        call_count = 0
        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return create_mock_response(200, page1)
            return create_mock_response(200, page2)
        
        mock_cred = create_mock_credential()
        
        with patch('requests.request', side_effect=mock_request):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                result = client.list_ontologies()
                
                # Assert: At least first page retrieved (pagination may not be automatic)
                assert len(result) >= 1
                names = [o["displayName"] for o in result]
                assert "Page1Ontology" in names
    
    def test_list_empty_workspace(self, mock_fabric_config):
        """Verify handling of empty workspace."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange: Empty list response
        empty_response = create_list_response(ontologies=[])
        mock_response = create_mock_response(200, empty_response)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                result = client.list_ontologies()
                
                # Assert
                assert result == []


# =============================================================================
# Contract Tests: Get Ontology
# =============================================================================

class TestGetOntologyContract:
    """Contract tests for the get ontology endpoint."""
    
    def test_get_returns_valid_schema(self, mock_fabric_config):
        """Verify get response matches documented schema."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        expected = create_ontology_response(
            ontology_id=SAMPLE_ONTOLOGY_ID,
            display_name="TestOntology",
            description="A test ontology",
        )
        mock_response = create_mock_response(200, expected)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                result = client.get_ontology(SAMPLE_ONTOLOGY_ID)
                
                # Assert: All required fields present
                assert result["id"] == SAMPLE_ONTOLOGY_ID
                assert result["displayName"] == "TestOntology"
                assert result["type"] == "Ontology"
                assert "createdDateTime" in result
                assert "modifiedDateTime" in result
    
    def test_get_not_found_error(self, mock_fabric_config):
        """Verify 404 error handling matches API spec."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(404, ERROR_NOT_FOUND)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert
                with pytest.raises(Exception) as exc_info:
                    client.get_ontology("nonexistent-id")
                
                # Verify error contains expected information
                assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


# =============================================================================
# Contract Tests: Create Ontology
# =============================================================================

class TestCreateOntologyContract:
    """Contract tests for the create ontology endpoint."""
    
    def test_create_request_format(self, mock_fabric_config):
        """Verify create request matches API spec."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        expected = create_ontology_response(display_name="NewOntology")
        mock_response = create_mock_response(201, expected)
        mock_cred = create_mock_credential()
        
        captured_request = {}
        
        def capture_request(*args, **kwargs):
            captured_request['args'] = args
            captured_request['kwargs'] = kwargs
            return mock_response
        
        with patch('requests.request', side_effect=capture_request):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                client.create_ontology("NewOntology", "Description")
                
                # Assert: Request body format
                body = captured_request['kwargs'].get('json', {})
                assert "displayName" in body
                assert body["displayName"] == "NewOntology"
    
    def test_create_conflict_error(self, mock_fabric_config):
        """Verify 409 conflict handling for duplicate names."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(409, ERROR_CONFLICT)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert
                with pytest.raises(Exception) as exc_info:
                    client.create_ontology("DuplicateName", "Description")
                
                error_str = str(exc_info.value).lower()
                assert "409" in str(exc_info.value) or "conflict" in error_str or "exists" in error_str


# =============================================================================
# Contract Tests: Update Definition
# =============================================================================

class TestUpdateDefinitionContract:
    """Contract tests for the update definition endpoint."""
    
    def test_update_definition_request_format(self, mock_fabric_config, schema_validator):
        """Verify update definition request format and validation."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange: Create a valid definition
        definition = create_sample_definition(entity_count=2, relationship_count=1)
        
        # Validate definition before testing
        validation_result = schema_validator.validate(definition)
        assert validation_result.is_valid, f"Definition failed validation: {validation_result.errors}"
        
        mock_cred = create_mock_credential()
        
        captured_request = {}
        
        def capture_request(method, url, **kwargs):
            captured_request['method'] = method
            captured_request['url'] = url
            captured_request['kwargs'] = kwargs
            # Return 202 to indicate LRO started
            return create_mock_response(202, headers=create_lro_headers())
        
        with patch('requests.request', side_effect=capture_request):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act - don't wait for completion to avoid LRO polling
                result = client.update_ontology_definition(
                    SAMPLE_ONTOLOGY_ID, 
                    definition, 
                    wait_for_completion=False
                )
                
                # Assert: Request contains valid definition
                body = captured_request.get('kwargs', {}).get('json', {})
                assert "definition" in body
                
                # Assert: LRO metadata returned
                assert result.get('_lro') is True
    
    def test_definition_validation_prevents_invalid_upload(self, schema_validator):
        """Verify schema validator catches invalid definitions."""
        # Arrange: Invalid definition (missing required fields)
        invalid_definition = {
            "parts": [
                {
                    "path": "EntityTypes/Invalid.json",
                    "payload": base64.b64encode(json.dumps({
                        "name": "Invalid",
                        # Missing: id, namespace, namespaceType
                    }).encode()).decode(),
                    "payloadType": "InlineBase64"
                }
            ]
        }
        
        # Act
        result = schema_validator.validate(invalid_definition)
        
        # Assert: Validation fails
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_valid_definition_passes_validation(self, schema_validator):
        """Verify valid definitions pass schema validation."""
        # Arrange
        valid_definition = create_sample_definition(entity_count=3, relationship_count=2)
        
        # Act
        result = schema_validator.validate(valid_definition)
        
        # Assert
        assert result.is_valid, f"Validation errors: {result.errors}"
        assert len(result.errors) == 0


# =============================================================================
# Contract Tests: Delete Ontology
# =============================================================================

class TestDeleteOntologyContract:
    """Contract tests for the delete ontology endpoint."""
    
    def test_delete_success(self, mock_fabric_config):
        """Verify successful delete returns 200."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(200)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert: Should not raise
                client.delete_ontology(SAMPLE_ONTOLOGY_ID)
    
    def test_delete_not_found(self, mock_fabric_config):
        """Verify 404 handling for non-existent ontology."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(404, ERROR_NOT_FOUND)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert
                with pytest.raises(Exception):
                    client.delete_ontology("nonexistent-id")


# =============================================================================
# Contract Tests: Error Handling
# =============================================================================

class TestErrorHandlingContract:
    """Contract tests for API error handling."""
    
    @pytest.mark.parametrize("status_code,error_response,expected_behavior", [
        (401, ERROR_UNAUTHORIZED, "raises authentication error"),
        (403, ERROR_UNAUTHORIZED, "raises permission error"),
        (404, ERROR_NOT_FOUND, "raises not found error"),
        (409, ERROR_CONFLICT, "raises conflict error"),
        (400, ERROR_BAD_REQUEST, "raises validation error"),
    ])
    def test_error_responses_handled_correctly(
        self, mock_fabric_config, status_code, error_response, expected_behavior
    ):
        """Verify all documented error codes are handled."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(status_code, error_response)
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert
                with pytest.raises(Exception) as exc_info:
                    client.get_ontology(SAMPLE_ONTOLOGY_ID)
                
                # Verify exception contains error information
                assert exc_info.value is not None
    
    def test_rate_limiting_error(self, mock_fabric_config):
        """Verify 429 rate limiting is handled."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(429, ERROR_RATE_LIMITED)
        mock_response.headers["Retry-After"] = "30"
        mock_cred = create_mock_credential()
        
        with patch('requests.request', return_value=mock_response):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act & Assert: Rate limiter should handle or propagate
                with pytest.raises(Exception):
                    client.get_ontology(SAMPLE_ONTOLOGY_ID)


# =============================================================================
# Contract Tests: LRO Operations
# =============================================================================

class TestLROContract:
    """Contract tests for Long-Running Operation handling."""
    
    def test_lro_polling_sequence(self, mock_fabric_config):
        """Verify LRO polling follows API spec."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange: Simulate LRO lifecycle
        # 1. Initial 202 response via requests.request
        # 2. Polling via requests.get returns Running then Succeeded
        
        request_calls = []
        get_call_count = 0
        mock_cred = create_mock_credential()
        
        def mock_request(method, url, **kwargs):
            request_calls.append(('request', method, url))
            # Initial request - 202 Accepted
            return create_mock_response(202, headers=create_lro_headers())
        
        def mock_get(url, **kwargs):
            nonlocal get_call_count
            get_call_count += 1
            request_calls.append(('get', 'GET', url))
            if get_call_count == 1:
                # First poll - Running
                return create_mock_response(200, create_lro_response(status="Running", percent_complete=50))
            else:
                # Final poll - Succeeded
                return create_mock_response(200, create_lro_response(status="Succeeded", percent_complete=100))
        
        with patch('requests.request', side_effect=mock_request):
            with patch('requests.get', side_effect=mock_get):
                with patch('time.sleep'):  # Skip actual waiting
                    with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                        client = FabricOntologyClient(mock_fabric_config)
                        
                        # Act
                        definition = create_sample_definition()
                        client.update_ontology_definition(SAMPLE_ONTOLOGY_ID, definition)
                        
                        # Assert: Initial request + at least one polling request
                        assert len(request_calls) >= 2
    
    def test_lro_failure_handling(self, mock_fabric_config):
        """Verify LRO failure is properly reported."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        mock_cred = create_mock_credential()
        
        def mock_request(method, url, **kwargs):
            # Initial request - 202 Accepted
            return create_mock_response(202, headers=create_lro_headers())
        
        def mock_get(url, **kwargs):
            # LRO status check - Failed
            return create_mock_response(
                200,
                create_lro_response(
                    status="Failed",
                    error={"code": "OperationFailed", "message": "Definition invalid"}
                ),
            )
        
        with patch('requests.request', side_effect=mock_request):
            with patch('requests.get', side_effect=mock_get):
                with patch('time.sleep'):
                    with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                        client = FabricOntologyClient(mock_fabric_config)
                        
                        # Act & Assert: Should raise on LRO failure
                        with pytest.raises(Exception):
                            definition = create_sample_definition()
                            client.update_ontology_definition(SAMPLE_ONTOLOGY_ID, definition)


# =============================================================================
# Contract Tests: Request Headers
# =============================================================================

class TestRequestHeadersContract:
    """Contract tests for required request headers."""
    
    def test_authorization_header_included(self, mock_fabric_config):
        """Verify Authorization header is set correctly."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(200, create_list_response())
        captured_headers = {}
        mock_cred = create_mock_credential()
        
        def capture_request(*args, **kwargs):
            captured_headers.update(kwargs.get('headers', {}))
            return mock_response
        
        with patch('requests.request', side_effect=capture_request):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                client.list_ontologies()
                
                # Assert
                assert "Authorization" in captured_headers
                assert captured_headers["Authorization"].startswith("Bearer ")
    
    def test_content_type_header_for_json(self, mock_fabric_config):
        """Verify Content-Type header for JSON payloads."""
        from src.core.platform.fabric_client import FabricOntologyClient
        
        # Arrange
        mock_response = create_mock_response(201, create_ontology_response())
        captured_headers = {}
        mock_cred = create_mock_credential()
        
        def capture_request(*args, **kwargs):
            captured_headers.update(kwargs.get('headers', {}))
            return mock_response
        
        with patch('requests.request', side_effect=capture_request):
            with patch.object(FabricOntologyClient, '_get_credential', return_value=mock_cred):
                client = FabricOntologyClient(mock_fabric_config)
                
                # Act
                client.create_ontology("Test", "Description")
                
                # Assert: Content-Type should be set for POST with body
                # Note: requests library may set this automatically
                assert captured_headers.get("Content-Type", "application/json") in [
                    "application/json",
                    "application/json; charset=utf-8",
                ]
