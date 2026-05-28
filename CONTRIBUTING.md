# Contributing to Phoenix-Evo

Thank you for your interest in contributing to Phoenix-Evo! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/Phoenix-Evo.git
   cd Phoenix-Evo
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature
   ```

## Development Workflow

### Code Style

- Follow PEP 8 conventions
- Use type hints for all function signatures
- Keep functions focused and under 50 lines when possible
- Write docstrings for all public classes and methods

### Testing

All new features and bug fixes must include tests:

```bash
# Run smoke tests (fast health check)
pytest tests/test_smoke.py -v

# Run full test suite
pytest tests/ -v

# Run a specific test file
pytest tests/test_immune_guard.py -v
```

### Project Structure

```
core/           - Core evolution engine (skill mining, immune guard, registry)
runtime/        - Runtime modules (router, guard, context injection, feedback)
integrations/   - External system adapters (Hermes bridge)
cli/            - Command-line interface
tests/          - Test suite
skills/         - Skill storage (draft/active/archived/rejected)
docs/           - Technical documentation
```

### Commit Messages

Use conventional commit format:

- `feat(module): description` for new features
- `fix(module): description` for bug fixes
- `test(module): description` for test additions
- `docs(module): description` for documentation
- `refactor(module): description` for refactoring

Examples:
```
feat(runtime): add project-level skill routing
fix(feedback): correct JSONL append mode in dispatcher
test(immune): add quarantine threshold tests
```

### Pull Request Process

1. Ensure all tests pass: `pytest tests/ -v`
2. Update documentation if adding/changing public APIs
3. Keep PRs focused -- one feature or fix per PR
4. Write a clear PR description explaining the change and its motivation

## Architecture Guidelines

### Self-Evolution Loop

Phoenix-Evo follows a closed-loop evolution pattern:

```
Task -> Trajectory -> Self-Evaluation -> Extraction -> Verification -> Storage -> Reuse
                |
            Failure Attribution -> Immune Defense -> Reject Dangerous Experience
```

When modifying core modules, ensure the loop integrity is preserved:

- New skills must enter `skills/draft/` first (never auto-activate)
- Dangerous patterns must be caught by the immune system
- All skills must be traceable to source trajectories
- Active skills must never be auto-modified or auto-deleted

### Runtime Guard Rules

The Runtime Guard enforces 8 security rules. When adding new guard rules:

1. Add the rule to `runtime/runtime_guard.py`
2. Add corresponding test cases in `tests/test_runtime_router.py`
3. Update the rule table in README.md

### Adding New Modules

1. Place core modules in `core/`
2. Place runtime modules in `runtime/`
3. Export key classes from the package `__init__.py`
4. Add import tests to `tests/test_smoke.py`
5. Add functional tests in `tests/`

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include reproduction steps for bugs
- Include Python version and OS information

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
