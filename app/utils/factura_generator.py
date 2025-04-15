# app/utils/factura_generator.py
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
import time
from PIL import Image, ImageDraw, ImageFont
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(BASE_DIR, "static")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Ajusta si usas Windows o Mac

def safe_decimal(valor):
    try:
        return f"{Decimal(valor):.2f}"
    except (InvalidOperation, TypeError):
        return "No disponible"

def safe_fecha(fecha_str):
    try:
        return datetime.fromisoformat(fecha_str).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return "No disponible"

def generate_factura_image(factura=None, dni=None):
    try:
        factura = factura or {
            'NumeroComprobante': 123456,
            'Periodo': '04/2024',
            'TotalFactura': '157.89',
            'FechaEmision': '2024-04-01T00:00:00',
            'VencimientoFactura': '2024-04-15T00:00:00',
            'Nombre': 'AGUILAR CARMEN',
            'CodigoSuministro': 1435,
            'EstadoFactura': 'P',
            'Calle': 'LAPRIDA',
            'Barrio': 'CENTRO',
            'ObservacionPostal': 'Suministro: 19041001 BARRIO: CENTRO',
            'NumeroMedidor': '01084469',
            'Consumo': '110.00'
        }

        dni = dni or '8067472'
        timestamp = int(time.time())
        image_filename = f"factura_{timestamp}.png"
        image_path = os.path.join(STATIC_DIR, image_filename)

        # Crear imagen base
        width, height = 600, 800
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Cargar fuente
        try:
            font_title = ImageFont.truetype(FONT_PATH, 24)
            font = ImageFont.truetype(FONT_PATH, 18)
        except IOError:
            font_title = font = ImageFont.load_default()

        y = 20
        draw.text((width//2 - 180, y), "Factura de Servicios Eléctricos", fill="black", font=font_title)
        y += 40
        draw.text((width//2 - 130, y), "Distribuidora Eléctrica de Caucete S.A.", fill="black", font=font)
        y += 40

        def line(text):
            nonlocal y
            draw.text((40, y), text, fill="black", font=font)
            y += 30

        # Datos
        line(f"Titular: {factura.get('Nombre')}")
        line(f"DNI: {dni}")
        line(f"▌ DATOS DE FACTURACIÓN")
        line(f"N° de cuenta: {factura.get('CodigoSuministro')}")
        line(f"N° Comprobante: {factura.get('NumeroComprobante')}")
        line(f"Fecha de Emisión: {safe_fecha(factura.get('FechaEmision'))}")
        line(f"Estado: {factura.get('EstadoFactura')}")
        line(f"Importe Total: ${safe_decimal(factura.get('TotalFactura'))}")
        line(f"Vencimiento: {safe_fecha(factura.get('VencimientoFactura'))}")
        line(f"▌ UBICACIÓN")
        line(f"Dirección: {factura.get('Calle')}, {factura.get('Barrio')}")
        line(f"Observación Postal: {factura.get('ObservacionPostal')}")
        line(f"▌ INFORMACIÓN DEL SUMINISTRO")
        line(f"N° de Medidor: {factura.get('NumeroMedidor')}")
        line(f"Periodo: {factura.get('Periodo')}")
        line(f"Consumo: {safe_decimal(factura.get('Consumo'))} kWh")

        # Footer
        y += 40
        draw.text((40, y), "Gracias por elegir DECSA. Si tienes consultas, contáctanos.", fill="gray", font=font)

        image.save(image_path)
        logging.info(f"Factura generada en {image_path}")
        return image_path

    except Exception as e:
        logging.error(f"Error generando factura: {str(e)}")
        raise
