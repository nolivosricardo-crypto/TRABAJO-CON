"""Lectura de comprobantes electrónicos desde texto (.md convertido de PDF/ZIP, .txt) o PDF."""
import re
import subprocess
from pathlib import Path

CLAVE_RE = re.compile(r"(?<!\d)\d{49}(?!\d)")
NUM = r"(-?\d[\d,]*[.,]\d{2})"


def normalizar(texto: str) -> str:
    """Quita tablas markdown y espacios repetidos; una línea por renglón con contenido."""
    out = []
    for linea in texto.splitlines():
        linea = linea.replace("|", " ")
        linea = re.sub(r"-{3,}", " ", linea)
        linea = re.sub(r"\s+", " ", linea).strip()
        if linea:
            out.append(linea)
    return "\n".join(out)


def leer_md(ruta) -> dict:
    """Divide el .md producido al convertir un ZIP ('## File: ...') en {archivo: texto}."""
    texto = Path(ruta).read_text(encoding="utf-8")
    bloques = re.split(r"\n## File: ", "\n" + texto)
    archivos = {}
    for b in bloques[1:]:
        nombre, _, cuerpo = b.partition("\n")
        nombre = nombre.strip()
        if "__MACOSX" in nombre or nombre.endswith(".DS_Store"):
            continue
        archivos[Path(nombre).name] = normalizar(cuerpo)
    if not archivos:  # .md/.txt de un solo comprobante
        archivos[Path(ruta).name] = normalizar(texto)
    return archivos


def leer_pdf(ruta) -> str:
    """Texto de un PDF con pdftotext (poppler). Requiere el binario instalado."""
    r = subprocess.run(["pdftotext", "-layout", str(ruta), "-"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext falló en {ruta}: {r.stderr.strip()}")
    return normalizar(r.stdout)


def dividir_paginas(paginas, nombre) -> list:
    """Agrupa las páginas de un PDF con varias facturas. Una página con clave de 49 dígitos abre una factura;
    las páginas con texto pero sin clave (totales que se desbordan) se anexan a la anterior; las vacías se ignoran.
    Devuelve [(f'{nombre}#pAA' o '#pAA-BB', texto)]."""
    grupos = []
    for i, pg in enumerate(paginas, 1):
        if not pg.strip():
            continue
        if CLAVE_RE.search(pg):
            grupos.append({"pag": [i], "txt": [pg]})
        elif grupos:
            grupos[-1]["pag"].append(i)
            grupos[-1]["txt"].append(pg)
    out = []
    for g in grupos:
        a, b = g["pag"][0], g["pag"][-1]
        rango = f"{a:02d}" if a == b else f"{a:02d}-{b:02d}"
        out.append((f"{nombre}#p{rango}", normalizar("\n".join(g["txt"]))))
    return out


def leer_pdf_facturas(ruta) -> dict:
    """{nombre: texto}. Si el PDF trae varias facturas se separan (nombre '#pAA-BB'); si trae una, queda con su nombre."""
    r = subprocess.run(["pdftotext", "-layout", str(ruta), "-"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext falló en {ruta}: {r.stderr.strip()}")
    nombre = Path(ruta).name
    grupos = dividir_paginas(r.stdout.split("\f"), nombre)
    if len(grupos) <= 1:
        return {nombre: normalizar(r.stdout)}
    return dict(grupos)


def leer_directorio(ruta) -> dict:
    """{nombre: texto} de todos los PDF/MD/TXT de una carpeta (no recursivo en subcarpetas ocultas)."""
    d = {}
    for p in sorted(Path(ruta).rglob("*")):
        if "__MACOSX" in p.parts or not p.is_file():
            continue
        if p.suffix.lower() == ".pdf":
            d.update(leer_pdf_facturas(p))
        elif p.suffix.lower() in (".md", ".txt"):
            d.update(leer_md(p))
    return d


def _num(m):
    if not m:
        return None
    v = m.group(1)
    if re.search(r",\d{2}$", v):          # decimal con coma (p. ej. 34,78 o 1.234,56)
        v = v.replace(".", "").replace(",", ".")
    return float(v.replace(",", ""))


def _buscar(patron, texto, flags=0):
    return re.search(patron, texto, flags)


def extraer_campos(texto: str, archivo: str = "") -> dict:
    """Extrae los campos de una factura electrónica ya normalizada. Faltantes quedan en None."""
    d = {"archivo": archivo, "advertencias": []}
    claves = CLAVE_RE.findall(texto)
    d["clave"] = claves[0] if claves else None
    if len(set(claves)) > 1:
        d["advertencias"].append("Más de una clave de 49 dígitos en el comprobante")

    m = _buscar(r"\bNo\.?\s*(\d{3}-\d{3}-\d{9})", texto) or _buscar(r"(\d{3}-\d{3}-\d{9})", texto)
    d["numero"] = m.group(1) if m else None

    m = _buscar(r"R\.?\s?U\.?\s?C\.?\s*:?\s*(\d{13})", texto)
    d["ruc_emisor"] = m.group(1) if m else None

    d["proveedor"] = _proveedor(texto, d["clave"])

    m = _buscar(r"Raz[oó]n Social / Nombres y Apellidos:?\s*([^\n]+)", texto)
    d["receptor"] = m.group(1).strip() if m else None
    if d["receptor"] is None:   # formato SIFACON: "Razón Social <nombre>" e "Identificación: <id>"
        m = _buscar(r"Raz[oó]n Social\s+([^\n]+)", texto)
        d["receptor"] = m.group(1).strip() if m else None
    if d["receptor"]:   # nombre partido en varias líneas / pegado a "Identificación:"
        d["receptor"] = re.split(r"\s+Identificaci[oó]n", d["receptor"])[0].strip()
        m = _buscar(r"Identificaci[oó]n:?\s+\d{10,13}[^\n]*\n([A-ZÁÉÍÓÚÑ ]+)\nDirecci[oó]n", texto)
        if m:
            d["receptor"] = f"{d['receptor']} {m.group(1).strip()}"
    m = _buscar(r"Identificaci[oó]n:?\s+(\d{10,13})", texto) or _buscar(r"RUC\s*/\s*CI:?\s*(\d{10,13})", texto)
    d["id_receptor"] = m.group(1) if m else None
    m = _buscar(r"Raz[oó]n Social:\s*(.*?)\s+RUC/CI:\s*(\d{10,13})", texto)   # formato "Razón Social: X RUC/CI: N"
    if m:
        d["receptor"] = d["receptor"] or m.group(1).strip()
        d["id_receptor"] = d["id_receptor"] or m.group(2)

    m = _buscar(r"Fecha\s+(\d{2}/\d{2}/\d{4})\s+Placa", texto) or _buscar(r"\b(\d{2}/\d{2}/\d{4})\b", texto)
    d["fecha"] = m.group(1) if m else None

    d["subtotal"] = _num(_buscar(r"SUBTOTAL SIN IMPUESTOS?:?[\s$]+" + NUM, texto, re.I))
    iva = _buscar(r"\bIVA\s*\d+(?:[.,]\d+)?\s*%:?[\s$]+" + NUM, texto)
    d["iva"] = _num(iva) if iva else 0.0
    d["total"] = _num(_buscar(r"(?:VALOR|IMPORTE) TOTAL(?!\s+SIN):?[\s$]+" + NUM, texto, re.I))
    if d["subtotal"] is None and d["total"] is not None:
        d["subtotal"] = round(d["total"] - d["iva"], 2)
        d["advertencias"].append("Subtotal calculado como total - IVA (no se encontró 'SUBTOTAL SIN IMPUESTOS')")
    sc = [_num(re.match(NUM, v)) for v in re.findall(r"Seguro Campesino:?\s+(\S+)", texto) if re.match(NUM, v)]
    d["otros_cargos"] = max(sc) if sc and max(sc) > 0 else 0.0   # aporte Seguro Campesino: suma al total sin ser IVA
    d["descripcion"] = _descripcion(texto)
    d["texto"] = texto
    for campo in ("clave", "numero", "fecha", "subtotal", "total", "receptor", "id_receptor"):
        if d[campo] is None:
            d["advertencias"].append(f"No se pudo leer: {campo}")
    return d


def _proveedor(texto, clave):
    """Razón social del emisor. Soporta el nombre en una o dos líneas, tanto en el .md convertido
    como en el texto de pdftotext (donde la 2.ª línea termina en 'AUTORIZACIÓN: dd/mm/aaaa hh:mm:ss')."""
    lineas = texto.splitlines()
    if not clave:
        return None
    for i, l in enumerate(lineas):
        if clave in l and i + 1 < len(lineas):
            nombre = re.sub(r"\s*FECHA Y HORA DE\s*$", "", lineas[i + 1]).strip()
            for k in (i + 2, i + 3):   # posible continuación del nombre antes de 'AUTORIZACIÓN:'
                if k < len(lineas):
                    m = re.match(r"^(.*?)\s*AUTORIZACI[OÓ]N:?\s*(?:\d{2}/\d{2}/\d{4}.*)?$", lineas[k])
                    if m and m.group(1).strip() and not re.match(r"^\d{2}/\d{2}/\d{4}", m.group(1).strip()):
                        nombre = f"{nombre} {m.group(1).strip()}"
                        break
            return nombre or None
    return None


_UNIDADES = {"ML", "MM", "G", "GR", "KG", "L", "OZ", "U", "UN", "X", "CM"}


def _limpiar(desc: str) -> str:
    """Quita códigos de producto, cantidades sueltas y repeticiones; conserva medidas (250 ML, 22x25, 1OZ)."""
    toks, out = desc.split(), []
    for i, t in enumerate(toks):
        sig = toks[i + 1].upper().strip(".") if i + 1 < len(toks) else ""
        if re.fullmatch(r"-?\d+(\.\d+)?", t) and sig not in _UNIDADES:
            continue                                   # número suelto (código/cantidad)
        if re.fullmatch(r"[A-Za-z]{0,4}\d{4,}[A-Za-z0-9-]*", t) or re.fullmatch(r"[A-Za-z]{1,3}\d{2,}[A-Za-z]+\d*", t):
            continue                                   # código tipo FE740617-1289523 / T63RSB02
        if re.fullmatch(r"[A-Za-z-]+-", t) and out and out[-1] == t:
            continue
        if out and out[-1] == t:
            continue                                   # repetición inmediata
        out.append(t)
    limpio = " ".join(out)
    limpio = re.sub(r"\b(?:\d{2}-PROD-|TERM-|PGMD-|PMPZ-)\s*", "", limpio)
    return re.sub(r"\s+", " ", limpio).strip(" -")


def _descripcion(texto):
    m = re.search(r"Principal Auxiliar Subsidio\n(.*?)\n(?:SUBTOTAL|Informaci[oó]n Adicional)", texto, re.S)
    if not m:   # formato SIFACON: el detalle va tras "Descuento Precio Total" (o "Unitario")
        m = re.search(r"(?:Descuento Precio Total|Principal[^\n]*Unitario)\n(.*?)\nSUBTOTAL", texto, re.S)
    if not m:   # formato con "Total Sin Impuestos" y bloque "INFORMACIÓN ADICIONAL"
        m = re.search(r"Impuestos\n(.*?)\nINFORMACI[OÓ]N ADICIONAL", texto, re.S)
    if not m:
        return None
    bruto = re.sub(r"\bnull\b", " ", m.group(1))
    bruto = re.sub(r"\s+", " ", bruto.replace("\n", " "))
    bruto = re.sub(r"^(?:Principal )?(?:Unitario )?", "", bruto)
    bruto = re.sub(r"^Principal Unitario\s*", "", bruto)
    bruto = re.sub(r"\b\d+[.,]\d{2,4}\b", " ", bruto)     # precios
    return _limpiar(bruto)[:200] or None
