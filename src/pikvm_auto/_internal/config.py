"""PiKVM settings configuration model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from pikvm_lib.pikvm import PiKVM
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource


class PiKVMSettings(BaseSettings):
    """Settings for connecting to a PiKVM device.

    Supports three configuration sources (highest priority first):
    1. Direct kwargs (CLI flag overrides)
    2. PIKVM_* environment variables
    3. Config file at ~/.config/pikvm-auto/config.toml
    """

    _toml_path: ClassVar[Path] = Path.home() / ".config" / "pikvm-auto" / "config.toml"

    model_config = SettingsConfigDict(
        env_prefix="PIKVM_",
    )

    host: str
    user: str = "admin"
    password: str
    schema_: str = Field("https", alias="PIKVM_SCHEMA", validation_alias="PIKVM_SCHEMA")
    cert_trusted: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        **kwargs: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customise settings sources to include TOML config file.

        Priority (highest to lowest):
        1. init_settings (direct kwargs / CLI overrides)
        2. env_settings (PIKVM_* environment variables)
        3. TOML config file (~/.config/pikvm-auto/config.toml)
        """
        toml_source = TomlConfigSettingsSource(
            settings_cls,
            toml_file=cls._toml_path,
        )
        return init_settings, env_settings, toml_source

    def create_client(self) -> PiKVM:
        """Create a PiKVM client instance from the current settings."""
        return PiKVM(
            hostname=self.host,
            username=self.user,
            password=self.password,
            schema=self.schema_,
            cert_trusted=self.cert_trusted,
        )
