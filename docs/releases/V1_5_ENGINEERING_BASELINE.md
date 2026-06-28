# V1.5 Engineering Baseline

**Release date:** ~2025-06  
**Summary:** Engineering modernization + real experiment infrastructure baseline

## Key Changes

### Lint & Style Compliance
- ruff lint compliance across 176 files

### Type Annotation Migration
- `Dict` → `dict`, `List` → `list`, `Tuple` → `tuple`, etc. (PEP 585)
- `IOError` → `OSError`
- `elif` chains refactored to `if` + early `return`

### Python Modernization
- `StrEnum` adoption where applicable

### API & Infrastructure
- FastAPI health endpoint added
- CI reliability improvements
- Build artifacts removed from git tracking

### New Modules (Infrastructure)
- `distributed` — distributed skill library scaffolding
- `enterprise` — enterprise integration scaffolding
- `multi_agent` — multi-agent collaborative evolution scaffolding
- `self_repair` — self-repairing architecture scaffolding

### Integrations
- DeepSeek API adapter for real LLM experiment execution

## Known Issues

- Docker CI still under investigation in v1.5.0

## Important Note

This is **not v2.0**. Experiment conclusions drawn from the E1–E6 suite are preliminary. See `docs/experiments/E1_E6_DEEPSEEK_PRELIMINARY.md` for details and `docs/LIMITATIONS.md` for known limitations.
