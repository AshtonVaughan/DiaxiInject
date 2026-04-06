<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/License-Private-red?style=for-the-badge&logo=lock&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Alpha-orange?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/Probes-69-blueviolet?style=for-the-badge&logo=target&logoColor=white" />
  <img src="https://img.shields.io/badge/Targets-9-green?style=for-the-badge&logo=crosshair&logoColor=white" />
  <img src="https://img.shields.io/badge/vLLM-Powered-FF6F00?style=for-the-badge&logo=lightning&logoColor=white" />
</p>

<h1 align="center">DiaxiInject</h1>

<p align="center">
  <strong>LLM security testing framework that uses local uncensored LLMs<br>to systematically test cloud-hosted LLMs for bug bounty programs.</strong>
</p>

<p align="center">
  <em>An LLM understands LLMs better than anyone.</em>
</p>

---

## How It Works

DiaxiInject uses a **dual-LLM architecture** - a local uncensored model acts as the attacker brain, generating adversarial prompts, scoring responses, and evolving novel bypass techniques against cloud-hosted targets.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#161b22', 'primaryTextColor': '#e6edf3', 'primaryBorderColor': '#30363d', 'lineColor': '#30363d', 'secondaryColor': '#161b22', 'tertiaryColor': '#161b22', 'fontSize': '13px'}}}%%
graph TD
    YOU(("You")) --> CLI["DiaxiInject CLI"]
    CLI --> ATK["Attacker LLM\n<i>local / vLLM / uncensored</i>"]
    CLI --> TGT["Target LLM\n<i>cloud API</i>"]
    ATK -.- TGT
    ATK --> SC["Scoring Pipeline\nrules - classifier - LLM judge"]
    TGT --> SC
    SC --> EV["Evidence Engine\nHackerOne / MSRC reports"]
```

---

## Supported Targets

| Provider | Platform | Max Bounty | Focus |
|:---------|:---------|:-----------|:------|
| Apple | Apple Bounty | **$1,000,000** | PCC infrastructure |
| Microsoft | MSRC | **$60,000** | M365 Copilot indirect PI, Azure filter bypass |
| Meta | HackerOne | **$50,000+** | Meta AI cross-user data, social media PI |
| Google | VRP | **$31,337+** | Gemini Workspace, multimodal PI |
| OpenAI | Bugcrowd | **$20,000** | GPT Actions SSRF, data exfil |
| Anthropic | HackerOne | **$15,000+** | Systematic jailbreaks, tool use abuse |
| HuggingFace | HackerOne | **$15,000+** | Model serialization RCE, Spaces |
| xAI | Unconfirmed | TBD | Grok API |
| Mistral | Resp. Disclosure | TBD | Le Chat, La Plateforme |

Each target has a YAML profile with scope, reward tiers, API config, priority attack surfaces, and known defenses.

---

## Attack Orchestrators

| Orchestrator | Method | Description |
|:-------------|:-------|:------------|
| `SingleTurn` | Probe + Mutate | Sends probes with optional encoding/structural mutations |
| `PAIR` | Iterative Refinement | Attacker LLM refines prompts based on target responses (~20 iterations) |
| `TAP` | Tree Search + Pruning | Explores branching attack tree, prunes weak paths (80%+ ASR) |
| `Crescendo` | Multi-Turn Escalation | Gradual drift from benign to target over 10-15 turns (98% ASR) |
| `Genetic` | Evolutionary Mutation | Tournament selection, crossover, mutation for novel bypasses |
| `Compound` | Chained Novel Methods | Layers multiple architectural exploits (ADA + OFC + LAF, etc.) |

---

## Novel Attack Methods

Six original methods grounded in **transformer architecture analysis**, not recycled jailbreak tricks:

| Method | Acronym | Exploits | Target Layer |
|:-------|:--------|:---------|:-------------|
| Attention Dilution Attack | `ADA` | Softmax attention budget | RLHF |
| Logit Anchor Forcing | `LAF` | Autoregressive first-token bias | RLHF |
| Token Boundary Disruption | `TBD` | Fixed tokenizer vs classifiers | Input Classifier |
| Objective Function Collision | `OFC` | Helpfulness vs harmlessness | Reward Model |
| Representation Space Navigation | `RSN` | Safety boundary blind spots | RLHF |
| Classifier Desynchronization | `CD` | Independent censorship layers | All 3 Layers |

**Compound chains:**

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#161b22', 'primaryTextColor': '#e6edf3', 'primaryBorderColor': '#30363d', 'lineColor': '#30363d', 'fontSize': '12px'}}}%%
graph LR
    subgraph chain1 ["Academic Erosion"]
        A1["ADA"] --> A2["OFC"] --> A3["LAF"]
    end
    subgraph chain2 ["Invisible Needle"]
        B1["TBD"] --> B2["CD"]
    end
    subgraph chain3 ["Slow Boil"]
        C1["RSN"] --> C2["OFC"] --> C3["Crescendo"]
    end
    subgraph chain4 ["Polymorphic"]
        D1["Genetic"] --> D2["All 6"]
    end
```

Full technical writeup in [`research/NOVEL-METHODOLOGY.md`](research/NOVEL-METHODOLOGY.md).

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/AshtonVaughan/DiaxiInject.git
cd DiaxiInject
pip install -e .
```

### 2. Start the Attacker LLM

```bash
# On your cloud GPU server (single H100 sufficient)
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-4-Maverick-17B-128E-Instruct \
  --port 8000 \
  --tensor-parallel-size 1
```

### 3. Configure

```bash
cp diaxiinject.yaml my-config.yaml
# Edit with your vLLM server URL and target API keys

export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...
```

### 4. Run

```bash
# Full multi-phase campaign
diaxiinject campaign --target openai --budget 30

# Single orchestrator
diaxiinject attack --target google --type crescendo --objective "extract system prompt"

# Evolve novel attacks
diaxiinject evolve --target microsoft --objective "indirect prompt injection" -g 100

# Single probe with mutators
diaxiinject probe --target openai --probe-id "LLM07-001" --mutators base64,homoglyph

# Stats and reporting
diaxiinject stats --campaign-id campaign-a1b2c3d4
diaxiinject report --campaign-id campaign-a1b2c3d4 --format hackerone
```

---

## Campaign Pipeline

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#161b22', 'primaryTextColor': '#e6edf3', 'primaryBorderColor': '#30363d', 'lineColor': '#30363d', 'fontSize': '12px'}}}%%
graph TD
    P1["Phase 1: Single-Turn Probes\n69 probes x raw + mutated"] -->|"score > 0.3"| P2["Phase 2: PAIR\n~20 iterations"]
    P1 -->|"score < 0.15"| P3["Phase 3: TAP\nwidth 4 / depth 5"]
    P2 --> P4["Phase 4: Crescendo\n10-15 turns"]
    P3 --> P4
    P4 -->|"score 0.5-0.7"| P5["Phase 5: Genetic\n50 gens / pop 20"]
    P1 -.->|success| OUT["Findings\nHackerOne / MSRC reports"]
    P2 -.->|success| OUT
    P3 -.->|success| OUT
    P4 -.->|success| OUT
    P5 -.->|success| OUT
```

---

## Scoring Pipeline

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#161b22', 'primaryTextColor': '#e6edf3', 'primaryBorderColor': '#30363d', 'lineColor': '#30363d', 'fontSize': '12px'}}}%%
graph LR
    IN["Response"] --> T1["Tier 1: Rules\n27 patterns\n<i>weight 0.35</i>"]
    T1 --> T2["Tier 2: Classifier\nrefusal ratio\n<i>weight 0.35</i>"]
    T2 --> T3["Tier 3: LLM Judge\nscores 1-10\n<i>weight 0.30</i>"]
    T3 --> SC["Score\n0.0 - 1.0\nthr: 0.7"]
```

---

## Project Structure

```
diaxiinject/
|-- cli.py                    # Click CLI with Rich output
|-- campaign.py               # 5-phase campaign controller
|-- config.py                 # YAML config loader
|-- models.py                 # Core data models
|
|-- providers/
|   |-- hub.py                # Provider registry (9 targets)
|   |-- litellm_adapter.py    # Universal target adapter via LiteLLM
|   |-- local_llm.py          # vLLM/Ollama attacker interface
|
|-- attacks/
|   |-- probes/               # 69 attack probes (5 categories)
|   |-- mutators/             # 11 mutators (encoding + structural)
|   |-- orchestrators/        # 6 orchestrators (PAIR, TAP, etc.)
|   |-- scoring/              # 3-tier scoring pipeline
|
|-- strategy/                 # Adaptive orchestrator selection
|-- memory/                   # SQLite attack history + transfer learning
|-- evidence/                 # Finding builder + report generators
|-- targets/profiles/         # 9 YAML target profiles
```

---

## Requirements

| Component | Specification |
|:----------|:-------------|
| Python | 3.11+ |
| Attacker LLM | vLLM server with Llama 4 Maverick (17B active / 128 experts) |
| GPU | Single H100 sufficient for Maverick/Scout |
| Target APIs | API keys for providers you want to test |
| Storage | SQLite (included, zero config) |

---

## Legal

> This tool is for **authorized security testing only**. Only use against targets with active bug bounty programs. Verify program scope before testing any target. The authors are not responsible for misuse.
