import ftplib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ftp_compare
from config import Settings
from hash_db import RemoteFact


def fake_ftp(
    listings: dict[str, list[tuple[str, dict[str, str]]]],
    failures: dict[str, Exception] | None = None,
) -> MagicMock:
    ftp = MagicMock(spec=ftplib.FTP)

    def mlsd(path: str, facts: list[str]) -> list[tuple[str, dict[str, str]]]:
        assert facts == ftp_compare.MLSD_FACTS
        if failures and path in failures:
            raise failures[path]
        return listings[path]

    ftp.mlsd.side_effect = mlsd
    return ftp


def test_compare_tree_reports_differences_and_ascii_equivalence(tmp_path: Path) -> None:
    (tmp_path / "b.bin").write_bytes(b"tiny")
    (tmp_path / "crlf.txt").write_bytes(b"one\r\ntwo\r\n")
    (tmp_path / "larger.txt").write_bytes(b"not crlf")
    (tmp_path / "same.txt").write_bytes(b"same")
    ftp = fake_ftp(
        {
            "/root": [
                ("a.txt", {"type": "file", "size": "10"}),
                ("b.bin", {"type": "file", "size": "10"}),
                ("crlf.txt", {"type": "file", "size": "8"}),
                ("larger.txt", {"type": "file", "size": "3"}),
                ("same.txt", {"type": "file", "size": "4"}),
                (".", {"type": "cdir"}),
                ("..", {"type": "pdir"}),
            ]
        }
    )

    with (tmp_path / "report.tsv").open("w", encoding="utf-8", buffering=1) as out:
        stats = ftp_compare.compare_tree(ftp, "/root/", str(tmp_path), out)

    lines = (tmp_path / "report.tsv").read_text().splitlines()
    assert lines[:-1] == [
        "MISSING\t/root/a.txt\t10",
        "SIZE\t/root/b.bin\tremote=10 local=4",
        "SIZE\t/root/larger.txt\tremote=3 local=8",
    ]
    assert lines[-1] == "DONE: 1 dirs, 5 remote files, 3 problems"
    assert stats.dirs == 1 and stats.files == 5 and stats.problems == 3
    ftp.mlsd.assert_called_once_with("/root", facts=ftp_compare.MLSD_FACTS)
    for operation in ("storbinary", "retrbinary", "delete", "mkd", "rmd"):
        getattr(ftp, operation).assert_not_called()


def test_compare_tree_walks_nested_dirs_and_skips_ignored(tmp_path: Path) -> None:
    ftp = fake_ftp(
        {
            "/root": [("sub", {"type": "dir"}), ("skip", {"type": "dir"})],
            "/root/sub": [("missing", {"type": "file", "size": "1"})],
        }
    )
    (tmp_path / "sub").mkdir()
    from io import StringIO

    out = StringIO()
    stats = ftp_compare.compare_tree(ftp, "/root", str(tmp_path), out, ("skip",))
    assert "MISSING\t/root/sub/missing\t1" in out.getvalue()
    assert stats.dirs == 2 and stats.files == 1
    assert [call.args[0] for call in ftp.mlsd.call_args_list] == ["/root", "/root/sub"]


def test_compare_tree_lists_failures_continues_and_tags_virus(tmp_path: Path) -> None:
    ftp = fake_ftp(
        {"/root": [("sub", {"type": "dir"}), ("VIRUS_php_shell_x.php", {"type": "file", "size": "12"})]},
        {"/root/sub": ftplib.error_perm("550 denied")},
    )
    from io import StringIO

    out = StringIO()
    stats = ftp_compare.compare_tree(ftp, "/root", str(tmp_path), out)
    assert "VIRUS\t/root/VIRUS_php_shell_x.php\t12" in out.getvalue()
    assert "LISTFAIL\t/root/sub\t550 denied" in out.getvalue()
    assert stats.dirs == 2 and stats.files == 1 and stats.problems == 2


def test_compare_tree_progress_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ftp_compare, "PROGRESS_EVERY_DIRS", 1)
    ftp = fake_ftp({"/root": []})
    with caplog.at_level(logging.INFO, logger="ftp_compare"), (tmp_path / "out").open("w") as out:
        ftp_compare.compare_tree(ftp, "/root", str(tmp_path), out)
    assert "1 dirs done, 0 queued, 0 files, 0 problems" in caplog.text


@pytest.mark.parametrize("local_exists,output_parent_exists", [(False, True), (True, False)])
def test_run_compare_fails_before_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_exists: bool, output_parent_exists: bool
) -> None:
    local = tmp_path / "local"
    if local_exists:
        local.mkdir()
    output_parent = tmp_path / "outdir"
    if output_parent_exists:
        output_parent.mkdir()
    settings = Settings((str(local),), "/root", "host", "user", "pass")
    connect = MagicMock(side_effect=AssertionError("should not connect"))
    monkeypatch.setattr(ftp_compare, "connect_ftp", connect)
    with pytest.raises(SystemExit) as error:
        ftp_compare.run_compare(settings, str(output_parent / "report.tsv"))
    assert error.value.code == 1
    connect.assert_not_called()


def test_list_remote_facts_walks_tree_relative_to_root() -> None:
    ftp = fake_ftp(
        {
            "/root": [
                ("a.php", {"type": "file", "size": "5", "modify": "20261024072300"}),
                ("sub", {"type": "dir"}),
                ("skip", {"type": "dir"}),
                (".", {"type": "cdir"}),
            ],
            "/root/sub": [("b.php", {"type": "file", "size": "7"})],
        }
    )
    facts = ftp_compare.list_remote_facts(ftp, "/root/", ("skip",))
    assert facts == {"a.php": RemoteFact(5, "20261024072300"), "sub/b.php": RemoteFact(7, "")}


def test_list_remote_facts_only_lists_given_subdirs() -> None:
    ftp = fake_ftp(
        {
            "/root": [("a.php", {"type": "file", "size": "5"}), ("sub", {"type": "dir"})],
            "/root/sub": [("b.php", {"type": "file", "size": "7"})],
        }
    )
    facts = ftp_compare.list_remote_facts(ftp, "/root", subdirs={"sub"})
    assert facts == {"sub/b.php": RemoteFact(7, "")}
    assert [call.args[0] for call in ftp.mlsd.call_args_list] == ["/root/sub"]


def test_list_remote_facts_skips_unlistable_dir() -> None:
    ftp = fake_ftp(
        {"/root": [("sub", {"type": "dir"}), ("a.php", {"type": "file", "size": "5"})]},
        {"/root/sub": ftplib.error_perm("550 denied")},
    )
    assert ftp_compare.list_remote_facts(ftp, "/root") == {"a.php": RemoteFact(5, "")}
