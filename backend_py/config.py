import os

def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_secret_key_change_in_prod')
    DATABASE = os.getenv('DATABASE', 'camarad.db')
    DEBUG = _env_bool('DEBUG', True)
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = _env_int('PORT', 5051)
    MAX_FREE_MESSAGES_PER_DAY = _env_int('MAX_FREE_MESSAGES_PER_DAY', 30)
    GROK_API_KEY = os.getenv('GROK_API_KEY', '')
