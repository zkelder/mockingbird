# Documentation index

This directory holds about 300 documents. Most are **design contracts** and
**milestone reports**, kept deliberately as the record of what was decided,
built, and verified. You do not need to read them to use or run MockingBird.
Start here.

## I want to use MockingBird

- [Using MockingBird](using-mockingbird.md): install, first run, add a camera, observe, review, back up
- [Support & compatibility matrix](support-matrix.md): the canonical statement of what is and is not supported
- [Troubleshooting](troubleshooting.md) and [Privacy & security](privacy-and-security.md)
- [Camera Node install guide](camera-node-install-guide.md): Raspberry Pi (reference) edge device
- [Portfolio demo walkthrough](portfolio-demo-walkthrough.md): try it with public-domain clips, no live camera

## I want to understand the design

Read in this order:

1. [Product doctrine](product-doctrine.md): what MockingBird is, and the truth model (evidence vs. reviewed truth)
2. [Architecture](architecture.md): components, data flow, storage, lifecycle, the Host / Camera Node split
3. [Runtime map](runtime-map.md): which file owns what, and the production-vs-research boundary
4. [Glossary](glossary.md): canonical domain terms
5. [Engineering case study](portfolio/case-study.md): the story in one page

Key contracts behind the main ideas:

| Idea | Document |
|---|---|
| Camera Node is an edge, not the system of record | [camera-node-boundary-design.md](camera-node-boundary-design.md) |
| Observation pipeline (detect, track, admit Visits) | [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md), [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md) |
| Humans decide; model output is only evidence | [reviewed-visit-truth-contract.md](reviewed-visit-truth-contract.md), [review-decision-provenance-contract.md](review-decision-provenance-contract.md) |
| Persistence, backup, recovery | [local-backup-recovery-design.md](local-backup-recovery-design.md), [single-app-runtime-recovery-design.md](single-app-runtime-recovery-design.md) |
| Tests never touch a real database | [test-repository-isolation-contract.md](test-repository-isolation-contract.md) |

## I want to contribute or run from source

- [CONTRIBUTING.md](../CONTRIBUTING.md) (includes the first-time test commands) and [Developer setup](developer-setup.md)
- [Development workflow](development-workflow.md) and [test validation tiers](test-suite-validation-tiers-contract.md)
- [AGENTS.md](../AGENTS.md): working rules and document routing, also used by coding agents

## Project status and planning

- [Release execution state](release-execution-state.md): what is accepted, what remains, what is authorized
- [Roadmap](roadmap.md) and [roadmap history](roadmap-history.md)
- [Final Release Hardening report](final-release-hardening-launch-candidate-v1-report.md): latest validation record
- [Owner release checklist](owner-release-checklist.md): decisions that belong to the repository owner

## Naming conventions

- `*-contract.md` / `*-design.md`: the intended behavior and why.
- `*-report.md`: a dated milestone report with the evidence gathered (commands, results, defects found and fixed). Reports are point-in-time records; later corrections appear in newer reports or the release execution state.
- `assets/`: screenshots used by the README and demo walkthrough (captured from the DEMO instance with public-domain clips; no private data).
- `demo/`: the manifest of the CC0 clips the demo downloads on request. The clips themselves are never committed.
- `gate-g-launch-package-v1/`: blank participant-facing templates for a planned external acceptance round that was waived; they contain no personal data.
