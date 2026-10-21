"""Bounded, deterministic orchestration of available OMEGA analyzers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .analyzers import analyze_file, compare_files
from .events import analyze_events
from .models import base_report


def run_investigation(
    artifact_path: str | Path | None = None,
    events_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run requested read-only analyses and combine evidence without inventing a verdict."""
    if artifact_path is None and events_path is None:
        raise ValueError("Supply at least one of --artifact or --events.")
    if baseline_path is not None and artifact_path is None:
        raise ValueError("--baseline requires --artifact so it has a target to compare.")

    report = base_report("bounded_investigation")
    report["investigation_model"] = "deterministic-orchestration-v1"
    report["verdict"] = {
        "status": "not_automatically_determined",
        "explanation": (
            "OMEGA aggregates evidence and review signals. It does not label a system "
            "compromised or clean from these checks alone."
        ),
    }
    report["plan"] = []
    report["analyses"] = {}
    report["evidence_index"] = []
    collected_findings: list[dict[str, Any]] = []

    if artifact_path is not None:
        artifact_report = analyze_file(artifact_path)
        report["analyses"]["target_artifact"] = artifact_report
        report["plan"].append({
            "step": "inspect_target_artifact",
            "status": "completed",
            "description": "Computed SHA-256, file hints, printable strings, and available basic PE metadata without execution.",
        })
        artifact = artifact_report["artifact"]
        report["evidence_index"].append({
            "evidence_id": "target-sha256",
            "kind": "artifact_fingerprint",
            "sha256": artifact["sha256"],
            "size_bytes": artifact["size_bytes"],
            "source": artifact["supplied_path"],
            "reference": "/analyses/target_artifact/artifact",
        })
        collected_findings.extend(
            {**finding, "analysis_stage": "target_artifact"}
            for finding in artifact_report.get("findings", [])
        )

    if baseline_path is not None and artifact_path is not None:
        diff_report = compare_files(baseline_path, artifact_path)
        report["analyses"]["baseline_comparison"] = diff_report
        report["plan"].append({
            "step": "compare_baseline",
            "status": "completed",
            "description": "Compared hashes, size, format hints, and printable strings; not a full semantic binary diff.",
        })
        for label in ("before", "after"):
            artifact = diff_report["artifacts"][label]
            report["evidence_index"].append({
                "evidence_id": "baseline" if label == "before" else "target-comparison",
                "kind": "artifact_fingerprint",
                "sha256": artifact["sha256"],
                "size_bytes": artifact["size_bytes"],
                "source": artifact["supplied_path"],
                "reference": "/analyses/baseline_comparison/artifacts/" + label,
            })

    if events_path is not None:
        events_report = analyze_events(events_path)
        report["analyses"]["event_timeline"] = events_report
        report["plan"].append({
            "step": "normalize_and_correlate_events",
            "status": "completed",
            "description": "Normalized exported timestamps and linked nearby events sharing a process identity.",
        })
        report["evidence_index"].append({
            "evidence_id": "event-export",
            "kind": "event_log",
            "source": events_report["source_artifact"]["supplied_path"],
            "size_bytes": events_report["source_artifact"]["size_bytes"],
            "records_parsed": events_report["summary"]["records_parsed"],
            "reference": "/analyses/event_timeline/events",
        })
        collected_findings.extend(
            {**finding, "analysis_stage": "event_timeline"}
            for finding in events_report.get("findings", [])
        )

    report["findings"] = collected_findings
    summary_parts: list[str] = []
    if "target_artifact" in report["analyses"]:
        count = len(report["analyses"]["target_artifact"].get("findings", []))
        summary_parts.append(f"Target artifact: {count} configured review indicator(s).")
    if "baseline_comparison" in report["analyses"]:
        same = report["analyses"]["baseline_comparison"]["diff"]["identical_sha256"]
        summary_parts.append("Baseline comparison: byte-identical." if same else "Baseline comparison: byte differences observed.")
    if "event_timeline" in report["analyses"]:
        event_summary = report["analyses"]["event_timeline"]["summary"]
        summary_parts.append(
            f"Event export: {event_summary['records_parsed']} record(s), "
            f"{event_summary['timeline_links']} temporal link(s)."
        )
    report["summary"] = {
        "steps_completed": len(report["plan"]),
        "findings_count": len(collected_findings),
        "evidence_items": len(report["evidence_index"]),
        "observations": summary_parts,
        "interpretation": "Review each referenced evidence item. Temporal correlation and static string matches are not proof of causation or compromise.",
    }
    return report
