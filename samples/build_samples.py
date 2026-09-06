"""Generate the sample documents used for manual and end-to-end testing.

One content definition produces a PDF, a DOCX and a TXT so all three parser
paths can be exercised on comparable material.

    python samples/build_samples.py
"""
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent

HR_POLICY = {
    "title": "HR Leave Policy (POL-4417)",
    "pages": [
        [
            ("Annual Leave", [
                "Full-time employees receive 20 days of paid annual leave each calendar year.",
                "Leave accrues monthly at a rate of 1.67 days per completed month of service.",
                "A maximum of 5 unused days may be carried into the following year.",
            ]),
            ("Eligibility", [
                "Employees become eligible for paid annual leave after 90 days of continuous service.",
                "Contractors and interns are not covered by this policy.",
            ]),
        ],
        [
            ("Parental Leave", [
                "Primary caregivers are entitled to 26 weeks of parental leave at full pay.",
                "Secondary caregivers are entitled to 8 weeks of parental leave at full pay.",
                "Requests must be submitted at least 30 days before the intended start date.",
            ]),
            ("Sick Leave", [
                "Employees receive 12 days of paid sick leave per year.",
                "A medical certificate is required for absences longer than 3 consecutive days.",
            ]),
        ],
        [
            ("Approval Process", [
                "Leave requests are approved by the reporting manager within 5 working days.",
                "Requests longer than 10 consecutive days also require department head approval.",
                "Policy reference POL-4417 must be quoted in any escalation.",
            ]),
        ],
    ],
}

FINANCE_POLICY = {
    "title": "Expense Reimbursement Policy (FIN-2291)",
    "pages": [
        [
            ("Reimbursable Expenses", [
                "Employees may claim travel, accommodation and client entertainment expenses.",
                "The daily meal per-diem is 45 USD for domestic travel and 75 USD internationally.",
                "Receipts are mandatory for any single expense above 25 USD.",
            ]),
            ("Submission Deadlines", [
                "Expense claims must be submitted within 30 days of the expense being incurred.",
                "Claims submitted after 60 days are rejected without exception.",
            ]),
        ],
        [
            ("Approval Limits", [
                "Managers may approve claims up to 2,000 USD under cost code FIN-2291.",
                "Claims above 2,000 USD require finance director approval.",
                "Cash advances are issued only for international travel exceeding 7 days.",
            ]),
        ],
    ],
}

SECURITY_POLICY = {
    "title": "Information Security Policy (SEC-8834)",
    "pages": [
        [
            ("Password Requirements", [
                "Passwords must be at least 14 characters long and include mixed character types.",
                "Multi-factor authentication is mandatory for all administrative accounts.",
                "Passwords are rotated every 180 days.",
            ]),
            ("Incident Reporting", [
                "Suspected security incidents must be reported to the security team within 1 hour.",
                "Incident ticket SEC-8834 templates are available on the internal portal.",
                "Employees must not investigate suspected phishing emails themselves.",
            ]),
        ],
    ],
}


def _page_lines(page: list[tuple[str, list[str]]]) -> list[tuple[str, bool]]:
    """Flatten a page into (text, is_heading) pairs."""
    lines: list[tuple[str, bool]] = []
    for heading, paragraphs in page:
        lines.append((heading, True))
        lines.extend((paragraph, False) for paragraph in paragraphs)
    return lines


def write_txt(document: dict, path: Path) -> None:
    """Write a TXT sample; form feeds mark page breaks."""
    pages = []
    for page in document["pages"]:
        block = "\n\n".join(text for text, _ in _page_lines(page))
        pages.append(block)
    path.write_text("\f".join(pages), encoding="utf-8")


def write_docx(document: dict, path: Path) -> None:
    """Write a DOCX sample using real Word heading styles."""
    import docx

    docx_document = docx.Document()
    docx_document.add_heading(document["title"], level=0)
    for page in document["pages"]:
        for text, is_heading in _page_lines(page):
            if is_heading:
                docx_document.add_heading(text, level=1)
            else:
                docx_document.add_paragraph(text)
    docx_document.save(str(path))


def write_pdf(document: dict, path: Path) -> None:
    """Write a multi-page PDF sample, one PDF page per content page."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    width, height = LETTER
    pdf = canvas.Canvas(str(path), pagesize=LETTER)
    for page in document["pages"]:
        cursor = height - 72
        for text, is_heading in _page_lines(page):
            pdf.setFont("Helvetica-Bold" if is_heading else "Helvetica", 14 if is_heading else 11)
            for line in _wrap(text, 90):
                pdf.drawString(72, cursor, line)
                cursor -= 16
            cursor -= 8
        pdf.showPage()
    pdf.save()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def main() -> None:
    write_pdf(HR_POLICY, SAMPLES_DIR / "hr_policy.pdf")
    write_txt(FINANCE_POLICY, SAMPLES_DIR / "finance_policy.txt")
    write_docx(SECURITY_POLICY, SAMPLES_DIR / "security_policy.docx")
    print(f"Sample documents written to {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
