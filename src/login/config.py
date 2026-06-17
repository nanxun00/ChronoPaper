import yaml
import os

from src.settings import get_settings


def _load_yaml():
    config_path = os.path.join("src", "saves", "login", "loginConfig.yaml")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    return {}


_settings = get_settings()
_yaml = _load_yaml()

config = {
    "secret": {
        "aes_key": _settings.aes_key,
        "aes_iv": _settings.aes_iv,
        "jwt_key": _settings.jwt_secret_key,
    },
    "token": {
        "expires_time": _settings.token_expires_time,
        "default_expires_time": _settings.token_default_expires_time,
    },
    "origins": _yaml.get("origins", []),
    "services": _yaml.get("services", {}),
    "time_out": _yaml.get("time_out", _settings.gateway_time_out),
    "mysql": {
        "host": _settings.mysql_host,
        "port": _settings.mysql_port,
        "user": _settings.mysql_user,
        "password": _settings.mysql_password,
        "database": _settings.mysql_db,
    },
}
