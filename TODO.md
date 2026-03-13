# TODO — Growth & Adoption

## In Progress

### PyPI Publishing
- [x] Rename package to `experience-graph` in pyproject.toml
- [x] Add classifiers, keywords, authors, project URLs
- [x] Add hatch-vcs fallback version
- [x] Verify `python -m build` succeeds
- [ ] Create GitHub repo at `experience-graph/experience-graph` (or update URLs to actual repo)
- [ ] Tag `v0.1.0` and push
- [ ] Publish to PyPI: `python -m twine upload dist/*`
- [ ] Verify `pip install experience-graph` works from a clean venv
- [ ] Set up GitHub Actions for automated PyPI publishing on tag push

### Framework Integration (LangGraph)
- [ ] Create `integrations/langgraph/` with XPG as a tool provider
- [ ] Wrap MCP tools as LangGraph `Tool` instances
- [ ] Add example: agent retrieves context → executes → saves trace
- [ ] Write README with setup instructions
- [ ] Open PR upstream to LangGraph's integrations/community tools

## Backlog

### Demo & Content
- [ ] Record 60-second demo GIF showing the retrieve → act → record feedback loop
- [ ] Write blog post: "Why AI agents keep making the same mistakes" (target HN, r/LocalLLaMA)
- [ ] Create starter knowledge pack (common deployment patterns, debugging playbooks) so new users get value on day one

### Discoverability
- [ ] Submit to awesome-mcp-servers list
- [ ] Submit to awesome-llm-agents / awesome-ai-tools lists
- [ ] Publish ClawHub skill: `clawhub publish integrations/openclaw/`

### Developer Experience
- [ ] Add hosted playground (Streamlit or Gradio) showing graph visualization and search
- [ ] Write persona-targeted docs: "XPG for platform teams", "XPG for solo devs with Claude Code"

### More Framework Integrations
- [ ] CrewAI integration (`integrations/crewai/`)
- [ ] AutoGen integration (`integrations/autogen/`)
- [ ] Contribute integration PRs upstream to each framework's repo
