body="# Tiny Plan — Improvements for steward.py

## 1. Config validation
Add schema checking against the keys defined in `config.yaml` before using them; surface missing/invalid entries early.

## 2. Error handling
Replace bare warnings with structured exceptions (`LLMTimeout`, `EmbeddingError`) and retry logic for flaky endpoints.

## 3. Atomic fallback
If the atomic model fails, gracefully fall back to the orchestrator for simpler tasks.

## 4. Help engine tuning
Allow per-session override of `min_similarity` or query-complexity based thresholds.

## 5. Logging
Switch from `print` to Python's `logging` module with configurable levels/handlers.

## 6. Output streaming
Expose partial tokens via an API while waiting for the full response.

## 7. Session persistence
Consider encrypting/compressing sensitive session data; add remote storage option if configured.

## 8. CLI enhancements
Add `--verbose`, `--dry-run`, and a `--checkpoint <id>` for resuming specific saved states.

## 9. Performance
Parallelize embedding of many skills; add progress indicators during index builds.

## 10. Shutdown safety
Ensure running LLM requests are cancelled cleanly on exit (context managers, signal handling)."