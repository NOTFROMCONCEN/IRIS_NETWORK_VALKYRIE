---
description: "Use when editing Python code in new_python, especially CLI args, inspection engine, device adapters, config.yaml, password.conf, and output generation. Enforces backward compatibility and config-driven changes."
name: "New Python Core Guidelines"
applyTo: "new_python/**/*.py"
---
# New Python Core Guidelines

- Keep CLI backward compatibility in `new_python/main.py`; avoid breaking existing flags or behaviors unless the user explicitly requests it.
- Put vendor-specific command behavior in adapter classes under `new_python/core/adapters.py`; do not scatter vendor conditionals in unrelated modules.
- Prefer configuration-driven behavior through `new_python/config/config.yaml` over hardcoded constants.
- Keep execution paths rooted in `new_python/` so relative paths for `devices/`, `output/`, and `config/` remain stable.
- When behavior changes, update the closest matching docs instead of duplicating long guidance in code comments or chat:
  - `new_python/README.md`
  - `new_python/doc/QUICKSTART.md`
  - `new_python/doc/ARCHITECTURE.md`
