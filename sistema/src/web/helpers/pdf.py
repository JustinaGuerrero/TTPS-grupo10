"""PDFs a partir de plantillas Jinja, con xhtml2pdf (S12).

    pdf = pdf_desde_plantilla("pdf/orden_extraccion.html", turno=turno)
    return respuesta_pdf(pdf, "orden-de-extraccion.pdf")

Las plantillas van en templates/pdf/ y no extienden layout.html: xhtml2pdf entiende HTML y CSS
simples (sin flexbox ni Bootstrap). Lo usan la orden de extracción y el consentimiento (E19) y
el resultado del estudio (E35).
"""

import io

from flask import Response, render_template
from xhtml2pdf import pisa


class ErrorDePdf(Exception):
    """xhtml2pdf no pudo armar el PDF."""


def pdf_desde_plantilla(plantilla: str, **contexto) -> bytes:
    """Renderiza la plantilla y la convierte en un PDF. Lanza ErrorDePdf si falla."""
    html = render_template(plantilla, **contexto)
    salida = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=salida, encoding="utf-8")
    if resultado.err:
        raise ErrorDePdf(f"No se pudo generar el PDF de {plantilla}.")
    return salida.getvalue()


def respuesta_pdf(pdf: bytes, nombre: str, descargar: bool = False) -> Response:
    """Respuesta HTTP con el PDF: se abre en el navegador o, con `descargar`, se baja."""
    disposicion = "attachment" if descargar else "inline"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre}"'},
    )
