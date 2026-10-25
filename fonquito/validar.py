"""Reglas de validación de comprobantes (gastos y ventas) de FonQuito Mujer."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from . import sri

# Ítems que suelen indicar consumo personal; se marcan REVISAR (no invalidan). Editable por línea de comandos.
PALABRAS_REVISAR = ["protectores", "afeitadora", "toalla sanitaria", "snack", "takis", "pringles", "chocolate",
                    "cacao", "combo", "cine", "licor", "cerveza", "vino", "whisky", "cigarr", "bebida alcoh"]

TIPO_ADMIN = r"profesional|honorario|asesor|contab|registro sanitario|digesa|informaci[oó]n nutricional|arriendo|internet|telef|software|hosting"
TIPO_VENTAS = r"feria|stand|dominio|p[áa]gina web|encomienda|courier|mensajer|flete|publicidad|marketing|pauta|promoci|evento|delivery"


@dataclass
class Parametros:
    tipo: str                      # "gasto" | "venta"
    ruc: str                       # 13 dígitos del emprendimiento/beneficiario
    emprendedora: str
    desde: date
    hasta: date
    palabras_revisar: list = field(default_factory=lambda: list(PALABRAS_REVISAR))
    tolerancia: float = 0.01       # redondeo aceptado entre subtotal + IVA y total


def parse_fecha(txt: str) -> date:
    return datetime.strptime(txt.strip(), "%d/%m/%Y").date()


def clasificar_gasto(descripcion: str, proveedor: str = "") -> str:
    t = f"{descripcion or ''} {proveedor or ''}".lower()
    if re.search(TIPO_VENTAS, t):
        return "GASTO VENTAS"
    if re.search(TIPO_ADMIN, t):
        return "GASTO ADMINISTRATIVO"
    return "COSTO OPERATIVO"


def validar(campos: dict, p: Parametros) -> dict:
    """Devuelve el registro de validación de un comprobante (campos de extraer.extraer_campos)."""
    r = dict(campos)
    r["modo"] = p.tipo
    obs, soft = [], []
    hard = False
    chk = {"m11": None, "fecha": None, "ruc": None, "receptor": None, "monto": None}
    r["dv_calc"] = r["dv_decl"] = r["suma"] = r["residuo"] = None
    r["fecha_clave"] = r["ruc_clave"] = None

    clave = campos.get("clave")
    info = None
    if not clave:
        obs.append("Sin clave de acceso de 49 dígitos (¿comprobante no electrónico SRI?)")
        hard = True
    else:
        info = sri.descomponer(clave)
        r.update(dv_calc=info["digito_calculado"], dv_decl=info["digito_declarado"], suma=info["suma"],
                 residuo=info["residuo"], fecha_clave=info["fecha"], ruc_clave=info["ruc"])
        chk["m11"] = info["modulo11_ok"]
        if not chk["m11"]:
            obs.append(f"Dígito verificador incorrecto (esperado {info['digito_calculado']}, declarado {info['digito_declarado']})")
            hard = True
        if info["tipo"] != "01":
            soft.append(f"Comprobante no es factura ({sri.TIPOS.get(info['tipo'], info['tipo'])})")
        if info["ambiente"] != "2":
            obs.append("Ambiente de pruebas (1)")
            hard = True
        if campos.get("numero") and campos["numero"] != info["numero"]:
            obs.append(f"Número impreso {campos['numero']} no coincide con el de la clave {info['numero']}")
            hard = True

    # fecha
    f_imp = None
    if campos.get("fecha"):
        try:
            f_imp = parse_fecha(campos["fecha"])
        except ValueError:
            obs.append(f"Fecha impresa ilegible: {campos['fecha']}")
            hard = True
    r["fecha_date"] = f_imp or (info["fecha"] if info else None)
    if info and info["fecha"] and f_imp:
        chk["fecha"] = (info["fecha"] == f_imp) and (p.desde <= f_imp <= p.hasta)
        if info["fecha"] != f_imp:
            obs.append(f"Fecha impresa {f_imp:%d/%m/%Y} distinta a la de la clave {info['fecha']:%d/%m/%Y}")
            hard = True
        if not (p.desde <= f_imp <= p.hasta):
            obs.append(f"FUERA DE PERÍODO ({f_imp:%d/%m/%Y}; válido {p.desde:%d/%m/%Y}-{p.hasta:%d/%m/%Y})")
            hard = True
    elif info and info["fecha"]:
        chk["fecha"] = p.desde <= info["fecha"] <= p.hasta
        if not chk["fecha"]:
            obs.append("FUERA DE PERÍODO")
            hard = True

    # RUC emisor
    if info:
        imp = campos.get("ruc_emisor")
        if imp:
            chk["ruc"] = imp == info["ruc"]
            if not chk["ruc"]:
                obs.append(f"RUC impreso {imp} distinto al de la clave {info['ruc']}")
                hard = True
        else:
            chk["ruc"] = True
            soft.append("RUC del emisor tomado de la clave (no se leyó el impreso)")
        if p.tipo == "venta" and info["ruc"] != p.ruc:
            chk["ruc"] = False
            obs.append(f"RUC EMISOR INCORRECTO (clave {info['ruc']}, esperado {p.ruc})")
            hard = True

    # receptor (gastos) / cliente (ventas)
    idr = campos.get("id_receptor")
    if p.tipo == "gasto":
        if idr is None:
            chk["receptor"] = None
            obs.append("No se leyó la identificación del receptor")
            hard = True
        else:
            chk["receptor"] = idr in (p.ruc, p.ruc[:10])
            if not chk["receptor"]:
                obs.append(f"RECEPTOR INCORRECTO (identificación {idr}, esperado {p.ruc})")
                hard = True
            elif idr != p.ruc:
                soft.append("Receptor identificado con C.I. (10 dígitos) que corresponde al RUC")
            if campos.get("receptor") and not _nombre_coincide(campos["receptor"], p.emprendedora):
                soft.append(f"Nombre del receptor distinto al de la emprendedora ('{campos['receptor']}')" + ("; RUC coincide" if chk["receptor"] else ""))
    else:
        chk["receptor"] = True
        comunes = _apellidos_comunes(campos.get("receptor") or "", p.emprendedora)
        if comunes:
            soft.append("Cliente con apellido en común con la emprendedora (" + ", ".join(sorted(comunes)) +
                        "): posible venta a un familiar; es legítima, se deja constancia")

    # monto
    s, i, t = campos.get("subtotal"), campos.get("iva") or 0.0, campos.get("total")
    if s is None or t is None:
        obs.append("Montos ilegibles")
        hard = True
    else:
        dif = round(s + i - t, 2)
        chk["monto"] = abs(dif) <= p.tolerancia
        otros = campos.get("otros_cargos") or 0.0
        if abs(dif) > p.tolerancia and otros and abs(round(s + i + otros - t, 2)) <= p.tolerancia:
            chk["monto"] = True
            soft.append(f"El total incluye ${otros:.2f} de aporte Seguro Campesino (no es IVA): {s:.2f} + {i:.2f} + {otros:.2f} = {t:.2f}")
        elif p.tolerancia < abs(dif) <= 0.05:
            chk["monto"] = False
            soft.append(f"Diferencia de ${abs(dif):.2f} entre subtotal + IVA y total ({s:.2f} + {i:.2f} ≠ {t:.2f}): "
                        "probable redondeo por ítem del emisor; verificar en el SRI")
        elif abs(dif) > p.tolerancia:
            obs.append(f"MONTO INCONSISTENTE: {s:.2f} + {i:.2f} = {s + i:.2f} ≠ {t:.2f}")
            hard = True
        elif dif != 0:
            soft.append(f"Diferencia de redondeo de ${abs(dif):.2f} entre subtotal + IVA y total")

    # palabras a revisar (solo gastos)
    revisar = []
    if p.tipo == "gasto":
        desc = (campos.get("texto") or "").lower()
        revisar = sorted({w for w in p.palabras_revisar if w.lower() in desc})
        if revisar:
            soft.append("Ítems de posible uso personal o ajenos al giro: " + ", ".join(revisar))

    r["checks"], r["hard"], r["revisar_palabras"] = chk, hard, revisar
    r["observaciones"] = obs + soft
    r["estado"] = "INVÁLIDA ❌" if hard else ("REVISAR ⚠️" if revisar else "VÁLIDA ✅")
    r["tipo_gasto"] = clasificar_gasto(campos.get("descripcion"), campos.get("proveedor")) if p.tipo == "gasto" else None
    r["duplicado_de"] = None
    return r


_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "SAS", "SA", "S", "A", "CIA", "LTDA"}


def _apellidos_comunes(cliente: str, emprendedora: str) -> set:
    """Apellidos de la emprendedora (formato SRI 'APELLIDO1 APELLIDO2 NOMBRES') que aparecen en el nombre
    del cliente, escrito en cualquier orden."""
    toks = lambda n: [t for t in re.findall(r"[A-ZÁÉÍÓÚÑ]+", n.upper()) if t not in _PARTICULAS]
    return set(toks(emprendedora)[:2]) & set(toks(cliente))


def _nombre_coincide(a: str, b: str) -> bool:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    return bool(ta) and (ta <= tb or tb <= ta)


def validar_lote(lista_campos, p: Parametros, manual=None, tipos=None):
    """Valida todos, detecta duplicados (misma clave o mismo número+RUC) y ordena por fecha."""
    regs = [validar(c, p) for c in lista_campos]
    if p.tipo == "venta":   # ventas: orden secuencial por número de factura
        regs.sort(key=lambda r: (r.get("numero") or "", r["fecha_date"] or date.max))
    else:                   # gastos: orden cronológico
        regs.sort(key=lambda r: (r["fecha_date"] or date.max, r.get("numero") or ""))
    vistos = {}
    for n, r in enumerate(regs, 1):
        r["n"] = n
        llaves = [k for k in (r.get("clave"), (r.get("numero"), r.get("ruc_clave"))) if k and k != (None, None)]
        previo = next((vistos[k] for k in llaves if k in vistos), None)
        if previo:
            r["duplicado_de"] = previo
            r["estado"] = "INVÁLIDA ❌"
            r["hard"] = True
            r["observaciones"].insert(0, f"DUPLICADO del N° {previo} (misma clave de acceso o número): no se contabiliza")
        else:
            for k in llaves:
                vistos[k] = n
    for r in regs:  # clasificación del técnico: {archivo: TIPO GASTO}; prevalece sobre la inferida
        if tipos and r["archivo"] in tipos:
            r["tipo_gasto"] = tipos[r["archivo"]]
    for r in regs:  # revisión con criterio del técnico: {archivo: motivo} -> REVISAR (no pisa una INVÁLIDA)
        motivo = (manual or {}).get(r["archivo"])
        if motivo:
            r["observaciones"].append(motivo)
            if r["estado"] == "VÁLIDA ✅":
                r["estado"] = "REVISAR ⚠️"
    return regs


def resumen(regs):
    est = lambda e: sum(1 for r in regs if r["estado"] == e)
    validos = [r for r in regs if r["estado"] != "INVÁLIDA ❌"]
    return {
        "procesados": len(regs), "validas": est("VÁLIDA ✅"), "revisar": est("REVISAR ⚠️"), "invalidas": est("INVÁLIDA ❌"),
        "duplicados": sum(1 for r in regs if r["duplicado_de"]),
        "subtotal": round(sum(r["subtotal"] or 0 for r in validos), 2),
        "iva": round(sum(r["iva"] or 0 for r in validos), 2),
        "total": round(sum(r["total"] or 0 for r in validos), 2),
        "total_excluido": round(sum(r["total"] or 0 for r in regs if r["estado"] == "INVÁLIDA ❌"), 2),
    }


def huecos_numeracion(regs):
    """Números de factura que faltan dentro de la secuencia de cada serie (estab-punto). Para ventas:
    un hueco es una factura no entregada o una anulada que debe constar en el Excel."""
    series = {}
    for r in regs:
        m = re.fullmatch(r"(\d{3}-\d{3})-(\d{9})", r.get("numero") or "")
        if m:
            series.setdefault(m.group(1), set()).add(int(m.group(2)))
    faltan = {}
    for serie, nums in series.items():
        perdidos = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
        if perdidos:
            faltan[serie] = [f"{serie}-{n:09d}" for n in perdidos]
    return faltan
