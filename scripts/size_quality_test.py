#!/usr/bin/env python3
"""Quality-vs-size experiment — 4 sizes spanning the cliffs."""
import json
import os
import random
import sys
import time
import urllib.request

API = sys.argv[1].rstrip("/")
HTTP_TIMEOUT = 120  # generous per-call timeout

NEEDLE = """2026-04-15 14:30:01 ERROR [saml] NAME_ID claim missing from IdP assertion for user=alice@acme.com
2026-04-15 14:30:01 ERROR [saml] Cannot create session: required attribute NAME_ID is null
2026-04-15 14:30:02 WARN [auth] Redirecting user to /portal/home with empty session due to missing NAME_ID
"""

NOISE = [
    "2026-04-15 13:{m:02d}:{s:02d} INFO [scheduler] Housekeeping iteration #{i}",
    "2026-04-15 13:{m:02d}:{s:02d} INFO [stats] CPU {c}% MEM {mem}% disk_free {d}GB",
    "2026-04-15 13:{m:02d}:{s:02d} INFO [items] User created item id=item{i} type=WebMap",
    "2026-04-15 13:{m:02d}:{s:02d} INFO [search] Indexing batch {i} of items",
    "2026-04-15 13:{m:02d}:{s:02d} INFO [http] GET /portal/sharing/rest/community returned 200",
]


def noise_line(i):
    t = random.choice(NOISE)
    return t.format(m=random.randint(0, 59), s=random.randint(0, 59), i=i,
                    c=random.randint(5, 60), mem=random.randint(30, 80), d=random.randint(50, 400))


def build_log(target_bytes, needle_offset):
    out, cur, planted, i = [], 0, False, 0
    while cur < target_bytes:
        if not planted and cur >= needle_offset:
            out.append(NEEDLE); cur += len(NEEDLE); planted = True; continue
        line = noise_line(i) + "\n"
        out.append(line); cur += len(line); i += 1
    if not planted:
        out.append(NEEDLE)
    return "".join(out)


def post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read())


def get_json(url):
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read())


def upload(url, path, name):
    bnd = "----epb" + str(random.randint(1, 1 << 32))
    with open(path, "rb") as f:
        c = f.read()
    body = (
        f"--{bnd}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{name}\"\r\n"
        f"Content-Type: text/plain\r\n\r\n"
    ).encode() + c + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={bnd}"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def check(report):
    if not report:
        return {"found": False, "rc_hit": False, "conf": None, "layer": None}
    blob = json.dumps(report).lower()
    found = "name_id" in blob or "name id" in blob
    rc = report.get("root_cause") or {}
    rc_hit = "name_id" in json.dumps(rc).lower() or "name id" in json.dumps(rc).lower()
    return {
        "found": found, "rc_hit": rc_hit,
        "conf": rc.get("confidence"), "layer": report.get("likely_layer"),
        "findings": len(report.get("key_findings") or []),
        "timeline": len(report.get("timeline") or []),
    }


def wait_for_indexing(cid, expected_min=10, max_wait_s=400):
    """Wait until indexed_chunks stabilises (no growth for 3 consecutive polls)."""
    prev, stable_count = -1, 0
    elapsed = 0
    while elapsed < max_wait_s:
        try:
            n = get_json(f"{API}/api/cases/{cid}/retrieval/stats").get("indexed_chunks", 0)
        except Exception as e:
            print(f"    (stats call failed: {e}, retrying)", flush=True)
            time.sleep(5); elapsed += 5; continue
        if n > 0 and n == prev:
            stable_count += 1
            if stable_count >= 3:
                return n
        else:
            stable_count = 0
        prev = n
        time.sleep(4); elapsed += 4
    return prev


def run_test(label, size_b, needle_off):
    print(f"\n========== {label}: {size_b/1_000_000:.2f}MB needle@{needle_off/1_000_000:.2f}MB ==========", flush=True)
    path = f"/tmp/portal_test_{label}.log"
    with open(path, "w") as f:
        f.write(build_log(size_b, needle_off))
    actual = os.path.getsize(path)
    print(f"  log: {actual:,} bytes", flush=True)

    case = post_json(f"{API}/api/cases", {
        "title": f"Size test {label}", "category_id": "auth_saml",
        "context": {"timestamps": "2026-04-15 14:30 EST", "summary": "SAML blank page",
                    "repro_steps": "Login via SAML", "versions": "Portal 11.3",
                    "topology": "single Portal", "recent_changes": "IdP cert rotated"},
    })
    cid = case["id"]
    print(f"  case={cid}", flush=True)

    t0 = time.time()
    upload(f"{API}/api/cases/{cid}/files", path, f"portal_{label}.log")
    print(f"  uploaded in {time.time()-t0:.1f}s, waiting for indexing...", flush=True)

    indexed = wait_for_indexing(cid)
    print(f"  indexed_chunks={indexed:,}", flush=True)

    t0 = time.time()
    post_json(f"{API}/api/cases/{cid}/orchestrate", {})
    status = None
    for i in range(150):
        try:
            st = get_json(f"{API}/api/cases/{cid}/orchestrate/status")
            if st.get("status") in ("done", "error", "reduce_failed", "no_evidence"):
                status = st.get("status"); break
        except Exception as e:
            print(f"    (status poll failed: {e})", flush=True)
        time.sleep(5)
    elapsed = time.time() - t0
    print(f"  orchestrator: {status} in {elapsed:.1f}s", flush=True)

    c = get_json(f"{API}/api/cases/{cid}")
    orch = (c.get("ai_results") or {}).get("orchestrator") or {}
    q = check(orch.get("report"))
    s = orch.get("stats") or {}
    r = {
        "label": label, "size_mb": round(actual / 1_000_000, 2),
        "offset_mb": round(needle_off / 1_000_000, 2),
        "indexed_chunks": indexed,
        "map_batches": s.get("map_batches"), "chunks_mapped": s.get("chunks_mapped"),
        "orch_time_s": round(elapsed, 1), "status": status, **q,
    }
    print(f"  RESULT: {json.dumps(r)}", flush=True)
    return r


# 3 sizes spanning the cliffs — keep total runtime tractable
TESTS = [
    ("B_1MB",   1 * 1024 * 1024,         512 * 1024),         # under all caps — baseline
    ("D_5MB",   5 * 1024 * 1024,         int(4.5 * 1024 * 1024)),  # PAST max_chunks=4000 (needle in late portion)
    ("E_12MB",  12 * 1024 * 1024,        int(11 * 1024 * 1024)),    # PAST max_index_bytes=10MB
]

results = []
for label, size, off in TESTS:
    try:
        results.append(run_test(label, size, off))
    except Exception as e:
        print(f"  !! {label} crashed: {e}", flush=True)
        results.append({"label": label, "error": str(e)})

print("\n========== TABLE ==========", flush=True)
print("| Test | Size MB | Needle@ MB | Indexed | Batches | Time | Needle found? | Root-cause hit? | Conf | Layer |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in results:
    if "error" in r:
        print(f"| {r['label']} | — | — | — | — | — | ERR | — | — | {r['error'][:32]} |")
        continue
    print(
        f"| {r['label']} | {r['size_mb']} | {r['offset_mb']} | "
        f"{r['indexed_chunks']:,} | {r.get('map_batches','?')} | {r['orch_time_s']}s | "
        f"{'YES' if r.get('found') else 'NO'} | "
        f"{'YES' if r.get('rc_hit') else 'NO'} | "
        f"{r.get('conf','?')} | {r.get('layer','?')} |"
    )

with open("/app/scripts/size_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
