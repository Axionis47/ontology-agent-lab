# OaK

Implementation of the OaK paper: build a domain schema and reusable functions, refine them from development tasks, then freeze them for inference. Model weights stay fixed.

Goal: a plug-and-play task and evidence interface for working agents, independent of their internal planner or native toolset. Accept completed work only after the required checks pass.

- **[Design](docs/oak/DESIGN.md)**: the complete specification, architecture, and component contracts.
- **[Setup](docs/OAK-SETUP.md)**: install dependencies and run local checks.
- **[Paper](docs/oak/paper/2608.22974v1.pdf)**: the pinned OaK source, with [provenance](docs/oak/paper/source.json).

Current state: design and offline contract harness. The production construction, refinement, and inference loops are still to be built.
