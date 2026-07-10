"""
agentreplay — Statica Trace Python capture SDK.

Public API is exported here for convenience.
"""

from agentreplay.anthropic_wrapper import wrap as wrap_anthropic
from agentreplay.client import AgentReplayClient
from agentreplay.langchain import AgentReplayCallbackHandler
from agentreplay.openai_wrapper import wrap as wrap_openai
from agentreplay.otel_exporter import AgentReplayOTelExporter

__version__ = "0.1.0"
__all__ = [
    "AgentReplayClient",
    "AgentReplayCallbackHandler",
    "wrap_openai",
    "wrap_anthropic",
    "AgentReplayOTelExporter",
]
