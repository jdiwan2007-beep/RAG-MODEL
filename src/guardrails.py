"""Input/output guardrails: DPDP-style PII redaction and PCI-DSS card-data blocking."""
import re

def _luhn(num: str) -> bool:
    digits = [int(d) for d in num][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
                for i, d in enumerate(digits))
    return total % 10 == 0

CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CVV = re.compile(r"(?i)\b(?:cvv|cvc|pin)\b\D{0,6}\d{3,6}")
AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

PCI_MESSAGE = ("For your security, please don't share card numbers, CVV or PINs here. "
               "I can't process or store them. Complete payments only on the secure "
               "checkout page. Ask me again without the card details and I'll help.")


def screen_input(text: str) -> dict:
    """Returns {'text': redacted, 'found': [types], 'blocked': bool, 'message': str|None}."""
    found, out = [], text

    def sub_card(m):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found.append("card")
            return "[CARD REMOVED]"
        return m.group()
    out = CARD.sub(sub_card, out)

    if CVV.search(out):
        found.append("cvv")
        out = CVV.sub("[CVV REMOVED]", out)

    for name, pat, tag in [("aadhaar", AADHAAR, "[AADHAAR]"), ("pan", PAN, "[PAN]"),
                           ("phone", PHONE, "[PHONE]"), ("email", EMAIL, "[EMAIL]")]:
        if pat.search(out):
            found.append(name)
            out = pat.sub(tag, out)

    blocked = "card" in found or "cvv" in found
    return {"text": out, "found": found, "blocked": blocked,
            "message": PCI_MESSAGE if blocked else None}


def redact_output(text: str) -> str:
    """Last line of defence: never let PII-like strings leave in an answer."""
    return screen_input(text)["text"]
