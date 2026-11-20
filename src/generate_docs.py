"""Generate 40 synthetic ElectroMart Indore policy docs.

Deliberately includes duplicates, outdated versions and contradictions.
Writes data/raw/*.txt (what the pipeline reads) and data/ground_truth.json
(answer key used ONLY for evaluation and the admin conflict checker).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# (doc_id, version, dept, effective_date, title, body, note)
# note = ground-truth label: "current", "outdated", "duplicate", "conflict"
DOCS = [
("RET-001", "v1", "Returns", "2024-01-01", "Return Policy",
 "Customers may return products within 7 days of delivery if the item is unused and in original packaging. Refunds are processed after inspection.", "outdated"),
("RET-001", "v2", "Returns", "2025-04-01", "Return Policy",
 "Customers may return any product within 10 days of delivery if it is unused and in original packaging. A return pickup is arranged free of charge within Indore.", "outdated"),
("RET-001", "v3", "Returns", "2026-02-01", "Return Policy",
 "Electronics may be returned within 10 days of delivery. Accessories (cases, cables, chargers) may be returned within 15 days. Items must be unused, with original packaging and invoice. Free pickup is available within Indore city limits; outside Indore the customer ships the item at their own cost.", "current"),
("RET-002", "v1", "Returns", "2025-06-15", "Return Process SOP",
 "Step 1: Agent verifies the order ID and delivery date. Step 2: Agent checks the item is eligible under the current Return Policy. Step 3: Agent raises a return ticket and schedules pickup. Step 4: Warehouse inspects the item within 2 working days. Step 5: Refund is initiated if inspection passes.", "current"),
("RET-003", "v1", "Returns", "2025-06-15", "Non-Returnable Items",
 "The following cannot be returned: software licences and gift cards, products with broken seals on memory cards or SSDs, customised or engraved products, and items damaged by the customer. Opened earphones can be returned only if defective, for hygiene reasons.", "current"),
("RET-004", "v1", "Returns", "2024-03-01", "Refund Timelines",
 "Refunds are credited within 7 working days after the returned item passes inspection.", "outdated"),
("RET-004", "v2", "Returns", "2026-01-10", "Refund Timelines",
 "| Payment method | Refund time |\n|---|---|\n| UPI | 2 working days |\n| Debit/Credit card | 5-7 working days |\n| Net banking | 5 working days |\n| Store wallet | Instant |\n| Cash on delivery | 5 working days by bank transfer |\nTimelines start after the returned item passes inspection.", "current"),
("RET-005", "v1", "Returns", "2024-02-01", "Returns FAQ",
 "Q: How long do I have to return an item? A: You have 7 days from delivery. Q: How long do refunds take? A: Refunds are credited within 3 working days. Q: Is pickup free? A: Yes, everywhere in India.", "conflict"),
("RET-006", "v1", "Returns", "2025-09-01", "Dead on Arrival (DOA) Policy",
 "If a product is dead on arrival (does not power on or is physically broken), report it within 48 hours of delivery with an unboxing video. A replacement is shipped within 3 working days after verification. Refund is offered only if no replacement stock is available.", "current"),
("WAR-001", "v1", "Warranty", "2024-01-01", "Warranty Policy",
 "Smartphones carry a 12 month manufacturer warranty. Laptops carry a 12 month warranty. Accessories carry a 6 month warranty.", "outdated"),
("WAR-001", "v2", "Warranty", "2025-08-01", "Warranty Policy",
 "| Category | Warranty |\n|---|---|\n| Smartphones | 12 months |\n| Laptops | 24 months |\n| Televisions | 24 months |\n| Accessories | 6 months |\nWarranty starts on the invoice date and requires the original invoice.", "current"),
("WAR-002", "v1", "Warranty", "2025-08-01", "Warranty Claim SOP",
 "Step 1: Ask for the invoice and serial number. Step 2: Confirm the product is within warranty. Step 3: Run the basic troubleshooting checklist. Step 4: If unresolved, register a claim and send the item to the authorised service centre. Step 5: Repairs take 7 to 14 working days; inform the customer of the ticket number.", "current"),
("WAR-003", "v1", "Warranty", "2025-10-01", "ElectroCare Extended Warranty",
 "ElectroCare adds 12 months of coverage after the standard warranty ends. It costs 8 percent of the product price for smartphones and 6 percent for laptops. ElectroCare must be bought within 30 days of purchase and covers hardware faults only.", "current"),
("WAR-004", "v1", "Warranty", "2025-08-01", "Warranty Exclusions",
 "Warranty does not cover physical damage, liquid damage, unauthorised repairs, burnt components from power surges, or software problems caused by third-party apps. Cosmetic wear such as scratches is not covered.", "current"),
("WAR-005", "v1", "Warranty", "2024-02-01", "Warranty FAQ",
 "Q: What warranty do laptops have? A: Laptops have a 12 month warranty. Q: Do I need the invoice? A: Yes. Q: How long does a repair take? A: Within 5 working days.", "conflict"),
("WAR-006", "v1", "Warranty", "2025-11-01", "Water and Liquid Damage Policy",
 "Liquid damage voids the manufacturer warranty. Customers with ElectroCare Plus (a separate plan) get one free liquid damage repair per year. Standard ElectroCare does not cover liquid damage.", "current"),
("ORD-001", "v1", "Orders", "2025-05-01", "Order Cancellation Policy",
 "Orders can be cancelled free of charge any time before they are dispatched. After dispatch, the customer must refuse delivery or use the return process. Prepaid cancellations are refunded to the original payment method.", "current"),
("ORD-002", "v1", "Orders", "2025-05-01", "Order Modification",
 "Delivery address can be changed only before dispatch and only within Indore pin codes. Product variant or colour changes require cancelling and re-ordering. Phone number changes must be verified by OTP.", "current"),
("ORD-003", "v1", "Orders", "2025-05-01", "Order Tracking FAQ",
 "Customers receive an SMS with a tracking link once the order is dispatched. Tracking updates every few hours. If tracking has not moved for 48 hours, escalate to the logistics team.", "current"),
("ORD-004", "v1", "Orders", "2025-07-01", "Bulk Order SOP",
 "Orders of 10 or more units are bulk orders. Route them to the B2B desk. Bulk customers get a quotation within 1 working day, need a GST number for invoicing, and pay 50 percent in advance. Discounts above 5 percent need manager approval.", "current"),
("ORD-006", "v1", "Orders", "2024-02-01", "Cancellation FAQ",
 "Q: Until when can I cancel my order? A: Only within 2 hours of placing it. Q: Is there a cancellation fee? A: Yes, 5 percent of the order value.", "conflict"),
("PAY-001", "v1", "Payments", "2025-03-01", "Accepted Payment Methods",
 "ElectroMart accepts UPI, debit and credit cards, net banking, store wallet and cash on delivery. Cash on delivery is available only for orders up to Rs 30,000 within Indore.", "current"),
("PAY-002", "v1", "Payments", "2024-06-01", "EMI Policy",
 "No-cost EMI is available on purchases of Rs 5,000 and above for select credit cards, with tenures of 3 and 6 months.", "outdated"),
("PAY-002", "v2", "Payments", "2026-01-15", "EMI Policy",
 "No-cost EMI is available on purchases of Rs 10,000 and above for select credit cards, with tenures of 3, 6 and 9 months. Debit card EMI is available for purchases above Rs 15,000. A processing fee of Rs 199 applies to debit card EMI.", "current"),
("PAY-003", "v1", "Payments", "2025-03-01", "Payment Failure Handling",
 "If money is debited but the order is not confirmed, the amount is automatically refunded within 5 to 7 working days. Agents must not retry the payment on the customer's behalf. If no refund arrives after 7 working days, raise a payment ticket with the transaction ID.", "current"),
("PAY-004", "v1", "Payments", "2025-12-01", "Card Data Handling SOP (PCI-DSS)",
 "Agents must never ask for, record or repeat full card numbers, CVV or PIN, in chat, email or call notes. If a customer shares card details, tell them not to, and delete the message where possible. Only the last 4 digits of a card may be referenced. Payments are completed only on the secure checkout page.", "current"),
("PAY-005", "v1", "Payments", "2025-03-01", "GST Invoice Policy",
 "A GST invoice can be requested at checkout or within 7 days of delivery by providing a valid GSTIN. Invoices cannot be changed to a different GSTIN after 7 days.", "current"),
("PAY-006", "v1", "Payments", "2025-12-01", "Refund Destination Rules",
 "Refunds go to the original payment method by default. Customers may choose the store wallet for an instant refund. Cash on delivery refunds are sent by bank transfer and need the account holder's name and IFSC; never accept bank details over chat without verifying the order.", "current"),
("DEL-001", "v1", "Delivery", "2024-05-01", "Delivery Timelines",
 "Orders within Indore are delivered the next working day. Other cities take 3 to 5 working days.", "outdated"),
("DEL-001", "v2", "Delivery", "2026-03-01", "Delivery Timelines",
 "Orders placed before 2 PM within Indore are delivered the same day. Orders after 2 PM are delivered the next working day. Other cities in Madhya Pradesh take 2 to 3 working days; the rest of India takes 4 to 6 working days.", "current"),
("DEL-002", "v1", "Delivery", "2025-04-01", "Delivery Charges",
 "Delivery is free for orders above Rs 999. Orders below Rs 999 pay Rs 49 within Indore and Rs 99 elsewhere. Express same-day delivery costs an extra Rs 79.", "current"),
("DEL-003", "v1", "Delivery", "2025-04-01", "Failed Delivery SOP",
 "The courier makes up to 3 delivery attempts on consecutive working days. After 3 failed attempts the parcel is returned to the warehouse and the customer is contacted. Reshipping after a failed delivery costs Rs 99 unless the failure was our fault.", "current"),
("DEL-004", "v1", "Delivery", "2025-10-15", "Installation Service",
 "Free installation is included for televisions of 32 inches and above, air conditioners and washing machines within Indore. Installation is scheduled within 2 working days of delivery. Wall mounting brackets are charged separately.", "current"),
("DEL-005", "v1", "Delivery", "2024-05-15", "Delivery FAQ",
 "Q: When will my Indore order arrive? A: Next working day. Q: Is delivery free? A: Delivery is free on orders above Rs 499.", "conflict"),
("SUP-001", "v1", "Support", "2025-02-01", "Support Hours",
 "Phone and chat support runs from 9 AM to 9 PM, Monday to Saturday. Sunday support is by email only, with replies within 24 hours.", "current"),
("SUP-002", "v1", "Support", "2025-02-01", "Escalation SOP",
 "Level 1 agents handle queries for up to 15 minutes. Unresolved cases go to Level 2 (team lead). Refunds above Rs 20,000 and legal threats go to the store manager. Consumer court notices must be forwarded to legal within 24 hours.", "current"),
("SUP-003", "v1", "Support", "2025-12-01", "Customer Data Privacy SOP (DPDP Act)",
 "Personal data such as phone number, address, email and Aadhaar must be used only for the order or service it was collected for. Agents must verify identity with the order ID and registered phone OTP before sharing order details. Never share one customer's data with another person. Do not store customer data in personal notes or messaging apps.", "current"),
("SUP-004", "v1", "Support", "2025-12-01", "Data Deletion Requests",
 "Customers may request deletion of their personal data. Verify identity first, then log the request with the privacy officer. Data is deleted within 30 days, except invoice records that must be kept for 8 years under tax law. Confirm completion to the customer by email.", "current"),
("SUP-005", "v1", "Support", "2025-06-01", "Loyalty Programme",
 "ElectroMart Rewards gives 1 point per Rs 100 spent. 100 points equal Rs 50 of store wallet credit. Points expire 12 months after they are earned and cannot be earned on gift cards.", "current"),
("SUP-006", "v1", "Support", "2025-06-01", "Store Locations and Pickup",
 "ElectroMart has two stores in Indore: Vijay Nagar and Palasia. Store pickup is free and available 2 hours after ordering online. Bring a government photo ID and the order confirmation SMS. Pickup orders are held for 5 days.", "current"),
]

HEADER = "ELECTROMART INDORE | INTERNAL USE ONLY | CONFIDENTIAL"
FOOTER = "Page 1 of 1 | ElectroMart Retail Pvt Ltd | Do not distribute"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    truth = []
    for doc_id, ver, dept, date, title, body, note in DOCS:
        fname = f"{doc_id}_{ver}.txt"
        text = (
            f"{HEADER}\n"
            f"Doc ID: {doc_id} | Version: {ver} | Department: {dept} | Effective: {date}\n\n"
            f"{title}\n\n{body}\n\n{FOOTER}\n"
        )
        (RAW / fname).write_text(text, encoding="utf-8")
        truth.append({"file": fname, "doc_id": doc_id, "version": ver,
                      "department": dept, "effective_date": date,
                      "title": title, "label": note})
    (ROOT / "data" / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print(f"Wrote {len(DOCS)} documents to {RAW}")


if __name__ == "__main__":
    main()
