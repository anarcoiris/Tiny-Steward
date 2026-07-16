# Managed Agent Cookbooks Policy — Electronic Crafts

*Tailored for a sole proprietor operating across EU and global markets. Low legal risk by default, aggressive when opportunity arises.*

## Core Principles
- **Default governing law**: Spain (EU). Any other jurisdiction requires explicit written justification.
- **No liability caps** unless narrowly tailored and explicitly agreed.
- **No indemnity clauses** that shift risk broadly; only specific, justified indemnities.
- **Open-source compliance**: all software used must be licensed; any proprietary tool usage triggers a warning.

## Guardrails
| Rule | Trigger | Action |
|------|---------|--------|
| Non-solicit / non-compete | Clause attempting to restrict future work | Flag RED — reject |
| Export restrictions | Clause limiting exports without justification | Flag RED — require written approval |
| Governing law ≠ Spain/EU | Contract governed by non‑EU jurisdiction (e.g., USA) | Flag YELLOW — require explicit justification |
| Liability caps / indemnities | Overly broad caps or indemnity language | Flag RED — reject unless narrowly tailored and justified |
| Data collection beyond order info | Request for personal data, analytics, or profiling | Flag RED — reject |

## Implementation Notes
- This policy applies to all contracts, NDAs, SOWs, and customer terms.
- If a counterparty insists on prohibited clauses, escalate to `legal-clinic/` for client communication templates.
- Keep this document versioned; any future changes must be recorded here.