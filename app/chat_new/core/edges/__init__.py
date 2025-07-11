"""
Edge Logic for Enhanced LangGraph Chat System

Provides intelligent routing logic between nodes based on:
- State analysis and health checks
- Route requirements and capabilities
- Error conditions and recovery strategies
- Tool availability and execution results
- Context completeness and quality

The edge functions determine the optimal flow through the conversation graph.
"""

from .routing import create_routing_logic

__all__ = ["create_routing_logic"]