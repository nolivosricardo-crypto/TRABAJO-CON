"""Renombrado de facturas: <No.>_<proveedor/cliente>_<n° factura>.pdf"""
import csv
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


def _limpio(s):
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ &.-]", "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    return s[:40].strip()


def nombre_nuevo(r) -> str:
    n = f"{r['n']:02d}"
    num = r.get("numero") or "SIN-NUMERO"
    if r.get("duplicado_de"):
        return f"{n}_DUPLICADO_{num}.pdf"
    if r.get("modo") == "venta":      # ventas: se nombra por el cliente
        quien = _limpio(r.get("receptor") or r.get("proveedor") or "SIN-NOMBRE")
    else:                             # gastos: se nombra por el proveedor
        quien = _limpio(r.get("proveedor") or r.get("receptor") or "SIN-NOMBRE")
    return f"{n}_{quien}_{num}.pdf"


def extraer_paginas(pdf_bytes: bytes, desde: int, hasta: int) -> bytes:
    """Devuelve un PDF con las páginas desde..hasta (usa pdfseparate/pdfunite de poppler)."""
    with tempfile.TemporaryDirectory() as d:
        entrada = Path(d) / "in.pdf"
        entrada.write_bytes(pdf_bytes)
        subprocess.run(["pdfseparate", "-f", str(desde), "-l", str(hasta), str(entrada), str(Path(d) / "p-%d.pdf")],
                       check=True, capture_output=True)
        if desde == hasta:
            return (Path(d) / f"p-{desde}.pdf").read_bytes()
        partes = [str(Path(d) / f"p-{n}.pdf") for n in range(desde, hasta + 1)]
        salida = Path(d) / "out.pdf"
        subprocess.run(["pdfunite", *partes, str(salida)], check=True, capture_output=True)
        return salida.read_bytes()


def renombrar(regs, origen, destino_zip):
    """Copia los PDF de `origen` (carpeta o .zip) a `destino_zip` con el nombre nuevo.
    Devuelve (renombrados, sin_pdf): archivos sin PDF correspondiente."""
    origen = Path(origen)
    pdfs = {}
    if origen.suffix.lower() == ".pdf":
        pdfs[origen.name] = origen.read_bytes()
    elif origen.suffix.lower() == ".zip":
        with zipfile.ZipFile(origen) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(".pdf") and "__MACOSX" not in info.filename:
                    pdfs[Path(info.filename).name] = z.read(info)
    else:
        for p in origen.rglob("*.pdf"):
            if "__MACOSX" not in p.parts:
                pdfs[p.name] = p.read_bytes()
    ok, falta = [], []
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as out:
        for r in regs:
            base, _, rango = r["archivo"].partition("#p")
            if base not in pdfs:
                falta.append(r["archivo"])
                continue
            if rango:   # una factura dentro de un PDF con varias: se extraen sus páginas
                a, _, b = rango.partition("-")
                contenido = extraer_paginas(pdfs[base], int(a), int(b or a))
            else:
                contenido = pdfs[base]
            out.writestr(nombre_nuevo(r), contenido)
            ok.append((r["archivo"], nombre_nuevo(r)))
    return ok, falta


def exportar_csv(regs, ruta):
    """Tabla de renombrado (abre bien en Excel: UTF-8 con BOM, separador ';')."""
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["No.", "Archivo original", "Nombre nuevo", "Fecha", "Factura", "Total", "Estado"])
        for r in regs:
            fecha = f"{r['fecha_date']:%d/%m/%Y}" if r.get("fecha_date") else ""
            w.writerow([r["n"], r["archivo"], nombre_nuevo(r), fecha, r.get("numero") or "",
                        f"{r['total']:.2f}".replace(".", ",") if r.get("total") is not None else "", r["estado"]])
