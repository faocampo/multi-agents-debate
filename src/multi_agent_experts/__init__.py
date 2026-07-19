"""Conflict-driven multi-agent expert analysis."""

from .analyzer import (
    MultiAgentAnalyzer,
    RolePlanningError,
    StageExecutionError,
    SwarmError,
)
from .client import ChatClient, ChatClientError, HTTPChatClient
from .models import AnalysisResult, ExpertOpinion, ExpertRole, SwarmConfig

__all__ = [
    "AnalysisResult",
    "ChatClient",
    "ChatClientError",
    "ExpertOpinion",
    "ExpertRole",
    "HTTPChatClient",
    "MultiAgentAnalyzer",
    "RolePlanningError",
    "StageExecutionError",
    "SwarmConfig",
    "SwarmError",
]

