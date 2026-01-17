# CodexDataLab — Delivery Plan (Agentic Roadmap)

This document is the execution roadmap for building CodexDataLab semi-autonomously with agents. It is written to minimize ambiguity: each deliverable is designed to map cleanly to a single branch/PR, with explicit dependencies and “definition of done”.

Canonical “what/why” lives in `VISION.md`. This file is “how/when/what first”.

> **Agent note (do not remove):** The checklist below is the authoritative record of MVP completion. Keep it updated so the project state survives context compactions.

## MVP Execution Checklist

- [x] FOUNDATION-0: Workspace kernel + metadata + tool harness
- [x] MVP-1: Local dataset import (copy/link + provenance)
- [x] MVP-2: Polars-backed dataset loading + table preview
- [x] MVP-3: Optional stats tab for a dataset
- [x] MVP-4: Cleaning transforms (raw → cleaned) with saved code
- [x] MVP-5: Quick analysis tools + structured results
- [x] MVP-6: Plotting v1 (TUI previews) + plot repository
- [x] MVP-7: Chat-with-your-data + answer recording
- [x] MVP-8: Provenance enforcement + UX affordances
- [x] MVP-9: Workspace summary (markdown) rendered in TUI

---

## Locked decisions (do not re-litigate without updating this doc)

### Canonical docs
- **Project definition**: `VISION.md` is the canonical source of product intent and operating principles; it is linked from `README.md` and `AGENTS.md`.

### Workspace layout (flat)
Workspaces use a flat structure at the root:
- `raw/` — imported source data (snapshots by default)
- `data/` — cleaned/merged datasets
- `transforms/` — code/snippets that produce `data/` and other artifacts
- `plots/` — plot definitions + previews
- `results/` — derived outputs (exports, analysis tables, intermediate artifacts)
- `reports/` — generated notebooks (later)
- `.codexdatalab/` — JSON metadata + app state (workspace “truth”)

### Data ingestion defaults
- **Copy-by-default** into `raw/`.
- If the file exceeds a configurable max-copy size, **prompt**: Link / Copy anyway (confirm) / Cancel.
- Support explicit CLI overrides: `--link`, `--force-copy`.
- **Global settings** live in `~/.codexdatalab/` and include at least the max-copy size.
- Always record provenance (original path/URL) and content hashes in workspace metadata.

### Metadata & lineage format
- Workspace metadata is stored as **JSON** files under `.codexdatalab/`.
- Relationships must support tracing every artifact back to raw inputs (raw→cleaned, transform→artifact, plot→dataset, Q&A→evidence).

### Codex integration (how agents run)
- The app integrates with Codex via the **local Codex CLI** (`codex exec`) when available, so it can use the user’s existing Codex setup.
- If the `codex` CLI is unavailable or not configured, the app runs in an **offline mode** (manual tools/UI still work; chat agent features are disabled).

### Workspace versioning
- Workspaces are **git-backed by default**:
  - `codexdatalab init` runs `git init` in the workspace if needed.
  - Raw data is gitignored by default.
  - Metadata/transforms/plots/results are auto-committed to support rollback + provenance.

### Repo-local dev/test workspace
- The repo keeps a **gitignored** workspace directory for manual development: `.codexdatalab_test_workspace/`.
- It is (re)generated from committed fixtures via: `python scripts/create_dev_workspace.py` (use `--reset` to recreate, or `--overwrite-fixtures` to refresh fixture files).
- Test fixtures live under `tests/fixtures/` and are copied into the workspace `raw/` directory.
- CI and unit tests must create **temporary workspaces dynamically** (do not rely on the repo-local workspace).

### MVP scope (Core MVP)
MVP includes:
- workspace init/open
- local CSV/Parquet ingestion
- saved cleaning transforms (raw→cleaned)
- table preview with optional stats
- basic plot previews (scatter/line/bar/hist) + plot gallery
- chat Q&A recorded for reporting
- end-to-end provenance links for datasets/transforms/plots/answers

---

## Terminology & entities (for code + metadata)

CodexDataLab needs a small set of stable concepts (both for the TUI and for agent tools):

- **Workspace**: a folder on disk containing the layout above + `.codexdatalab/` metadata.
- **Dataset**
  - `raw` dataset: imported file snapshot (or link) in `raw/`
  - `cleaned` dataset: output produced by a transform, stored in `data/`
- **Transform**: a reproducible step that produces one or more outputs (usually cleaned datasets). Stored as code in `transforms/` plus metadata.
- **Artifact**: a saved thing derived from data (plot, result table/export, answer). Stored in `plots/`/`results/` with metadata + lineage.
- **Answer (Q&A)**: a structured record of a question asked and the evidence used to answer it (datasets/plots/results), stored in `.codexdatalab/qa.json`.

### Identity & reproducibility rules
- Every Dataset/Transform/Artifact/Answer has a stable **ID** (e.g., `ds_...`, `tf_...`, `pl_...`, `ans_...`).
- Every dataset records:
  - provenance (original path/URL), including potentially multiple “sources” for the same content
  - file hash (content hash)
  - import timestamp
  - whether it’s a copy vs link
- Every derived artifact records:
  - input dataset IDs (and optionally their hashes)
  - transform IDs (if applicable)
  - “why” text (user intent / agent rationale)
- Every “write” operation that changes workspace state triggers an auto-commit (when workspace git is enabled).

### Versioning rules (no guessing)
- **Datasets**: dataset IDs are content-addressed by hash (same content → same dataset ID). A re-import adds a new provenance “source” record; changed content produces a new dataset ID.
- **Transforms**:
  - changes create a new transform version by default (keep the previous script file; link via `parent_transform_id`)
  - allow “edit in place” only when explicitly requested
- **Plots**:
  - edits create a new plot version by default (link via `parent_plot_id`)
  - allow “edit in place” only when explicitly requested
- **Answers (Q&A)**:
  - answers are append-only records; if a user revises an answer, create a new answer record that references the prior one

### Workspace metadata files (v0 minimum)
All workspace metadata files live in `.codexdatalab/` and are JSON. Each file must include a top-level `schema_version` integer so we can migrate safely.

- `manifest.json`
  - purpose: registry of datasets + transforms present in the workspace
  - minimum fields:
    - `schema_version`
    - `datasets`: map `{ "<dataset_id>": { ... } }` with:
      - `id` (content-addressed, e.g. `ds_<sha256prefix>`), `kind` (`raw`|`cleaned`), `path` (workspace-relative), `format` (`csv`|`parquet`|...)
      - `sha256`, `size_bytes`
      - `sources`: list of `{ "source": "<path|url>", "imported_at": "<iso>", "import_mode": "copy|link" }`
      - `created_at` (ISO8601)
      - optional: `parent_dataset_id`, `produced_by_transform_id`, `notes`
    - `transforms`: map `{ "<transform_id>": { ... } }` with:
      - `id`, `path` (workspace-relative), `created_at` (ISO8601)
      - `why` (string), optional `parent_transform_id`
- `lineage.json`
  - purpose: graph edges connecting datasets/transforms/plots/results/answers
  - minimum fields:
    - `schema_version`
    - `edges`: list of `{ "from": "<id>", "to": "<id>", "type": "<relation>", "created_at": "<iso>" }`
- `plots.json`
  - purpose: plot registry and versioning
  - minimum fields:
    - `schema_version`
    - `plots`: map `{ "<plot_id>": { ... } }` with:
      - `id`, `path` (e.g., `plots/<plot_id>.json`), `dataset_ids`, `why`, `created_at`
      - optional: `parent_plot_id`
- `qa.json`
  - purpose: structured answers for later reporting
  - minimum fields:
    - `schema_version`
    - `answers`: map `{ "<answer_id>": { ... } }` with:
      - `id`, `question`, `answer`, `created_at`
      - `dataset_ids`, `artifact_ids` (results/plots), optional `parent_answer_id`
- `state.json`
  - purpose: app UI state (not part of provenance)
  - minimum fields:
    - `schema_version`
    - `ui`: selected dataset/plot IDs, toggle states (stats on/off), last view, etc.

---

## Milestone 0 — Foundation (must be built in one go)

This is the minimum scaffolding required before feature work can be split across branches/PRs safely.

### FOUNDATION-0: Workspace kernel + metadata + tool harness (single PR)

**Goal**
Create a stable workspace core that future PRs can build on without reworking fundamentals.

**Includes**
- Global settings loader/writer at `~/.codexdatalab/` (JSON):
  - at least: `max_copy_bytes`, default behaviors for import prompts, optional “offline mode” toggles
- Workspace detection + initialization:
  - `codexdatalab init [path]` creates folder structure + `.codexdatalab/` JSON files
  - `codexdatalab` launched inside a folder opens it as a workspace (or prompts to init)
- Workspace git integration:
  - initialize git repo if missing
  - generate `.gitignore` (ignore `raw/` by default; keep metadata/transforms/plots/results tracked)
  - helper for auto-commit messages (import, transform run, plot create, answer record, etc.)
- Metadata schema v0 + IO layer:
  - `.codexdatalab/manifest.json` (datasets registry)
  - `.codexdatalab/lineage.json` (edges between entities)
  - `.codexdatalab/qa.json` (answers registry)
  - `.codexdatalab/plots.json` (plot definitions registry)
  - `.codexdatalab/state.json` (UI/app state like last-opened dataset/plot, toggles)
  - schema versioning field to allow migrations later
- “Tool harness” for agentic actions (server-side API surface, even if initially local):
  - a Python interface that exposes workspace operations as “tools” (import, list datasets, preview, stats, run transform, create plot, record answer)
  - explicit confirmation hooks for risky actions (large-file copy override, web download, executing transforms generated by an agent, destructive deletes)
- Textual app foundation wiring:
  - app starts with a “workspace loaded” banner/status
  - skeleton panels: file browser, table view, plot view, chat view (existing UI can be refit)
  - keybindings reserved in `AGENTS.md` are implemented as no-ops or navigation only (no data loss)
- Dev/test harness scaffolding:
  - committed fixtures under `tests/fixtures/`
  - a gitignored local workspace `.codexdatalab_test_workspace/` generated by script
  - pytest-based CI coverage for workspace scaffolding and future features

**Definition of done**
- Running `codexdatalab init` creates a valid workspace with all folders + base JSON.
- Running `codexdatalab` inside that folder opens the app and loads workspace metadata without errors.
- Workspace state changes (e.g., toggling UI flags) persist to `.codexdatalab/state.json`.
- Workspace git is initialized and an initial commit exists (unless disabled).

---

## Milestone 1 — MVP deliverables (Core MVP, PR-sized)

All MVP deliverables assume FOUNDATION-0 is merged. Each deliverable should land as an independent PR, with dependencies explicitly listed.

### MVP-1: Local dataset import (copy/link + provenance)

**Goal**
Import local CSV/Parquet files into `raw/` with reproducible metadata.

**Dependencies**
- FOUNDATION-0 (settings + metadata + git helpers)

**Includes**
- CLI command: `codexdatalab import <path>`
  - copies to `raw/` by default
  - if file > `max_copy_bytes`: prompt Link / Copy anyway / Cancel
  - flags: `--link`, `--force-copy`
- Deterministic naming for imported raw files (e.g., `raw/<dataset_id>.<ext>`) so re-imports can reuse the same bytes.
- Record in `.codexdatalab/manifest.json`:
  - dataset ID (content-addressed), local path, hash, size
  - append a new entry to `sources` for each import (original path/URL, timestamp, import mode)
- Auto-commit the import metadata (and any non-ignored files)

**Definition of done**
- Importing a file creates a dataset entry and the file exists in `raw/` (or is linked).
- Re-importing identical content reuses the existing dataset ID and adds a new provenance “source” record (no duplicate bytes copied unless explicitly requested).

### MVP-2: Polars-backed dataset loading + table preview

**Goal**
Fast table preview in the TUI for CSV/Parquet datasets, prioritizing cleaned datasets.

**Dependencies**
- MVP-1 (so there is something to load)

**Includes**
- Polars integration (lazy loading where possible)
- Workspace browser that:
  - shows datasets (not raw filesystem entries) with clear labels
  - prioritizes `data/` (cleaned) over `raw/`
- Scrollable table view for a selected dataset:
  - configurable max rows/cols for preview
  - handles large files gracefully (sampling)

**Definition of done**
- Selecting a dataset in the UI shows a scrollable table preview within the TUI.

### MVP-3: Optional stats tab for a dataset

**Goal**
Provide a toggleable stats panel for quick understanding of the current dataset.

**Dependencies**
- MVP-2 (table selection + loading)

**Includes**
- Toggleable “Stats” panel/tab in the TUI
- For numeric columns: min/max/mean (extendable later)
- For categorical/text columns: unique count + value counts (top-N)
- Store UI toggle state in `.codexdatalab/state.json`

**Definition of done**
- Stats panel can be toggled on/off; computed stats match the dataset preview.

### MVP-4: Cleaning transforms (raw → cleaned) with saved code

**Goal**
Enable reproducible cleaning/merging steps and keep outputs + code + lineage linked.

**Dependencies**
- MVP-1 (raw data exists)
- FOUNDATION-0 (tool harness + metadata + git)

**Includes**
- Transform representation:
  - stored as code under `transforms/` (e.g., Python script template)
  - transform metadata stored under `.codexdatalab/manifest.json` or a dedicated transforms registry
- Transform runner:
  - executes transform to produce one or more outputs in `data/`
  - enforces output path restrictions (must write inside workspace)
  - captures logs/errors into `results/` and metadata
- Lineage updates:
  - edge(s): raw dataset → cleaned dataset(s)
  - edge(s): transform → output dataset(s)
- Auto-commit transform + lineage changes

**Definition of done**
- A basic transform (rename/select columns) can be created, run, and produces a cleaned dataset in `data/`.
- The cleaned dataset is selectable in the UI and traces back to the raw dataset in metadata.

### MVP-5: “Quick analysis” tools (Polars) + structured results

**Goal**
Provide small, composable analysis tools that both the user and Codex can invoke.

**Dependencies**
- MVP-2 (datasets load)

**Includes**
- Tool functions (initial set):
  - describe schema + null counts
  - numeric summary (min/max/mean, maybe std)
  - value counts for a column
  - groupby count for (column(s))
- Store outputs as artifacts under `results/` (e.g., `results/<artifact_id>.json|md|csv`)
- Record artifacts + lineage edges (dataset → result)

**Definition of done**
- Running a tool produces a stored result artifact and can be referenced later (by ID) in chat and reporting.

### MVP-6: Plotting v1 (TUI previews) + plot repository

**Goal**
Let users (and Codex) create and store plots tied to datasets.

**Dependencies**
- MVP-2 (datasets load)
- FOUNDATION-0 (plots registry + lineage)

**Includes**
- Plot types (minimum):
  - scatter, line, bar (categorical), histogram
- Color support:
  - per-series/per-category color mapping (including distinct bar colors)
- UI for manual plot creation:
  - select dataset
  - select x/y (and optional category/series)
  - render a Textual braille plot in the plot panel
- Plot persistence:
  - plot definition stored as JSON (e.g., `plots/<plot_id>.json`)
  - metadata entry in `.codexdatalab/plots.json` including “why”
  - lineage edge: dataset(s) → plot
- Plot gallery:
  - list plots, open existing plots, create new versions or edit in place (see “Versioning rules” above)

**Definition of done**
- A plot can be created, saved, reopened, and re-rendered.
- Plot metadata includes the dataset ID(s) and a rationale string.

### MVP-7: Chat-with-your-data + answer recording (agent-ready)

**Goal**
Turn the app into “chat with your data”, while keeping outputs structured and reproducible.

**Dependencies**
- MVP-5 (analysis tools) and MVP-6 (plots) are strongly recommended, but chat can ship earlier if needed.

**Includes**
- Chat UI that can:
  - reference datasets/artifacts by name/ID
  - show tool runs and outputs clearly
- Codex integration path (agent tool usage):
  - Codex can call the tool harness for: list datasets, preview, stats, quick analysis, run transforms, create plots
  - confirm before running transforms or large operations (human-in-loop)
- Structured answer recording:
  - every answered question becomes an entry in `.codexdatalab/qa.json` containing:
    - question, answer summary
    - referenced dataset IDs / artifact IDs
    - optional “evidence pointers” (paths, row/col selections, plot IDs)
    - timestamps and agent/user attribution

**Definition of done**
- User asks a data question; the system runs at least one tool; the answer appears in chat and is recorded structurally with evidence links.

### MVP-8: Provenance enforcement + UX affordances

**Goal**
Make “trace every result back to raw data” true in practice, not just in metadata.

**Dependencies**
- MVP-1 through MVP-7

**Includes**
- UI affordance to inspect lineage for a selected dataset/plot/result/answer
- Standardized “why” capture for:
  - transforms
  - plots
  - stored answers
- Auto-commit policies tuned so the workspace history stays readable (one commit per logical action)

**Definition of done**
- From any plot/result/answer in the UI, the user can navigate to its source dataset(s) and then to the raw import record.

### MVP-9: Workspace summary (markdown) rendered in TUI

**Goal**
Provide a living, user-visible summary of the project/workspace.

**Dependencies**
- MVP-7 (agent/chat) strongly recommended, but can be stubbed with manual editing first.

**Includes**
- Summary stored as markdown (suggested): `results/summary.md`
- TUI view to render it
- Optional: “Regenerate summary” action that uses Codex and pulls from:
  - dataset list
  - recent plots
  - recent answers

**Definition of done**
- A markdown summary exists on disk, is rendered in the app, and can be updated.

---

## Future work (independent deliverables; define now, build later)

Each item below should be implementable as a separate PR after MVP. Dependencies are noted to avoid ambiguity.

### FUT-1: Web dataset search + download (Codex-assisted, curated)

**Goal**
Let Codex find candidate datasets on the web and download them into `raw/` with provenance.

**Dependencies**
- FOUNDATION-0 (tool harness + confirmations)
- MVP-1 (import/provenance patterns)

**Includes**
- Explicit user command (no silent web browsing):
  - `codexdatalab fetch <query|url>`
- Curated sources / allowlist (configurable)
- Download into `raw/` with:
  - source URL, retrieval time, content hash, license/provenance notes if available
- Optional: dataset “receipt” artifact under `results/` summarizing source and terms

### FUT-2: Computed columns (“recipes”) and lightweight aggregators

**Goal**
Support user/agent-defined derived columns that are reproducible and editable.

**Dependencies**
- MVP-4 (transforms) and MVP-2 (data loading)

**Includes**
- “Recipe” definition stored as a snippet (e.g., `transforms/recipes/<recipe_id>.py|json`)
- Ability to apply recipes to a dataset to produce a derived dataset (or virtual view)
- UI affordance to mark columns as derived and to edit the snippet

### FUT-3: Expanded plotting (fits, multi-series, more chart types)

**Goal**
Increase expressiveness of terminal previews.

**Dependencies**
- MVP-6 (plot system)

**Includes**
- Scatter with trend/line fits
- Multi-series coloring and legend support
- Additional plot types: violin (if feasible in TUI), error bars

### FUT-4: Interactive widgets for filtering/exploration

**Goal**
Provide simple interactive controls (slider/select/dropdown) that can be attached to tables/plots.

**Dependencies**
- MVP-2 (tables) and/or MVP-6 (plots)

**Includes**
- A small set of widget primitives (filter, range slider, category selector)
- A binding mechanism so a plot/table can reference widget state
- Persist widget config/state in `.codexdatalab/state.json`

### FUT-5: Notebook report export (from workspace + chat context)

**Goal**
Generate a polished Jupyter notebook that reproduces the analysis with narrative.

**Dependencies**
- MVP-4 (transforms), MVP-6 (plots), MVP-7 (Q&A recording)

**Includes**
- `codexdatalab report` command that creates `reports/<report_id>.ipynb`
- Notebook contains:
  - data loading (from `data/` and/or `raw/` with transforms)
  - key stats + samples
  - matplotlib versions of plots
  - markdown narrative derived from summary + Q&A + plot rationales
- Links/pointers to workspace artifacts for traceability

### FUT-6: Multi-project workspaces + cross-linking

**Goal**
Allow multiple “projects” inside a workspace, sharing or linking datasets.

**Dependencies**
- MVP completed (needs stable metadata + lineage)

**Includes**
- Introduce optional `projects/<name>/...` structure while keeping the current flat layout as the default “project”
- Cross-project dataset references (shared datasets registry or explicit links)
- One report per project (initially)

### FUT-7: Safer execution + permissions model (agent hardening)

**Goal**
Make agentic automation safer and more predictable as capabilities grow.

**Dependencies**
- FOUNDATION-0 tool harness

**Includes**
- Explicit permissions prompts and allowlists:
  - filesystem access outside workspace
  - network downloads
  - running transforms or arbitrary code
- Audit log of tool calls (append-only log in `.codexdatalab/`)

---

## Versioning & release workflow (repo operations)

This is included here because agents will ship changes regularly and need a repeatable release path.

- Version bumps are done with `bump2version` and create tags `vX.Y.Z`.
- The GitHub release workflow triggers on pushed `v*` tags and generates release notes (Codex-assisted) before publishing artifacts.

---

## How to use this plan (agent workflow)

- Each deliverable is a separate PR with:
  - clear scope (one deliverable only)
  - validation steps (commands run)
  - screenshots for TUI changes (use `terminal-shot` skill when applicable)
- If a deliverable introduces a new decision, add it to this file under “Locked decisions” (or a new decision section) and resolve it explicitly.
