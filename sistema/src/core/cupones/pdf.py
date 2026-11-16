"""PDF del cupón. El módulo de cupones solo entrega el código, así que el sistema arma el PDF.

Lleva el código numérico como texto (de ahí lo lee codigo_desde_pdf, G7) y como código QR.
"""

import io
from decimal import Decimal

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TAMANO_DEL_QR = 150


def pdf_del_cupon(codigo: str, porcentaje: Decimal) -> bytes:
    salida = io.BytesIO()
    lienzo = canvas.Canvas(salida, pagesize=A4)
    _, alto = A4
    lienzo.setFont("Helvetica-Bold", 20)
    lienzo.drawString(72, alto - 100, "Cupón de descuento")
    lienzo.setFont("Helvetica", 14)
    lienzo.drawString(72, alto - 140, f"Descuento: {porcentaje.normalize():f}%")
    lienzo.drawString(72, alto - 170, f"Código: {codigo}")
    qr = QrCodeWidget(codigo)
    x0, y0, x1, y1 = qr.getBounds()
    dibujo = Drawing(
        TAMANO_DEL_QR,
        TAMANO_DEL_QR,
        transform=[TAMANO_DEL_QR / (x1 - x0), 0, 0, TAMANO_DEL_QR / (y1 - y0), 0, 0],
    )
    dibujo.add(qr)
    renderPDF.draw(dibujo, lienzo, 72, alto - 360)
    lienzo.setFont("Helvetica", 10)
    lienzo.drawString(72, alto - 390, "Vence a los 30 días de su generación. Se usa una sola vez.")
    lienzo.drawString(72, alto - 405, "Ingresalo o subí este PDF al pagar tu estudio.")
    lienzo.save()
    return salida.getvalue()
