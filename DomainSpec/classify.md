# Skill topic classifier (DomainSpec catalog)

Bootstrap classifier that maps ~831 skill slugs into **topic buckets** for organizing `skills/`.

## Layout decision

**Topic-primary** folders; verb prefix kept as metadata.

```text
skills/
└── <primary_topic>/          # e.g. application_and_api_security/
    └── <skill_id>/           # original slug, unchanged
```

CSV columns `verb_prefix` and `secondary_domains` support persona filters without a second folder tree.

These topic buckets are **catalog tags**, not DomainSpec v2 `type: domain` nodes (`git`, `docker`, `python`). Do not treat mapping rows as Domainspec domain files.

## Files

| File | Role |
|------|------|
| `skills_raw.txt` | Input slug list |
| `classify.py` | Classifier + CSV writer + golden check |
| `domainspec_mapping.csv` | Generated mapping (regenerate; do not hand-edit) |
| `golden_set.csv` | Regression expectations |
| `migrate_skills.py` | Move skill dirs into `skills/<topic>/` from the CSV |

## Run

```bash
python DomainSpec/classify.py
```

Exit code `0` only if golden set passes. Regenerates `domainspec_mapping.csv`.

## Matching rules

1. Exact anchors: bare domains (`bash`, `git`, …), meta/infra, `legal` → policy.
2. Synonym rewrite (`server-side-request-forgery` → `ssrf`, `canary-tokens` → `canarytoken`, …).
3. Domain keyword lists, ordered specific → general. **First hit = primary topic.**
4. Short / risky tokens (`cape`, `c2`, `jwt`, `soc2`, …) match as **hyphen-delimited path segments** only — prevents `cape`∈`landscape`/`escape` and `c2`∈`soc2`.
5. Additional domain hits become `secondary_domains` (semicolon-separated).
6. Fallback: prefixes `detecting-` / `hunting-` / `triaging-` → `detection_engineering_and_threat_hunting`.

## Latest metrics (after finalize)

| Metric | Value |
|--------|------:|
| Total slugs | 831 |
| Skills | 817 |
| Bare domains | 6 |
| Meta / triage | 7 |
| Policy | 1 |
| Unclassified | **0** |
| Golden set | **23/23 pass** |

Largest topic buckets: detection eng (~101), app/API (~81), cloud (~62), AD/identity (~54), DFIR (~54), TI (~53).

## Known limits

- Single primary label is a forced choice for cross-cutting skills (e.g. Android malware → mobile, with malware as secondary when both hit).
- Keyword lists will need maintenance as the catalog grows; extend `golden_set.csv` when fixing regressions.
- Ready as a **mapping artifact**, not yet a filesystem migration. Migration should dry-run from the CSV after a human spot-check.

## Relation to `plan.md`

`plan.md` originally proposed verb-prefix folders. That plan is superseded: **topic-primary** is the organizing axis; verbs remain filter metadata in the CSV.
