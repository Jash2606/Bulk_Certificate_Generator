"""The single predefined certificate template, drawn as a landscape A4 PDF with ReportLab."""
import uuid
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN = 36  # points (1/2 inch) between the page edge and the outer border
MAX_TEXT_WIDTH = PAGE_WIDTH - 4 * MARGIN  # text must stay well inside the borders
NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#B08D57")


def render_certificate(
    *,
    certificate_id: uuid.UUID,
    recipient_name: str,
    course_name: str,
    issue_date: date,
    issued_by: str | None,
    output_path: Path,
) -> Path:
    """Draw one certificate and save it to output_path, replacing any earlier file at that path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.setTitle(f"Certificate of Completion - {recipient_name}")

    # Double border: thick navy outside, thin gold inside.
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(4)
    pdf.rect(MARGIN, MARGIN, PAGE_WIDTH - 2 * MARGIN, PAGE_HEIGHT - 2 * MARGIN)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)
    inset = MARGIN + 10
    pdf.rect(inset, inset, PAGE_WIDTH - 2 * inset, PAGE_HEIGHT - 2 * inset)

    _draw_centered(pdf, "CERTIFICATE OF COMPLETION", "Times-Bold", 36, y=455, color=NAVY)
    _draw_centered(pdf, "This is to certify that", "Times-Italic", 18, y=395)
    _draw_centered(pdf, recipient_name, "Times-BoldItalic", 40, y=335, color=NAVY)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.line(PAGE_WIDTH / 2 - 220, 320, PAGE_WIDTH / 2 + 220, 320)
    _draw_centered(pdf, "has successfully completed", "Times-Italic", 18, y=280)
    _draw_centered(pdf, course_name, "Times-Bold", 26, y=235, color=NAVY)

    issued = f"Issued on {issue_date:%d %B %Y}"
    if issued_by:
        issued += f" by {issued_by}"
    _draw_centered(pdf, issued, "Times-Roman", 15, y=175)
    _draw_centered(pdf, f"Certificate ID: {certificate_id}", "Helvetica", 9, y=MARGIN + 28, color=colors.grey)

    pdf.showPage()
    pdf.save()
    return output_path


def fit_font_size(text: str, font: str, max_size: float) -> float:
    """Largest font size (up to max_size) at which text fits within MAX_TEXT_WIDTH.

    Text width grows linearly with font size, so the size that fits is a simple proportion.
    """
    width = stringWidth(text, font, max_size)
    return max_size if width <= MAX_TEXT_WIDTH else max_size * MAX_TEXT_WIDTH / width


def _draw_centered(
    pdf: Canvas, text: str, font: str, max_size: float, *, y: float, color: colors.Color = colors.black
) -> None:
    pdf.setFont(font, fit_font_size(text, font, max_size))
    pdf.setFillColor(color)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, text)
