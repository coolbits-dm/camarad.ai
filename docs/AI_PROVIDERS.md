# AI Providers

Camarad separates agent roles from model providers.

Agents define role behavior, tool permissions, workflow expectations, and output
contracts. Providers supply model execution.

## MVP Modes

Hosted Camarad can use a platform OpenAI key, but only server-side:

```env
CAMARAD_DISTRIBUTION=hosted
CAMARAD_PROVIDER_MODE=platform_default
ALLOW_PLATFORM_DEFAULT_PROVIDER=true
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_DEFAULT_MODEL=gpt-4.1-mini
```

Open-source/self-hosted Camarad uses instance BYOK:

```env
CAMARAD_DISTRIBUTION=self_hosted
CAMARAD_PROVIDER_MODE=byok
ALLOW_PLATFORM_DEFAULT_PROVIDER=false
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_DEFAULT_MODEL=gpt-4.1-mini
```

Self-hosted instances fail closed if `platform_default` is selected. They must
provide their own key or remain in `setup_required`.

## Safe Status

Use:

```http
GET /api/ai/provider/status
```

The endpoint returns safe metadata only:

```json
{
  "distribution": "self_hosted",
  "mode": "byok",
  "configured": true,
  "status": "configured",
  "provider": "openai",
  "credential_source": "instance_env",
  "default_model": "gpt-4.1-mini",
  "message": "OpenAI instance BYOK provider is configured server-side."
}
```

It must never return API keys, key prefixes, project secrets, or raw environment
dumps.

## Current Scope

This is the first provider policy layer. It centralizes configuration decisions
and exposes a safe status endpoint. It does not yet migrate every model call to
the OpenAI Responses API.

Next provider-runtime increment:

- add `backend_py/ai/providers/base.py`
- add an OpenAI Responses API provider
- route model execution through a provider router
- keep user/workspace BYOK behind a later encrypted credential-store task
