# AI Governance Policy — Electronic Crafts

*Tailored for a solo proprietor who uses only open-source tools. Any drift to unlicensed shareware triggers a warning.*

## Core Principles
- **Open-source only** — no proprietary or unlicensed software. All tooling must be released under an OSI-approved license (MIT, Apache‑2.0, GPL, etc.).
- **No AI agents** — we do not employ AI models for drafting, analysis, or decision support. If a third‑party AI is used, it must be pre‑approved and documented.
- **Data minimization** — if any AI processing occurs, only the minimal data required for the task may be sent; personal data beyond order details is prohibited.

## Guardrails
| Rule | Trigger | Action |
|------|---------|--------|
| No non-solicit / non-compete | Any clause attempting to restrict future work | Flag RED — reject |
| Export restrictions | Any clause limiting exports without justification | Flag RED — require written approval |
| Governing law ≠ Spain/EU | Contract governed by non‑EU jurisdiction (e.g., USA) | Flag YELLOW — require explicit justification |
| Liability caps / indemnities | Overly broad caps or indemnity language | Flag RED — reject unless narrowly tailored and justified |
| Data collection beyond order info | Any request for personal data, analytics, or profiling | Flag RED — reject |

## Implementation Notes
- This policy applies to all contracts, NDAs, SOWs, and customer terms.
- If a counterparty insists on prohibited clauses, escalate to `legal-clinic/` for client communication templates.
- Keep this document versioned; any future AI integration must be recorded in a change log here.