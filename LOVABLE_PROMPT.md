# Sistema de Seguimiento Ex Post – FonQuito Mujer (CONQUITO)

Paquete para construir el sistema en **Lovable**. Uso:
1. Pegar el **Prompt maestro** (sección 1) en un proyecto nuevo de Lovable.
2. Conectar Supabase cuando Lovable lo pida.
3. Pegar cada **Fase** (sección 3) en orden, una por mensaje, y revisar antes de pasar a la siguiente.

---

## 1. Prompt maestro (pegar primero)

```
Construye una aplicación web en español llamada "Seguimiento Ex Post FonQuito Mujer"
para un técnico de seguimiento de CONQUITO que da seguimiento posterior al desembolso
de capital semilla a 14 emprendimientos de mujeres.

STACK: React + TypeScript + Tailwind + shadcn/ui + Supabase (Auth, Postgres, Storage,
Row Level Security). Interfaz 100% en español (Ecuador), moneda USD, fechas dd/mm/aaaa,
diseño sobrio institucional, responsive, modo claro.

USUARIOS Y ROLES
- tecnico: ve y edita todo el portafolio.
- coordinador: solo lectura + descarga de informes.
- Login con email/contraseña. Todas las tablas con RLS por rol.

PORTAFOLIO (datos semilla, 14 emprendimientos)
ANANAU, BIO1, FAROLA, JCV SOCIAL, KALIMERA, KAMIMO, LUNA MIA, MARKEZINA, RUNAWANA,
SHAMPOOIK, SOLUCIONES CBD, TEACOMPANO, TITHAN, VIVATEC.
Cada uno con: nombre emprendimiento, nombre emprendedora, RUC, correo, teléfono,
monto de capital semilla, fecha de desembolso, período de seguimiento (inicio/fin),
estado (activo / en alerta / cerrado).

MODELO DE DATOS (Postgres)
- emprendimientos(id, nombre, emprendedora, ruc, email, telefono, capital_semilla,
  fecha_desembolso, periodo_inicio, periodo_fin, estado)
- periodos(id, emprendimiento_id, mes, anio, estado[pendiente|en_proceso|completo])
- comprobantes(id, periodo_id, tipo[venta|gasto], numero_fila, clave_acceso, fecha_emision,
  ruc_emisor, razon_social_emisor, ruc_receptor, serie, secuencial, subtotal, iva, total,
  archivo_path, resultado_validacion[valido|observado|invalido], observaciones, nombre_final)
- actas(id, periodo_id, fecha_reunion, hora_inicio, hora_fin, modalidad, asistentes jsonb,
  objetivos text, puntos_desarrollados text, compromisos jsonb, evidencia_paths jsonb,
  ingresos_mes, costos_mes, estado)
- visitas_tecnicas(id, emprendimiento_id, numero[1..4], fecha, tipo[primera|periodica],
  indicadores jsonb, evaluacion_asesor text, alertas text, inventario jsonb)
- informes_cobro(id, mes, anio, numero_informe, contenido jsonb, estado, archivo_path)
- profiles(id, nombre, rol)
Storage buckets privados: comprobantes, actas-evidencia, informes.

MÓDULOS
1. Dashboard del portafolio: 14 tarjetas con semáforo por emprendimiento (comprobantes
   validados, acta del mes, visitas hechas 0/4, alertas), filtros por mes y estado,
   KPIs de ventas vs costos consolidados, gráfico de barras ventas/gastos por emprendimiento.
2. Ficha del emprendimiento: datos, línea de tiempo mensual, accesos a cada módulo.
3. Validación de comprobantes electrónicos (SRI): carga masiva de PDF/XML/imagen,
   extracción de datos, validación automática y tabla de resultados exportable a Excel.
4. Renombrado de facturas: ZIP de PDFs + tabla Ventas/Gastos → renombra con
   "<No.>_<proveedor o cliente>_<n° factura>.pdf" y descarga un ZIP.
5. Acta de reunión mensual: formulario guiado que genera el Word institucional.
6. Visita técnica: ficha (hoja Visita + hoja Inventario de bienes adquiridos con el
   capital semilla), 1 primera supervisión + 3 periódicas por emprendimiento.
7. Informe técnico mensual de cobro: consolida los 14 emprendimientos y genera el Word.
8. Reportes y exportaciones: Excel y Word descargables.

Empieza solo con: autenticación, layout con sidebar, el esquema de base de datos con
RLS, los datos semilla de los 14 emprendimientos y el Dashboard. Los demás módulos los
pediré por fases.
```

---

## 2. Reglas de negocio clave (referencia para las fases)

**Validación de clave de acceso SRI (49 dígitos)**
Estructura: fecha emisión `ddmmaaaa` (8) · tipo comprobante (2) · RUC emisor (13) ·
ambiente (1) · serie (6) · secuencial (9) · código numérico (8) · tipo emisión (1) ·
dígito verificador (1).
Módulo 11: tomar los 48 primeros dígitos, multiplicar de derecha a izquierda por
2,3,4,5,6,7,2,3… ; sumar; `dv = 11 − (suma mod 11)`; si `dv = 11 → 0`; si `dv = 10 → 1`.
Debe coincidir con el dígito 49.

**Reglas de validación de comprobante** (estado `valido` / `observado` / `invalido`)
- Clave de acceso de 49 dígitos y dígito verificador correcto.
- VENTAS: RUC emisor = RUC del emprendimiento. GASTOS: RUC receptor = RUC del emprendimiento.
- Fecha de emisión dentro del período válido del mes de seguimiento.
- Sin duplicados (misma clave de acceso o mismo serie+secuencial+RUC emisor).
- Totales coherentes (subtotal + IVA = total).
- Todo lo que falle se marca con la observación específica; nunca se descarta en silencio.

**Renombrado de facturas** – tres estrategias de cruce, en este orden:
1. N° de factura embebido en el nombre del archivo.
2. Clave de acceso SRI leída del PDF.
3. Orden secuencial como último recurso (marcado como "por confirmar").
Manejar duplicados y filas especiales (notas de crédito, filas sin comprobante).

**Acta mensual (7 tablas, formato institucional exacto)**
Descripción de la reunión · Objetivos · Asistentes · Puntos desarrollados · Compromisos ·
Evidencia fotográfica · Firmas. Código de formato: `CEDE-EMPR-ACTA REUNIÓN`.

**Visita técnica**: primera supervisión in situ + 3 periódicas; hojas "Visita" e
"Inventario". Alertas visibles en el dashboard.

**Informe de cobro**: código `CEDE-EMPR-INF-2026-NN`. Estructura: Antecedentes · Base Legal ·
Desarrollo (4–5 productos contractuales) · Conclusiones y Recomendaciones · Anexos · Firmas.
Soporta "mes caído" y resumen financiero consolidado de los 14 emprendimientos.

> Nota: las plantillas Word/Excel institucionales y las citas legales exactas deben
> subirse al proyecto (carpeta `plantillas/`) para que los módulos 5–7 las reproduzcan
> sin improvisar.

---

## 3. Fases (pegar una por mensaje)

**Fase 1 – Fundamentos** → el prompt maestro (sección 1).

**Fase 2 – Validación de comprobantes**
```
Implementa el módulo "Validación de comprobantes". Pantalla con selector de
emprendimiento, mes, tipo (Ventas/Gastos) y período válido. Carga múltiple de
PDF/XML/imágenes a Storage. Una Edge Function extrae los datos (para XML: parseo
directo; para PDF/imagen: extracción con IA) y valida: clave de acceso de 49 dígitos
con dígito verificador Módulo 11, RUC emisor/receptor según tipo, fecha dentro del
período, duplicados y coherencia de totales. Muestra tabla con semáforo
(válido/observado/inválido) y observaciones editables; permite corrección manual.
Botón "Exportar a Excel" con el formato Gastos_<MesAño>_<EMPRENDIMIENTO>.xlsx /
Ventas_<MesAño>_<EMPRENDIMIENTO>.xlsx. Guarda todo en la tabla comprobantes.
```

**Fase 3 – Renombrado de facturas**
```
Agrega el módulo "Renombrar facturas": el usuario sube un ZIP con PDFs y el Excel de
Gastos o Ventas del emprendimiento. Cruza cada PDF con la columna "No." del Excel
usando, en orden: (1) n° de factura en el nombre del archivo, (2) clave de acceso
leída del PDF, (3) orden secuencial marcado "por confirmar". Vista previa editable
con nombre propuesto "<No.>_<proveedor/cliente>_<n° factura>.pdf", detección de
duplicados y filas sin comprobante, y descarga de un ZIP con los archivos renombrados.
```

**Fase 4 – Acta de reunión**
```
Agrega el módulo "Acta de reunión mensual" por emprendimiento y mes. Formulario por
pasos con las 7 secciones institucionales (Descripción de la reunión, Objetivos,
Asistentes, Puntos desarrollados, Compromisos, Evidencia fotográfica con carga de
fotos, Firmas). Precarga ingresos y costos del mes desde los comprobantes validados.
Genera y descarga el acta en Word (.docx) con el formato CEDE-EMPR-ACTA REUNIÓN
usando la plantilla subida en plantillas/. Estados: borrador / firmada.
```

**Fase 5 – Visitas técnicas**
```
Agrega el módulo "Visitas técnicas": por emprendimiento, 4 visitas (1 primera
supervisión + 3 periódicas) con contador 0/4. Formulario con datos del beneficiario,
indicadores del negocio, evaluación del asesor, alertas e inventario de bienes
adquiridos con el capital semilla (tabla editable: bien, cantidad, valor, estado,
ubicación, foto). Exporta a Excel con las hojas "Visita" e "Inventario" siguiendo
la plantilla 'Formato visita tecnica Quito Mujer.xlsx'. Las alertas aparecen en el
Dashboard.
```

**Fase 6 – Informe técnico de cobro**
```
Agrega el módulo "Informe de cobro": selecciona mes/año y genera el Informe Técnico
CEDE-EMPR-INF-2026-NN consolidando los 14 emprendimientos (actas hechas, comprobantes
validados, visitas, resumen financiero consolidado de ventas y costos). Secciones:
Antecedentes, Base Legal, Desarrollo del contenido, Conclusiones y Recomendaciones,
Anexos, Firmas. Editor previo de cada sección y descarga en Word según plantilla.
Soportar "mes caído". Marcar los emprendimientos con datos incompletos antes de generar.
```

**Fase 7 – Pulido**
```
Agrega: bitácora de auditoría (quién cambió qué), notificaciones de pendientes del
mes por emprendimiento, búsqueda global, importación masiva de emprendimientos desde
Excel, y copia de seguridad exportable. Revisa RLS y accesibilidad.
```

---

## 4. Pendientes que necesito de ti

- Plantillas Word/Excel institucionales (acta, informe, visita técnica) para `plantillas/`.
- Listado real del portafolio (RUC, montos, fechas de desembolso) para los datos semilla.
- Texto exacto de la Base Legal del informe.
- Confirmar si habrá más de un usuario técnico.
