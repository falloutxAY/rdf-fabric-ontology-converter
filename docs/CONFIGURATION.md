# Configuration Guide

## Overview

The RDF to Fabric Ontology Converter uses a JSON configuration file to manage connection settings, authentication, and conversion options.

## Configuration File

Create `config.json` in the project root:

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "ontology_id": "",
    "api_base_url": "https://api.fabric.microsoft.com/v1",
    "tenant_id": "YOUR_TENANT_ID",
    "client_id": "",
    "client_secret": "",
    "use_interactive_auth": true
  },
  "ontology": {
    "default_namespace": "usertypes",
    "id_prefix": 1000000000000
  },
  "logging": {
    "level": "INFO",
    "log_file": "rdf_import.log"
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
| `client_secret` | string | No | Client secret (leave empty for interactive auth) |
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

## Authentication Methods

### Interactive Authentication (Recommended for Development)

```json
{
  "fabric": {
    "use_interactive_auth": true,
    "client_id": "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
    "tenant_id": "YOUR_TENANT_ID"
  }
}
```

This uses the Azure CLI public client and opens a browser for login.

### Service Principal Authentication (For Automation)

1. Create an App Registration in Azure AD
2. Grant required permissions:
   - `Item.ReadWrite.All` (delegated)
3. Create a client secret
4. Configure:

```json
{
  "fabric": {
    "use_interactive_auth": false,
    "client_id": "YOUR_APP_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "tenant_id": "YOUR_TENANT_ID"
  }
}
```

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

You can also use environment variables (they override config.json):

```bash
# Windows
set FABRIC_WORKSPACE_ID=your-workspace-id
set FABRIC_TENANT_ID=your-tenant-id

# Linux/Mac
export FABRIC_WORKSPACE_ID=your-workspace-id
export FABRIC_TENANT_ID=your-tenant-id
```

## Security Best Practices

### For Development
- ✅ Use interactive authentication
- ✅ Keep `config.json` in `.gitignore`
- ✅ Use `config.sample.json` for templates

### For Production
- ✅ Use service principal authentication
- ✅ Store secrets in Azure Key Vault or similar
- ✅ Use managed identities when possible
- ✅ Rotate secrets regularly

⚠️ Never commit secrets to source control

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

The tool validates your configuration on startup:

```bash
python main.py test
```

This will:
- ✅ Check configuration file exists
- ✅ Validate required fields
- ✅ Test authentication
- ✅ Verify workspace access

## Multiple Configurations

You can maintain multiple configurations:

```bash
# Development
python main.py upload sample.ttl --config config.dev.json

# Production
python main.py upload sample.ttl --config config.prod.json
```

## Example Configurations

### Minimal Configuration (Interactive Auth)
```json
{
  "fabric": {
    "workspace_id": "12345678-1234-1234-1234-123456789abc",
    "tenant_id": "87654321-4321-4321-4321-cba987654321",
    "use_interactive_auth": true
  }
}
```

### Full Configuration (Service Principal)
```json
{
  "fabric": {
    "workspace_id": "12345678-1234-1234-1234-123456789abc",
    "ontology_id": "",
    "api_base_url": "https://api.fabric.microsoft.com/v1",
    "tenant_id": "87654321-4321-4321-4321-cba987654321",
    "client_id": "abcdef12-3456-7890-abcd-ef1234567890",
    "client_secret": "your-secret-here",
    "use_interactive_auth": false
  },
  "ontology": {
    "default_namespace": "usertypes",
    "id_prefix": 1000000000000
  },
  "logging": {
    "level": "INFO",
    "log_file": "rdf_import.log"
  }
}
```
