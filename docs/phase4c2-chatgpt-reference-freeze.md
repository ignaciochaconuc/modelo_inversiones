# Phase 4C.2.2 — Congelación de referencias exploratorias ChatGPT

Estado del artefacto: `references_frozen`. Clasificación:
`chatgpt_assisted_exploratory_review`. No es ground truth humano independiente.
Este cierre de custodia no certifica calidad semántica ni cierra técnicamente
Phase 4C.2. Phase 4C.3 permanece `not_started`.

## Identidad del conjunto

Artefacto local: `data/cache/news_attribution_review/chatgpt-v1/references-frozen.json`.
Contenedor mixto: `chatgpt-attribution-review-v2`, sin migrar los imports v1.

- `reference_fingerprint` (identidad canónica de `references`):
  `8430b8d83b33b06297710eb30bba0890ffb9e758e8d9f3e5f60e8a97d843bfe0`.
- SHA-256 de los bytes del archivo:
  `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
- `frozen_at`: `2026-10-14T20:34:57.939397+00:00`, registrado por la
  herramienta local al congelar; no es timestamp de ejecución de ChatGPT.
- Ocho bloques, 32 `case_id` únicos, 100 menciones/unidades y 800 dimensiones.
- 776 referencias de citas textuales exactas y 21 referencias al índice neutral
  de identidad. Son ocurrencias de referencias, no necesariamente citas únicas.

## Reconstrucción e integridad

Se comprobaron exactamente los archivos B01–B08 en `imports/`, los 32 IDs y
fingerprints contra los casos originales, los hashes de fuentes/instrucciones/
paquetes congelados y los ocho campos dimensionales por unidad. Se verificaron
los IDs de evidencia y la presencia literal de cada cita en el campo del caso
declarado, sin normalización ni reparación automática.

Para cada import v1 se reconstruyó el objeto completo desde los bytes del archivo
de respuesta, su procedencia local y el paquete original, incluido su `record_id`.
El objeto reconstruido coincide exactamente con el persistido. La procedencia
externa también coincide con la embebida en cada registro.

B01 usa `responses/B01-attempt2.txt` y `provenance/B01-attempt2.json`.
El primer intento y su estrato contaminado permanecen intactos y fuera del
conjunto principal; conservarlo no elimina la limitación metodológica del reintento.

B04 conserva su cadena v2 completa: respuesta original, derivado corregido,
manifiesto previo, lista versionada de cambios, autorización e import. Los bytes
embebidos coinciden con los archivos locales; hashes, autorización y reconstrucción
del único cambio declarado se verificaron. Solo cambió la mayúscula inicial de una
cita, sin alterar otras evidencias ni conclusiones. El original mantiene el rechazo
`quote_not_in_declared_case_field`. Su derivado es una anotación editorial posterior,
no una nueva generación de ChatGPT ni una respuesta original válida.

Distribución: siete bloques originales v1 válidos (28 casos) y un bloque derivado
editorial v2 (cuatro casos). El error original de B04 no se contabiliza como éxito
original ni se oculta tras su corrección. No es un fallo técnico de bloque en las
anotaciones finalmente importadas.

## Procedencia declarada

Responsable de captura: Nacho. Evaluación manual en ChatGPT, cero llamadas API.
`GPT-6` es únicamente una etiqueta visible declarada por el propietario; snapshot,
parámetros internos y tokens API permanecen `null`. El coste de suscripción no se
midió. No se infieren snapshot, identidad interna ni parámetros de API.

Todos los horarios siguientes corresponden a 2026-10-14, offset `-03:00`.
Son declaraciones del propietario, no timestamps verificados por la plataforma.

| Bloque | Contrato importado | Inicio–fin declarados | Menciones | Dimensiones |
| --- | --- | --- | ---: | ---: |
| B01 (intento 2) | v1 | 15:50–16:00 | 17 | 136 |
| B02 | v1 | 16:22–16:24 | 11 | 88 |
| B03 | v1 | 16:30–16:32 | 10 | 80 |
| B04 (derivado editorial) | v2 | 16:36–16:39 | 14 | 112 |
| B05 | v1 | 17:10–17:13 | 10 | 80 |
| B06 | v1 | 17:17–17:20 | 14 | 112 |
| B07 | v1 | 17:23–17:26 | 13 | 104 |
| B08 | v1 | 17:28–17:31 | 11 | 88 |

Para los intentos principales el propietario declara conversaciones nuevas, sin
historial de desarrollo ni predicciones de Nacho. Los fingerprints prueban
integridad de los paquetes, no aislamiento efectivo de contexto, memoria o
instrucciones de ChatGPT. No existe adjudicación humana independiente o prueba
criptográfica de la identidad del autorizante. El protocolo humano original se
conserva para uso futuro; la revisión Finnhub externa continúa bloqueada por derechos.

## Incertidumbres y estados conservados

Casos: 28 `annotated`, cuatro `nonconclusive` (uno en B03, uno en B04 y dos en B06),
cero `abstained` y cero `technical_error`. Se preservan 143 entradas de
`uncertainties`, no necesariamente 143 problemas distintos.

| Dimensión | conclusive | uncertain | insufficient | not_applicable |
| --- | ---: | ---: | ---: | ---: |
| corporate_identity | 67 | 30 | 3 | 0 |
| participation | 94 | 5 | 1 | 0 |
| role | 95 | 4 | 1 | 0 |
| relationship | 84 | 10 | 6 | 0 |
| ticker_link | 9 | 0 | 81 | 10 |
| event_state | 98 | 1 | 0 | 1 |
| event_stage | 84 | 4 | 4 | 8 |
| impact_support | 89 | 0 | 11 | 0 |
| Total | 620 | 54 | 107 | 19 |

Estos son estados asignados por el evaluador, no resultados de validación de
entailment ni estimaciones de precisión, recall, causalidad o generalización.
Las ocho dimensiones deben compararse por separado; no convertir incertidumbre
en una referencia concluyente ni una mención contextual en exposición confirmada.

## Freeze y reproducibilidad

Se ejecutó el comando previsto, solo después de pasar la verificación conjunta:

```powershell
python tools/evaluation/prepare_chatgpt_review.py freeze --imports data/cache/news_attribution_review/chatgpt-v1/imports --destination data/cache/news_attribution_review/chatgpt-v1/references-frozen.json
```

Se reconstruyó el payload desde los imports y se comprobó igualdad exacta con
`references`, identidad canónica, clasificación y versión del contenedor. Repetir
el mismo freeze con la implementación existente mantuvo exactamente los bytes,
SHA-256, `frozen_at` y fecha de modificación del archivo. La repetición es
idempotente; el identificador canónico no contiene el reloj de congelación, pero
el hash de bytes sí lo incluye. No afirmar igualdad de bytes para una creación
independiente con otro timestamp.

No sobrescribir, editar ni regenerar las referencias congeladas. Ante cualquier
inconsistencia futura, detener la comparación y conservar la evidencia. Una nueva
evaluación requiere artefactos/versiones separados, no correcciones retroactivas.

## Validaciones y conservación histórica

- `python -m pytest`: 675 tests aprobados, 44,02 s.
- `python scripts/validate_data.py`: correcto; 905 capturas/payloads/revisiones,
  811 artículos, cero hashes inválidos, linaje faltante o duplicados; cuatro
  snapshots de enriquecimiento válidos. Features y targets separados.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Control SHA-256 antes/después de 3.481 archivos existentes: cero cambios.
  Incluye datos históricos de Phase 3, 4A, 4B y caché 4C, fuentes/contratos/prompts,
  scripts/herramientas, configuración, evaluación y documentación existente, junto
  con los cinco documentos raíz de gobernanza. Se excluyen `__pycache__`, el nuevo
  freeze y este informe; no se carga `.env`.
- Inventarios comprobados: data 3.178; src 137; scripts 32; tools 6; config 15;
  evaluation 55; docs existentes 53; documentos raíz 5. Para cada inventario se
  compara SHA-256 del mapa canónico ordenado de ruta relativa a hash de bytes.

Los únicos artefactos nuevos de esta tarea son el freeze local y este informe.
Los archivos originales, manifiestos, contratos históricos y registros importados
no se modificaron. No se abrió TEST oficial ni se ejecutaron los smokes anteriores.

## Comparación posterior

Referencias listas para una comparación posterior autorizada, no ejecutada en
esta tarea. La generación de predicciones Nacho requiere autorización separada;
sus intentos deben comenzar después de `frozen_at`. La alineación deberá declarar
el SHA-256 exacto de este freeze y del archivo de salidas. El comparador existente
preserva omisiones, abstenciones, rechazos, errores y estados no concluyentes,
sin estimar métricas poblacionales ni promover interpretaciones a operativas.

No se realizaron inferencias, llamadas API, consulta externa Finnhub ni
predicciones Nacho. No se modificaron algoritmos, prompts o contratos de producción.
Phase 4C.3 no se inició.
