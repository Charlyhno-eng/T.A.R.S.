---
name: pyside6-qml  
description: Define strict architecture and coding rules for PySide6 and QML applications.
---

# PySide6 + QML

## Architecture

Use exactly this structure:

```text
Application_Name/
│
├── README.md
├── LICENSE
├── .gitignore
│
├── assets/             (if necessary)
│   ├── icons/
│   ├── sounds/
│   └── fonts/
│
├── config/             (if necessary)
│   ├── default.toml
│   ├── development.toml
│   └── production.toml
│
├── src/
│   │
│   ├── app.py
│   │
│   ├── app/
│   │   ├── example1.py
│   │   ├── example2.py
│   │   ├── example3.py
│   │   └── example4.py
│   │
│   ├── core/           (business logic)
│   │
│   └── ui/
│       ├── Main.qml
│       ├── pages/
│       ├── components/
│       └── theme/
```

Keep features separated by responsibility. Each file must have one clear purpose. Avoid generic files such as `utils.py`, `helpers.py`, or `manager.py`.

## Python / QML

**Python:** business logic, services, data, configuration, integrations, long-running tasks, and application state.

**QML:** interface, layout, animations, styles, interactions, and visual state.

Never put business logic in QML or directly manipulate QML elements from Python except in exceptional cases.

Expose Python functionality through `Property`, `Signal`, `Slot`, and Qt models. Expose only the API required by QML.

## QML

- `pages/`: application screens.
- `components/`: reusable components.
- `theme/`: shared visual constants.
- `Main.qml`: lightweight application composition.

Avoid large JavaScript blocks in QML.

## Lifecycle

`main.py` must remain minimal.

- `bootstrap.py`: builds dependencies and initializes the application.
- `container.py`: centralizes dependency construction.
- `application.py`: owns the Qt application and QML engine.
- `lifecycle.py`: manages service startup and shutdown.

Avoid global singletons and import-time initialization.

## Concurrency

Never block the GUI thread. Use appropriate Qt mechanisms for long-running tasks. Workers communicate with the UI through signals.

## Comments

All comments and docstrings must be in English.

Do not use line comments, end-of-line comments, `TODO`, `FIXME`, or commented-out code.

Only function, method, or API documentation is allowed, limited to one line.

```python
def shutdown(self) -> None:
    """Stop the service and release its resources."""
```

## Code

- Use complete Python type hints.
- Prefer constructor dependency injection.
- Keep classes and functions small.
- Prefer native Qt mechanisms.
- Keep two blank lines between declarations and after imports.
- Place every feature in the files matching its responsibility.

## Validation

Before completing a modification:

- verify Python and QML imports and syntax;
- verify Python types;
- run relevant tests;
- verify clean application startup and shutdown.
