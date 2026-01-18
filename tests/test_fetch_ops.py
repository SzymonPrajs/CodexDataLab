from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from codexdatalab.fetch_ops import fetch_url
from codexdatalab.settings import Settings
from codexdatalab.workspace import init_workspace


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        return None


def _start_server(directory: Path) -> ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_fetch_url_downloads(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "sample.csv"
    csv_path.write_text("a,b\n1,2\n")

    server = _start_server(data_dir)
    try:
        port = server.server_address[1]
        url = f"http://127.0.0.1:{port}/sample.csv"
        settings = Settings(
            max_copy_bytes=1024 * 1024,
            offline_mode=False,
            prompt_on_large_file=True,
            allowed_domains=["127.0.0.1"],
        )
        workspace = init_workspace(tmp_path / "ws", settings, git_enabled=False)

        result = fetch_url(workspace, url)
        manifest = workspace.load_manifest()
        dataset = manifest["datasets"][result.dataset_id]

        assert (workspace.root / dataset["path"]).is_file()
        assert any(source["source"] == url for source in dataset["sources"])
        assert any(source["import_mode"] == "download" for source in dataset["sources"])
        assert result.receipt_path.is_file()
    finally:
        server.shutdown()


def test_fetch_url_blocks_disallowed_domain(tmp_path: Path) -> None:
    settings = Settings(
        max_copy_bytes=1024,
        offline_mode=False,
        prompt_on_large_file=True,
        allowed_domains=["example.com"],
    )
    workspace = init_workspace(tmp_path / "ws", settings, git_enabled=False)

    with pytest.raises(ValueError):
        fetch_url(workspace, "https://not-allowed.test/data.csv")
