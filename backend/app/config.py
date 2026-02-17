"""
LoopGrid Configuration
======================

Environment-based configuration. All settings via env vars.
"""

import os


class Settings:
    """Application settings from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv("LOOPGRID_DATABASE_URL", "sqlite:///./loopgrid.db")
    
    # LLM API Keys (for replay execution)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Server
    HOST: str = os.getenv("LOOPGRID_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("LOOPGRID_PORT", "8000"))
    
    # Replay
    REPLAY_TIMEOUT: int = int(os.getenv("LOOPGRID_REPLAY_TIMEOUT", "30"))
    
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)
    
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)
    
    def has_any_llm(self) -> bool:
        return self.has_openai() or self.has_anthropic()


settings = Settings()
