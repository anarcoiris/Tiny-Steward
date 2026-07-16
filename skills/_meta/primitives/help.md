---
name: help
type: skill
requires: []
provides: [capability-discovery, troubleshooting]
tags: [help, discover, search, skills, troubleshooting]
related: []
---

# Help — Capability Discovery

Search for skills relevant to your current problem. Uses semantic embedding
search over the skills/ directory.

## When to Use

- **Error recovery**: paste the error message → get relevant fixes
- **Capability discovery**: describe what you need → get relevant skills
- **Domain exploration**: name a domain → get a skill overview

## Usage

```xml
<action name="help">Permission denied (publickey)</action>
<action name="help">how to create a Docker container</action>
<action name="help">python virtual environment</action>
```

## How It Works

1. Your query is embedded using Nomic
2. Cosine similarity against all indexed skills
3. Top matching skills are returned with full documentation
4. Related skills are listed as hints for follow-up

## Tips

- Be specific: "container won't start" > "docker help"
- Include error messages verbatim for best matching
- Use help() multiple times to drill down: first "docker", then "docker compose networking"
- Hub skills return a table of contents — call help() again with a specific sub-skill
