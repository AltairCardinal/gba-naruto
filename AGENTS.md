# Project Memory Rules

This repository is used as the persistent project memory for the ROM reverse-engineering and sequel-planning work.

Required rules:

1. All meaningful findings must be written into files inside this repository.
2. All effective development work must leave durable project artifacts in this repository.
3. Do not rely on chat history as the primary memory. If something matters later, record it in `notes/`, `docs/`, `tools/`, or another appropriate project file.
4. When a debugging method proves useful, document both the method and the result.
5. When a reverse-engineering conclusion changes, update the relevant note instead of leaving the old state only in conversation.
6. When roadmap progress changes, update `docs/sequel-roadmap.md` in the same work cycle.

Preferred locations:

- `notes/`: investigation logs, intermediate findings, memory maps, experiment results
- `docs/`: stable plans, workflows, architecture, reverse-engineering strategy
- `tools/`: scripts, automation, reproducible probes

Minimum expectation for each successful step:

- record what was attempted
- record what was learned
- record what file or address range is now important
