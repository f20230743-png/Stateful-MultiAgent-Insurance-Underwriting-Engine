from typing import Any, Literal, TypedDict


class CustomerIncidentPDF(TypedDict, total=False):
    incident_details: str
    required_proofs: list[str]
    incident_date: str
    claim_amount: float
    customer_name: str
    customer_email: str
    source_file_path: str


class CustomerDatabaseRecord(TypedDict, total=False):
    customer_id: str
    contract_details: str
    payment_history: list[str]
    policy_id: str
    policy_status: str
    customer_profile: dict[str, str]


class RulebookDocument(TypedDict, total=False):
    rulebook_id: str
    version: str
    content: str
    fetched_from: str
    fetched_at: str


class CommunicationDraft(TypedDict, total=False):
    draft_id: str
    draft_type: str
    subject: str
    body: str
    channel: Literal["email", "sms", "portal", "letter"]
    fetched_at: str


class ClaimDecision(TypedDict, total=False):
    status: Literal["approved", "rejected", "partial", "needs_more_info", "pending_review"]
    reason: str
    approved_amount: float
    rejected_amount: float
    partial_explanation: str
    decided_at: str
    decided_by: str


class PartialCaseLearningRecord(TypedDict, total=False):
    case_id: str
    judgement_notes: str
    features_used: list[str]
    final_outcome: str
    tagged_for_finetuning: bool
    stored_at: str


class AuditEvent(TypedDict, total=False):
    event_time: str
    actor: str
    action: str
    details: str


class DatabaseHistoryUpdate(TypedDict, total=False):
    update_time: str
    table_name: str
    record_id: str
    operation: Literal["insert", "update", "delete"]
    status: Literal["success", "failure"]
    error_message: str


class InsuranceClaimStates(TypedDict, total=False):
    customer_incident_pdf: CustomerIncidentPDF
    customer_database_record: CustomerDatabaseRecord
    customer_details_rulebook: RulebookDocument
    need_more_info_communication_draft: CommunicationDraft
    decision_rulebook: RulebookDocument
    standard_decision_communication_drafts: list[CommunicationDraft]
    partial_case_judgements_for_finetuning: list[PartialCaseLearningRecord]
    final_claim_decision: ClaimDecision
    audit_log: list[AuditEvent]
    database_history_updates: list[DatabaseHistoryUpdate]
    ingest_metadata: dict[str, Any]
    gateway_route: str
    workflow_route: str
    needs_more_info_message: str
    human_review_packet: dict[str, Any]
    human_review_status: str
    outbound_customer_communication: dict[str, str]
    partial_learning_suggestion: dict[str, Any]
    partial_pattern_tracker: dict[str, int]
    dummy_pdf_payload: dict[str, Any]
