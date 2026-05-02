"""Safe AI provider policy resolution.

This module intentionally does not initialize SDK clients or expose secret
material. It only answers whether the current instance is allowed to use an AI
provider and which non-secret mode is active.
"""

from dataclasses import dataclass
import os


VALID_DISTRIBUTIONS = {"hosted", "self_hosted"}
VALID_PROVIDER_MODES = {"platform_default", "byok", "disabled"}
DEFAULT_DISTRIBUTION = "self_hosted"
DEFAULT_PROVIDER_MODE = "byok"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def _clean(value):
    return str(value or "").strip()


def _clean_lower(value):
    return _clean(value).lower()


def _env_bool(value, default=False):
    raw = _clean_lower(value)
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _env_value(env, key, default=""):
    try:
        return env.get(key, default)
    except AttributeError:
        return default


@dataclass(frozen=True)
class AIProviderPolicy:
    distribution: str
    mode: str
    configured: bool
    status: str
    provider: str | None
    credential_source: str
    default_model: str
    message: str

    def safe_status(self):
        return {
            "distribution": self.distribution,
            "mode": self.mode,
            "configured": self.configured,
            "status": self.status,
            "provider": self.provider,
            "credential_source": self.credential_source,
            "default_model": self.default_model,
            "message": self.message,
        }


def get_default_model(env=None):
    env = env or os.environ
    return _clean(_env_value(env, "OPENAI_DEFAULT_MODEL")) or DEFAULT_OPENAI_MODEL


def get_ai_provider_policy(env=None):
    env = env or os.environ
    distribution = _clean_lower(_env_value(env, "CAMARAD_DISTRIBUTION", DEFAULT_DISTRIBUTION)) or DEFAULT_DISTRIBUTION
    mode = _clean_lower(_env_value(env, "CAMARAD_PROVIDER_MODE", DEFAULT_PROVIDER_MODE)) or DEFAULT_PROVIDER_MODE
    allow_platform_default = _env_bool(_env_value(env, "ALLOW_PLATFORM_DEFAULT_PROVIDER"), default=False)
    has_openai_key = bool(_clean(_env_value(env, "OPENAI_API_KEY")))
    default_model = get_default_model(env)

    if distribution not in VALID_DISTRIBUTIONS:
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=False,
            status="invalid_config",
            provider=None,
            credential_source="none",
            default_model=default_model,
            message="Invalid CAMARAD_DISTRIBUTION. Use hosted or self_hosted.",
        )

    if mode not in VALID_PROVIDER_MODES:
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=False,
            status="invalid_config",
            provider=None,
            credential_source="none",
            default_model=default_model,
            message="Invalid CAMARAD_PROVIDER_MODE. Use platform_default, byok, or disabled.",
        )

    if mode == "disabled":
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=False,
            status="disabled",
            provider=None,
            credential_source="none",
            default_model=default_model,
            message="AI provider access is disabled.",
        )

    if distribution == "self_hosted" and mode == "platform_default":
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=False,
            status="invalid_config",
            provider=None,
            credential_source="none",
            default_model=default_model,
            message="Self-hosted Camarad cannot use the platform default provider. Configure instance BYOK.",
        )

    if mode == "platform_default":
        if not allow_platform_default:
            return AIProviderPolicy(
                distribution=distribution,
                mode=mode,
                configured=False,
                status="invalid_config",
                provider=None,
                credential_source="none",
                default_model=default_model,
                message="Platform default provider is not allowed by this instance.",
            )
        if not has_openai_key:
            return AIProviderPolicy(
                distribution=distribution,
                mode=mode,
                configured=False,
                status="setup_required",
                provider="openai",
                credential_source="none",
                default_model=default_model,
                message="Configure OPENAI_API_KEY server-side to enable the platform default provider.",
            )
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=True,
            status="configured",
            provider="openai",
            credential_source="platform_default",
            default_model=default_model,
            message="OpenAI platform default provider is configured server-side.",
        )

    if mode == "byok":
        if has_openai_key:
            return AIProviderPolicy(
                distribution=distribution,
                mode=mode,
                configured=True,
                status="configured",
                provider="openai",
                credential_source="instance_env",
                default_model=default_model,
                message="OpenAI instance BYOK provider is configured server-side.",
            )
        return AIProviderPolicy(
            distribution=distribution,
            mode=mode,
            configured=False,
            status="setup_required",
            provider="openai",
            credential_source="none",
            default_model=default_model,
            message="Configure an OpenAI API key server-side to enable AI.",
        )

    return AIProviderPolicy(
        distribution=distribution,
        mode=mode,
        configured=False,
        status="invalid_config",
        provider=None,
        credential_source="none",
        default_model=default_model,
        message="AI provider policy could not be resolved.",
    )


def is_ai_available(env=None):
    return bool(get_ai_provider_policy(env).configured)


def safe_provider_status(env=None):
    return get_ai_provider_policy(env).safe_status()


def setup_required_payload(env=None):
    policy = get_ai_provider_policy(env)
    return {
        "error": policy.status,
        "message": policy.message,
        "provider": policy.provider,
        "configured": policy.configured,
    }
