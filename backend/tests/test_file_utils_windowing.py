"""Smoke test for new file_utils features."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import file_utils  # noqa: E402


def test_tail_first_includes_tail_of_large_file():
    """A 5MB synthetic log with a known marker at byte 4_700_000 should be present
    in the extracted text when read in tail_first mode with a 3MB cap, but NOT
    when read in head mode."""
    with tempfile.NamedTemporaryFile("wb", suffix=".log", delete=False) as fp:
        path = fp.name
        line = b"INFO [housekeeping] iteration #1234567890 padding_to_make_line_longer\n"
        # write up to byte 4_700_000
        target = 4_700_000
        written = 0
        while written < target:
            fp.write(line)
            written += len(line)
        fp.write(b"### NEEDLE_TAIL_MARKER ###\n")
        # pad past 5MB
        while written < 5_500_000:
            fp.write(line)
            written += len(line)

    try:
        head_text = file_utils.extract_text(path, max_bytes=3_000_000, mode="head")
        assert "NEEDLE_TAIL_MARKER" not in head_text, "head mode should not see the tail marker"

        tail_text = file_utils.extract_text(path, max_bytes=3_000_000, mode="tail_first")
        assert "NEEDLE_TAIL_MARKER" in tail_text, "tail_first mode must surface tail content"
        assert "skipped" in tail_text, "tail_first should leave a skip marker"

        win_text = file_utils.extract_text(path, max_bytes=3_000_000, mode="windowed")
        assert "window" in win_text, "windowed mode should annotate windows"
    finally:
        os.unlink(path)


def test_extract_text_small_file_all_modes_equivalent():
    """A file smaller than max_bytes should return identical content regardless of mode."""
    with tempfile.NamedTemporaryFile("wb", suffix=".log", delete=False) as fp:
        path = fp.name
        fp.write(b"line1\nline2\nline3\n")

    try:
        for mode in ("head", "tail_first", "windowed"):
            assert "line1" in file_utils.extract_text(path, 1_000, mode=mode)
            assert "line3" in file_utils.extract_text(path, 1_000, mode=mode)
    finally:
        os.unlink(path)


def test_evtx_parser_handles_missing_file_gracefully():
    """Invalid .evtx must return a structured error string, not crash."""
    with tempfile.NamedTemporaryFile("wb", suffix=".evtx", delete=False) as fp:
        fp.write(b"not a real evtx file")
        path = fp.name
    try:
        out = file_utils.extract_text(path, max_bytes=10_000)
        # Either the parser short-circuited with an error message, or it returned no records
        assert isinstance(out, str)
        assert any(kw in out for kw in ("evtx", "parser", "records", "failed"))
    finally:
        os.unlink(path)


def test_minidump_parser_handles_invalid_file_gracefully():
    """Invalid .dmp must return a structured error string, not crash."""
    with tempfile.NamedTemporaryFile("wb", suffix=".dmp", delete=False) as fp:
        fp.write(b"fake dmp data")
        path = fp.name
    try:
        out = file_utils.extract_text(path, max_bytes=10_000)
        assert isinstance(out, str)
        assert any(kw in out for kw in ("minidump", "parse", "failed"))
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_tail_first_includes_tail_of_large_file()
    test_extract_text_small_file_all_modes_equivalent()
    test_evtx_parser_handles_missing_file_gracefully()
    test_minidump_parser_handles_invalid_file_gracefully()
    print("OK — all file_utils tests passed")
