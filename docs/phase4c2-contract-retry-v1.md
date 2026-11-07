# Reintento contractual trazable v1

Implementación offline. **No se creó el segundo workspace real de Bravqulin.**
El intento original queda íntegro: formulario `in_progress`, 13 mappings,
sesión `completed`, reloj `stopped`, autorizaciones, eventos, hashes y recibos.
La falta de tiempo de mapping no invalida sus propuestas ni permite inventar
mediciones. La nueva herramienta no cambia esa conclusión.

## Comando de preparación futura — no ejecutado

Cuando el propietario autorice preparar el workspace real:

```powershell
python tools/evaluation/pilot_contract_workflow.py `
  --workspace data/cache/news_development_pilot/contract-D-a8db3a0c74d93eb8-attempt02 `
  prepare-retry `
  --source data/cache/news_development_pilot/contract-D-a8db3a0c74d93eb8-attempt01 `
  --case D-a8db3a0c74d93eb8 `
  --reason contract_mapping_not_timed
```

No usar `prepare` sobre un manifiesto viejo para evitar el bloqueo del origen.
El destino debe ser nuevo y separado. `prepare-retry` comprueba el workflow del
intento original, su selección, factual completo, disposición y cierre, contrato
v3, evidencias, recibos, hashes y reloj antes de escribir. Rechaza sesiones en
curso, casos aprobados/completados, mappings incompletos y motivos que no se
correspondan con la falta temporal observada. No fuerza ninguna condición.

## Materiales y estados resultantes

El comando generará:

- Nuevo review_id y `workflow.json` versión `news-pilot-contract-workflow-v2`.
- `retry-lineage-v1.json`: referencias y SHA-256 de workflow, manifiesto,
  formulario, sesión e inventario del predecesor; motivo y ambos review_id.
- `DERIVED-PROPOSAL-v1.json`: los 13 mappings exactos del primer intento,
  incluidos modo, rationale y limits_acknowledged, resultados permitidos y
  rationale global; solo el review_id del sobre corresponde al nuevo intento.
- `materials/CHATGPT-PACKET.md`: noticia original, factual íntegro, 13 dimensiones,
  evidencias, contrato técnico y propuesta, identificada como derivada y no
  aprobada ni independiente. Las fuentes y su procedencia permanecen disponibles.
- `OPENING-TEMPLATE.json` y `CONTENT-APPROVAL-TEMPLATE.json`: plantillas inválidas
  hasta que exista autorización/aprobación real; fechas, fuentes desconocidas y
  fingerprint de aprobación aún no calculado en null. No son decisiones emitidas.
- Formulario contractual `unfilled`, sin mappings ni owner_decision, y sesión
  `unfilled`, sin persona, autorización enlazada, reloj o intervalos. Los mappings
  están preservados como propuesta aparte: no se copian juicios al formulario.

Las referencias de Yrvexil y los otros cuatro casos se conservan. El manifiesto
del workspace nuevo selecciona el segundo intento de Bravqulin sin modificar
la selección ni los archivos del primero. La deriva se audita en cada operación;
cambios en un archivo previo o en el inventario completo bloquean el linaje.

## Verificación futura

Solo una vez preparado el workspace por autorización posterior:

```powershell
$work = 'data/cache/news_development_pilot/contract-D-a8db3a0c74d93eb8-attempt02'
python tools/evaluation/pilot_contract_workflow.py --workspace $work validate
```

No habrá apertura ni reloj. El nuevo review_id se usará para solicitar una
autorización de apertura específica. La autorización del intento anterior no
es válida para este. La implementación actual tampoco autoriza preparar el
workspace real: esta entrega se limita al código y fixtures temporales.

## Actividad prospectiva posterior

Tras la autorización de apertura, usar el procedimiento habitual `open`.
Cuando el propietario empiece realmente a comprobar representabilidad, puede
iniciar el reloj en `contract_mapping`. Debe contrastar los 13 mappings con el
contrato, evidencias, justificaciones, incertidumbres y omisiones. La validación
técnica o importación automática no sustituye ese trabajo. No hace falta volver
a producir una noticia ni repetir la revisión factual aprobada.

Después de la comprobación humana, podrá importarse explícitamente la propuesta:

```powershell
python tools/evaluation/pilot_contract_workflow.py --workspace $work apply `
  --annotation "$work/DERIVED-PROPOSAL-v1.json"
```

Esto registra un borrador; no aprobación ni evaluación independiente. Una
corrección que se decida después se documenta como otra propuesta versionada,
sin editar la copia derivada ni su fuente. Registrar `owner_review` cuando se
realice realmente, pausando para esperas de ChatGPT y descansos. Detener el reloj
solo al terminar. Todos los intervalos nuevos deben empezar después del fin de
la sesión anterior. No se trasladan los 164,873113 segundos activos ni la pausa
anterior al nuevo registro. Tampoco se reclasifican como trabajo de mapping.

`approval-plan` seguirá exigiendo tiempos reales de mapping y revisión del
propietario, todos los hechos y sesión completada. Generará el fingerprint nuevo
con esa sesión. La plantilla inicial de aprobación no tiene fingerprint válido:
utilizar entonces la plantilla del plan verificado. Aprobación de contenido y
autorización de cierre siguen separadas; ninguna se genera automáticamente.

## Compatibilidad, retención y alcance

El flujo ordinario v1 y el primer caso de Yrvexil no cambian. No se modifican
`news-pilot-contract-form-v2`, `news-pilot-contract-session-v1`, validadores o
contrato económico v3. El cronometraje factual original sigue excluido.

El lector tipado del predecesor conserva su TTL de 90 días desde el fin de su
sesión. Preparar o validar el reintento no amplía ese plazo. Si el predecesor
vence, la verificación del linaje se bloquea; no hay recuperación alternativa
de contenido ni extensión de retención. Ante persistencia parcial se conserva
lo escrito, se bloquea y no se reintenta automáticamente.

No se cambian estados oficiales, no se completa el piloto ni el experimento,
y no se ejecutan inferencias, APIs o evaluaciones del modelo.

## Verificaciones de implementación

- Suite completa de la versión final: 1126 tests pasan; 23 tests específicos
  del reintento usan exclusivamente directorios y relojes sintéticos.
- Se probó una derivación exacta de 13 mappings, nueva autorización obligatoria,
  tiempos nuevos sin acumulación, ambos motivos admitidos, hashes alterados,
  cambios de inventario, TTL, sesiones activas/aprobadas, stop inconsistente,
  fallo de escritura sin reintento y compatibilidad del flujo ordinario.
- `validate_data.py` y `compileall -q src scripts tools/evaluation/pilot_contract_workflow.py`: correctos.
- Preflight real, solo de lectura: Bravqulin conserva sus 13 mappings y formulario
  `in_progress`, sesión `completed` y reloj detenido. Su formulario conserva
  SHA-256 `532578df3ba8e67009670564eb91440bcc6ad6dccb704f7b31a545d054e7dde8`
  y su sesión `6ab1c92e211868e1a76df870d58fc91f88ca4b59de645064281672e3f0927d9c`.
- Integridad: 3795 archivos bajo `data`, `evaluation`, `config` y `src` sin
  modificaciones ni incorporaciones respecto del inicio. Yrvexil sigue
  `completed`; los otros cuatro casos siguen `unfilled`.
- No se ejecutó `prepare-retry` contra datos reales: `attempt02` no existe.
  No se creó autorización, aprobación, mapping, sesión o medición real nueva.
