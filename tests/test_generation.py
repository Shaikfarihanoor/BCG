from pathlib import Path
from app.services.certificate_generator import generate_certificate_pdf


def test_certificate_pdf_generation(tmp_path):
    output_pdf = tmp_path / "test_cert.pdf"
    result = generate_certificate_pdf(
        output_path=output_pdf,
        recipient_name="Alexander Hamilton",
        event_name="Constitutional Law Seminar 2026",
        issue_date="2026-10-10",
        cert_id="12345678-1234-5678-1234-567812345678",
    )

    assert result.exists()
    assert result.is_file()
    assert result.stat().st_size > 0

    with open(result, "rb") as f:
        header = f.read(5)
        assert header.startswith(b"%PDF")


def test_certificate_very_long_name_scaling(tmp_path):
    # A very long recipient name should trigger the dynamic font shrinker
    long_name = (
        "Professor Dr. Wolfeschlegelsteinhausenbergerdorffvoralternwarengewissenhaft "
        "Senior Chancellor of Advanced Engineering and Applied Systems"
    )
    output_pdf = tmp_path / "test_long_cert.pdf"
    result = generate_certificate_pdf(
        output_path=output_pdf,
        recipient_name=long_name,
        event_name="Grand Honorary Convocation 2026",
        issue_date="2026-10-10",
        cert_id="87654321-4321-8765-4321-876543210987",
    )

    assert result.exists()
    assert result.stat().st_size > 0
    with open(result, "rb") as f:
        assert f.read(4) == b"%PDF"
