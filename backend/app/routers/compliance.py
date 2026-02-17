"""
LoopGrid Compliance Router
==========================

Generates compliance reports mapping to EU AI Act, NIST RMF,
and ISO 42001 requirements. This is infrastructure, not a dashboard —
it generates structured compliance artifacts via API.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Decision
from ..hashing import verify_chain

router = APIRouter()


def _compute_stats(db: Session, service_name: Optional[str] = None):
    """Compute decision statistics for compliance report."""
    query = db.query(Decision)
    if service_name:
        query = query.filter(Decision.service_name == service_name)

    total = query.count()
    if total == 0:
        return {"total": 0}

    incorrect = query.filter(Decision.status == "incorrect").count()
    corrected = query.filter(Decision.status == "corrected").count()
    recorded = query.filter(Decision.status == "recorded").count()

    # Unique models and services
    models = db.query(Decision.model_data).distinct().count()
    services = db.query(Decision.service_name).distinct().count()
    decision_types = db.query(Decision.decision_type).distinct().count()

    # Time range
    first = query.order_by(Decision.created_at.asc()).first()
    last = query.order_by(Decision.created_at.desc()).first()

    # Correction rate
    correction_rate = round((corrected / total) * 100, 1) if total > 0 else 0
    error_rate = round(((incorrect + corrected) / total) * 100, 1) if total > 0 else 0

    return {
        "total": total,
        "recorded": recorded,
        "incorrect": incorrect,
        "corrected": corrected,
        "correction_rate": correction_rate,
        "error_rate": error_rate,
        "unique_models": models,
        "unique_services": services,
        "unique_decision_types": decision_types,
        "first_decision": first.created_at.isoformat() if first else None,
        "last_decision": last.created_at.isoformat() if last else None,
    }


@router.get("/compliance/report")
def generate_compliance_report(
    service_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Generate a structured compliance report.
    
    Maps LoopGrid data to EU AI Act Article 12 (Record-Keeping),
    Article 14 (Human Oversight), and Article 9 (Risk Management).
    """
    stats = _compute_stats(db, service_name)

    # Verify ledger integrity
    query = db.query(Decision).order_by(Decision.created_at.asc())
    if service_name:
        query = query.filter(Decision.service_name == service_name)
    integrity = verify_chain(query.all())

    report = {
        "report_type": "EU AI Act Compliance Assessment",
        "generated_at": datetime.utcnow().isoformat(),
        "generator": "LoopGrid v0.1.0",
        "service_filter": service_name,
        "summary": stats,
        "ledger_integrity": integrity,
        "eu_ai_act_mapping": {
            "article_12_record_keeping": {
                "status": "compliant" if stats["total"] > 0 and integrity["valid"] else "non_compliant",
                "description": "Automatic logging of AI system events throughout lifecycle",
                "evidence": {
                    "total_decisions_logged": stats["total"],
                    "immutable_hash_chain": integrity["valid"],
                    "chain_length": integrity["total"],
                    "logging_period_start": stats.get("first_decision"),
                    "logging_period_end": stats.get("last_decision"),
                }
            },
            "article_14_human_oversight": {
                "status": "compliant" if stats.get("corrected", 0) > 0 or stats.get("incorrect", 0) > 0 else "partial",
                "description": "Human oversight measures for AI system operation",
                "evidence": {
                    "human_corrections": stats.get("corrected", 0),
                    "flagged_for_review": stats.get("incorrect", 0),
                    "correction_rate": stats.get("correction_rate", 0),
                    "human_in_the_loop": True
                }
            },
            "article_9_risk_management": {
                "status": "partial",
                "description": "Risk management system for AI lifecycle",
                "evidence": {
                    "error_rate_tracked": True,
                    "error_rate_percent": stats.get("error_rate", 0),
                    "replay_capability": True,
                    "systematic_improvement": stats.get("corrected", 0) > 0
                }
            }
        }
    }

    return report


@router.get("/compliance/report/html", response_class=HTMLResponse)
def generate_compliance_report_html(
    service_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Generate a printable HTML compliance report for auditors."""
    stats = _compute_stats(db, service_name)

    query = db.query(Decision).order_by(Decision.created_at.asc())
    if service_name:
        query = query.filter(Decision.service_name == service_name)
    integrity = verify_chain(query.all())

    art12_status = "COMPLIANT" if stats["total"] > 0 and integrity["valid"] else "NON-COMPLIANT"
    art14_status = "COMPLIANT" if stats.get("corrected", 0) > 0 else "PARTIAL"
    integrity_badge = "PASS" if integrity["valid"] else "FAIL"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>LoopGrid Compliance Report</title>
<style>
body{{font-family:-apple-system,Arial,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.6}}
h1{{color:#1B2A4A;border-bottom:3px solid #1B2A4A;padding-bottom:8px}}
h2{{color:#2E5090;margin-top:32px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:4px;font-weight:bold;font-size:14px}}
.pass{{background:#d4edda;color:#155724}}.fail{{background:#f8d7da;color:#721c24}}
.partial{{background:#fff3cd;color:#856404}}
table{{width:100%;border-collapse:collapse;margin:16px 0}}
th,td{{text-align:left;padding:8px 12px;border:1px solid #ddd}}
th{{background:#f5f5f5}}
.footer{{margin-top:48px;padding-top:16px;border-top:1px solid #ddd;color:#666;font-size:13px}}
</style></head><body>
<h1>LoopGrid Compliance Report</h1>
<p><strong>Generated:</strong> {now}<br>
<strong>Service:</strong> {service_name or "All services"}<br>
<strong>Generator:</strong> LoopGrid v0.1.0</p>

<h2>Ledger Integrity</h2>
<p>Hash chain verification: <span class="badge {'pass' if integrity['valid'] else 'fail'}">{integrity_badge}</span></p>
<p>{integrity['message']}</p>

<h2>Decision Statistics</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total decisions logged</td><td>{stats['total']}</td></tr>
<tr><td>Recorded (no issues)</td><td>{stats.get('recorded',0)}</td></tr>
<tr><td>Flagged incorrect</td><td>{stats.get('incorrect',0)}</td></tr>
<tr><td>Human corrected</td><td>{stats.get('corrected',0)}</td></tr>
<tr><td>Error rate</td><td>{stats.get('error_rate',0)}%</td></tr>
<tr><td>Correction rate</td><td>{stats.get('correction_rate',0)}%</td></tr>
</table>

<h2>EU AI Act Compliance Mapping</h2>
<table>
<tr><th>Article</th><th>Requirement</th><th>Status</th></tr>
<tr><td>Article 12</td><td>Record-Keeping — automatic logging of events</td>
<td><span class="badge {'pass' if art12_status=='COMPLIANT' else 'fail'}">{art12_status}</span></td></tr>
<tr><td>Article 14</td><td>Human Oversight — human-in-the-loop mechanisms</td>
<td><span class="badge {'pass' if art14_status=='COMPLIANT' else 'partial'}">{art14_status}</span></td></tr>
<tr><td>Article 9</td><td>Risk Management — lifecycle risk tracking</td>
<td><span class="badge partial">PARTIAL</span></td></tr>
</table>

<div class="footer">
<p>This report was generated by LoopGrid — Control Plane for AI Decision Reliability.<br>
Report data is derived from the immutable decision ledger with cryptographic hash chain verification.</p>
</div></body></html>"""

    return HTMLResponse(content=html)


@router.get("/export/decisions")
def export_decisions(
    service_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: str = Query("json", description="Export format: json or csv"),
    db: Session = Depends(get_db)
):
    """Export decisions for auditing purposes."""
    query = db.query(Decision)
    if service_name:
        query = query.filter(Decision.service_name == service_name)
    if status:
        query = query.filter(Decision.status == status)

    decisions = query.order_by(Decision.created_at.desc()).limit(1000).all()

    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["decision_id", "created_at", "service_name", "decision_type", "status", "content_hash"])
        for d in decisions:
            writer.writerow([d.id, d.created_at.isoformat(), d.service_name, d.decision_type, d.status, d.content_hash or ""])
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=loopgrid_decisions.csv"}
        )

    return {"decisions": [d.to_dict() for d in decisions], "total": len(decisions)}
