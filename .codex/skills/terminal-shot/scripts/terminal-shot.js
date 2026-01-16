const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const pty = require("@homebridge/node-pty-prebuilt-multiarch");
const yargs = require("yargs/yargs");
const { hideBin } = require("yargs/helpers");

const { startServer } = require("./server");
const { loadTape, runTape } = require("./tape-runner");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function mkdirp(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeLastPng(outDir, screenshotPath) {
  const lastPath = path.join(outDir, "last.png");
  fs.copyFileSync(screenshotPath, lastPath);
}

async function main() {
  const scriptDir = __dirname;
  const skillRoot = path.resolve(scriptDir, "..");
  const repoRoot = path.resolve(skillRoot, "..", "..", "..");

  const argv = yargs(hideBin(process.argv))
    .option("config", { type: "string", default: path.join(skillRoot, "config.json") })
    .option("cmd", { type: "string", default: "python -m codexdatalab" })
    .option("cwd", { type: "string", default: repoRoot })
    .option("tape", { type: "string" })
    .option("cols", { type: "number" })
    .option("rows", { type: "number" })
    .option("outDir", { type: "string" })
    .option("viewportWidth", { type: "number" })
    .option("viewportHeight", { type: "number" })
    .option("headless", { type: "boolean" })
    .option("headed", { type: "boolean" })
    .option("host", { type: "string", default: "127.0.0.1" })
    .option("port", { type: "number", default: 0 })
    .help()
    .parse();

  const config = readJson(argv.config);

  const cols = Number(argv.cols ?? config.cols ?? 120);
  const rows = Number(argv.rows ?? config.rows ?? 34);
  const outDir = argv.outDir ?? config.outDir ?? "/tmp/tui-shot";
  const wsPath = config.wsPath || "/ws";

  const viewport = {
    width: Number(argv.viewportWidth ?? config.viewport?.width ?? 1512),
    height: Number(argv.viewportHeight ?? config.viewport?.height ?? 982),
  };

  const headless =
    argv.headed === true
      ? false
      : argv.headless === true || argv.headless === false
        ? argv.headless
        : config.headless ?? true;

  const framesDir = path.join(outDir, "frames");
  mkdirp(framesDir);

  const shell = process.env.SHELL || (process.platform === "win32" ? "powershell.exe" : "/bin/bash");
  const shellArgs = process.platform === "win32" ? ["-NoLogo", "-Command", argv.cmd] : ["-lc", argv.cmd];

  const ptyProcess = pty.spawn(shell, shellArgs, {
    name: "xterm-256color",
    cols,
    rows,
    cwd: argv.cwd,
    env: { ...process.env, TERM: "xterm-256color" },
  });

  const assetsDir = path.join(skillRoot, "assets");

  const server = await startServer({
    assetsDir,
    host: argv.host,
    port: argv.port,
    wsPath,
    ptyProcess,
  });

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();

  const tapeSteps = argv.tape ? loadTape(argv.tape) : [{ wait: 500 }, { screenshot: "startup.png" }];

  try {
    await page.goto(
      `${server.url}/?cols=${encodeURIComponent(String(cols))}&rows=${encodeURIComponent(String(rows))}&wsPath=${encodeURIComponent(wsPath)}`,
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForFunction(() => window.__terminalShotReady === true);

    const terminal = page.locator("#terminal");
    await runTape(page, tapeSteps, {
      onScreenshot: async (filename) => {
        const safeName = path.basename(filename);
        const target = path.join(framesDir, safeName);
        await terminal.screenshot({ path: target });
        writeLastPng(outDir, target);
      },
    });
  } finally {
    await browser.close();
    await server.close();
    try {
      ptyProcess.kill();
    } catch {
      // ignore
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
