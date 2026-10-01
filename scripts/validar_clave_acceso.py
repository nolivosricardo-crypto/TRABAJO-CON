#!/usr/bin/env python3
"""Valida la clave de acceso SRI (49 dígitos) de un comprobante electrónico.

Uso:
  validar_clave_acceso.py CLAVE [--ruc RUC] [--tipo gasto|venta]
                                [--desde dd/mm/aaaa --hasta dd/mm/aaaa]

Con --ruc y --tipo se verifica además que el RUC del emprendimiento figure
como emisor (venta). En gasto el receptor no va en la clave, así que solo se
avisa que debe confirmarse contra el comprobante. Sale con código 0 si no hay
errores, 1 si hay errores, 2 si solo hay observaciones.
"""
import argparse
import json
import sys
from datetime import datetime

TIPOS = {"01": "Factura", "03": "Liquidación de compra", "04": "Nota de crédito",
         "05": "Nota de débito", "06": "Guía de remisión", "07": "Retención"}


def digito_verificador(base48: str) -> int:
    pesos = [2, 3, 4, 5, 6, 7]
    suma = sum(int(d) * pesos[i % 6] for i, d in enumerate(reversed(base48)))
    dv = 11 - (suma % 11)
    return 0 if dv == 11 else 1 if dv == 10 else dv


def parse_fecha(txt: str):
    return datetime.strptime(txt, "%d/%m/%Y").date()


def validar(clave, ruc=None, tipo=None, desde=None, hasta=None):
    errores, observaciones = [], []
    clave = (clave or "").strip()
    if not (clave.isdigit() and len(clave) == 49):
        return {"clave": clave, "errores": ["La clave debe tener exactamente 49 dígitos"],
                "observaciones": [], "resultado": "invalido"}

    datos = {
        "fecha_emision": f"{clave[0:2]}/{clave[2:4]}/{clave[4:8]}",
        "tipo_comprobante": clave[8:10],
        "ruc_emisor": clave[10:23],
        "ambiente": clave[23],
        "serie": clave[24:30],
        "secuencial": clave[30:39],
        "codigo_numerico": clave[39:47],
        "tipo_emision": clave[47],
        "digito_verificador": clave[48],
    }
    esperado = digito_verificador(clave[:48])
    if esperado != int(clave[48]):
        errores.append(f"Dígito verificador incorrecto (esperado {esperado}, hay {clave[48]})")

    try:
        fecha = parse_fecha(datos["fecha_emision"])
    except ValueError:
        fecha = None
        errores.append(f"Fecha de emisión inválida en la clave: {datos['fecha_emision']}")

    if datos["tipo_comprobante"] not in TIPOS:
        observaciones.append(f"Tipo de comprobante desconocido: {datos['tipo_comprobante']}")
    elif datos["tipo_comprobante"] != "01":
        observaciones.append(f"Comprobante no es factura: {TIPOS[datos['tipo_comprobante']]}")
    if datos["ambiente"] != "2":
        observaciones.append("Ambiente de pruebas (1); solo producción (2) es válido")

    if desde and hasta and fecha and not (desde <= fecha <= hasta):
        errores.append(f"Fecha {datos['fecha_emision']} fuera del período válido")

    if ruc and tipo == "venta" and datos["ruc_emisor"] != ruc:
        errores.append(f"RUC emisor {datos['ruc_emisor']} distinto al del emprendimiento {ruc}")
    if ruc and tipo == "gasto":
        if datos["ruc_emisor"] == ruc:
            errores.append("En un gasto el emisor no puede ser el propio emprendimiento")
        observaciones.append("Confirmar en el comprobante que el RUC receptor sea el del emprendimiento")

    resultado = "invalido" if errores else "observado" if observaciones else "valido"
    return {"clave": clave, **datos, "errores": errores,
            "observaciones": observaciones, "resultado": resultado}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("clave")
    p.add_argument("--ruc")
    p.add_argument("--tipo", choices=["gasto", "venta"])
    p.add_argument("--desde")
    p.add_argument("--hasta")
    a = p.parse_args()
    desde = parse_fecha(a.desde) if a.desde else None
    hasta = parse_fecha(a.hasta) if a.hasta else None
    r = validar(a.clave, a.ruc, a.tipo, desde, hasta)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(1 if r["errores"] else 2 if r["observaciones"] else 0)


if __name__ == "__main__":
    main()
