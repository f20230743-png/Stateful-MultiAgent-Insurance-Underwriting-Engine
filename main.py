from pprint import pformat

from graph import run_claim_graph
from tools import fetch_communication_drafts


def _customer_payloads() -> list[dict]:
    return [
        {
            "label": "Customer 1 - Approval Case",
            "dummy_pdf_payload": {
                "plain_text": (
                    "Dear Team, I am filing a claim for car bumper damage after an incident.\n"
                    "Incident date: 2026-04-09\nClaim amount: INR 12000\n"
                    "Customer ID: CUST-1001\nEmail: aisha.verma@example.com\n"
                    "Name: Aisha Verma\nAttached proofs: government_id, photos, repair_estimate."
                ),
                "incident_details": "Car bumper damage after minor collision.",
                "required_proofs": ["government_id", "photos", "repair_estimate"],
                "incident_date": "2026-04-09",
                "claim_amount": 12000.0,
                "customer_name": "Aisha Verma",
                "customer_email": "aisha.verma@example.com",
                "customer_id": "CUST-1001",
                "source_file_path": "dummy_claim_customer_1.pdf",
            },
        },
        {
            "label": "Customer 2 - Partial Approval Case",
            "dummy_pdf_payload": {
                "plain_text": (
                    "Dear Team, I am filing a claim for water damage and renovation costs.\n"
                    "Incident date: 2026-04-08\nClaim amount: INR 25000\n"
                    "Customer ID: CUST-2002\nEmail: rahul.mehta@example.com\n"
                    "Name: Rahul Mehta\nAttached proofs: government_id, photos, repair_estimate."
                ),
                "incident_details": "Kitchen water damage due to pipeline leak with renovation request.",
                "required_proofs": ["government_id", "photos", "repair_estimate"],
                "incident_date": "2026-04-08",
                "claim_amount": 25000.0,
                "customer_name": "Rahul Mehta",
                "customer_email": "rahul.mehta@example.com",
                "customer_id": "CUST-2002",
                "source_file_path": "dummy_claim_customer_2.pdf",
            },
        },
    ]


def _print_case_result(title: str, result: dict) -> None:
    print("=" * 90)
    print(title)
    print("=" * 90)

    print("\nVALID CLAIM EMAIL DECISION")
    print(f"- Gateway route: {result.get('gateway_route')}")
    print(f"- Workflow route: {result.get('workflow_route')}")

    print("\nINTERNAL COMMUNICATION DRAFT SENT FOR HUMAN APPROVAL")
    print(pformat(result.get("human_review_packet", {}), sort_dicts=False))

    print("\nFINAL DECISION")
    print(pformat(result.get("final_claim_decision", {}), sort_dicts=False))

    print("\nCOMMUNICATION SENT TO CUSTOMER")
    print(pformat(result.get("outbound_customer_communication", {}), sort_dicts=False))

    print("\nAUDIT LOG (TIMESTAMP + DETAILS)")
    for event in result.get("audit_log", []):
        print(
            f"- {event.get('event_time')} | {event.get('actor')} | "
            f"{event.get('action')} | {event.get('details')}"
        )

    print("\nPARTIAL CASE LEARNING DOCUMENT")
    print(pformat(result.get("partial_case_judgements_for_finetuning", []), sort_dicts=False))
    print("\nPARTIAL LEARNING SUGGESTION FOR HUMAN APPROVAL")
    print(pformat(result.get("partial_learning_suggestion", {}), sort_dicts=False))
    print()


def main() -> None:
    print("STANDARD COMMUNICATION DRAFTS")
    print(pformat(fetch_communication_drafts(), sort_dicts=False))
    print()

    for idx, payload in enumerate(_customer_payloads(), start=1):
        result = run_claim_graph(
            initial_state={"dummy_pdf_payload": payload["dummy_pdf_payload"]},
            thread_id=f"customer-thread-{idx}",
        )
        _print_case_result(payload["label"], result)


if __name__ == "__main__":
    main()
