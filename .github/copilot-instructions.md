# Project Guidelines

## Scope
This workspace contains the active Python project under `new_python/`. Prefer implementing and editing features there unless the user explicitly asks to touch `others/` or top-level `output/`.

## Build And Run
- Install deps: `cd new_python && pip install -r requirements.txt`
- Environment check: `cd new_python && python scripts/check_env.py`
- CLI run: `cd new_python && python main.py`
- UI run: `cd new_python && python main.py --ui`
- Useful verification: `cd new_python && python main.py --help`

## Architecture
- Entry point: `new_python/main.py` (arg parsing, config loading, workflow dispatch)
- Core business logic: `new_python/core/`
- Device vendor adapters: `new_python/core/adapters.py`
- Execution engine and concurrency: `new_python/core/engine.py`
- UI layer: `new_python/ui/` (Streamlit device management)
- Runtime config: `new_python/config/config.yaml` and `new_python/config/password.conf`

See architecture details in `new_python/doc/ARCHITECTURE.md` and usage flows in `new_python/doc/QUICKSTART.md`.

## Conventions
- Preserve CLI backward compatibility in `new_python/main.py` when adding or changing flags.
- Keep vendor-specific command behavior inside adapter classes in `new_python/core/adapters.py`; avoid scattering vendor conditionals across unrelated modules.
- Prefer extending configuration through `new_python/config/config.yaml` instead of hardcoding constants.
- Keep path handling project-root aware (commands are expected to run from `new_python/`).
- For UI work, keep data operations in `new_python/ui/device_manager.py` and presentation logic in `new_python/ui/app.py`.

## Docs-First Linking
- Project overview: `new_python/README.md`
- Detailed docs index: `new_python/doc/README.md`
- Migration context: `new_python/doc/MIGRATION_GUIDE.md`

When changing behavior, update or reference the relevant doc file instead of duplicating long guidance in chat responses.

