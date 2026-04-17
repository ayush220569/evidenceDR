"""File handling: extraction, metadata, layer detection, zip safe-extraction."""
import os
import re
import zipfile
from pathlib import Path

TEXT_EXTS = {".log", ".txt", ".json", ".xml", ".csv", ".har", ".md", ".yaml", ".yml", ".ini", ".conf"}
BINARY_EXTS = {".dmp", ".evtx", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip"}

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


def extract_text(path: str, max_bytes: int = 200_000) -> str:
    """Best-effort text extraction. Truncates to max_bytes."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in TEXT_EXTS or ext == "":
            with open(path, "rb") as f:
                data = f.read(max_bytes)
            return data.decode("utf-8", errors="replace")
        if ext in {".png", ".jpg", ".jpeg", ".gif"}:
            return f"(binary image file: {p.name}, {os.path.getsize(path)} bytes — visual evidence)"
        if ext == ".pdf":
            return f"(PDF file: {p.name} — not parsed in MVP; please extract text externally if critical)"
        if ext == ".dmp":
            return f"(Windows process dump: {p.name}, {os.path.getsize(path)} bytes — analyze externally with WinDbg)"
        if ext == ".evtx":
            return f"(Windows event log: {p.name} — convert to .txt/.csv with wevtutil for full analysis)"
        if ext == ".zip":
            return f"(Zip archive: {p.name} — extract via /api/cases/{{id}}/files/{{fid}}/extract)"
        # fallback: try as text
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"(text extraction failed: {e})"


def safe_extract_zip(zip_path: str, dest_dir: str) -> list:
    """Extract zip, blocking path traversal. Returns list of extracted member paths."""
    extracted = []
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            # Block absolute paths and traversal
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
