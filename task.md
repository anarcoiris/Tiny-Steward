# Task: Analyze and Document Redundant Scripts in Qwythos Environment

## Goal
Identify, categorize, and document redundant or duplicate PowerShell scripts within the `C:\Users\soyko\Documents\Ollama\docker\llamacpp` directory. Focus on maintaining alignment with the overall system objectives.

## Current Status
- **Directory**: `C:\Users\soyko\Documents\Ollama\docker\llamacpp`
- **Scripts Listed**: 38 total (including utilities, startup scripts, and common functions)
- **Key Observations from Initial Scan**:
  - `atomic96-qwythos256.ps1` (1.3KB) — core atomic server launcher
  - `start-qwythos.ps1` (6.4KB) — comprehensive stack starter
  - `set-atomic-lane-profile.ps1` (8.3KB) — profile configuration
  - Multiple Gemma-related scripts (`start-gemma-*.ps1`, `stop-gemma-*.ps1`)
  - Repair and restore utilities (`repair-llama-server.ps1`, `restore-atomic-bin.ps1`)
  - Common functions (`_common.ps1`, `free-gpus.ps1`)

## Next Steps
1. Compare script contents to identify duplicates or near-duplicates
2. Check for scripts with identical functionality but different names
3. Document findings in a structured report
4. Recommend consolidation actions where appropriate

## Long Term mission Goal:
 adding visual projector

## Async Clock Tools / Heartbeat — Build & Integrate
- Goal: Provide a heartbeat/timer that always inputs a user prompt interaction with instructions on pending awaitings
- Must work as "while, for, if" loops; if no approved steps require human-in-the-loop, scan `../repo-hygiene/*` (in Documents) for tasks
- If out of jobs: clone https://github.com/anarcoiris/editorial_anarcoiris and incorporate its skills
- Add this reminder to task.md so it is not missed or left incomplete