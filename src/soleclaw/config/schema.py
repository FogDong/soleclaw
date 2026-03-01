from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AgentConfig(BaseModel):
    workspace: str = "~/.soleclaw"
    model: str = "claude-sonnet-4-6"
    max_turns: int = 20
    max_budget_usd: float | None = None


class TelegramConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = Field(default_factory=list)


class SlackConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    app_token: str = ""
    channels: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)


class ForgeConfig(BaseModel):
    max_retries: int = 3


class CronConfig(BaseModel):
    enabled: bool = True


class VikingConfig(BaseModel):
    enabled: bool = False
    path: str = "~/.soleclaw/viking-data"


class MemoryConfig(BaseModel):
    backend: str = "local"


class Config(BaseSettings):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    forge: ForgeConfig = Field(default_factory=ForgeConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    viking: VikingConfig = Field(default_factory=VikingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    @property
    def workspace_path(self) -> Path:
        return Path(self.agent.workspace).expanduser()

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        p = path or Path("~/.soleclaw/config.json").expanduser()
        if p.exists():
            import json
            return cls.model_validate(json.loads(p.read_text()))
        return cls()
