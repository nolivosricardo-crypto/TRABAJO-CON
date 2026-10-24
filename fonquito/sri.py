"""Clave de acceso SRI (49 dígitos) y dígito verificador Módulo 11."""
from datetime import date

PESOS = (2, 3, 4, 5, 6, 7)
TIPOS = {"01": "Factura", "03": "Liquidación de compra", "04": "Nota de crédito",
         "05": "Nota de débito", "06": "Guía de remisión", "07": "Retención"}


def modulo11(base48: str):
    """Devuelve (dígito, suma ponderada, residuo). Pesos 2..7 de derecha a izquierda."""
    suma = sum(int(c) * PESOS[i % 6] for i, c in enumerate(reversed(base48)))
    residuo = suma % 11
    dv = 0 if residuo == 0 else 1 if residuo == 1 else 11 - residuo
    return dv, suma, residuo


def descomponer(clave: str) -> dict:
    """Separa los campos de una clave de 49 dígitos (lanza ValueError si no es válida en formato)."""
    clave = (clave or "").strip()
    if not (clave.isdigit() and len(clave) == 49):
        raise ValueError("La clave debe tener exactamente 49 dígitos")
    dd, mm, aaaa = int(clave[0:2]), int(clave[2:4]), int(clave[4:8])
    try:
        fecha = date(aaaa, mm, dd)
    except ValueError:
        fecha = None
    dv, suma, residuo = modulo11(clave[:48])
    return {
        "clave": clave, "fecha": fecha, "tipo": clave[8:10], "ruc": clave[10:23],
        "ambiente": clave[23], "serie": clave[24:30], "secuencial": clave[30:39],
        "numero": f"{clave[24:27]}-{clave[27:30]}-{clave[30:39]}",
        "digito_declarado": int(clave[48]), "digito_calculado": dv,
        "suma": suma, "residuo": residuo, "modulo11_ok": dv == int(clave[48]),
    }


def generar_clave(fecha: date, tipo: str, ruc: str, ambiente: str, serie: str,
                  secuencial: str, codigo: str = "12345678", emision: str = "1") -> str:
    """Construye una clave válida (útil para pruebas)."""
    base = f"{fecha:%d%m%Y}{tipo}{ruc}{ambiente}{serie}{secuencial}{codigo}{emision}"
    return base + str(modulo11(base)[0])
