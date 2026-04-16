# Conventional Commits

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

## Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Code style changes (formatting, no logic change) |
| `refactor` | Code refactoring (no feature/fix) |
| `perf` | Performance improvements |
| `test` | Adding or correcting tests |
| `chore` | Build process, auxiliary tools, dependency updates |
| `revert` | Reverts a previous commit |

## Scope

Optional scope indicates the affected area:

- `deps` — dependencies
- `rom` — ROM analysis/patching
- `tools` — tooling
- `docs` — documentation
- `dialogue` — dialogue system
- `map` — map/level system
- `battle` — battle system
- `web-editor` — web editor frontend/backend

## Examples

```
feat(dialogue): add new dialogue entry for episode 5
fix(rom): correct battle config pointer offset
docs(readme): update build instructions
chore(deps): lock fastapi version to 0.109.0
refactor(tools): simplify build_mod.py patch logic
```

## Rules

- Use imperative mood: "add" not "added", "fix" not "fixed"
- Keep subject line ≤72 characters
- Use lowercase after the colon
- Reference issues in footer: `Refs: #123`
