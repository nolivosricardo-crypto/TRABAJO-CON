# fonquito

Herramientas deterministas para el seguimiento ex post de FonQuito Mujer (CONQUITO).

```
python3 -m fonquito validar --tipo gasto --entrada Recibidas.md --ruc <RUC13> \
    --emprendimiento <NOMBRE> --emprendedora "<NOMBRE COMPLETO>" \
    --desde 01/08/2026 --hasta 31/08/2026 --mes "Agosto 2026" --salida Gastos_Ago2026_<NOMBRE>.xlsx \
    [--pdfs Recibidas.zip] [--revisar "archivo.pdf=motivo"]
python3 -m fonquito clave <49 dígitos>
python3 -m unittest discover -s tests
```

Módulos: `sri` (clave y Módulo 11) · `extraer` (campos desde .md/PDF) · `validar` (reglas y estados) ·
`excel` (libro institucional de 3 hojas) · `renombrar` (ZIP con `<No.>_<proveedor>_<n° factura>.pdf`).

Alcance de la validación automática: formato y dígito de la clave, fecha dentro del período, RUC del emisor,
receptor, suma subtotal + IVA = total (tolerancia $0,01), duplicados y palabras de posible consumo personal.
No juzga lugar/hora de las compras, partes relacionadas ni si el gasto corresponde al plan de inversión:
eso lo revisa el técnico (ver `.claude/agents/fonquito.md`).

Dependencias: Python 3, `openpyxl`; `pdftotext` (poppler) solo para leer PDF directamente.
