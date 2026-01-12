# Configuration Guide

## Quick Setup

1. Copy the sample config: `copy config.sample.json config.json` (in project root)
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
    "client_id": "04b07795-8ddb-461a-bbcb-537c989290d8",
    "use_interactive_auth": true
  }
}
```

> **Note:** The `client_id` above is Azure CLI's well-known client ID. You can use your own app registration if needed.

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

### Service Principal Client ID

To use a Service Principal, you need to create an App Registration in Microsoft Entra ID:

1. **Go to Azure Portal** → [portal.azure.com](https://portal.azure.com)

2. **Navigate to Microsoft Entra ID** → **App registrations** → **New registration**

3. **Create the app:**
   - Name: e.g., `RDF-DTDL-Converter`
   - Supported account types: "Accounts in this organizational directory only"
   - Click **Register**

4. **Copy the Client ID:**
   - On the app's **Overview** page, copy the **Application (client) ID** — this is your `client_id`

5. **Create a Client Secret:**
   - Go to **Certificates & secrets** → **New client secret**
   - Add a description and expiration
   - Copy the **Value** immediately (you won't see it again) — set this as `FABRIC_CLIENT_SECRET`

6. **Grant Fabric API Permission:**
   - Go to **API permissions** → **Add a permission**
   - Select **APIs my organization uses** → search for **Power BI Service**
   - Add **Application permission**: `Item.ReadWrite.All`
   - Click **Grant admin consent** (requires admin privileges)

## Environment Variables

Environment variables override config file values:

| Variable | Description |
|----------|-------------|
| `FABRIC_CLIENT_SECRET` | Service principal secret |
| `AZURE_TENANT_ID` | Tenant ID |
| `AZURE_CLIENT_ID` | Client ID |
| `AZURE_CLIENT_SECRET` | Alternative to `FABRIC_CLIENT_SECRET` |
| `FABRIC_USE_SDK` | Set to `true` to use the SDK client instead of legacy |

## SDK Client Mode

This tool can use the [Unofficial-Fabric-Ontology-SDK](https://github.com/falloutxAY/Unofficial-Fabric-Ontology-SDK) for Fabric API operations:

```powershell
# Enable SDK mode (recommended)
$env:FABRIC_USE_SDK = "true"

# Run commands as usual
python -m src.main list
```

**Benefits of SDK mode:**
- Consistent behavior with other SDK consumers
- Automatic version updates via Dependabot
- Shared authentication and error handling

> **Note:** The legacy client (`FabricOntologyClient`) is still available and used by default. Set the environment variable to switch to the SDK adapter.

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
| `client_id` | Yes | Azure CLI client ID (`04b07795-8ddb-461a-bbcb-537c989290d8`) for interactive, or your app registration for SP |
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

