"""File handling: extraction, metadata, layer detection, zip safe-extraction."""
import os
import re
import zipfile
from pathlib import Path
from typing import Callable, Dict

TEXT_EXTS = {".log", ".txt", ".json", ".xml", ".csv", ".har", ".md", ".yaml", ".yml", ".ini", ".conf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif"}

LAYER_HINTS = [
    ("web_tier", [r"webadaptor", r"\biis\b", r"nginx", r"apache", r"\.har$", r"reverse[-_ ]?proxy"]),
    ("portal", [r"portal", r"sharing/rest", r"\bportal\.log"]),
    ("server", [r"\barcgis\s*server\b", r"server\.log", r"arcsoc", r"\bgp\b", r"\bsoc\b"]),
    ("datastore", [r"datastore", r"data[-_ ]?store", r"replication"]),
    ("client_pro", [r"\bpro[-_ ]?crash", r"errorreports?", r"diagnostic\s*monitor", r"\barcgispro\b", r"\.dmp$"]),
    ("browser", [r"\.har$", r"console", r"chrome", r"firefox", r"edge"]),
    ("os_system", [r"\.evtx$", r"event\s*viewer", r"procmon", r"system\.log"]),
]


def detect_layer(filename: str, sample_text: str = "") -> str:
    name = (filename or "").lower()
    text = (sample_text or "").lower()
    for layer, patterns in LAYER_HINTS:
        for p in patterns:
            if re.search(p, name) or re.search(p, text[:2000]):
                return layer
    return "unknown"


def _read_as_text(path: str, max_bytes: int) -> str:
    with open(path, "rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="replace")


def _placeholder_image(path: str) -> str:
    p = Path(path)
    return f"(binary image file: {p.name}, {os.path.getsize(path)} bytes — visual evidence)"


def _placeholder_pdf(path: str) -> str:
    return f"(PDF file: {Path(path).name} — not parsed in MVP; please extract text externally if critical)"


def _placeholder_dmp(path: str) -> str:
    p = Path(path)
    return f"(Windows process dump: {p.name}, {os.path.getsize(path)} bytes — analyze externally with WinDbg)"


def _placeholder_evtx(path: str) -> str:
    return f"(Windows event log: {Path(path).name} — convert to .txt/.csv with wevtutil for full analysis)"


def _placeholder_zip(path: str) -> str:
    return f"(Zip archive: {Path(path).name} — extract via /api/cases/{{id}}/files/{{fid}}/extract)"


# Dispatch table: extension → handler. Keeps extract_text() flat and easy to extend.
_HANDLERS: Dict[str, Callable[[str], str]] = {
    ".pdf": _placeholder_pdf,
    ".dmp": _placeholder_dmp,
    ".evtx": _placeholder_evtx,
    ".zip": _placeholder_zip,
}


def extract_text(path: str, max_bytes: int = 200_000) -> str:
    """Best-effort text extraction. Truncates to max_bytes."""
    ext = Path(path).suffix.lower()
    try:
        if ext in TEXT_EXTS or ext == "":
            return _read_as_text(path, max_bytes)
        if ext in IMAGE_EXTS:
            return _placeholder_image(path)
        handler = _HANDLERS.get(ext)
        if handler is not None:
            return handler(path)
        # unknown extension: try as text (last-resort)
        return _read_as_text(path, max_bytes)
    except Exception as e:
        return f"(text extraction failed: {e})"


def safe_extract_zip(zip_path: str, dest_dir: str) -> list:
    """Extract zip, blocking path traversal. Returns list of extracted member paths."""
    extracted = []
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            name = member.filename
            if name.endswith("/"):
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest) + os.sep) and str(target) != str(dest):
                continue  # skip suspicious
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as src, open(target, "wb") as out:
                out.write(src.read())
            extracted.append(str(target))
    return extracted
