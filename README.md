# Tiny Steward — Semantic Capability Graph Micro-Agent Runtime

<p align="center">
  <img src="https://raw.githubusercontent.com/anarcoiris/tiny-steward/main/assets/banner.png" alt="Tiny Steward" width="60%">
</p>

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![MITRE ATT&CK](https://img.shields.io/badge/MITRE%20ATT&CK-v19.1-blue)](https://attack.mitre.org)
[![GitHub stars](https://img.shields.io/github/stars/anarcoiris/tiny-steward?style=flat-square)](https://github.com/anarcoiris/tiny-steward/stargazers)

</div>

**🎯 AI agents with expert cybersecurity skills — structured knowledge for autonomous security operations**



---

> ⚠️ **Community Project** — This is an independent, community-created project. Not affiliated with any specific company or organization.
>
> 🔐 **Authorized & lawful use only.** This runtime includes offensive and dual-use techniques (e.g., red-team C2, phishing simulation, exploitation) intended for authorized penetration testing, security research, defense, and education. Only use them against systems you own or have **explicit written permission** to test, and comply with all applicable laws and rules of engagement. You are solely responsible for how you use these skills. See [SECURITY.md](SECURITY.md).

## 🎯 What is Tiny Steward?

Tiny Steward is a **semantic capability graph micro-agent runtime** that gives AI agents access to structured cybersecurity knowledge — turning generic LLMs into capable security analysts with practitioner-level workflows encoded directly into the system.

Unlike tool repos that give you scripts or payloads, this project provides an **AI-native knowledge base** built from the ground up for agentic workflows: YAML frontmatter for sub-second discovery, structured Markdown for step-by-step execution, and reference files for deep technical context.

**Every skill encodes real practitioner workflows**, not generated summaries. Clone it, point your agent at it, and your next security investigation gets expert-level guidance in seconds.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **817+ cybersecurity skills** | Spanning 29 security domains, each following the open-standard format |
| **6-framework cross-mapping** | MITRE ATT&CK v19.1, NIST CSF 2.0, MITRE ATLAS, MITRE D3FEND, NIST AI RMF, and MITRE F3 |
| **Semantic search** | Find relevant skills by describing what you need rather than searching keywords |
| **Session management** | Long-running investigations with persistent context |
| **Task execution** | Run single tasks and get structured results |
| **Skill index building** | Automatically build embeddings for fast retrieval |

## 🚀 Quick Start

### Option 1: npx (recommended)

```bash
npx skills add anarcoiris/tiny-steward
```

### Option 2: Git clone

```bash
git clone https://github.com/anarcoiris/tiny-steward.git
cd tiny-steward
```

Works immediately with Claude Code, GitHub Copilot, OpenAI Codex CLI, Cursor, Gemini CLI, and any agentskills.io-compatible platform.

## 📚 What's Inside — 29 Security Domains

| Domain | Skills | Key capabilities |
|--------|--------|------------------|
| Cloud Security | 66 | AWS, Azure, GCP hardening · CSPM · cloud attack emulation · cloud forensics |
| Threat Hunting | 58 | Hypothesis-driven hunts · LOTL detection · EVTX hunting · fleet hunting |
| Threat Intelligence | 52 | STIX/TAXII · MISP · OpenCTI · feed integration · actor profiling |
| Network Security | 43 | IDS/IPS · firewall rules · VLAN segmentation · traffic analysis |
| Web Application Security | 42 | OWASP Top 10 · SQLi · XSS · SSRF · deserialization |
| Digital Forensics | 41 | Disk imaging · memory forensics · Hayabusa/KAPE/Plaso timelines |
| Malware Analysis | 39 | Static/dynamic analysis · reverse engineering · sandboxing |
| Identity & Access Management | 37 | Entra ID/ROADtools · device-code phishing · PAM · zero trust identity |
| SOC Operations | 35 | Playbooks · escalation workflows · Graph-log detection · tabletop exercises |
| Red Teaming | 33 | ADCS/Certipy · BloodHound CE · Sliver/Havoc C2 · NTLM relay |
| Container Security | 33 | K8s RBAC · image scanning · Falco · container escape |
| Security Operations | 28 | SIEM correlation · log analysis · alert triage |
| OT/ICS Security | 28 | Modbus · DNP3 · IEC 62443 · historian defense · SCADA |
| API Security | 28 | GraphQL · REST · OWASP API Top 10 · WAF bypass |
| Incident Response | 26 | Breach containment · ransomware response · IR playbooks |
| Vulnerability Management | 25 | Nessus · scanning workflows · patch prioritization · CVSS |
| Penetration Testing | 21 | Network · web · cloud · mobile · NetExec lateral movement |
| DevSecOps | 18 | CI/CD security · Trivy IaC/image scanning · code signing |
| Zero Trust Architecture | 17 | BeyondCorp · CISA maturity model · microsegmentation |
| Endpoint Security | 17 | EDR · LOTL detection · fileless malware · persistence hunting |
| Cryptography | 16 | TLS · Ed25519 · post-quantum migration · key management |
| Phishing Defense | 15 | Email authentication · BEC detection · phishing IR |
| AI Security | 14 | LLM red-teaming (garak/PyRIT) · prompt injection · MCP/agentic security · guardrails |
| Mobile Security | 13 | Android/iOS analysis · mobile pentesting · MDM forensics |
| Ransomware Defense | 13 | Precursor detection · response · recovery · encryption analysis |
| Compliance & Governance | 9 | NIST 800-30/RMF · CMMC · HIPAA · TPRM · CIS benchmarks |
| Supply Chain Security | 8 | SBOMs · dependency confusion · malicious-package triage · SLSA/Sigstore |
| Deception Technology | 6 | Honeytokens · canarytokens · breach detection |
| Hardware & Firmware Security | 4 | CHIPSEC/UEFI audit · Secure Boot bypass · TPM attestation · bootkit hunting |

## 🧠 How AI Agents Use These Skills

Each skill costs **~30 tokens to scan** (frontmatter only) and **500–2,000 tokens to fully load** (complete workflow). This progressive disclosure architecture lets agents search all 817 skills in a single pass without blowing context windows.

```
User prompt: "Analyze this memory dump for signs of credential theft"

Agent's internal process:

  1. Scans 817 skill frontmatters (~30 tokens each)
     → identifies 12 relevant skills by matching tags, description, domain

  2. Loads top 3 matches:
     • performing-memory-forensics-with-volatility3
     • hunting-for-credential-dumping-lsass
     • analyzing-windows-event-logs-for-credential-access

  3. Executes the structured Workflow section step-by-step
     → runs Volatility3 plugins, checks LSASS access patterns,
        correlates with event log evidence

  4. Validates results using the Verification section
     → confirms IOCs, maps findings to ATT&CK T1003 (Credential Dumping)
```

**Without these skills**, the agent guesses at tool commands and misses critical steps. **With them**, it follows the same playbook a senior DFIR analyst would use.

## 📁 Skill Anatomy

Every skill follows a consistent directory structure:

```
skills/performing-memory-forensics-with-volatility3/
├── SKILL.md              ← Skill definition (YAML frontmatter + Markdown body)
├── references/
│   ├── standards.md      ← MITRE ATT&CK, ATLAS, D3FEND, NIST mappings
│   └── workflows.md      ← Deep technical procedure reference
├── scripts/
│   └── process.py        ← Working helper scripts
└── assets/
    └── template.md       ← Filled-in checklists and report templates
```

### YAML frontmatter (real example)

```yaml
---
name: performing-memory-forensics-with-volatility3
description: >-
  Analyze memory dumps to extract running processes, network connections,
  injected code, and malware artifacts using the Volatility3 framework.
domain: cybersecurity
subdomain: digital-forensics
tags: [forensics, memory-analysis, volatility3, incident-response, dfir]
atlas_techniques: [AML.T0047]
d3fend_techniques: [D3-MA, D3-PSMD]
nist_ai_rmf: [MEASURE-2.6]
nist_csf: [DE.CM-01, RS.AN-03]
version: "1.2"
author: anarcoiris
license: Apache-2.0
---
```

### Markdown body sections

```markdown
## When to Use
Trigger conditions — when should an AI agent activate this skill?

## Prerequisites
Required tools, access levels, and environment setup.

## Workflow
Step-by-step execution guide with specific commands and decision points.

## Verification
How to confirm the skill was executed successfully.
```

Frontmatter fields: `name` (kebab-case, 1–64 chars), `description` (keyword-rich for agent discovery), `domain`, `subdomain`, `tags`,  `atlas_techniques` (MITRE ATLAS IDs), `d3fend_techniques` (MITRE D3FEND IDs), `nist_ai_rmf` (NIST AI RMF references), `nist_csf` (NIST CSF 2.0 categories). MITRE ATT&CK technique mappings are documented in each skill's `references/standards.md` file and in the ATT&CK Navigator layer included with releases.

## 🧩 Framework Cross-Mapping

### MITRE ATT&CK v19.1 — full coverage

Every skill carries a `mitre_attack` frontmatter list validated against **MITRE ATT&CK v19.1** (the latest release) using the official `mitreattack-python` library — 286 distinct techniques across all 15 Enterprise tactics, plus ICS and Mobile techniques where relevant. Zero revoked or deprecated IDs.

| Tactic | ID | Skills |
|--------|----|--------|
| Reconnaissance | TA0043 | 103 |
| Resource Development | TA0042 | 22 |
| Initial Access | TA0001 | 467 |
| Execution | TA0002 | 350 |
| Persistence | TA0003 | 444 |
| Privilege Escalation | TA0004 | 464 |
| Stealth | TA0005 | 442 |
| Defense Impairment | TA0112 | 92 |
| Credential Access | TA0006 | 202 |
| Discovery | TA0007 | 237 |
| Lateral Movement | TA0008 | 68 |
| Collection | TA0009 | 172 |
| Command and Control | TA0011 | 123 |
| Exfiltration | TA0010 | 82 |
| Impact | TA0040 | 50 |

### NIST CSF 2.0 alignment — all 6 functions

| Function | Skills | Examples |
|---|--------|----------|
| **Govern (GV)** | 30+ | Risk strategy, policy frameworks, roles & responsibilities |
| **Identify (ID)** | 120+ | Asset discovery, threat landscape assessment, risk analysis |
| **Protect (PR)** | 150+ | IAM hardening, WAF rules, zero trust, encryption |
| **Detect (DE)** | 200+ | Threat hunting, SIEM correlation, anomaly detection |
| **Respond (RS)** | 160+ | Incident response, forensics, breach containment |
| **Recover (RC)** | 40+ | Ransomware recovery, BCP, disaster recovery |

NIST CSF 2.0 (February 2024) added the **Govern** function and expanded scope from critical infrastructure to all organizations. Skill mappings align to all 22 categories and reference 106 subcategories.

### MITRE ATLAS v5.4 — AI/ML adversarial threats

ATLAS maps adversarial tactics, techniques, and case studies specific to AI and machine learning systems. Version 5.4 covers **16 tactics and 84 techniques** including agentic AI attack vectors added in late 2025: AI agent context poisoning, tool invocation abuse, MCP server compromises, and malicious agent deployment. Skills mapped to ATLAS help agents identify and defend against threats to ML pipelines, model weights, inference APIs, and autonomous workflows.

### MITRE D3FEND v1.3 — Defensive countermeasures

D3FEND is an NSA-funded knowledge graph of **267 defensive techniques** organized across 7 tactical categories: Model, Harden, Detect, Isolate, Deceive, Evict, and Restore. Built on OWL 2 ontology, it uses a shared Digital Artifact layer to bidirectionally map defensive countermeasures to ATT&CK offensive techniques. Skills tagged with D3FEND identifiers let agents recommend specific countermeasures for detected threats.

### NIST AI RMF 1.0 + GenAI Profile (AI 600-1)

The AI Risk Management Framework defines 4 core functions — Govern, Map, Measure, Manage — with **72 subcategories** for trustworthy AI development. The GenAI Profile (AI 600-1, July 2024) adds **12 risk categories** specific to generative AI, from confabulation and data privacy to prompt injection and supply chain risks. Skills mapped to NIST AI RMF help agents comply with emerging AI governance requirements.

### MITRE F3 (Fight Fraud Framework) — financial fraud TTPs

The **[MITRE Fight Fraud Framework (F3)](https://ctid.mitre.org/fraud/)** was released **April 9, 2026** by MITRE's Center for Threat-Informed Defense (CTID), co-developed with JPMorganChase, Citigroup, Lloyds Banking Group, Standard Chartered, CrowdStrike, Verizon Business, FS-ISAC, and others. It is an ATT&CK-compatible TTP catalog for **cyber-enabled financial fraud** — filling the gap ATT&CK leaves after initial compromise.

F3 v1.1 adds **two fraud-specific tactics** that ATT&CK does not enumerate:
- **Positioning** (`FA0001`) — actions taken after access to collect/manipulate data and prepare the fraud (synthetic-identity seeding, account warming, beneficiary setup, SIM-swap pre-positioning, banking-session hijack).
- **Monetization** (`FA0002`) — converting stolen assets into usable funds (money-mule layering, APP fraud, crypto off-ramping, card cash-out, refund/chargeback abuse).

Fraud-specific techniques use `F1XXX` IDs (e.g. `F1005.003` Add Beneficiary, `F1025.003` Wire Transfer, `F1007` Adversary-in-the-Browser); reused ATT&CK techniques keep their `T1XXX` IDs. Mappings live in each skill's `mitre_f3:` frontmatter block — all 123 F3 v1.1 technique IDs were verified against the upstream STIX bundle.

## 🏗️ Architecture

```
tiny-steward/
├── steward.py                 ← Entry point (interactive REPL or single tasks)
├── config.yaml                ← Orchestrator, embedder, skills settings
├── core/
│   ├── llm.py                ← LLM client wrapper
│   ├── embedder.py           ← Embedding generation
│   ├── skill_loader.py       ← Index building & loading
│   ├── help.py               ← Semantic search engine
│   ├── runtime.py            ← Task execution orchestration
│   ├── session.py            ← Session persistence
│   └── primitives.py         ← Action primitives (pwsh, bash, http, etc.)
├── skills/                    ← 817+ structured cybersecurity skills
│   ├── _index.json          ← Skill metadata index
│   ├── _index.npy           ← Embeddings array
│   ├── SKILL.md             ← Individual skill definitions
│   └── references/          ← Framework mappings
├── sessions/                  ← Long-running investigation context
├── tests/                    ← Unit & integration tests
└── SECURITY.md               ← Rules of engagement
```

### Core Components

| Module | Responsibility |
|--------|----------------|
| **LLMClient** | Wraps local LLM endpoints (llamacpp/Ollama) with configurable parameters |
| **Embedder** | Generates embeddings for semantic search over skills |
| **SkillIndex** | Builds and loads the skills metadata index with vector storage |
| **HelpEngine** | Semantic search engine that finds relevant skills by description |
| **SessionManager** | Persists long-running investigations across multiple steps |
| **Runtime** | Orchestrates task execution, result validation, and response generation |

## 🛠️ Configuration

The `config.yaml` file controls all runtime behavior:

```yaml
# Tiny Steward — Semantic Capability Graph
# Endpoints for llamacpp / Ollama local stack

llm:
  orchestrator:
    base_url: "http://127.0.0.1:11440"
    api: "openai"                      # llamacpp /v1/chat/completions
    model: "qwythos-9b-96k"
    ctx: 98304
    max_tokens: 16384
    temperature: 0.6
    top_p: 0.95
    repeat_penalty: 1.05
  atomic:
    base_url: "http://127.0.0.1:11439"
    api: "openai"
    model: "qwen3-4b-instruct-96k"
    ctx: 98304
    max_tokens: 4096
    temperature: 0.1

embeddings:
  base_url: "http://127.0.0.1:11438"
  api: "ollama"                        # Ollama /api/embeddings
  model: "nomic-embed-text"

help:
  top_k: 5
  min_similarity: 0.35
  max_inject_tokens: 4000             # budget for skill text injection

skills:
  root: "./skills"
  index: "./skills/_index.json"
  rebuild_on_start: false

sessions:
  dir: "./sessions"
  auto_save: true
```

### Required Endpoints

Before running Tiny Steward, ensure these services are available:

| Service | Port | Model | Purpose |
|---------|------|-------|---------|
| Orchestrator LLM | 11440 | qwythos-9b-96k | Main reasoning and response generation |
| Atomic LLM | 11439 | qwen3-4b-instruct-96k | Lightweight tool-use calls |
| Embeddings | 11438 | nomic-embed-text | Semantic search over skills |

You can adjust models and endpoints by editing `config.yaml`. The runtime will print health status on startup.

## 🎬 Usage Scenarios

### Interactive REPL (default)

```bash
python steward.py                          # interactive REPL, default session
```

Type skills in natural language:

- "Analyze this memory dump for signs of credential theft"
- "Detect lateral movement via WMI"
- "Build a threat timeline from logs"

### Single task execution

```bash
python steward.py --task "list all .py files in ~/projects"
```

### Session management

```bash
python steward.py --session deploy-flask   # resume named session
```

### Build skill index

```bash
python steward.py --build-index            # rebuild skill embeddings
```

### List indexed skills

```bash
python steward.py --list-skills            # show all available skills
```

## 🧪 Testing

```bash
# Run test suite
pytest tests/

# Generate test output report
cat test_output.txt
```

## 🔒 Security

This repository contains offensive and dual-use techniques (e.g., red-team C2, phishing simulation, exploitation) intended for **authorized penetration testing, security research, defense, and education**. Only use them against systems you own or have **explicit written permission** to test, and comply with all applicable laws and rules of engagement. You are solely responsible for how you use these skills. See [SECURITY.md](SECURITY.md) for detailed policies.

## 🤝 Contributing

This project grows through community contributions. Here is how to get involved:

**Add a new skill** — Domains like Deception Technology (2 skills) and Compliance & Governance (5 skills) need the most help. Follow the template in [CONTRIBUTING.md](CONTRIBUTING.md) and submit a PR with the title `Add skill: your-skill-name`.

**Improve existing skills** — Add framework mappings, fix workflows, update tool references, or contribute scripts and templates.

**Report issues** — Found an inaccurate procedure or broken script? [Open an issue](https://github.com/anarcoiris/tiny-steward/issues).

Every PR is reviewed for technical accuracy and agentskills.io standard compliance within 48 hours. Check [good first issues](https://github.com/anarcoiris/tiny-steward/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) for a starting point.

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you agree to uphold this code.

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE). You are free to use, modify, and distribute these skills in both personal and commercial projects.

## Citation

If you use this project in research or publications:

```bibtex
@software{tiny_steward,
  author       = {anarcoiris},
  title        = {Tiny Steward — Semantic Capability Graph Micro-Agent Runtime},
  year         = {2026},
  url          = {https://github.com/anarcoiris/tiny-steward},
  license      = {Apache-2.0},
  note         = {817 structured cybersecurity skills for AI agents,
                  mapped to MITRE ATT&CK, NIST CSF 2.0, MITRE ATLAS,
                  MITRE D3FEND, NIST AI RMF, and MITRE F3}
}
```

---

<div align="center">

**If this project helps your security work, consider giving it a ⭐**

[⭐ Star](https://github.com/anarcoiris/tiny-steward/stargazers) · [🍴 Fork](https://github.com/anarcoiris/tiny-steward/fork) · [💬 Discuss](https://github.com/anarcoiris/tiny-steward/discussions) · [📝 Contribute](CONTRIBUTING.md)

Community project by [@anarcoiris](https://github.com/anarcoiris). Not affiliated with any specific company or organization.

</div>
