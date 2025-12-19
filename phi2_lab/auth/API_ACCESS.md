# PhiLab API Access Control

## Overview

PhiLab uses API keys to control access to different models:

- **Phi-2 is open access** - No API key required
- **Other models require an API key** - Phi-3, Llama, Mistral, etc.

## Getting an API Key

Contact the PhiLab maintainers to request an API key for restricted models.

## Using Your API Key

You can provide your API key in three ways (in order of priority):

### 1. HTTP Header (Recommended)

```bash
curl -H "X-PhiLab-API-Key: your_key_here" \
  "http://localhost:8000/api/geometry/runs?model=microsoft/phi-3-mini-4k-instruct"
```

### 2. Query Parameter

```bash
curl "http://localhost:8000/api/geometry/runs?model=microsoft/phi-3-mini-4k-instruct&api_key=your_key_here"
```

### 3. Environment Variable

```bash
export PHILAB_API_KEY=your_key_here
# Then make requests without including the key
```

## Available Endpoints

### Check Available Models

```
GET /api/geometry/models
```

Returns models you have access to based on your API key:

```json
{
  "models": ["microsoft/phi-2", "phi-2", "phi2"],
  "default": "microsoft/phi-2",
  "authenticated": false
}
```

With a valid API key:

```json
{
  "models": ["microsoft/phi-2", "microsoft/phi-3-mini-4k-instruct", ...],
  "default": "microsoft/phi-2",
  "authenticated": true
}
```

### Query Runs

```
GET /api/geometry/runs?model=microsoft/phi-2
GET /api/geometry/runs?model=microsoft/phi-3-mini-4k-instruct&api_key=YOUR_KEY
```

## Error Responses

### 403 Forbidden

```json
{
  "detail": "Model 'microsoft/phi-3-mini-4k-instruct' requires a valid API key. Phi-2 is open access and does not require a key."
}
```

## For Administrators

### Setting Up API Keys

Create API keys using the helper function:

```python
from phi2_lab.auth import generate_api_key

key = generate_api_key()
print(key)  # e.g., "philab_a1b2c3d4e5f6..."
```

### Environment Variables

Set these environment variables on your server:

```bash
# Comma-separated list of valid API keys
export PHILAB_ALLOWED_KEYS="philab_key1,philab_key2,philab_key3"

# Admin keys have full access and higher rate limits
export PHILAB_ADMIN_KEYS="philab_admin_key1"
```

## Rate Limits

| Tier | Requests/Hour |
|------|---------------|
| Unauthenticated (phi-2 only) | 100 |
| Authenticated | 1,000 |
| Admin | 10,000 |

## Open Access Models

These models never require an API key:

- `microsoft/phi-2`
- `phi-2`
- `phi2`

## Restricted Models

These models require an API key:

- `microsoft/phi-3-mini-4k-instruct`
- `microsoft/phi-3-mini-128k-instruct`
- `microsoft/phi-3-small-8k-instruct`
- `microsoft/phi-3-medium-4k-instruct`
- `meta-llama/Llama-2-7b-hf`
- `mistralai/Mistral-7B-v0.1`

Additional models can be added in `config/app.yaml`.
