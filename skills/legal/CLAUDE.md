# Commercial Contracts Practice Profile

This is the configuration/playbook profile for the legal domain. All legal specialist agents read this before performing evaluations.

---

## Who we are

**Company Name:** Tiny Steward Inc.
**Final Escalation Point:** General Counsel (GC)
**CLM System:** Local File-based Register

---

## Who's using this

**Role:** Lawyer / legal professional
**Attorney contact:** N/A (Directly managed by counsel)

---

## Playbook

**Active side:** both

### Sales-side playbook
*Applies when the company is the vendor. Usually our paper.*

#### Limitation of liability
- **Direct cap:** 12 months fees paid or payable.
- **Indirect/consequential damages:** Excluded.
- **Acceptable carveouts:** Gross negligence, willful misconduct, breach of confidentiality, IP indemnity.
- **Never accept:** Uncapped indirect damages.

#### Indemnification
- **Standard position:** We indemnify for IP infringement claims arising from our service. Customer indemnifies for its data and use of the service.

#### Term and termination
- **Standard position:** Annual term, auto-renewing, 30-day notice to cancel.

#### Governing law and venue
- **Preferred:** Delaware.
- **Acceptable:** New York.
- **Never accept:** Counterparty's state (unless New York/Delaware).

---

### Purchasing-side playbook
*Applies when the company is the customer. Usually their paper.*

#### Limitation of liability
- **Direct cap:** Vendor liability capped at 2x fees paid or payable in the 12 months preceding the claim.
- **Indirect/consequential damages:** Excluded, except for breach of confidentiality, data breach, and IP indemnity.
- **Carveouts required:** Vendor's gross negligence, willful misconduct, breach of confidentiality, data breach, IP indemnity.
- **Never accept:** Vendor liability capped at 3 months fees or less.

#### Indemnification
- **Standard position:** Vendor indemnifies us for IP infringement and data breach. We indemnify vendor only for our unauthorized use of vendor's IP.

#### Term and termination
- **Standard position:** Termination for convenience on 30 days' notice.

#### Governing law and venue
- **Preferred:** Delaware.
- **Acceptable:** New York, California.
- **Never accept:** Foreign countries.

---

## Escalation Matrix

| Can approve | Threshold | Escalates to | Via |
|---|---|---|---|
| Contracts Manager | Standard terms, <$50K | Counsel | Slack |
| Counsel | Non-standard terms, <$250K | GC | Slack or email |
| GC | Everything else | CFO/Board | Meeting |

**Automatic escalation triggers (regardless of dollar value):**
- Unlimited liability
- IP assignment of our core technology to the counterparty
- Anything on a "Never accept" list above

---

## Outputs format

Prepended work-product header:
`PRIVILEGED & CONFIDENTIAL — ATTORNEY WORK PRODUCT — PREPARED AT THE DIRECTION OF COUNSEL`
