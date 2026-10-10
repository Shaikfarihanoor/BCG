from pathlib import Path
from typing import Union
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


def sanitize_text(text: str) -> str:
    """Ensure text is safe for ReportLab's standard type 1 fonts.
    Replaces non-latin1 characters with safe equivalents to avoid crashes.
    """
    if not text:
        return ""
    # Try encoding to latin-1, replace unsupported characters with ?
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_certificate_pdf(
    output_path: Union[str, Path],
    recipient_name: str,
    event_name: str,
    issue_date: str,
    cert_id: str,
) -> Path:
    """Generate a high-quality landscape A4 certificate PDF.

    Args:
        output_path: Destination path where PDF will be saved.
        recipient_name: Name of recipient to display prominently.
        event_name: Name of the event, workshop, or course.
        issue_date: Date string to display.
        cert_id: Unique UUID of the certificate for verification.

    Returns:
        Path to the generated PDF.
    """
    target_path = Path(output_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Sanitize strings for standard PDF canvas
    safe_name = sanitize_text(recipient_name.strip())
    safe_event = sanitize_text(event_name.strip())
    safe_date = sanitize_text(issue_date.strip())
    safe_id = sanitize_text(str(cert_id).strip())

    # A4 Landscape dimensions: width = 841.89, height = 595.27
    width, height = landscape(A4)

    # Initialize canvas
    c = canvas.Canvas(str(target_path), pagesize=landscape(A4))
    c.setTitle(f"Certificate - {safe_name}")
    c.setAuthor("Bulk Certificate Generator")
    c.setSubject(safe_event)

    # Color Palette
    navy = colors.HexColor("#0F284E")
    gold = colors.HexColor("#C59B27")
    light_gold = colors.HexColor("#F9F4E8")
    slate = colors.HexColor("#475569")
    dark_gray = colors.HexColor("#1E293B")
    border_gold = colors.HexColor("#D4AF37")

    # 1. Background subtle tint
    c.setFillColor(colors.HexColor("#FAFAFA"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer & Inner Borders
    # Outer Border
    c.setStrokeColor(navy)
    c.setLineWidth(4)
    c.rect(24, 24, width - 48, height - 48)

    # Inner Border
    c.setStrokeColor(border_gold)
    c.setLineWidth(1.5)
    c.rect(30, 30, width - 60, height - 60)

    # Corner decorative squares
    corner_size = 12
    c.setFillColor(border_gold)
    for x in [24, width - 24 - corner_size]:
        for y in [24, height - 24 - corner_size]:
            c.rect(x, y, corner_size, corner_size, fill=1, stroke=0)

    # 3. Header / Organization Badge
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(gold)
    c.drawCentredString(width / 2.0, height - 70, "EXCELLENCE & RECOGNITION")

    # 4. Certificate Main Title
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(navy)
    c.drawCentredString(width / 2.0, height - 115, "CERTIFICATE OF COMPLETION")

    # Thin accent rule
    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(width / 2.0 - 150, height - 130, width / 2.0 + 150, height - 130)

    # 5. Presentation text
    c.setFont("Helvetica", 13)
    c.setFillColor(slate)
    c.drawCentredString(width / 2.0, height - 165, "THIS IS PROUDLY PRESENTED TO")

    # 6. Recipient Name (with dynamic font auto-shrinking)
    max_name_width = width - 160  # Maximum horizontal room
    name_font_size = 36
    font_name = "Helvetica-Bold"

    # Shrink font until it fits comfortably
    name_width = stringWidth(safe_name, font_name, name_font_size)
    while name_width > max_name_width and name_font_size > 14:
        name_font_size -= 2
        name_width = stringWidth(safe_name, font_name, name_font_size)

    c.setFont(font_name, name_font_size)
    c.setFillColor(navy)
    c.drawCentredString(width / 2.0, height - 225, safe_name)

    # Recipient underline
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.setLineWidth(1)
    c.line(width / 2.0 - 220, height - 240, width / 2.0 + 220, height - 240)

    # 7. Reason / Event description
    c.setFont("Helvetica", 12)
    c.setFillColor(slate)
    c.drawCentredString(width / 2.0, height - 280, "for successfully demonstrating competence and fulfilling all requirements of")

    # Event Name
    event_font_size = 22
    event_width = stringWidth(safe_event, "Helvetica-Bold", event_font_size)
    while event_width > max_name_width and event_font_size > 12:
        event_font_size -= 2
        event_width = stringWidth(safe_event, "Helvetica-Bold", event_font_size)

    c.setFont("Helvetica-Bold", event_font_size)
    c.setFillColor(gold)
    c.drawCentredString(width / 2.0, height - 325, safe_event)

    # 8. Signatures & Date Section (Lower half)
    # Left: Date
    date_x = 130
    sig_y = 120
    c.setStrokeColor(dark_gray)
    c.setLineWidth(1)
    c.line(date_x - 60, sig_y, date_x + 120, sig_y)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(navy)
    c.drawCentredString(date_x + 30, sig_y - 18, safe_date)
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawCentredString(date_x + 30, sig_y - 32, "DATE OF ISSUANCE")

    # Right: Signature line
    sig_x = width - 190
    c.setStrokeColor(dark_gray)
    c.setLineWidth(1)
    c.line(sig_x - 90, sig_y, sig_x + 90, sig_y)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(navy)
    c.drawCentredString(sig_x, sig_y - 18, "AUTHORIZED SIGNATURE")
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawCentredString(sig_x, sig_y - 32, "PROGRAM DIRECTOR")

    # Center: Seal rosette / badge representation
    center_y = sig_y - 10
    c.setFillColor(light_gold)
    c.circle(width / 2.0, center_y, 28, fill=1, stroke=0)
    c.setStrokeColor(gold)
    c.setLineWidth(2)
    c.circle(width / 2.0, center_y, 28, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(gold)
    c.drawCentredString(width / 2.0, center_y - 3, "VERIFIED")

    # 9. Certificate ID Reference at Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawCentredString(width / 2.0, 42, f"Certificate ID: {safe_id}")

    # Finalize and write PDF
    c.showPage()
    c.save()

    return target_path
