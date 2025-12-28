# Configuration Guide

## Authentication

Two options:

- Interactive (dev): `use_interactive_auth: true` — opens a browser to sign in
- Service principal (CI/CD): `use_interactive_auth: false` — set `client_id`, `tenant_id`, and provide `client_secret` via environment variable

Required permission for service principals: `Item.ReadWrite.All`.

## Finding Your Configuration Values

### Workspace ID

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com)
2. Navigate to your workspace
3. The workspace ID is in the URL: `https://app.fabric.microsoft.com/groups/{workspace-id}/...`

### Tenant ID

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com)
2. Navigate to your workspace
3. Click your profile photo (top right).
4. See Tenant details

```

## Environment Variables

Environment variables override `config.json`. Recommended for secrets:

```powershell
# Windows (PowerShell)
$env:FABRIC_CLIENT_SECRET = "<secret>"

# Linux/Mac
export FABRIC_CLIENT_SECRET="<secret>"
```

## Security Best Practices

- Never commit secrets to source control
- Prefer Managed Identity or Key Vault for production
- Use environment variables for local development secrets
- Keep `src/config.json` in `.gitignore`

## Config - Interactive authentication

Create `src/config.json`:

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "use_interactive_auth": true
  },
  "ontology": { "default_namespace": "usertypes", "id_prefix": 1000000000000 },
  "logging":  { "level": "INFO", "log_file": "logs/app.log" }
}
```

## Config - Service Principal

Note: This has not been tested

```json
{
  "fabric": {
    "workspace_id": "<workspace-id>",
    "tenant_id": "<tenant-id>",
    "client_id": "<app-id>",
    "use_interactive_auth": false,
    "rate_limit": { "enabled": true, "requests_per_minute": 10, "burst": 15 },
    "circuit_breaker": { "enabled": true, "failure_threshold": 5, "recovery_timeout": 60.0, "success_threshold": 2 }
  }
}
```


## Configuration Options

### Fabric Settings

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `workspace_id` | string | Yes | Your Microsoft Fabric workspace GUID |
| `ontology_id` | string | No | Specific ontology ID (leave empty for name-based operations) |
| `api_base_url` | string | Yes | Fabric API base URL (default shown above) |
| `tenant_id` | string | Yes | Azure AD tenant ID |
| `client_id` | string | Yes | Azure AD application client ID |
| `client_secret` | string | No | Client secret (use env var; avoid storing in files) |
| `use_interactive_auth` | boolean | Yes | Use interactive browser login (true) or service principal (false) |

### Ontology Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_namespace` | string | "usertypes" | Default namespace for custom types |
| `id_prefix` | integer | 1000000000000 | Starting ID for generated entity/property IDs |

### Logging Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | "INFO" | Logging level: DEBUG, INFO, WARNING, ERROR |
| `log_file` | string | "rdf_import.log" | Path to log file |

### Rate Limiting Settings

Used to avoid 429s by throttling proactively. Defaults are conservative. See official [Fabric throttling](https://learn.microsoft.com/en-us/rest/api/fabric/articles/throttling).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `rate_limit.enabled` | boolean | true | Enable client-side rate limiting |
| `rate_limit.requests_per_minute` | integer | 10 | Long-term request rate |
| `rate_limit.burst` | integer | 15 | Short burst capacity |

Tuning: lower the rate if you hit 429s; raise modestly if you never do.

### Circuit Breaker Settings

Prevents cascading failures when the API is unhealthy.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `circuit_breaker.enabled` | boolean | true | Enable circuit breaker |
| `circuit_breaker.failure_threshold` | integer | 5 | Failures before opening circuit |
| `circuit_breaker.recovery_timeout` | float | 60.0 | Wait before attempting recovery |
| `circuit_breaker.success_threshold` | integer | 2 | Successes to fully close circuit |

## Troubleshooting

### "Unauthorized" Error
- Verify tenant_id, client_id, and client_secret
- Check app registration permissions
- Ensure you have Contributor access to the workspace

### "Invalid workspace_id"
- Confirm the workspace ID is correct
- Verify workspace has Ontology feature enabled
- Check you have access to the workspace

### Interactive auth not working
- Ensure you're using the correct tenant_id
- Try signing out and back in
- Check browser allows popups from Microsoft login

## Configuration Validation

Quick sanity check:

```powershell
python src/main.py test
```

## Multiple Configurations

You can maintain multiple configurations:

```powershell
# Development
python src\main.py upload sample.ttl --config config.dev.json

# Production
python src\main.py upload sample.ttl --config config.prod.json
```

