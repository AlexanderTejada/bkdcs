# app/utils/text_processor.py
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def preprocess_text(text):
    """
    Preprocesa el texto para corregir errores ortográficos comunes usando regex.
    """
    logging.info(f"Preprocesando texto original: {text}")
    text = text.lower()
    text = re.sub(r'\bk\w*', lambda m: m.group(0).replace('k', 'qu') if 'k' in m.group(0) else m.group(0).replace('k', 'c'), text)
    text = re.sub(r'\bz\w*', lambda m: m.group(0).replace('z', 's') if 'z' in m.group(0) else m.group(0), text)
    text = re.sub(r'\bx\w*', lambda m: m.group(0).replace('x', 's') if 'x' in m.group(0) else m.group(0).replace('x', 'j'), text)
    text = re.sub(r'\b(k|q)uier[oa]|kere\b', 'quiero', text)
    text = re.sub(r'\b(ak|ac)tua(l|ll)?(l|ll)?iz(ar|er)|aktuali[zs]ar\b', 'actualizar', text)
    text = re.sub(r'\b(rek|rec|rel)al[mo]|reclamoo?\b', 'reclamo', text)
    text = re.sub(r'\b(kom|con|kol)sul(tar|tar)|consul[dt]ar\b', 'consultar', text)
    text = re.sub(r'\b(ha|as)cer|aser\b', 'hacer', text)
    text = re.sub(r'\b(direk|dier|dir)ec(c|k)ion|direcsion\b', 'direccion', text)
    text = re.sub(r'\b(est|es)tadoo?\b', 'estado', text)
    text = re.sub(r'(\w*?)([aeiou])\2(\w*)', r'\1\2\3', text)
    text = re.sub(r'(\w)r(\w)e', r'\1er\2', text)
    logging.info(f"Texto preprocesado: {text}")
    return text