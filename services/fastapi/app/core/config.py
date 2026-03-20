from __future__ import annotations

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	app_env: str = "development"
	app_debug: bool = True
	app_host: str = "0.0.0.0"
	app_port: int = 8000
	app_secret_key: str

	supabase_url: str
	supabase_anon_key: str
	supabase_service_role_key: str
	database_url: str

	keycloak_url: str
	keycloak_realm: str
	keycloak_client_id: str
	keycloak_client_secret: str
	keycloak_jwks_url: str

	redis_url: str
	redis_ttl_default: int = 300
	redis_ttl_drug_list: int = 600

	elasticsearch_url: str
	elasticsearch_index_drugs: str = "meditrack_drugs"
	elasticsearch_username: str = ""
	elasticsearch_password: str = ""

	openai_api_key: str
	openai_model: str = "gpt-4o"
	openai_max_tokens: int = 1000
	openai_timeout: int = 30

	storage_bucket_prescriptions: str = "prescription-files"
	storage_signed_url_expiry: int = 3600

	rate_limit_requests: int = 100
	rate_limit_window: int = 60

	pagination_default_page_size: int = 20
	pagination_max_page_size: int = 100

	cors_origins: str = "http://localhost:3000,http://localhost:5173"

	alembic_database_url: str

	model_config = SettingsConfigDict(
		env_file=".env",
		case_sensitive=False,
		extra="ignore",
	)

	@computed_field(return_type=bool)
	@property
	def is_development(self) -> bool:
		return self.app_env.lower() == "development"


settings = Settings()
