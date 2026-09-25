"""
Application configuration.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Database
    database_url: str = "postgresql+asyncpg://mealchain:mealchain_dev@localhost:5432/mealchain"
    
    # JWT
    jwt_secret: str = "dev_jwt_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    
    # AWS
    aws_region: str = "ap-southeast-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    
    # Bedrock / AgentCore
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    agentcore_runtime_arn: str = ""
    agentcore_gateway_url: str = ""
    
    # SAP
    sap_mode: str = "mock"
    mock_sap_key: str = "not-a-real-key"
    
    # App
    debug: bool = True
    app_name: str = "MealChain Guardian"


settings = Settings()
