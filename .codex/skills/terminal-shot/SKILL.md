---
name: terminal-shot
description: Capture PNG screenshots of terminal TUIs (Textual) by running an app in a PTY, mirroring it to xterm.js in a browser, and driving scripted input via Playwright.
---

# Terminal Shot (Local)

Creates PNG screenshots of a real terminal session rendered in a browser (xterm.js). Intended for local development and visual regression snapshots.

## Quick start

From the repo root:

```bash
cd .codex/skills/terminal-shot
npm install
npx playwright install
node scripts/terminal-shot.js --cmd "python -m codexdatalab" --tape tapes/demo.yaml
```

Outputs:

- `/tmp/tui-shot/frames/*.png`
- `/tmp/tui-shot/last.png`

## Config

Defaults are in `config.json` (`cols`, `rows`, `viewport`, `outDir`). CLI flags override config values.

## Tape format

A tape is a YAML/JSON array of steps. Supported steps:

- `{ wait: <ms> }`
- `{ key: "<combo>" }` (e.g. `ctrl+g`, `tab`, `down`, `enter`)
- `{ type: "<text>" }`
- `{ screenshot: "<filename>.png" }`
- `{ resize: { cols: <n>, rows: <n> } }`

## Notes

- Uses the default xterm theme (no custom colors are applied).
- The spawned command runs with `cwd` defaulting to the repo root (override with `--cwd`).
