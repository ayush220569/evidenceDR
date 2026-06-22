"""Regression test: hybrid retrieval must surface ERROR/WARN needles even in a
homogeneous INFO-dominated log where pure semantic search ranks them at the noise floor.
"""
import os
import sys
import uuid

# Make backend modules importable without changing PYTHONPATH globally
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import retrieval  # noqa: E402


def _make_corpus(noise_lines: int = 500) -> str:
    """Build a synthetic log: lots of INFO housekeeping + one block of SAML ERRORs."""
    out = []
    for i in range(noise_lines):
        out.append(
            f"2026-04-15 13:{i%60:02d}:{(i*7)%60:02d} INFO [scheduler] Housekeeping iteration #{i}"
        )
        out.append(
            f"2026-04-15 13:{i%60:02d}:{(i*11)%60:02d} INFO [items] User created item id=item{i} type=WebMap"
        )
    # plant needle in the middle
    mid = len(out) // 2
    needle = [
        "2026-04-15 14:30:01 ERROR [saml] NAME_ID claim missing from IdP assertion for user=alice@acme.com",
        "2026-04-15 14:30:01 ERROR [saml] Cannot create session: required attribute NAME_ID is null",
        "2026-04-15 14:30:02 WARN [auth] Redirecting user to /portal/home with empty session due to missing NAME_ID",
    ]
    out[mid:mid] = needle
    return "\n".join(out)


def test_hybrid_retrieves_severity_needle_in_noisy_log():
    case_id = "test-hybrid-" + uuid.uuid4().hex[:8]
    file_id = uuid.uuid4().hex[:10]
    text = _make_corpus(noise_lines=500)

    try:
        n = retrieval.index_file(case_id, file_id, "synthetic.log", "portal", text)
        assert n > 0, "indexing produced no chunks"

        # Query that targets the needle but is mostly already-frequent vocabulary
        hits = retrieval.retrieve(case_id, "NAME_ID claim missing SAML assertion", top_k=20)
        assert hits, "no hits returned"

        # The needle MUST be in the top results, surfaced by the lexical branch
        needle_rank = next(
            (i for i, h in enumerate(hits) if "NAME_ID" in (h.get("text") or "")),
            -1,
        )
        assert needle_rank >= 0, "needle not surfaced at all"
        assert needle_rank < 5, f"needle ranked too low: {needle_rank}"
        assert hits[needle_rank].get("source") in ("lexical", "hybrid"), (
            f"needle should be surfaced by lexical or hybrid branch, got {hits[needle_rank].get('source')}"
        )
    finally:
        retrieval.clear_case(case_id)


if __name__ == "__main__":
    test_hybrid_retrieves_severity_needle_in_noisy_log()
    print("OK")
