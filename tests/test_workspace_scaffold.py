from __future__ import annotations

from pathlib import Path

from codexdatalab.workspace_scaffold import create_workspace_skeleton, populate_raw_from_fixtures


def test_create_workspace_skeleton(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws"
    create_workspace_skeleton(workspace_root)

    assert (workspace_root / "raw").is_dir()
    assert (workspace_root / "data").is_dir()
    assert (workspace_root / "transforms").is_dir()
    assert (workspace_root / "plots").is_dir()
    assert (workspace_root / "results").is_dir()
    assert (workspace_root / "reports").is_dir()
    assert (workspace_root / "projects").is_dir()
    assert (workspace_root / ".codexdatalab").is_dir()

    assert (workspace_root / ".codexdatalab" / "manifest.json").is_file()
    assert (workspace_root / ".codexdatalab" / "lineage.json").is_file()
    assert (workspace_root / ".codexdatalab" / "plots.json").is_file()
    assert (workspace_root / ".codexdatalab" / "qa.json").is_file()
    assert (workspace_root / ".codexdatalab" / "state.json").is_file()


def test_populate_raw_from_fixtures(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws"
    create_workspace_skeleton(workspace_root)

    fixture_1 = tmp_path / "people.csv"
    fixture_1.write_text("person_id,name\n1,Alice\n")
    fixture_2 = tmp_path / "orders.csv"
    fixture_2.write_text("order_id,person_id\n100,1\n")

    populate_raw_from_fixtures(workspace_root, [fixture_1, fixture_2])

    assert (workspace_root / "raw" / "people.csv").is_file()
    assert (workspace_root / "raw" / "orders.csv").is_file()
