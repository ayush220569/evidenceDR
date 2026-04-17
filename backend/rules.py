"""Evidence rules engine and category definitions for EvidencePilot AI."""

CATEGORIES = {
    "agol_admin": {
        "id": "agol_admin",
        "name": "ArcGIS Online org / admin events",
        "short": "AGOL Admin",
        "icon": "Buildings",
        "clues": [
            "who changed something",
            "sharing/licensing changes",
            "usage spikes",
            "member/app activity",
        ],
        "collect_first": [
            "Activity report CSV",
            "Status / usage exports",
            "Pro license activity",
        ],
        "add_if_needed": ["HAR for web UI flows"],
        "layers": ["browser", "client_pro"],
        "tips": "Cross-reference activity timestamps with the user-reported incident window (with timezone). License changes often precede a support spike.",
    },
    "auth_saml": {
        "id": "auth_saml",
        "name": "Authentication / SAML / OAuth / redirect / custom domain",
        "short": "Auth / SAML",
        "icon": "ShieldCheck",
        "clues": [
            "blank page after sign in",
            "redirect loop",
            "NAME_ID / claim issues",
            "only vanity URL fails",
            "CORS / CSP errors",
        ],
        "collect_first": [
            "HAR / Fiddler",
            "Portal logs with DEBUG window",
            "IdP / SAML metadata",
        ],
        "add_if_needed": [
            "Web Adaptor / IIS / proxy logs",
            "Certificate chain details",
        ],
        "layers": ["browser", "web_tier", "portal"],
        "tips": "Reproduce in private browsing and capture HAR with 'Preserve log' enabled. Compare vanity URL vs direct portal URL.",
    },
    "web_tier": {
        "id": "web_tier",
        "name": "Web tier / Web Adaptor / reverse proxy / TLS",
        "short": "Web Tier",
        "icon": "Globe",
        "clues": [
            "502 / 403 / 404 via Web Adaptor",
            "direct 7443 / 6443 works",
            "intermittent front-door failures",
            "HTTP/2 edge cases",
        ],
        "collect_first": [
            "IIS / proxy logs",
            "HAR",
            "Web Adaptor config",
        ],
        "add_if_needed": [
            "Portal / Server logs",
            "Binding / listener screenshots",
        ],
        "layers": ["web_tier", "portal", "server"],
        "tips": "If direct 7443/6443 works while Web Adaptor fails, the issue is almost certainly in the front-door (proxy/Web Adaptor/TLS).",
    },
    "portal_ops": {
        "id": "portal_ops",
        "name": "Portal (Enterprise) operations",
        "short": "Portal",
        "icon": "Browsers",
        "clues": [
            "user/account creation",
            "content/item operations",
            "sharing/permissions",
            "indexing/search",
            "UI errors",
        ],
        "collect_first": [
            "Portal logs (queried & on-disk)",
        ],
        "add_if_needed": [
            "Web server / proxy logs if request path is suspect",
        ],
        "layers": ["portal", "web_tier"],
        "tips": "Pull both queried logs (Portal Admin) AND on-disk logs. They are not always identical due to log level filtering.",
    },
    "server_services": {
        "id": "server_services",
        "name": "Server / services (Enterprise)",
        "short": "Server / Services",
        "icon": "HardDrives",
        "clues": [
            "service fails to start",
            "ArcSOC crash",
            "GP service errors",
            "publish failures",
            "slow services",
        ],
        "collect_first": [
            "Server logs from Manager",
            "Relevant log codes",
        ],
        "add_if_needed": [
            "OS logs (Event Viewer / journalctl)",
            "Process dumps if crash",
        ],
        "layers": ["server", "os_system"],
        "tips": "ArcSOC crashes leave Watson/dump artifacts. Capture the last good vs first bad timestamp.",
    },
    "datastore": {
        "id": "datastore",
        "name": "Data Store / hosted layers",
        "short": "Data Store",
        "icon": "Database",
        "clues": [
            "hosted services fail",
            "datastore unhealthy",
            "replication / backup troubles",
            "hosting server complaints",
        ],
        "collect_first": [
            "Data Store logs",
            "Server logs",
            "Portal logs",
        ],
        "add_if_needed": [
            "Disk / IO metrics",
            "Datastore machine OS logs",
        ],
        "layers": ["datastore", "server", "portal", "os_system"],
        "tips": "Always grab logs from ALL Data Store nodes (primary AND standby). Replication issues often show only on the standby.",
    },
    "webgisdr": {
        "id": "webgisdr",
        "name": "WebGISDR backup / restore",
        "short": "WebGISDR",
        "icon": "FloppyDisk",
        "clues": [
            "manual works but scheduled fails",
            "UNC / share permission / path errors",
            "sleep interrupted",
            "temp / disk full",
        ],
        "collect_first": [
            "webgisdr.log",
            "Portal / Server / Data Store logs",
            "Scheduler history",
        ],
        "add_if_needed": [
            "ProcMon filtered to share/temp path",
            "OS event logs",
        ],
        "layers": ["server", "datastore", "portal", "os_system"],
        "tips": "Scheduled-fails-only is almost always a service-account permission or sleep/wake issue. ProcMon filtered to the temp + UNC path will prove it in minutes.",
    },
    "licensing": {
        "id": "licensing",
        "name": "Licensing (Named User / License Manager)",
        "short": "Licensing",
        "icon": "Key",
        "clues": [
            "Pro cannot validate Named User",
            "license manager unreachable",
            "session issues",
        ],
        "collect_first": [
            "Portal licensing endpoints / logs",
            "Portal logs",
            "Org license activity",
        ],
        "add_if_needed": [
            "Network / proxy logs",
            "System time drift checks",
        ],
        "layers": ["portal", "client_pro", "web_tier"],
        "tips": "Time drift > 5 min between Pro client and Portal commonly breaks token validation silently.",
    },
    "pro_crash": {
        "id": "pro_crash",
        "name": "ArcGIS Pro crash",
        "short": "Pro Crash",
        "icon": "WarningOctagon",
        "clues": [
            "crash on launch / open project / layout / tool",
            "often after Windows / GPU / Pro update",
        ],
        "collect_first": [
            ".dmp",
            "ErrorReports",
            "Event Viewer",
            "Pro build",
            "GPU driver",
            "Add-ins",
        ],
        "add_if_needed": [
            "Repair test",
            "Clean profile repro",
            "Diagnostic Monitor if reproducible",
        ],
        "layers": ["client_pro", "os_system"],
        "tips": "Clean-profile repro (rename %appdata%\\ESRI\\ArcGISPro) isolates user-profile corruption from product defects.",
    },
    "pro_hang": {
        "id": "pro_hang",
        "name": "ArcGIS Pro hang / performance / GP issues",
        "short": "Pro Hang / Perf",
        "icon": "Hourglass",
        "clues": [
            "gray UI",
            "long GP",
            "memory growth",
            "slow startup / map load",
        ],
        "collect_first": [
            "Diagnostic Monitor",
            "GP diagnostic messages",
            "Performance counters",
        ],
        "add_if_needed": [
            "Dump during hang",
            "ProcMon if file/profile suspicion",
        ],
        "layers": ["client_pro", "os_system"],
        "tips": "Hangs need Diagnostic Monitor — not just dumps. Capture the hang window, then take a process dump WHILE Pro is unresponsive.",
    },
}

LAYERS = {
    "browser": {"name": "Browser", "color": "#00E5FF"},
    "web_tier": {"name": "Web Tier", "color": "#7C3AED"},
    "portal": {"name": "Portal", "color": "#10B981"},
    "server": {"name": "Server", "color": "#F59E0B"},
    "datastore": {"name": "Data Store", "color": "#FF9F1C"},
    "client_pro": {"name": "Pro Client", "color": "#EF4444"},
    "os_system": {"name": "OS / System", "color": "#A1A1AA"},
    "unknown": {"name": "Unknown", "color": "#71717A"},
}

CONTEXT_FIELDS = [
    {"key": "timestamps", "label": "Timestamps with timezone", "weight": 15},
    {"key": "repro_steps", "label": "Exact reproduction steps", "weight": 15},
    {"key": "urls", "label": "Exact URLs", "weight": 10},
    {"key": "versions", "label": "Software / product versions", "weight": 15},
    {"key": "topology", "label": "Deployment topology", "weight": 15},
    {"key": "recent_changes", "label": "Recent changes (patches, certs, GPU, OS, policy)", "weight": 15},
    {"key": "already_tested", "label": "Already-tested actions", "weight": 5},
    {"key": "environment_notes", "label": "Customer environment notes", "weight": 10},
]

# Logic tree: dynamic per category. Each node: {id, q, opts:[{label, value, next?, leaf?}]}
LOGIC_TREE = {
    "auth_saml": [
        {"id": "blank", "q": "Is the user seeing a blank page or a redirect loop after sign-in?",
         "opts": [{"label": "Blank page", "value": "blank"}, {"label": "Redirect loop", "value": "loop"}, {"label": "Other", "value": "other"}]},
        {"id": "vanity", "q": "Does the failure happen ONLY via the vanity / custom domain?",
         "opts": [{"label": "Yes (vanity-only)", "value": "vanity_only"}, {"label": "No (also direct)", "value": "all"}]},
        {"id": "har", "q": "Do you have a HAR captured with 'Preserve log' enabled across the failed login?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]},
    ],
    "web_tier": [
        {"id": "direct", "q": "Does direct 7443/6443 work while Web Adaptor fails?",
         "opts": [{"label": "Yes (direct works)", "value": "direct_works"}, {"label": "No (both fail)", "value": "both_fail"}, {"label": "Not tested", "value": "untested"}]},
        {"id": "code", "q": "What HTTP status are users seeing through the front-door?",
         "opts": [{"label": "502", "value": "502"}, {"label": "403", "value": "403"}, {"label": "404", "value": "404"}, {"label": "Mixed / intermittent", "value": "mixed"}]},
    ],
    "pro_crash": [
        {"id": "when", "q": "When does Pro crash?",
         "opts": [{"label": "On launch", "value": "launch"}, {"label": "Opening project", "value": "project"}, {"label": "Specific tool/layout", "value": "tool"}]},
        {"id": "recent", "q": "Was there a recent Windows, GPU driver, or Pro update before the crashes started?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}, {"label": "Unknown", "value": "unknown"}]},
        {"id": "dump", "q": "Do you have a .dmp file from the crash?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]},
    ],
    "pro_hang": [
        {"id": "type", "q": "Is the issue a crash or a hang?",
         "opts": [{"label": "Hang / unresponsive", "value": "hang"}, {"label": "Slow but responsive", "value": "slow"}, {"label": "Crash", "value": "crash"}]},
        {"id": "diag", "q": "Have you captured Diagnostic Monitor while reproducing?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]},
        {"id": "path", "q": "Is the issue reproducible on a local drive vs a network path?",
         "opts": [{"label": "Local OK, network fails", "value": "network"}, {"label": "Both fail", "value": "both"}, {"label": "Not tested", "value": "untested"}]},
    ],
    "webgisdr": [
        {"id": "sched", "q": "Does the manual run succeed while only the scheduled run fails?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No (both fail)", "value": "no"}]},
        {"id": "perm", "q": "Are there path / permission errors in webgisdr.log?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}, {"label": "Unsure", "value": "unsure"}]},
    ],
    "default": [
        {"id": "repro", "q": "Do you have a reproducible timestamp with timezone?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]},
        {"id": "scope", "q": "Is the issue browser-only or system-wide?",
         "opts": [{"label": "Browser-only", "value": "browser"}, {"label": "System-wide", "value": "system"}, {"label": "Unsure", "value": "unsure"}]},
        {"id": "changed", "q": "Was there a recent proxy, certificate, OS, GPU, or app update?",
         "opts": [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}, {"label": "Unknown", "value": "unknown"}]},
    ],
}


def get_logic_tree(category_id: str):
    return LOGIC_TREE.get(category_id, LOGIC_TREE["default"])


def score_evidence(case: dict) -> dict:
    """Return completeness score and gaps."""
    context = case.get("context", {}) or {}
    files = case.get("files", []) or []
    category_id = case.get("category_id")
    cat = CATEGORIES.get(category_id, {})

    # Context score (max 100)
    context_total = 0
    context_max = sum(f["weight"] for f in CONTEXT_FIELDS)
    context_gaps = []
    for f in CONTEXT_FIELDS:
        val = context.get(f["key"])
        if val and str(val).strip():
            context_total += f["weight"]
        else:
            context_gaps.append(f["label"])
    context_pct = round(context_total / context_max * 100) if context_max else 0

    # Files score: based on whether layers expected by category are covered
    expected_layers = set(cat.get("layers", []))
    present_layers = {f.get("layer") for f in files if f.get("layer") and f.get("layer") != "unknown"}
    if expected_layers:
        layer_pct = round(len(expected_layers & present_layers) / len(expected_layers) * 100)
    else:
        layer_pct = 100 if present_layers else 0
    missing_layers = list(expected_layers - present_layers)

    overall = round(0.6 * context_pct + 0.4 * layer_pct)

    if overall >= 80:
        readiness = "high"
    elif overall >= 50:
        readiness = "medium"
    else:
        readiness = "low"

    return {
        "context_pct": context_pct,
        "layer_pct": layer_pct,
        "overall_pct": overall,
        "readiness": readiness,
        "context_gaps": context_gaps,
        "missing_layers": missing_layers,
        "expected_layers": list(expected_layers),
        "present_layers": list(present_layers),
    }
