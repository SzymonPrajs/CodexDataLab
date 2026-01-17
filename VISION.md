# CodexDataLab — Project Vision

CodexDataLab is a terminal-first, human-in-the-loop “chat with your data” workspace for small-to-medium **tabular** datasets. It uses a Textual TUI for fast iteration and integrates Codex to help users ingest data, clean it, explore it, visualize it, and produce reproducible outputs.

## Product goals

- **Local-first:** Prefer local data and local compute; keep workflows fast and privacy-friendly.
- **Agentic, but accountable:** Codex can propose and execute actions, but the user stays in control (confirmations, previews, clear provenance).
- **Reproducible by design:** Every result must be traceable back to raw data and the exact transforms/code that produced it.
- **Workspace-centric:** Opening a folder creates (or uses) a workspace with a consistent structure and metadata.
- **Terminal UX:** Tables, plots, and navigation work well in a TUI; rich outputs can be exported later.

## Core concepts

- **Workspace:** A folder on disk that contains data, artifacts, and `.codexdatalab/` metadata.
- **Dataset**
  - **Raw dataset:** Imported snapshots stored under `raw/`.
  - **Cleaned dataset:** Outputs of cleaning/merging transforms stored under `data/`.
- **Transform:** Code (usually generated with Codex) that turns raw data into cleaned data (rename, select columns, merge, etc.). Stored under `transforms/` and referenced from metadata.
- **Artifact:** A saved plot/view, a Q&A answer, or any result stored under `plots/` / `results/` and linked to its inputs.
- **Provenance/lineage:** JSON metadata that connects datasets, transforms, artifacts, and decisions.

## Workspace layout (standard)

Workspaces use a flat, predictable structure:

- `raw/` — imported source data (snapshots by default)
- `data/` — cleaned/merged datasets
- `transforms/` — scripts/snippets that produce `data/` and other artifacts
- `plots/` — saved plot definitions and rendered previews
- `results/` — derived outputs (tables, exports, intermediate computations)
- `reports/` — generated reports (initially notebooks)
- `.codexdatalab/` — workspace metadata (JSON) and app state

## Data ingestion (rules)

- **Copy by default:** Imports copy files into `raw/` to keep workspaces self-contained.
- **Size-aware:** If a file exceeds a configurable max-copy size, prompt: **Link / Copy anyway / Cancel** (support `--force-copy`).
- **Global settings:** Stored under `~/.codexdatalab/` (e.g., max-copy size, default behaviors).
- **Provenance always recorded:** Original location/URL, timestamps, and content hashes are stored in `.codexdatalab/`.

## Metadata & provenance (JSON)

Workspace state is stored as JSON files under `.codexdatalab/` (names may evolve, but intent is stable):

- `manifest.json` — datasets present in the workspace and where they came from
- `lineage.json` — relationships (raw→cleaned, code→artifact, plot→dataset, etc.)
- `qa.json` — structured record of questions answered + evidence/links to data/artifacts
- `plots.json` — plot definitions (what/why) and versions

## UI expectations (Textual)

- **Workspace browser:** view/select files, prioritizing cleaned/merged datasets.
- **Table preview:** scrollable table view for selected dataset.
- **Optional stats tab:** toggleable panel showing:
  - numeric: min/max/mean (and room to expand later)
  - categorical/text: unique count + value counts
- **Plotting panel:** terminal plots (braille) with sensible defaults; supports scatter/line/bar/hist to start.
- **Chat panel:** user asks questions; Codex can run tools/transforms and create artifacts.

## Data engine (tabular)

- Focus on **tabular** data first.
- Use **Polars** as the primary dataframe engine for speed and simplicity.
- Provide small “quick analysis” tools for common tasks (describe, groupby counts, correlations, missingness).

## Plots and analysis as saved artifacts

- Users can create plots manually; plots are stored as reusable definitions in `plots/`.
- Codex can also create/edit plots and must record **what** was created and **why**.
- Artifacts are versioned (new version vs edit-in-place depends on user intent) and always reference input datasets.

## Computed columns (“recipes”)

Support lightweight computed columns where the user (or Codex) defines a small expression/lambda:

- Stored as a “recipe” snippet under `transforms/` (or a dedicated recipes file).
- Treat computed columns as derived and re-generatable; keep the source snippet alongside metadata.

## Versioning & rollback (workspace git)

- `codexdatalab init` initializes a git repo inside the workspace (if needed).
- Raw data is gitignored by default; metadata/transforms/plots/results are committed to support rollback.
- The app can later expose simple “undo/restore” interactions powered by git history.

## Reporting (export)

The TUI tables/plots are fast previews. When requested, the app generates a **Jupyter notebook** in `reports/` that:

- Replays key transforms and snippets,
- Adds narrative Markdown cells derived from the chat context,
- Produces publication-quality plots (e.g., matplotlib) and summaries,
- Preserves links back to workspace artifacts and raw data.

## Longer-term ideas

- Multi-project workspaces with cross-linked data.
- Web dataset search + download (curated sources) with explicit provenance and user confirmation.
- Simple interactive TUI widgets (filters/sliders/dropdowns) for exploration.

