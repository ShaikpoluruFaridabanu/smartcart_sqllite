from xhtml2pdf import pisa
from io import BytesIO


def generate_pdf(template_html):
    """Convert HTML string to PDF BytesIO buffer."""
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(template_html, dest=pdf)
    if pisa_status.err:
        return None
    return pdf

