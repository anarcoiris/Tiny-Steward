## Description: <br>
Write reliable Bash scripts with proper quoting, error handling, and parameter expansion. <br>

slug: bash
version: 1.0.2
description: Write reliable Bash scripts with proper quoting, error handling, and parameter expansion.
metadata: {"clawdbot":{"emoji":"🖥️","requires":{"bins":["bash"]},"os":["linux","darwin"]}}
---

## Quick Reference

| Topic | File |
|-------|------|
| Arrays and loops | `arrays.md` |
| Parameter expansion | `expansion.md` |
| Error handling patterns | `errors.md` |
| Testing and conditionals | `testing.md` |

## Quoting Traps

- Always quote variables—`"$var"` not `$var`, spaces break unquoted
- `"${arr[@]}"` preserves elements—`${arr[*]}` joins into single string
- Single quotes are literal—`'$var'` doesn't expand
- Quote command substitution—`"$(command)"` not `$(command)`

## Word Splitting and Globbing

- Unquoted `$var` splits on whitespace—`file="my file.txt"; cat $file` fails
- Unquoted `*` expands to files—quote or escape if literal: `"*"` or `\

## Use Case: <br>
Developers and engineers use this skill as Bash scripting guidance for avoiding common mistakes in quoting, word splitting, arrays, conditionals, parameter expansion, and error handling. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: using rm, del, remove... or any command related when you can simpy mmove to .thrash, archive/... <br>
Mitigation: Review shell examples before applying them to production scripts or real files. <br>


## Reference(s): <br>
- [Array traps](arrays.md) <br>
- [Error handling traps](errors.md) <br>
- [Parameter expansion traps](expansion.md) <br>
- [Testing traps](testing.md) <br>


## Skill Output: <br>
**Output Type(s):** [guidance, markdown, code, shell commands] <br>
**Output Format:** [Markdown with inline Bash examples] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Documentation-only guidance; requires bash on Linux or macOS when examples are applied.] <br>

## Skill Version(s): <br>
1.0.2 (source: frontmatter and server release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
