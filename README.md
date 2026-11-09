# Insurance Claims Workflow (LangGraph + Claude)

This project implements a multi-step insurance claim workflow using LangGraph state orchestration and Claude models for classification and decision support. It ingests customer claim data, routes claim vs non-claim emails, retrieves internal context, and prepares human-reviewed communication before sending customer updates. The pipeline also tracks audit logs, database updates, and partial-approval learning signals for ongoing rulebook improvement.

## 9-Node Architecture

1. **`ingest_node`**  
   Extracts plain text and metadata from a dummy PDF payload (customer id, email, claim amount, incident date, proofs, etc.) and stores intake state.

2. **`gateway_node` (Haiku)**  
   Checks whether the incoming email is a claim-related email. Non-claim emails are routed to human pipeline and stopped; claim emails continue.

3. **`parallel_retrieval_node` (3a/3b/3c)**  
   Fetches customer database context, decision rulebooks/checklists, and communication drafts in parallel retrieval lanes.

4. **`classification_node` (Haiku)**  
   Verifies whether required information is complete for adjudication. If data is missing, creates a "need more information" draft and routes to human verification.

5. **`decision_node` (Sonnet)**  
   Applies reasoning over customer context + rulebook to classify the case as approved, rejected, or partial approval, with detailed rationale.

6. **`human_in_the_loop_node`**  
   Packages decision, draft, and context for human review/approval before any customer-facing communication is sent.

7. **`partial_cases_node` (Sonnet-assisted pattern tracking)**  
   Maintains partial-approval learning context, tracks recurring patterns, and prepares rulebook update suggestions for human approval after threshold recurrence.

8. **`trigger_communication_node` (Haiku-triggered)**  
   Sends the appropriate approved communication draft (approval/rejection/partial/need-more-info) to the customer.

9. **`log_node`**  
   Persists final audit events, history updates, and learning context (especially for partial approvals) with timestamps.

## Tech Stack

- **Python**
- **LangGraph** (state graph orchestration + `MemorySaver` checkpointing)
- **Claude Haiku** (routing and completeness checks)
- **Claude Sonnet** (decision reasoning and partial-case intelligence)
- **FastAPI** (recommended API layer for exposing this workflow as service endpoints)

## Run Locally

1. Create/activate virtual environment:
   - `python3 -m venv venv`
   - `source venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Set Anthropic key in `.env/.env` (already expected by project):
   - `anthropic_api_key=<your_key>`
4. Run demo pipeline with two dummy customers:
   - `python3 main.py`

This prints:
- claim-email validity decision
- human-approval communication packet
- final decision per customer
- outbound communication content
- audit trail with timestamps
- partial-case learning records

## Industry Applicability

This workflow pattern applies to any domain that needs document intake, AI-assisted triage, human approval, and auditable decision trails, including:

- **Insurance** (claims adjudication, policy exceptions)
- **Banking and Financial Services** (disputes, chargebacks, exception approvals)
- **Healthcare** (prior authorization, claims review)
- **Logistics and Supply Chain** (damage claims, vendor disputes)
- **E-commerce and Marketplaces** (refund/return investigations)
- **Legal and Compliance Operations** (case intake, policy-guided review flows)
