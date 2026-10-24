"""Uso:
  python3 -m fonquito validar --tipo gasto --entrada Recibidas.md --ruc 1790000000001 \\
      --emprendimiento EJEMPLO --emprendedora "APELLIDO1 APELLIDO2 NOMBRE" \\
      --desde 01/08/2026 --hasta 31/08/2026 --mes Ago2026 --salida Gastos_Ago2026_EJEMPLO.xlsx [--pdfs Recibidas.zip]
  python3 -m fonquito clave <49 dígitos>
"""
import argparse
import sys
from pathlib import Path

from . import sri
from .conciliar import conciliar, leer_anexo
from .excel import construir
from .extraer import extraer_campos, leer_directorio, leer_md, leer_pdf_facturas
from .renombrar import exportar_csv, renombrar
from .validar import PALABRAS_REVISAR, Parametros, huecos_numeracion, parse_fecha, resumen, validar_lote


def cmd_clave(a):
    info = sri.descomponer(a.clave)
    for k in ("fecha", "tipo", "ruc", "ambiente", "numero", "digito_declarado", "digito_calculado", "modulo11_ok"):
        print(f"{k}: {info[k]}")
    return 0 if info["modulo11_ok"] else 1


def cmd_validar(a):
    entrada = Path(a.entrada)
    if entrada.is_dir():
        docs = leer_directorio(entrada)
    elif entrada.suffix.lower() == ".pdf":
        docs = leer_pdf_facturas(entrada)
    else:
        docs = leer_md(entrada)
    if not a.pdfs and entrada.suffix.lower() in (".pdf", "") and (entrada.is_dir() or entrada.suffix.lower() == ".pdf"):
        a.pdfs = str(entrada)   # los PDF originales son la propia entrada
    if not docs:
        print("No se encontraron comprobantes en la entrada", file=sys.stderr)
        return 2
    campos = [extraer_campos(t, n) for n, t in docs.items()]
    palabras = PALABRAS_REVISAR + (a.palabras or [])
    p = Parametros(a.tipo, a.ruc, a.emprendedora, parse_fecha(a.desde), parse_fecha(a.hasta), palabras)
    manual = dict(x.split('=', 1) for x in (a.revisar or []) if '=' in x)
    tipos = dict(x.split('=', 1) for x in (a.tipos or []) if '=' in x)
    regs = validar_lote(campos, p, manual, tipos)
    concil = conciliar(regs, leer_anexo(a.formato, a.tipo), a.tipo) if a.formato else None
    huecos = huecos_numeracion(regs) if a.tipo == "venta" else {}
    notas = [f"NUMERACIÓN: faltan en la secuencia {', '.join(v)}: son facturas no entregadas o anuladas; las anuladas deben constar "
             f"en el registro como INVÁLIDA (cliente 'ANULADA')." for v in huecos.values()]
    wb = construir(regs, p, a.emprendimiento, Path(a.salida).name, a.mes, a.abrev, a.mes_contrato, a.categoria,
                   notas_extra=notas, clientes_b2b=a.b2b, conciliacion=concil,
                   productos=dict(x.split('=', 1) for x in (a.productos or []) if '=' in x))
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    wb.save(a.salida)
    r = resumen(regs)
    csv_ruta = Path(a.salida).with_name(Path(a.salida).stem + "_renombrado.csv")
    exportar_csv(regs, csv_ruta)
    print(f"Excel: {a.salida} | Tabla de renombrado: {csv_ruta}")
    print(f"Procesados {r['procesados']} | válidas {r['validas']} | revisar {r['revisar']} | inválidas {r['invalidas']} (duplicados {r['duplicados']})")
    print(f"Totales sin inválidas: subtotal {r['subtotal']:.2f} + IVA {r['iva']:.2f} = total {r['total']:.2f} (excluido {r['total_excluido']:.2f})")
    if concil:
        print("CONCILIACIÓN con el formato:")
        for nivel, n, num, msg in concil:
            print(f"  [{nivel}] {('N° %s ' % n) if n else ''}{num} {msg}")
    for v in huecos.values():
        print(f"ATENCIÓN numeración: faltan {', '.join(v)} (¿anuladas o no entregadas?)")
    for x in regs:
        if x["estado"] != "VÁLIDA ✅":
            print(f"  N° {x['n']} {x['archivo']}: {x['estado']} – {'; '.join(x['observaciones'])}")
    if a.pdfs:
        destino = Path(a.salida).with_name(Path(a.salida).stem + "_facturas_renombradas.zip")
        ok, falta = renombrar(regs, a.pdfs, destino)
        print(f"Renombrado: {len(ok)} PDF -> {destino}" + (f" | sin PDF: {', '.join(falta)}" if falta else ""))
    else:
        print("Renombrado: pendiente (indica --pdfs con el ZIP o carpeta de PDF originales)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fonquito")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clave", help="valida una clave de acceso de 49 dígitos")
    c.add_argument("clave")
    c.set_defaults(fn=cmd_clave)
    v = sub.add_parser("validar", help="valida un lote de comprobantes y genera el Excel")
    v.add_argument("--tipo", choices=["gasto", "venta"], required=True)
    v.add_argument("--entrada", required=True, help=".md convertido del ZIP, o carpeta con PDF/MD")
    v.add_argument("--ruc", required=True)
    v.add_argument("--emprendimiento", required=True)
    v.add_argument("--emprendedora", required=True)
    v.add_argument("--desde", required=True, help="dd/mm/aaaa")
    v.add_argument("--hasta", required=True, help="dd/mm/aaaa")
    v.add_argument("--mes", required=True, help="etiqueta, p. ej. Ago2026")
    v.add_argument("--salida", required=True)
    v.add_argument("--pdfs", help="ZIP o carpeta con los PDF originales (para el renombrado)")
    v.add_argument("--palabras", nargs="*", help="palabras adicionales que marcan REVISAR")
    v.add_argument("--revisar", nargs="*", help='marca REVISAR con criterio propio: "archivo.pdf=motivo"')
    v.add_argument("--tipos", nargs="*", help='clasificación propia de gasto: "archivo.pdf=GASTO VENTAS"')
    v.add_argument("--productos", nargs="*", help='ventas: etiquetas de producto por texto de la factura: "PIZZA=Pizza"')
    v.add_argument("--formato", help="formato institucional (.xlsm) para conciliar el Anexo 1 o 2 contra las facturas (solo lectura)")
    v.add_argument("--abrev", help="ventas: abreviatura para el No. ING-EXPOST-ABREV-NN")
    v.add_argument("--mes-contrato", help="ventas: número de mes del contrato")
    v.add_argument("--categoria", help="ventas: categoría general PRODUCTO O SERVICIO")
    v.add_argument("--b2b", nargs="*", help="ventas: textos (nombre o RUC) de clientes con canal VENTAS B2B")
    v.set_defaults(fn=cmd_validar)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
