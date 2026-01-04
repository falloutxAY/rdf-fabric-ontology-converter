# Configuration Guide

## Quick Setup

1. Copy the sample config: `copy config.sample.json src\config.json`
2. Edit with your Fabric workspace details
3. Test: `python -m src.main test`

## Authentication

| Method | Use Case | Config |
|--------|----------|--------|
| **Interactive** | Development | `"use_interactive_auth": true` |
| **Service Principal** | CI/CD | `"use_interactive_auth": false` + credentials |

### Interactive (Browser Login)

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "use_interactive_auth": true
  }
}
```

### Service Principal

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "client_id": "YOUR_CLIENT_ID",
    "use_interactive_auth": false
  }
}
```

Set the secret via environment variable (never in config file):
```powershell
$env:FABRIC_CLIENT_SECRET = "your-secret"
```

**Required permission:** `Item.ReadWrite.All`

## Finding Your IDs

### Workspace ID
1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com)
2. Navigate to your workspace
3. Copy from URL: `https://app.fabric.microsoft.com/groups/{workspace-id}/...`

### Tenant ID
1. Click your profile photo (top right)
2. See "Tenant details"

## Environment Variables

Environment variables override config file values:

| Variable | Description |
|----------|-------------|
| `FABRIC_CLIENT_SECRET` | Service principal secret |
| `AZURE_TENANT_ID` | Tenant ID |
| `AZURE_CLIENT_ID` | Client ID |
| `AZURE_CLIENT_SECRET` | Alternative to `FABRIC_CLIENT_SECRET` |

## Configuration Options

### Full Example

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "client_id": "YOUR_CLIENT_ID",
    "use_interactive_auth": false,
    "rate_limit": {
      "enabled": true,
      "requests_per_minute": 10
    },
    "circuit_breaker": {
      "enabled": true,
      "failure_threshold": 5,
      "recovery_timeout": 60.0
    }
  },
  "ontology": {
    "default_namespace": "usertypes",
    "id_prefix": 1000000000000
  },
  "dtdl": {
    "component_mode": "skip",
    "command_mode": "skip",
    "scaled_decimal_mode": "json_string"
  },
  "logging": {
    "level": "INFO",
    "file": "logs/app.log"
  }
}
```

### Fabric Settings

| Option | Required | Description |
|--------|----------|-------------|
| `workspace_id` | Yes | Fabric workspace GUID |
| `tenant_id` | Yes | Azure AD tenant ID |
| `client_id` | For SP | Service principal client ID |
| `use_interactive_auth` | Yes | `true` for browser, `false` for SP |

### Rate Limiting

| Option | Default | Description |
|--------|---------|-------------|
| `rate_limit.enabled` | `true` | Enable client-side rate limiting |
| `rate_limit.requests_per_minute` | `10` | Request rate |
| `rate_limit.burst` | `15` | Short burst capacity |

### Circuit Breaker

| Option | Default | Description |
|--------|---------|-------------|
| `circuit_breaker.enabled` | `true` | Enable circuit breaker |
| `circuit_breaker.failure_threshold` | `5` | Failures before opening |
| `circuit_breaker.recovery_timeout` | `60.0` | Seconds to wait before retry |

### DTDL Settings

| Option | Default | Description |
|--------|---------|-------------|
| `dtdl.component_mode` | `skip` | `skip`, `flatten`, or `separate` |
| `dtdl.command_mode` | `skip` | `skip`, `property`, or `entity` |
| `dtdl.scaled_decimal_mode` | `json_string` | `json_string`, `structured`, or `calculated` |

### Logging

| Option | Default | Description |
|--------|---------|-------------|
| `logging.level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `logging.file` | `logs/app.log` | Log file path |
| `logging.format` | `text` | `text` or `json` |

## Multiple Configurations

```powershell
python -m src.main upload --format rdf sample.ttl --config config.dev.json
python -m src.main upload --format rdf sample.ttl --config config.prod.json
```

## Security Best Practices

- ✅ Use environment variables for secrets
- ✅ Keep `config.json` in `.gitignore`
- ✅ Use Managed Identity for Azure-hosted deployments
- ✅ Use Azure Key Vault for production secrets
- ❌ Never commit secrets to source control

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Unauthorized" | Verify credentials, check workspace access |
| "Invalid workspace_id" | Confirm workspace ID, verify Ontology feature enabled |
| Interactive auth not working | Check tenant_id, allow browser popups |

Test your configuration:
```powershell
python -m src.main test
```

## See Also

- [CLI Commands](CLI_COMMANDS.md) - Command reference
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

