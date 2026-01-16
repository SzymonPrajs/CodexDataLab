const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { WebSocketServer } = require("ws");

function resolveFirst(candidates) {
  for (const candidate of candidates) {
    try {
      return require.resolve(candidate);
    } catch {
      // ignore
    }
  }
  throw new Error(`Unable to resolve any of: ${candidates.join(", ")}`);
}

function getVendorPaths() {
  const xtermCss = resolveFirst([
    "@xterm/xterm/css/xterm.css",
    "@xterm/xterm/dist/xterm.css",
    "xterm/css/xterm.css",
    "xterm/dist/xterm.css",
  ]);
  const xtermJs = resolveFirst([
    "@xterm/xterm/lib/xterm.js",
    "@xterm/xterm/dist/xterm.js",
    "xterm/lib/xterm.js",
    "xterm/dist/xterm.js",
  ]);
  return { xtermCss, xtermJs };
}

function contentTypeFor(filePath) {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

function serveFile(res, filePath) {
  try {
    const data = fs.readFileSync(filePath);
    res.writeHead(200, {
      "Content-Type": contentTypeFor(filePath),
      "Cache-Control": "no-store",
    });
    res.end(data);
  } catch (error) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(String(error));
  }
}

function attachPtyHandlers(ptyProcess, onData, onExit) {
  if (typeof ptyProcess.onData === "function") {
    const disposable = ptyProcess.onData(onData);
    if (typeof ptyProcess.onExit === "function") ptyProcess.onExit(onExit);
    return () => {
      if (disposable && typeof disposable.dispose === "function") disposable.dispose();
    };
  }
  ptyProcess.on("data", onData);
  ptyProcess.on("exit", onExit);
  return () => {
    ptyProcess.off("data", onData);
    ptyProcess.off("exit", onExit);
  };
}

async function startServer({ assetsDir, host, port, wsPath, ptyProcess }) {
  const vendor = getVendorPaths();
  const indexPath = path.join(assetsDir, "index.html");

  const clients = new Set();
  let buffered = "";

  const server = http.createServer((req, res) => {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

    if (url.pathname === "/") return serveFile(res, indexPath);
    if (url.pathname === "/vendor/xterm.css") return serveFile(res, vendor.xtermCss);
    if (url.pathname === "/vendor/xterm.js") return serveFile(res, vendor.xtermJs);

    const assetPrefix = "/assets/";
    if (url.pathname.startsWith(assetPrefix)) {
      const rel = url.pathname.slice(assetPrefix.length);
      const safeRel = rel.replace(/^(\.\.(\/|\\|$))+/, "");
      return serveFile(res, path.join(assetsDir, safeRel));
    }

    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not found");
  });

  const wss = new WebSocketServer({ server, path: wsPath });
  wss.on("connection", (ws) => {
    clients.add(ws);

    if (buffered) {
      ws.send(JSON.stringify({ type: "output", data: buffered }));
      buffered = "";
    }

    ws.on("message", (raw) => {
      try {
        const message = JSON.parse(String(raw));
        if (message.type === "input" && typeof message.data === "string") {
          ptyProcess.write(message.data);
        }
        if (message.type === "resize") {
          const cols = Number(message.cols);
          const rows = Number(message.rows);
          if (Number.isFinite(cols) && Number.isFinite(rows) && typeof ptyProcess.resize === "function") {
            ptyProcess.resize(cols, rows);
          }
        }
      } catch {
        // ignore
      }
    });

    ws.on("close", () => clients.delete(ws));
  });

  const disposePty = attachPtyHandlers(
    ptyProcess,
    (data) => {
      const payload = JSON.stringify({ type: "output", data });
      if (clients.size === 0) {
        buffered += data;
        return;
      }
      for (const ws of clients) ws.send(payload);
    },
    (event) => {
      const code = typeof event?.exitCode === "number" ? event.exitCode : 0;
      const payload = JSON.stringify({ type: "exit", code });
      for (const ws of clients) ws.send(payload);
    },
  );

  await new Promise((resolve) => server.listen(port, host, resolve));
  const address = server.address();
  const actualPort = typeof address === "object" && address ? address.port : port;

  return {
    url: `http://${host}:${actualPort}`,
    port: actualPort,
    close: async () => {
      disposePty();
      for (const ws of clients) ws.close();
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

module.exports = { startServer };
