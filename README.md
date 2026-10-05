# Personal AI - Content Dev Copilot

Private, always-on AI copilot for bootcamp content development. Monitors a Slack channel, remembers content decisions and timelines, generates daily plans, creates lecture notebooks, and sends messages with your approval.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) — Personal AI track.

## Stack

| Layer | Tool |
|-------|------|
| LLM | NVIDIA Nemotron 3 (Nano 30b / Super 120b / Ultra 550b) via Nebius Token Factory |
| Agent harness | Hermes Agent (MIT) |
| Sandbox | NemoClaw / OpenShell |
| Memory | ChromaDB (local) |
| Notebooks | nbformat + nbclient |
| Dashboard | Streamlit |
| Search | Tavily (optional) |

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/emad-malik/personal-ai.git
cd personal-ai
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env with your Nebius Token Factory key

# 3. Verify LLM connection
python -m copilot.llm
```

## Project structure

```
copilot/          # Core Python modules (Stages 0-2)
  llm.py          # Token Factory client
  slack_reader.py # Slack channel reader
  memory.py       # ChromaDB memory store
  planner.py      # Daily plan generator
  approvals.py    # Human-in-the-loop approval
  cli.py          # CLI entry point
  notebook/       # Notebook generation & validation
agent/            # Hermes Agent wiring (Stages 3-5)
  config.yaml     # Hermes config for Token Factory
  skills/         # SKILL.md files
  openshell/      # NemoClaw sandbox policy
dashboard/        # Streamlit app (demo URL)
demo/             # Seed data & Slack workspace setup
tests/
docs/
```

## License

MIT
