from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.value_objects import AppSettings, BridgeSettings, RadicaleSettings
from proton_agent_suite.security.permissions import describe_permissions, permissions_are_insecure


class EnvironmentCredentialStore:
    def __init__(self, env_file: Path | None = None) -> None:
        self.env_file = env_file
        if env_file is not None and env_file.exists():
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)

    def _read_systemd_secret(self, directory: Path | None, name: str) -> str | None:
        if directory is None:
            return None
        path = directory / name
        if path.exists():
            return path.read_text().strip()
        return None

    def _optional_secret(self, key: str, fallback_filename: str, directory: Path | None) -> str | None:
        env_value = os.getenv(key)
        if env_value:
            return env_value
        return self._read_systemd_secret(directory, fallback_filename)

    def load_settings(self, profile: str | None = None, db_override: str | None = None) -> AppSettings:
        credentials_dir_raw = os.getenv("CREDENTIALS_DIRECTORY")
        credentials_dir = Path(credentials_dir_raw) if credentials_dir_raw else None
        bridge = BridgeSettings(
            host=os.getenv("PROTON_AGENT_BRIDGE_HOST", "127.0.0.1"),
            imap_port=int(os.getenv("PROTON_AGENT_BRIDGE_IMAP_PORT", "1143")),
            smtp_port=int(os.getenv("PROTON_AGENT_BRIDGE_SMTP_PORT", "1025")),
            username=os.getenv("PROTON_AGENT_BRIDGE_USERNAME"),
            password=self._optional_secret(
                "PROTON_AGENT_BRIDGE_PASSWORD",
                "proton_agent_bridge_password",
                credentials_dir,
            ),
            label_prefix=os.getenv("PROTON_AGENT_BRIDGE_LABEL_PREFIX", "Labels"),
            folder_prefix=os.getenv("PROTON_AGENT_BRIDGE_FOLDER_PREFIX", "Folders"),
            allow_insecure_localhost=os.getenv("PROTON_AGENT_BRIDGE_ALLOW_INSECURE_LOCALHOST", "true").lower() == "true",
        )
        radicale = RadicaleSettings(
            base_url=os.getenv("PROTON_AGENT_RADICALE_BASE_URL"),
            username=os.getenv("PROTON_AGENT_RADICALE_USERNAME"),
            password=self._optional_secret(
                "PROTON_AGENT_RADICALE_PASSWORD",
                "proton_agent_radicale_password",
                credentials_dir,
            ),
            default_calendar=os.getenv("PROTON_AGENT_RADICALE_DEFAULT_CALENDAR"),
            allow_insecure=os.getenv("PROTON_AGENT_RADICALE_ALLOW_INSECURE", "false").lower() == "true",
        )
        db_path = Path(db_override or os.getenv("PROTON_AGENT_DB_PATH", "./data/proton-agent.sqlite3"))
        return AppSettings(
            profile=profile or os.getenv("PROTON_AGENT_PROFILE", "default"),
            db_path=db_path,
            bridge=bridge,
            radicale=radicale,
            ics_public_base_url=os.getenv("PROTON_AGENT_ICS_PUBLIC_BASE_URL"),
            credentials_directory=credentials_dir,
        )


def validate_settings(settings: AppSettings, env_file: Path | None = None) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    if not settings.bridge.username:
        problems.append({"code": ErrorCode.CONFIG_INVALID.value, "message": "Bridge username is missing"})
    if not settings.bridge.password:
        problems.append({"code": ErrorCode.CONFIG_INVALID.value, "message": "Bridge password is missing"})
    if settings.radicale.base_url and settings.radicale.base_url.startswith("http://") and not settings.radicale.allow_insecure:
        problems.append({
            "code": ErrorCode.CONFIG_INVALID.value,
            "message": "Radicale URL uses http:// but insecure mode is not enabled",
        })
    if env_file and env_file.exists() and permissions_are_insecure(env_file):
        problems.append({
            "code": ErrorCode.SECRET_FILE_PERMISSIONS_INSECURE.value,
            "message": f"{env_file} is too permissive ({describe_permissions(env_file)})",
        })
    if settings.credentials_directory and settings.credentials_directory.exists() and permissions_are_insecure(settings.credentials_directory):
        problems.append({
            "code": ErrorCode.SECRET_FILE_PERMISSIONS_INSECURE.value,
            "message": f"{settings.credentials_directory} is too permissive ({describe_permissions(settings.credentials_directory)})",
        })
    return problems


def require_valid_settings(settings: AppSettings, env_file: Path | None = None) -> AppSettings:
    problems = validate_settings(settings, env_file=env_file)
    if problems:
        first = problems[0]
        raise make_error(ErrorCode(first["code"]), first["message"], {"problems": problems})
    return settings
