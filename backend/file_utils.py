"""File handling: extraction, metadata, layer detection, zip safe-extraction.

Text extraction supports three read modes for large files:
  - head        : read the first max_bytes (fast, but loses tail where errors often live)
  - tail_first  : prepend tail to head (best default for ArcGIS logs where exceptions
                  typically appear near shutdown / end-of-window)
  - windowed    : sample head + middle + tail (best for very long-running services
                  where evidence may be anywhere in the run)

EVTX (.evtx) and DMP (.dmp) handlers are real parsers now, not placeholders.
"""
import io
import os
import re
import zipfile
from pathlib import Path
from typing import Callable, Dict, Optional

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


# -------- text reads with windowing --------
def _read_head(path: str, max_bytes: int) -> str:
    with open(path, "rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="replace")


def _read_tail_first(path: str, max_bytes: int) -> str:
    """Tail-biased read: 65% tail (placed FIRST in the returned string) + 35% head.

    Why tail-first in the *string*: when the chunk cap kicks in, the chunker keeps
    the first N chunks and drops the rest. Putting tail bytes first guarantees that
    near-tail content (where errors usually live in ArcGIS logs) is always indexed
    even when max_chunks_per_file truncates the run.

    Includes a visible marker between the two slices so the LLM can tell the file
    was sampled rather than streamed in order.
    """
    size = os.path.getsize(path)
    if size <= max_bytes:
        return _read_head(path, max_bytes)
    head_bytes = int(max_bytes * 0.35)
    tail_bytes = max_bytes - head_bytes
    with open(path, "rb") as f:
        head = f.read(head_bytes)
        f.seek(max(0, size - tail_bytes))
        tail = f.read(tail_bytes)
    skipped = size - head_bytes - tail_bytes
    head_marker = (
        f"\n\n[... evidencepilot: head slice ({head_bytes:,} bytes) of "
        f"{Path(path).name} ({size:,} total) -- head/tail window mode ...]\n\n"
    ).encode()
    tail_marker = (
        f"[... evidencepilot: tail slice ({tail_bytes:,} bytes), "
        f"skipped {skipped:,} bytes in middle -- appears FIRST so it survives the chunk cap ...]\n\n"
    ).encode()
    return (tail_marker + tail + head_marker + head).decode("utf-8", errors="replace")


def _read_windowed(path: str, max_bytes: int, windows: int = 4) -> str:
    """Sample N evenly-spaced windows across the whole file.

    Use this for very long-running service logs where errors may surface in any
    middle hour. windows=4 gives a 25%-of-cap slice from each quartile.
    """
    size = os.path.getsize(path)
    if size <= max_bytes:
        return _read_head(path, max_bytes)
    per_window = max_bytes // max(1, windows)
    step = size // max(1, windows)
    parts: list = []
    with open(path, "rb") as f:
        for i in range(windows):
            offset = min(size - per_window, i * step)
            f.seek(max(0, offset))
            data = f.read(per_window)
            marker = (
                f"\n\n[... evidencepilot: window {i+1}/{windows} starting at byte "
                f"{offset:,} of {size:,} ({Path(path).name}) ...]\n\n"
            ).encode()
            parts.append(marker + data)
    return b"".join(parts).decode("utf-8", errors="replace")


# -------- EVTX (Windows Event Log) --------
def _parse_evtx(path: str, max_bytes: int) -> str:
    """Convert .evtx binary records into a chronological text stream the LLM can read.

    We extract: timestamp, event id, level (info/warn/error/critical), provider name,
    channel, and the rendered event message (or a substring of the raw XML if rendering
    fails). Stop once we've produced max_bytes of output so we respect the index cap.
    """
    try:
        from Evtx.Evtx import Evtx  # noqa: WPS433 -- lazy import (heavy module)
    except Exception as e:
        return f"(evtx parser unavailable: {e})"

    buf = io.StringIO()
    written = 0

    # Level numeric -> label per Microsoft Event Log convention
    level_map = {1: "CRITICAL", 2: "ERROR", 3: "WARN", 4: "INFO", 5: "VERBOSE"}

    try:
        with Evtx(path) as log:
            for record in log.records():
                try:
                    x = record.xml()
                except Exception:
                    continue
                # Cheap field extraction with regex -- avoids full XML parse cost
                ts_m = re.search(r'TimeCreated SystemTime="([^"]+)"', x)
                eid_m = re.search(r"<EventID[^>]*>(\d+)</EventID>", x)
                lvl_m = re.search(r"<Level>(\d+)</Level>", x)
                prov_m = re.search(r'Provider Name="([^"]+)"', x)
                chan_m = re.search(r"<Channel>([^<]+)</Channel>", x)
                msg_parts = re.findall(r"<Data[^>]*>([^<]*)</Data>", x)
                lvl_num = int(lvl_m.group(1)) if lvl_m else 4
                line = (
                    f"{ts_m.group(1) if ts_m else '?'} "
                    f"{level_map.get(lvl_num, 'LEVEL'+str(lvl_num))} "
                    f"[{prov_m.group(1) if prov_m else '?'}/{chan_m.group(1) if chan_m else '?'}] "
                    f"EventID={eid_m.group(1) if eid_m else '?'} "
                    f"msg=\"{' | '.join(s.strip() for s in msg_parts if s.strip())[:500]}\"\n"
                )
                # respect budget
                if written + len(line) > max_bytes:
                    buf.write(f"\n[... evidencepilot: evtx truncated at {written:,} bytes of output ...]\n")
                    break
                buf.write(line)
                written += len(line)
    except Exception as e:
        buf.write(f"\n(evtx read failed: {e})\n")

    return buf.getvalue() or "(evtx contained no readable records)"


# -------- Minidump (Pro / Server crash) --------
def _parse_minidump(path: str, max_bytes: int) -> str:
    """Extract crash metadata from a Windows minidump.

    Symbol-less, so we can't unwind stacks fully, but we can surface:
      - exception code + faulting thread id + faulting instruction RIP
      - loaded module list (modules near the faulting address are the prime suspect)
      - OS / CPU / process metadata
    That's enough for the LLM to triage which Pro / Server module crashed.
    """
    try:
        from minidump.minidumpfile import MinidumpFile  # noqa: WPS433
    except Exception as e:
        return f"(minidump parser unavailable: {e})"

    buf = io.StringIO()
    try:
        md = MinidumpFile.parse(path)
    except Exception as e:
        return f"(minidump parse failed: {e})"

    sysinfo = getattr(md, "sysinfo", None)
    if sysinfo:
        buf.write(
            f"OS: ProductType={getattr(sysinfo, 'ProductType', '?')} "
            f"Version={getattr(sysinfo, 'MajorVersion', '?')}.{getattr(sysinfo, 'MinorVersion', '?')}."
            f"{getattr(sysinfo, 'BuildNumber', '?')} "
            f"CPU={getattr(sysinfo, 'ProcessorArchitecture', '?')} "
            f"CPUs={getattr(sysinfo, 'NumberOfProcessors', '?')}\n"
        )

    exc = getattr(md, "exception", None)
    if exc and getattr(exc, "ExceptionRecords", None):
        for rec in exc.ExceptionRecords[:3]:
            buf.write(
                f"EXCEPTION code=0x{rec.ExceptionCode:08X} "
                f"flags=0x{rec.ExceptionFlags:08X} "
                f"address=0x{rec.ExceptionAddress:X} "
                f"thread_id={getattr(exc, 'ThreadId', '?')}\n"
            )

    # Faulting thread context (RIP / instruction pointer)
    threads = getattr(md, "threads", None)
    if threads and threads.threads:
        buf.write(f"\nThreads: {len(threads.threads)} total\n")
        faulting_tid = getattr(exc, "ThreadId", None) if exc else None
        for t in threads.threads[:8]:
            marker = " [!] FAULTING" if t.ThreadId == faulting_tid else ""
            buf.write(
                f"  thread tid={t.ThreadId} prio={t.Priority} "
                f"teb=0x{t.Teb:X}{marker}\n"
            )

    mods = getattr(md, "modules", None)
    if mods and mods.modules:
        buf.write(f"\nLoaded modules: {len(mods.modules)} total. Top by base address:\n")
        # Sort by base address so caller can see what's loaded near a crash address
        for m in sorted(mods.modules, key=lambda x: x.baseaddress)[:60]:
            name = (m.name or "?").split("\\")[-1]
            buf.write(
                f"  0x{m.baseaddress:016X}+0x{m.size:08X}  {name}  "
                f"v={'.'.join(str(p) for p in (m.versioninfo.major_ver, m.versioninfo.minor_ver, m.versioninfo.build_ver, m.versioninfo.private_part_ver)) if getattr(m, 'versioninfo', None) else '?'}\n"
            )
        # Highlight ArcGIS-relevant modules anywhere in the list
        agp = [m for m in mods.modules if re.search(r"arc(gis|pro|object)|esri|gp\.dll|server\.exe", (m.name or "").lower())]
        if agp:
            buf.write(f"\nArcGIS-named modules ({len(agp)}):\n")
            for m in agp[:30]:
                buf.write(f"  0x{m.baseaddress:016X}  {Path(m.name).name}\n")

    out = buf.getvalue()
    if len(out.encode()) > max_bytes:
        out = out.encode()[:max_bytes].decode("utf-8", errors="replace")
        out += "\n[... evidencepilot: minidump output truncated ...]\n"
    return out or "(minidump produced no extractable metadata)"


def _placeholder_image(path: str) -> str:
    p = Path(path)
    return f"(binary image file: {p.name}, {os.path.getsize(path)} bytes -- visual evidence)"


def _placeholder_pdf(path: str) -> str:
    return f"(PDF file: {Path(path).name} -- not parsed in MVP; please extract text externally if critical)"


def _placeholder_zip(path: str) -> str:
    return f"(Zip archive: {Path(path).name} -- extract via /api/cases/{{id}}/files/{{fid}}/extract)"


# Dispatch table: extension -> handler(path, max_bytes). Keeps extract_text() flat.
_BINARY_HANDLERS: Dict[str, Callable[[str, int], str]] = {
    ".evtx": _parse_evtx,
    ".dmp": _parse_minidump,
}

_STATIC_HANDLERS: Dict[str, Callable[[str], str]] = {
    ".pdf": _placeholder_pdf,
    ".zip": _placeholder_zip,
}


def extract_text(path: str, max_bytes: int = 200_000, mode: str = "tail_first") -> str:
    """Best-effort text extraction.

    For text-like extensions reads via the chosen `mode` (head / tail_first / windowed).
    For binary extensions delegates to a registered handler (EVTX, DMP) or placeholder.
    """
    ext = Path(path).suffix.lower()
    try:
        if ext in TEXT_EXTS or ext == "":
            if mode == "head":
                return _read_head(path, max_bytes)
            if mode == "windowed":
                return _read_windowed(path, max_bytes)
            return _read_tail_first(path, max_bytes)
        if ext in IMAGE_EXTS:
            return _placeholder_image(path)
        binary = _BINARY_HANDLERS.get(ext)
        if binary is not None:
            return binary(path, max_bytes)
        static = _STATIC_HANDLERS.get(ext)
        if static is not None:
            return static(path)
        # unknown extension: try as text (last-resort, head-only to avoid corrupting unknown binaries)
        return _read_head(path, max_bytes)
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
