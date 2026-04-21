---
description: "Use when editing Streamlit UI files under new_python/ui, including app layout, device CRUD flows, and UI-triggered actions. Keeps UI and data layers separated."
name: "UI Layer Boundaries"
applyTo: "new_python/ui/**/*.py"
---
# UI Layer Boundaries

- Keep data operations and device file CRUD in `new_python/ui/device_manager.py`.
- Keep presentation, interaction flow, and Streamlit widgets in `new_python/ui/app.py`.
- If UI needs new business behavior, add or adjust methods in `device_manager.py` first, then call them from `app.py`.
- Avoid importing unrelated core internals directly into UI unless it is a documented integration path.
- Preserve command-line entry compatibility: UI launch should continue to work via `python main.py --ui`.
- If UI behavior changes, update `new_python/ui/README.md` with usage-impacting notes.
