"""Plugin ABC for MCP-style external integrations."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PluginSpec(BaseModel):
    name: str = Field(..., description="Unique plugin name")
    description: str = Field(..., description="What the plugin does")
    version: str = Field(default="1.0.0")
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    actions: List[str] = Field(default_factory=list)


class Plugin(ABC):
    """Base class for all external integrations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._initialized = False

    @abstractmethod
    def spec(self) -> PluginSpec:
        """Return the plugin specification."""
        ...

    def initialize(self) -> None:
        """Initialize the plugin with its config."""
        if not self._initialized:
            self._on_initialize()
            self._initialized = True

    def _on_initialize(self) -> None:
        """Override to perform initialization logic."""

    @abstractmethod
    def execute(self, action: str, **kwargs: Any) -> Any:
        """Execute a plugin action."""
        ...

    def list_actions(self) -> List[str]:
        return self.spec().actions

    def is_configured(self) -> bool:
        """Check if required config is present."""
        required = {k for k, v in self.spec().config_schema.items()}
        return required.issubset(self.config.keys())
