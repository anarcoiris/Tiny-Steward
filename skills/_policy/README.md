# _policy/ — Legal Plugin Policy Directory

This folder contains:

- **`references/`** — shared templates and boilerplates used by all plugins
  - `company-profile-template.md` — the canonical company/firm profile that every plugin writes first; subsequent reads of this file inform all downstream outputs. Edit directly or re-run any plugin's `/cold-start-interview` to update it.
  - `dashboard-template.md` — guidance for generating consistent, scannable dashboards (HTML artifacts for Cowork/Claude Desktop, markdown summaries for terminal users). Keep them simple: title/metadata, summary stats, reviewer note, at most two charts, one table, a decision tree. Apply the HTML-escape defense to all untrusted input before rendering.
  - `questionary.md` — a fill‑in form for a given company/firm. The questionary captures the placeholders defined in the templates and any additional fields needed for legal coverage. It is used by plugins that need to interview or gather facts about an entity before producing outputs.

- **`ai-governance-legal/`** — AI safety, model licensing (e.g., LLMs, embeddings), output attribution, hallucination handling, data provenance.
- **`commercial-legal/`** — contracts, NDAs, SOWs, vendor agreements, pricing terms, liability caps, IP assignment clauses.
- **`corporate-legal/`** — corporate governance, bylaws, shareholder agreements, board minutes, cap tables, director indemnities.
- **`employment-legal/`** — employment contracts, NDAs, confidentiality, non-compete, IP assignment, termination letters, benefit plans.
- **`external_plugins/`** — integration points with third‑party tools or plugins that may be invoked by this environment.
- **`ip-legal/`** — patents, trademarks, copyrights, trade secrets, licensing arrangements, open-source compliance.
- **`law-student/`** — academic papers, case briefs, statutes, regulatory guidance for students and researchers.
- **`legal/`** — core legal outputs: contracts, memos, clauses, advice letters, review findings.
- **`legal-builder-hub/`** — reusable clause libraries, template fragments, boilerplate snippets that can be assembled by plugins.
- **`legal-clinic/`** — client-facing deliverables: intake forms, engagement letters, matter summaries, billing records.
- **`litigation-legal/`** — discovery documents, pleadings, depositions, motions, case briefs, settlement agreements.
- **`managed-agent-cookbooks/`** — agent‑level playbooks for specialized tasks (e.g., contract review pipelines).
- **`privacy-legal/`** — GDPR, CCPA, HIPAA, data retention policies, privacy notices, consent management.
- **`product-legal/`** — product terms, EULAs, warranties, SLAs, service level commitments, liability disclaimers.
- **`regulatory-legal/`** — industry regulations (financial, healthcare, construction), licensing requirements, compliance reports.
- **`scripts/`** — utility scripts for batch processing, validation, and automation within the legal domain.

## Usage

Plugins in each subdirectory inherit the shared templates from `references/`. When a new plugin is instantiated, it writes its own `company-profile-template.md` (or reads an existing one) to establish the facts that will inform all downstream outputs. The questionary form in `questionary.md` is meant to be filled out interactively or programmatically before any legal analysis begins.