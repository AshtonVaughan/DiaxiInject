# DiaxiInject

LLM security testing tool that uses local uncensored LLMs to systematically test cloud-hosted LLMs for bug bounty programs.

## Architecture

DiaxiInject uses a **dual-LLM architecture**:
- **Attacker LLM** (local, uncensored): Generates adversarial prompts, scores responses, evolves novel attacks
- **Target LLM** (cloud API): The system being tested

## Supported Targets

| Provider | Platform | Max Bounty | Focus |
|----------|----------|------------|-------|
| Microsoft | MSRC | $60,000 | M365 Copilot indirect PI, Azure content filter bypass |
| Meta | HackerOne | $50,000+ | Meta AI cross-user data, social media PI |
| Google | VRP | $31,337+ | Gemini Workspace attacks, multimodal PI |
| OpenAI | Bugcrowd | $20,000 | GPT Actions SSRF, data exfil |
| Anthropic | HackerOne | $15,000+ | Systematic jailbreaks, tool use abuse |
| HuggingFace | HackerOne | $15,000+ | Model serialization RCE, Spaces |
| Apple | Apple Bounty | $1,000,000 | PCC infrastructure |

## Attack Orchestrators

- **SingleTurn** - Basic probe delivery with mutation chains
- **PAIR** - Prompt Automatic Iterative Refinement (converges in ~20 iterations)
- **TAP** - Tree of Attacks with Pruning (80%+ ASR on GPT-4)
- **Crescendo** - Multi-turn gradual escalation (98% ASR on GPT-4)
- **Genetic** - Evolutionary prompt mutation for novel bypass discovery

## Quick Start

```bash
# Install
pip install -e .

# Configure
cp diaxiinject.yaml my-config.yaml
# Edit my-config.yaml with your settings

# Set API keys for targets
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...

# Start vLLM with attacker model (on cloud GPU server)
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-4-Maverick-17B-128E-Instruct \
  --port 8000 \
  --tensor-parallel-size 1

# Run a campaign
diaxiinject campaign --target openai --budget 30 --config my-config.yaml

# Run a specific attack
diaxiinject attack --target openai --type pair --objective "extract system prompt"

# Evolve novel attacks
diaxiinject evolve --target anthropic --objective "bypass safety" --generations 100
```

## Requirements

- Python 3.11+
- vLLM server (default, recommended for cloud GPU) or Ollama (local dev)
- API keys for target providers
- Cloud GPU (single H100 sufficient for Llama 4 Maverick/Scout)

## Legal

This tool is for authorized security testing only. Only use against targets with active bug bounty programs. Verify scope before testing.
