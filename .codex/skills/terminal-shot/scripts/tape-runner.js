const fs = require("node:fs");
const path = require("node:path");
const YAML = require("yaml");

function loadTape(filePath) {
  const data = fs.readFileSync(filePath, "utf8");
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".yaml" || ext === ".yml") return YAML.parse(data);
  return JSON.parse(data);
}

const KEY_ALIASES = {
  tab: "Tab",
  enter: "Enter",
  return: "Enter",
  esc: "Escape",
  escape: "Escape",
  up: "ArrowUp",
  down: "ArrowDown",
  left: "ArrowLeft",
  right: "ArrowRight",
  backspace: "Backspace",
  delete: "Delete",
  del: "Delete",
  space: "Space",
  home: "Home",
  end: "End",
  pageup: "PageUp",
  pagedown: "PageDown",
};

const MODIFIER_ALIASES = {
  ctrl: "Control",
  control: "Control",
  alt: "Alt",
  option: "Alt",
  shift: "Shift",
  meta: "Meta",
  cmd: "Meta",
  command: "Meta",
};

function toPlaywrightKey(combo) {
  const parts = String(combo)
    .split("+")
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length === 0) throw new Error(`Invalid key combo: ${combo}`);

  const rawKey = parts.pop().toLowerCase();
  const key = KEY_ALIASES[rawKey] || (rawKey.length === 1 ? rawKey.toUpperCase() : rawKey);
  const modifiers = parts.map((p) => {
    const mod = MODIFIER_ALIASES[p.toLowerCase()];
    if (!mod) throw new Error(`Unknown modifier: ${p}`);
    return mod;
  });

  return [...modifiers, key].join("+");
}

async function runTape(page, tapeSteps, { onScreenshot }) {
  if (!Array.isArray(tapeSteps)) throw new Error("Tape must be an array");

  for (const step of tapeSteps) {
    if (!step || typeof step !== "object") continue;

    if (typeof step.wait === "number") {
      await page.waitForTimeout(step.wait);
      continue;
    }

    if (typeof step.key === "string") {
      await page.keyboard.press(toPlaywrightKey(step.key));
      continue;
    }

    if (typeof step.type === "string") {
      await page.keyboard.type(step.type);
      continue;
    }

    if (step.resize && typeof step.resize === "object") {
      const cols = Number(step.resize.cols);
      const rows = Number(step.resize.rows);
      if (!Number.isFinite(cols) || !Number.isFinite(rows)) throw new Error("resize.cols/resize.rows must be numbers");
      await page.evaluate(
        ({ cols, rows }) => window.__terminalShotResize && window.__terminalShotResize(cols, rows),
        { cols, rows },
      );
      continue;
    }

    if (typeof step.screenshot === "string") {
      await onScreenshot(step.screenshot);
      continue;
    }
  }
}

module.exports = { loadTape, runTape, toPlaywrightKey };

