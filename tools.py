from typing import Any


# Production API would call a customer-service endpoint like:
# GET /api/v1/customers/{customer_id}/claim-context
def fetch_customer_claim_context(customer_id: str) -> dict[str, Any]:
    mock_db = {
        "CUST-1001": {
            "customer_id": "CUST-1001",
            "customer_name": "Aisha Verma",
            "email": "aisha.verma@example.com",
            "claim_type": "vehicle_damage",
            "claim_amount": 12000.0,
            "payment_history": ["on_time", "on_time", "on_time", "on_time"],
            "contract_status": "active",
            "policy_tenure_years": 4,
        },
        "CUST-2002": {
            "customer_id": "CUST-2002",
            "customer_name": "Rahul Mehta",
            "email": "rahul.mehta@example.com",
            "claim_type": "home_water_damage",
            "claim_amount": 25000.0,
            "payment_history": ["on_time", "late_7_days", "on_time", "on_time"],
            "contract_status": "active",
            "policy_tenure_years": 2,
        },
    }
    return mock_db.get(customer_id, {})


# Production API would fetch rulebook docs from a policy/rules engine:
# GET /api/v1/rulebooks/claims/{rulebook_name}
def fetch_claim_decision_rulebook() -> dict[str, Any]:
    return {
        "rulebook_id": "RB-CLAIMS-DECISION-001",
        "version": "2026.04",
        "approve_rules": [
            "Policy must be active",
            "Claim amount must be within insured limit",
            "No fraud flags for customer",
            "Minimum required documents are valid",
        ],
        "reject_rules": [
            "Policy inactive or expired",
            "Claim event not covered under policy",
            "Clear fraud signal detected",
            "Critical mandatory document missing after reminder window",
        ],
        "partial_rules": [
            "Part of claim is out of policy coverage",
            "Damage estimate exceeds approved benchmark",
        ],
    }


# Production API would fetch email templates from a template service:
# GET /api/v1/communications/templates?domain=claims
def fetch_communication_drafts() -> dict[str, str]:
    return {
        "approval_draft": (
            "Subject: Claim Approved\n"
            "Dear {customer_name}, your claim for {claim_type} has been approved "
            "for INR {approved_amount}. The payout will be processed in 3-5 days."
        ),
        "rejection_draft": (
            "Subject: Claim Rejected\n"
            "Dear {customer_name}, we are unable to approve your claim due to: "
            "{reason}. You may appeal within 15 days."
        ),
        "partial_approval_draft": (
            "Subject: Claim Partially Approved\n"
            "Dear {customer_name}, your claim has been partially approved for INR "
            "{approved_amount}. Non-approved amount reason: {reason}."
        ),
        "need_more_info_draft": (
            "Subject: Additional Information Required for Claim\n"
            "Dear {customer_name}, we received your email and need more details: "
            "{missing_items}. Please share within 7 days."
        ),
    }


# Production API would fetch workflow checklist from claims-intake service:
# GET /api/v1/claims/intake/checklist
def fetch_claim_email_checklist() -> dict[str, list[str]]:
    return {
        "is_claim_email_required_signals": [
            "Incident description present",
            "Incident date present",
            "Claim amount mentioned",
            "Customer identity details available",
        ],
        "required_documents_for_decision": [
            "Government ID proof",
            "Policy/contract reference",
            "Incident evidence (photos/reports)",
            "Cost estimate or invoice",
        ],
    }


# Production API would call an NLP/classification endpoint:
# POST /api/v1/claims/intake/classify-email
def classify_if_claim_email(email_text: str) -> bool:
    text = email_text.lower()
    keywords = ["claim", "incident", "damage", "policy", "reimbursement"]
    return any(word in text for word in keywords)


# Production API would call a response-orchestration endpoint:
# POST /api/v1/claims/intake/draft-more-info
def build_more_info_email(customer_name: str, missing_items: list[str]) -> str:
    drafts = fetch_communication_drafts()
    template = drafts["need_more_info_draft"]
    return template.format(customer_name=customer_name, missing_items=", ".join(missing_items))


# Production API would come from an adjudication engine:
# GET /api/v1/claims/examples?scenario=approved,partial
def get_customer_examples() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "CASE-APR-001",
            "decision": "approved",
            "customer_context": fetch_customer_claim_context("CUST-1001"),
            "approved_amount": 12000.0,
            "reason": "All required documents valid and claim fully covered.",
        },
        {
            "case_id": "CASE-PAR-002",
            "decision": "partial_approved",
            "customer_context": fetch_customer_claim_context("CUST-2002"),
            "approved_amount": 18000.0,
            "requested_amount": 25000.0,
            "reason": "Water damage covered, but renovation upgrades not covered.",
        },
    ]
