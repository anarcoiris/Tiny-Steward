# Plan: Organizing skills/ Directory

*Reference: DomainSpec/classify.md — topic classifier and layout decision.*

---

## Decision

**Topic-primary** layout. Verb prefixes (`testing-`, `detecting-`, …) are metadata, not folders.

Rationale: ~831 cyber skills cluster by subject matter (cloud, DFIR, appsec, …). Verb-only folders scatter related capabilities and conflict with DomainSpec progressive loading by topic/persona.

Topic buckets from `classify.py` are **catalog tags**, not DomainSpec v2 `type: domain` nodes.

---

## Proposed Structure

```text
skills/
├── application_and_api_security/
│   ├── testing-for-xss-vulnerabilities/
│   ├── exploiting-server-side-request-forgery/
│   └── ...
├── cloud_security/
├── detection_engineering_and_threat_hunting/
├── digital_forensics_and_incident_response/
├── active_directory_and_identity_attacks/
├── malware_analysis_and_reverse_engineering/
├── threat_intelligence/
├── network_security_and_perimeter/
├── container_and_kubernetes_security/
├── ...
└── _meta/                          # infra / triage (optional)
    ├── primitives/
    └── ...
```

Leaf directory names stay the original skill IDs (no rename).

Persona filtering can still use verb metadata from `domainspec_mapping.csv` (`verb_prefix` column) or secondary topics.

---

## Migration Steps

1. **Classify** (done bootstrap):
   ```bash
   python DomainSpec/classify.py
   ```
   Requires golden set pass (`DomainSpec/golden_set.csv`).

2. **Human spot-check** mapping CSV — sample per topic + all `secondary_domains` that look surprising.

3. **Migrate** with `DomainSpec/migrate_skills.py` (uses the CSV):
   ```bash
   python DomainSpec/migrate_skills.py --dry-run
   python DomainSpec/migrate_skills.py
   ```
   Do **not** use any `skills/**/migrate.py` that groups by verb first-word only — that path dumped everything into `unclassified/`.

4. **Update references** in personas / loaders that assume a flat `skills/` tree.

---

## Out of scope (for now)

- Converting topic folders into DomainSpec `.domain.md` files
- Verb-primary alternate tree (rejected)
- Automatic secondary-topic folders

---

DONE
