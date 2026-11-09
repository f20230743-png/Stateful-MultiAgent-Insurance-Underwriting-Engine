import os
from datetime import datetime, timezone
from typing import Any, Optional

from anthropic import Anthropic

from state import InsuranceClaimStates
from tools import (
    build_more_info_email,
    classify_if_claim_email,
    fetch_claim_decision_rulebook,
    fetch_claim_email_checklist,
    fetch_communication_drafts,
    fetch_customer_claim_context,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_dummy_pdf_payload() -> dict[str, Any]:
    return {
        "plain_text": (
            "Dear Insurance Team,\n"
            "I want to raise a claim for water damage in my kitchen after a pipeline leak.\n"
            "Incident date: 2026-04-08\n"
            "Claim amount: INR 25000\n"
            "Customer ID: CUST-2002\n"
            "Email: rahul.mehta@example.com\n"
            "Name: Rahul Mehta\n"
            "Attached proofs: photos, repair estimate."
        ),
        "incident_details": "Water damage in kitchen after pipeline leak.",
        "required_proofs": ["photos", "repair_estimate"],
        "incident_date": "2026-04-08",
        "claim_amount": 25000.0,
        "customer_name": "Rahul Mehta",
        "customer_email": "rahul.mehta@example.com",
        "customer_id": "CUST-2002",
        "source_file_path": "dummy_customer_claim.pdf",
    }


def _haiku_claim_email_check(extracted_text: str) -> bool:
    api_key = os.getenv("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return classify_if_claim_email(extracted_text)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=8,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": (
                    "Decide if this is an insurance claim email. "
                    "Reply only YES or NO.\n\n"
                    f"Email:\n{extracted_text}"
                ),
            }
        ],
    )
    content = ""
    if response.content:
        first_block = response.content[0]
        content = getattr(first_block, "text", "") or ""
    return content.strip().upper().startswith("YES")


def _haiku_missing_info_check(metadata: dict[str, Any], checklist: list[str]) -> list[str]:
    api_key = os.getenv("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        required_map = {
            "Incident description present": bool(metadata.get("incident_details")),
            "Incident date present": bool(metadata.get("incident_date")),
            "Claim amount mentioned": bool(metadata.get("claim_amount")),
            "Customer identity details available": bool(
                metadata.get("customer_id") and metadata.get("customer_email")
            ),
            "Government ID proof": "government_id" in metadata.get("required_proofs", []),
            "Policy/contract reference": bool(metadata.get("contract_reference")),
            "Incident evidence (photos/reports)": any(
                x in metadata.get("required_proofs", []) for x in ["photos", "report", "reports"]
            ),
            "Cost estimate or invoice": any(
                x in metadata.get("required_proofs", []) for x in ["repair_estimate", "invoice"]
            ),
        }
        return [item for item in checklist if not required_map.get(item, False)]

    client = Anthropic(api_key=api_key)
    checklist_text = "\n".join(f"- {item}" for item in checklist)
    prompt = (
        "Given the metadata and checklist, list missing checklist items only.\n"
        "Return one item per line. If none missing, return EXACTLY: NONE\n\n"
        f"Metadata:\n{metadata}\n\nChecklist:\n{checklist_text}"
    )
    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    content = ""
    if response.content:
        content = getattr(response.content[0], "text", "") or ""
    normalized = content.strip()
    if normalized.upper() == "NONE":
        return []
    lines = [line.strip("- ").strip() for line in normalized.splitlines() if line.strip()]
    return lines


def ingest_node(state: Optional[InsuranceClaimStates] = None) -> InsuranceClaimStates:
    """
    Node 1: ingest customer PDF and normalize metadata into state.
    """
    current_state: InsuranceClaimStates = state or {}
    payload = current_state.get("dummy_pdf_payload", _build_dummy_pdf_payload())

    current_state["customer_incident_pdf"] = {
        "incident_details": payload["incident_details"],
        "required_proofs": payload["required_proofs"],
        "incident_date": payload["incident_date"],
        "claim_amount": payload["claim_amount"],
        "customer_name": payload["customer_name"],
        "customer_email": payload["customer_email"],
        "source_file_path": payload["source_file_path"],
    }

    current_state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "ingest_node",
            "action": "pdf_ingested",
            "details": (
                f"Extracted plain text and metadata for customer_id={payload['customer_id']}, "
                f"email={payload['customer_email']}, claim_amount={payload['claim_amount']}."
            ),
        }
    )
    current_state.setdefault("database_history_updates", []).append(
        {
            "update_time": _utc_now(),
            "table_name": "claim_intake_events",
            "record_id": payload["customer_id"],
            "operation": "insert",
            "status": "success",
            "error_message": "",
        }
    )
    # Extra metadata used by downstream nodes before retrieval begins.
    current_state["ingest_metadata"] = {
        "extracted_plain_text": payload["plain_text"],
        "customer_id": payload["customer_id"],
        "customer_email": payload["customer_email"],
        "claim_amount": payload["claim_amount"],
        "incident_date": payload["incident_date"],
    }
    return current_state


def gateway_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 2: route to human pipeline if non-claim email, else continue.
    """
    extracted_text = state.get("ingest_metadata", {}).get("extracted_plain_text", "")
    is_claim_email = _haiku_claim_email_check(extracted_text)

    if not is_claim_email:
        state["final_claim_decision"] = {
            "status": "pending_review",
            "reason": "Gateway classified message as non-claim; routed to human pipeline.",
            "decided_at": _utc_now(),
            "decided_by": "gateway_node_haiku",
        }
        state.setdefault("audit_log", []).append(
            {
                "event_time": _utc_now(),
                "actor": "gateway_node",
                "action": "routed_to_human_pipeline",
                "details": "Haiku classified this email as non-claim. Workflow stopped.",
            }
        )
        state["gateway_route"] = "human_pipeline_stop"
        return state

    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "gateway_node",
            "action": "claim_email_detected",
            "details": "Haiku classified this email as claim-related. Continue pipeline.",
        }
    )
    state["gateway_route"] = "continue_to_parallel_retrieval"
    return state


def parallel_retrieval_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 3 (3a/3b/3c): fetch customer details, rulebook, and communication drafts.
    """
    ingest_metadata = state.get("ingest_metadata", {})
    customer_id = ingest_metadata.get("customer_id", "")

    # 3a: customer details retrieval
    customer_context = fetch_customer_claim_context(customer_id)
    state["customer_database_record"] = {
        "customer_id": customer_context.get("customer_id", customer_id),
        "contract_details": customer_context.get("contract_status", ""),
        "payment_history": customer_context.get("payment_history", []),
        "policy_id": f"POL-{customer_id}" if customer_id else "",
        "policy_status": customer_context.get("contract_status", ""),
        "customer_profile": {
            "customer_name": customer_context.get("customer_name", ""),
            "email": customer_context.get("email", ""),
            "claim_type": customer_context.get("claim_type", ""),
        },
    }

    # 3b: decision rulebook retrieval
    decision_rulebook = fetch_claim_decision_rulebook()
    state["decision_rulebook"] = {
        "rulebook_id": decision_rulebook.get("rulebook_id", ""),
        "version": decision_rulebook.get("version", ""),
        "content": str(decision_rulebook),
        "fetched_from": "mock_rulebook_service",
        "fetched_at": _utc_now(),
    }
    state["customer_details_rulebook"] = {
        "rulebook_id": "RB-CLAIMS-INTAKE-001",
        "version": "2026.04",
        "content": str(fetch_claim_email_checklist()),
        "fetched_from": "mock_intake_service",
        "fetched_at": _utc_now(),
    }

    # 3c: communication drafts retrieval
    drafts = fetch_communication_drafts()
    state["need_more_info_communication_draft"] = {
        "draft_id": "DRAFT-NEED-MORE-INFO-001",
        "draft_type": "need_more_info",
        "subject": "Additional Information Required for Claim",
        "body": drafts.get("need_more_info_draft", ""),
        "channel": "email",
        "fetched_at": _utc_now(),
    }
    state["standard_decision_communication_drafts"] = [
        {
            "draft_id": "DRAFT-APPROVAL-001",
            "draft_type": "approval",
            "subject": "Claim Approved",
            "body": drafts.get("approval_draft", ""),
            "channel": "email",
            "fetched_at": _utc_now(),
        },
        {
            "draft_id": "DRAFT-REJECTION-001",
            "draft_type": "rejection",
            "subject": "Claim Rejected",
            "body": drafts.get("rejection_draft", ""),
            "channel": "email",
            "fetched_at": _utc_now(),
        },
        {
            "draft_id": "DRAFT-PARTIAL-001",
            "draft_type": "partial_approval",
            "subject": "Claim Partially Approved",
            "body": drafts.get("partial_approval_draft", ""),
            "channel": "email",
            "fetched_at": _utc_now(),
        },
    ]

    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "parallel_retrieval_node",
            "action": "retrieval_complete",
            "details": "Fetched customer context, rulebooks, and communication drafts in parallel lanes.",
        }
    )
    return state


def classification_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 4: check completeness; route to need-more-info (human verify) or decision node.
    """
    ingest_metadata = state.get("ingest_metadata", {})
    customer_pdf = state.get("customer_incident_pdf", {})
    checklist_data = fetch_claim_email_checklist()
    completeness_checklist = (
        checklist_data.get("is_claim_email_required_signals", [])
        + checklist_data.get("required_documents_for_decision", [])
    )
    metadata_for_check = {
        "customer_id": ingest_metadata.get("customer_id"),
        "customer_email": ingest_metadata.get("customer_email"),
        "claim_amount": ingest_metadata.get("claim_amount"),
        "incident_date": ingest_metadata.get("incident_date"),
        "incident_details": customer_pdf.get("incident_details"),
        "required_proofs": customer_pdf.get("required_proofs", []),
        "contract_reference": state.get("customer_database_record", {}).get("policy_id"),
    }
    missing_items = _haiku_missing_info_check(metadata_for_check, completeness_checklist)

    if missing_items:
        customer_name = customer_pdf.get("customer_name", "Customer")
        state["needs_more_info_message"] = build_more_info_email(customer_name, missing_items)
        state["workflow_route"] = "human_verification_need_more_info"
        state["final_claim_decision"] = {
            "status": "needs_more_info",
            "reason": f"Missing checklist items: {', '.join(missing_items)}",
            "decided_at": _utc_now(),
            "decided_by": "classification_node_haiku",
        }
        state.setdefault("audit_log", []).append(
            {
                "event_time": _utc_now(),
                "actor": "classification_node",
                "action": "needs_more_info_routed",
                "details": "Haiku detected missing information; draft prepared for human verification.",
            }
        )
        return state

    state["workflow_route"] = "continue_to_decision_node"
    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "classification_node",
            "action": "complete_data_detected",
            "details": "All checklist information available; case routed to decision node.",
        }
    )
    return state


def _sonnet_decision_reasoning(context: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        claim_type = context.get("claim_type", "")
        claim_amount = float(context.get("claim_amount", 0) or 0)
        contract_status = context.get("contract_status", "")
        if contract_status != "active":
            return {
                "status": "rejected",
                "approved_amount": 0.0,
                "reason": "Policy inactive based on customer contract status.",
            }
        if "water_damage" in claim_type and claim_amount > 20000:
            return {
                "status": "partial",
                "approved_amount": 18000.0,
                "reason": "Renovation-related components are out of coverage scope.",
                "partial_explanation": "Core water damage approved, upgrade costs excluded.",
            }
        return {
            "status": "approved",
            "approved_amount": claim_amount,
            "reason": "Policy active and claim aligns with coverage checklist.",
        }

    client = Anthropic(api_key=api_key)
    prompt = (
        "You are an insurance adjudication assistant.\n"
        "Read the provided context and decide one status: approved, rejected, or partial.\n"
        "Return strict JSON with keys: status, approved_amount, reason, partial_explanation.\n\n"
        f"Context:\n{context}"
    )
    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=300,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    content = ""
    if response.content:
        content = getattr(response.content[0], "text", "") or ""
    # Lightweight fallback parse for robustness in mock flow.
    normalized = content.lower()
    if "partial" in normalized:
        return {
            "status": "partial",
            "approved_amount": context.get("claim_amount", 0),
            "reason": content.strip() or "Partial approval after Sonnet reasoning.",
            "partial_explanation": "See Sonnet rationale.",
        }
    if "reject" in normalized:
        return {
            "status": "rejected",
            "approved_amount": 0.0,
            "reason": content.strip() or "Rejected after Sonnet reasoning.",
        }
    return {
        "status": "approved",
        "approved_amount": context.get("claim_amount", 0),
        "reason": content.strip() or "Approved after Sonnet reasoning.",
    }


def decision_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 5: Sonnet decides approve/reject/partial with detailed context.
    """
    if state.get("workflow_route") != "continue_to_decision_node":
        return state

    customer_record = state.get("customer_database_record", {})
    incident = state.get("customer_incident_pdf", {})
    context = {
        "customer_id": customer_record.get("customer_id"),
        "claim_type": customer_record.get("customer_profile", {}).get("claim_type"),
        "claim_amount": incident.get("claim_amount"),
        "contract_status": customer_record.get("contract_details"),
        "payment_history": customer_record.get("payment_history"),
        "rulebook": state.get("decision_rulebook", {}).get("content"),
    }
    result = _sonnet_decision_reasoning(context)
    requested_amount = float(incident.get("claim_amount", 0) or 0)
    approved_amount = float(result.get("approved_amount", 0) or 0)

    state["final_claim_decision"] = {
        "status": result.get("status", "pending_review"),
        "reason": result.get("reason", ""),
        "approved_amount": approved_amount,
        "rejected_amount": max(requested_amount - approved_amount, 0.0),
        "partial_explanation": result.get("partial_explanation", ""),
        "decided_at": _utc_now(),
        "decided_by": "decision_node_sonnet",
    }
    state["workflow_route"] = "human_in_the_loop_review"
    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "decision_node",
            "action": "sonnet_decision_created",
            "details": f"Decision={result.get('status')} generated with full context for human review.",
        }
    )
    return state


def human_in_the_loop_node(state: InsuranceClaimStates, human_approved: bool = True) -> InsuranceClaimStates:
    """
    Node 6: send Sonnet decision and draft to human reviewer.
    """
    if state.get("workflow_route") not in {"human_in_the_loop_review", "human_verification_need_more_info"}:
        return state

    decision_status = state.get("final_claim_decision", {}).get("status", "pending_review")
    drafts = state.get("standard_decision_communication_drafts", [])
    selected_draft = next(
        (d for d in drafts if d.get("draft_type") in {decision_status, "partial_approval"} and decision_status in d.get("draft_type", "")),
        None,
    )
    if decision_status == "needs_more_info":
        selected_draft = state.get("need_more_info_communication_draft")

    state["human_review_packet"] = {
        "decision": state.get("final_claim_decision", {}),
        "draft": selected_draft or {},
        "context": {
            "customer_incident_pdf": state.get("customer_incident_pdf", {}),
            "customer_database_record": state.get("customer_database_record", {}),
            "decision_rulebook": state.get("decision_rulebook", {}),
        },
    }
    state["human_review_status"] = "approved" if human_approved else "changes_requested"
    state["workflow_route"] = (
        "trigger_communication" if human_approved else "await_human_corrections"
    )
    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "human_in_the_loop_node",
            "action": "human_review_completed",
            "details": f"Human review status={state['human_review_status']}.",
        }
    )
    return state


def partial_cases_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 7: track recurring partial patterns and propose checklist updates after 10 repeats.
    """
    decision = state.get("final_claim_decision", {})
    if decision.get("status") != "partial":
        return state

    customer_profile = state.get("customer_database_record", {}).get("customer_profile", {})
    claim_type = customer_profile.get("claim_type", "unknown_claim_type")
    pattern_key = f"partial_pattern::{claim_type}"
    tracker = state.setdefault("partial_pattern_tracker", {})
    tracker[pattern_key] = int(tracker.get(pattern_key, 0)) + 1
    occurrence_count = tracker[pattern_key]

    state.setdefault("partial_case_judgements_for_finetuning", []).append(
        {
            "case_id": state.get("customer_database_record", {}).get("customer_id", "unknown_case"),
            "judgement_notes": decision.get("reason", ""),
            "features_used": [claim_type, "partial_approval", "human_validated_context"],
            "final_outcome": "partial",
            "tagged_for_finetuning": occurrence_count >= 10,
            "stored_at": _utc_now(),
        }
    )

    if occurrence_count >= 10:
        state["partial_learning_suggestion"] = {
            "pattern": pattern_key,
            "occurrence_count": occurrence_count,
            "suggested_rule_update": (
                "Recurring partial approvals detected. Add finer rule coverage for this pattern "
                "and route to human for approval before checklist update."
            ),
            "requires_human_confirmation": True,
        }

    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "partial_cases_node",
            "action": "partial_case_pattern_tracked",
            "details": f"Tracked {pattern_key}, count={occurrence_count}.",
        }
    )
    return state


def trigger_communication_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 8: Haiku triggers customer communication after human approval.
    """
    if state.get("workflow_route") != "trigger_communication":
        return state

    decision = state.get("final_claim_decision", {})
    customer_name = state.get("customer_incident_pdf", {}).get("customer_name", "Customer")
    claim_type = state.get("customer_database_record", {}).get("customer_profile", {}).get("claim_type", "claim")
    drafts = fetch_communication_drafts()
    sent_message = ""

    if decision.get("status") == "approved":
        sent_message = drafts["approval_draft"].format(
            customer_name=customer_name,
            claim_type=claim_type,
            approved_amount=decision.get("approved_amount", 0),
        )
    elif decision.get("status") == "rejected":
        sent_message = drafts["rejection_draft"].format(
            customer_name=customer_name,
            reason=decision.get("reason", "Not covered under policy."),
        )
    elif decision.get("status") == "partial":
        sent_message = drafts["partial_approval_draft"].format(
            customer_name=customer_name,
            approved_amount=decision.get("approved_amount", 0),
            reason=decision.get("reason", ""),
        )
    elif decision.get("status") == "needs_more_info":
        sent_message = state.get("needs_more_info_message", "")

    state["outbound_customer_communication"] = {
        "sent_via": "haiku_email_trigger",
        "sent_at": _utc_now(),
        "message": sent_message,
    }
    state["workflow_route"] = "log_updates"
    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "trigger_communication_node",
            "action": "customer_communication_triggered",
            "details": "Approved human-reviewed communication sent to customer.",
        }
    )
    return state


def log_node(state: InsuranceClaimStates) -> InsuranceClaimStates:
    """
    Node 9: write audit trail, DB updates, and partial learning context.
    """
    decision = state.get("final_claim_decision", {})
    customer_id = state.get("customer_database_record", {}).get("customer_id", "unknown_customer")
    state.setdefault("database_history_updates", []).append(
        {
            "update_time": _utc_now(),
            "table_name": "claim_decision_history",
            "record_id": customer_id,
            "operation": "update",
            "status": "success",
            "error_message": "",
        }
    )
    state.setdefault("audit_log", []).append(
        {
            "event_time": _utc_now(),
            "actor": "log_node",
            "action": "decision_persisted",
            "details": (
                f"Persisted status={decision.get('status')} with reason={decision.get('reason', '')} "
                "and updated learning/rulebook context for partial cases if applicable."
            ),
        }
    )
    state["workflow_route"] = "completed"
    return state
