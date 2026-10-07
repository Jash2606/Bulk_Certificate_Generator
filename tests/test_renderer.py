"""Certificate generation: the predefined template produces a PDF with the recipient's details."""
import uuid
from datetime import date

from pypdf import PdfReader
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.services.certificate_renderer import MAX_TEXT_WIDTH, fit_font_size, render_certificate


def pdf_text(path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


def test_certificate_pdf_contains_recipient_and_course_details(tmp_path):
    certificate_id = uuid.uuid4()
    output_path = tmp_path / "job" / "certificate.pdf"  # the job folder doesn't exist yet

    result = render_certificate(
        certificate_id=certificate_id,
        recipient_name="José Müller",
        course_name="FastAPI Bootcamp",
        issue_date=date(2026, 10, 8),
        issued_by="Aero Academy",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.read_bytes().startswith(b"%PDF")
    text = pdf_text(output_path)
    assert "CERTIFICATE OF COMPLETION" in text
    assert "José Müller" in text  # Latin accents are supported by the built-in fonts
    assert "FastAPI Bootcamp" in text
    assert "Issued on 08 October 2026 by Aero Academy" in text
    assert str(certificate_id) in text


def test_issuer_line_is_optional(tmp_path):
    output_path = tmp_path / "certificate.pdf"

    render_certificate(
        certificate_id=uuid.uuid4(),
        recipient_name="Asha Rao",
        course_name="FastAPI Bootcamp",
        issue_date=date(2026, 10, 8),
        issued_by=None,
        output_path=output_path,
    )

    text = pdf_text(output_path)
    assert "Issued on 08 October 2026" in text
    assert " by " not in text


def test_long_text_is_shrunk_to_fit_inside_the_border():
    long_name = "Wolfeschlegelsteinhausenbergerdorff " * 2 + "Maximilian Alexander"  # 92 characters

    size = fit_font_size(long_name, "Times-BoldItalic", 40)

    assert size < 40
    assert stringWidth(long_name, "Times-BoldItalic", size) <= MAX_TEXT_WIDTH + 0.01
    assert fit_font_size("Asha Rao", "Times-BoldItalic", 40) == 40  # short text keeps its full size
