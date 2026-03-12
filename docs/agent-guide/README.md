# Agent Guide

Operational reference for AI agents interacting with the Experience Graph. These documents provide exact schemas, CLI commands, REST API endpoints, MCP tools, SDK methods, and step-by-step playbooks needed to read from and write to the shared experience store. They are framework-agnostic and applicable to any LLM-based agent.

## Contents

| Document | Description |
|----------|-------------|
| [trace-format.md](trace-format.md) | Complete reference for constructing and ingesting valid trace JSON |
| [schemas.md](schemas.md) | Machine-readable catalog of all Pydantic schemas with field definitions and examples |
| [operations.md](operations.md) | Full CLI, REST API, MCP, SDK, and Python mutation API reference |
| [playbooks.md](playbooks.md) | Step-by-step operational procedures for common agent tasks |

## Integration Layers

| Layer | Entry Point | Best For |
|-------|-------------|----------|
| CLI (`xpg`) | `xpg <command>` | Scripts, CI/CD, human operators, agent tool calls |
| REST API | `xpg admin serve` / `xpg-api` | Distributed deployments, SDK remote mode |
| MCP Macro Tools | `xpg-mcp` | IDE integrations (Cursor, Cline, Claude Code) |
| Python SDK | `from xpgraph_sdk import XPGClient` | Orchestrators (LangGraph, CrewAI), custom agents |
