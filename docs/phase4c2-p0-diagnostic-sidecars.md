# Phase 4C.2.2 — P0: observabilidad diagnóstica

P0 implementado; integración en futuras evaluaciones pendiente de revisión.
No se autoriza ninguna inferencia. Phase 4C.3 sigue `not_started`.

## Implementación y contrato

`agents.news_interpretation.diagnostic_events` captura ramas mediante contexto
local; `diagnostic_sidecar` valida/persiste metadata por separado. Versión:
`news-evaluation-diagnostics-v1`. Política: `diagnostic-metadata-retention-v1`.
Ruta: `data/cache/news_evaluation_diagnostics/<run_id>/<case_id>.json`, ignorada
por la regla Git existente `data/cache/*`.

Cada sidecar contiene case_id/run_id, outcome agrupado y native_outcome original,
error_code cerrado, pipeline_stage y rejection_code primario; diagnósticos con
stage/rule/subcode/field_path. Incluye request/revision IDs, fingerprints de
fuente/evidencia/settings/wire, cache_key, attempt_id/record_id y timestamps UTC.
El contenedor fija el sidecar_id canónico. No hay citas, artículos, prompts,
respuestas, rationale, mensajes de excepción, cifras extraídas, unidades,
períodos o IDs de evidencia desconocidos propuestos por el modelo.

Enums cerrados, propiedades extra prohibidas, rutas de vocabulario cerrado e
índices acotados impiden copiar keys/valores arbitrarios. Se ocultan inputs en
errores; keys desconocidos se sustituyen por unknown_field. El CLI solo devuelve
códigos fijos en errores. Los índices estructurales no son valores financieros.

run_id tiene forma `eval-` + UUID hexadecimal de 32 caracteres y case_id S-hex16;
no usar nombres/secrets como identificadores. El wrapper verifica el fingerprint
de los textos sintéticos frente a la fuente declarada sin guardarlos en el sidecar.

## Subcódigos emitidos al validar

| Regla | Subcódigos v1 |
| --- | --- |
| stage_not_supported | completion_literal_missing; announced_literal_missing; proposed_literal_missing |
| numeric_fidelity | number_lexeme_unparseable; number_value_nonfinite_or_transformed; number_absent_from_context; unit_absent_from_context; scale_absent_from_context; period_absent_from_context |
| negation_lost | negation_token_present_flag_false |
| unknown_evidence_id | evidence_id_not_in_request |
| wrong_revision | evidence_revision_not_primary |
| quote_not_found_in_declared_field | exact_quote_absent |
| ambiguous_quote | exact_quote_ambiguous |

Los predicados y mensajes anteriores no cambian. Las ramas generan DTOs fijos
en origen; los fallos numéricos los adjuntan a BranchViolation, subclase de
ValueError. El adaptador Pydantic toma el objeto tipado y su ruta, no analiza
mensajes. Los mappers legacy conservan sus salidas genéricas; la precisión
nueva solo aparece en el sidecar. Otras reglas enum existentes conservan
not_available cuando no tienen subcódigo propio; no se inventa precisión.

Se captura solo el primer evaluate de un intento nuevo. La captura se sella
antes de verificaciones repetidas de envelopes y persistencia: no se duplican
eventos ni se producen sidecars por imports, settings, wires o replay. Las
rutas de etapa/negación incluyen índice de evento; números conservan su índice
estructural Pydantic. No se cambia ninguna regla de aceptación o atribución.

## Retención independiente

**90 días exactos desde created_at**, sin prórroga automática. Se deniega lectura
si now < created_at o now >= expires_at. Cambiar expires_at y recalcular hash no
cumple la política. El lector audita solo metadata y funciona tras vencer el
TTL de respuesta, sin abrir contenido/attempts/outputs/cache. El TTL original de
contenido no cambia. No hay borrado físico automático ni restauración de datos:
la purga de sidecars expirados requiere autorización y lista exacta de targets,
sin alcanzar referencias, intentos o ledgers. Metadata sigue siendo local
restringida; no se convierte en telemetría pública.

La integridad se comprueba con el ID canónico; el orquestador futuro debe fijarlo
en su manifest y suministrar expected-id al auditar. No es una firma digital.

## Preflight y auditoría offline

```powershell
python scripts/validate_news_diagnostic_sidecar.py --validate-only
```

Valida un espécimen exclusivamente de metadata, schema y retención. Cero
credenciales, providers, escrituras o resultados de inferencia. No revalida ni
habilita un perfil LLM vencido. El CLI no tiene modo de inferencia/API key/dotenv.

Auditoría futura (placeholders; no usar contra la corrida antigua):

```powershell
python scripts/validate_news_diagnostic_sidecar.py --audit --run-id <eval-UUIDhex> --case-id <S-hex16> --expected-id <sidecar_id>
```

## Propuesta de integración futura — todavía NO activada

El ejecutor de evaluación existente y su perfil no se modificaron. Incorporar
el wrapper solo tras revisión, con run ID nuevo, perfil vigente, plan que
incluya versión/política/retención/código y autorización expresa posterior.
No reutilizar autorizaciones antiguas. Ejemplo orientativo, **no ejecutar ahora**:

```python
# Dentro de una futura corrida secuencial ya autorizada y presupuestada:
delivery, sidecar_id = interpret_observed(
    service, request, case_id=binding["case_id"],
    source_evidence_fingerprint=binding["evidence_fingerprint"],
    store=SidecarStore(),
)
# Fijar sidecar_id en el manifest, sin copiar respuestas.
```

El servicio conserva router, autorización, precios, presupuesto y persistencia.
Se exige runtime v4/salida económica v3 y un intento; usa force_new, no cache
recovery. No hay API que acepte un record_id/delivery histórico para completar
diagnósticos. Los run IDs antiguos se bloquean antes de llamar al servicio.

Si la escritura del sidecar falla, detener el orquestador, conservar el intento
y ledger y no reintentar inferencia. No cambiar el outcome semántico para
aparentar observabilidad correcta. record_not_run cubre razones cerradas
not_authorized/preflight_failed/upstream_halt, sin IDs de intento ficticios.
No usarlo si pudo ocurrir una llamada cuya persistencia falló: revisar el ledger
y no clasificar automáticamente como not_run. La coordinación de workers
paralelos queda fuera del wrapper secuencial; no sustituye un scheduler.

## Compatibilidad, riesgos y validaciones

No cambian regex, aceptación/rechazo, estados, fechas, números, atribución,
prompts, schemas LLM, DTOs o versiones v1/v2/v3/v4 anteriores. Sí cambia el
código fuente por instrumentación: un plan futuro tendrá otro fingerprint.
Los schemas legacy/económico conservan sus hashes anteriores; tests comparan
resultados serializados con/sin captura y wire/cache keys con/sin observador.
Los mensajes fijos anteriores y diagnósticos genéricos se conservan.

No se crean sidecars ni se reabren los contenidos de
nacho-synthetic-20261014-run01. Compatibilidad se prueba con replays/DTOs
sintéticos, no leyendo datos históricos vencidos ni desplazando su reloj.
Los subcódigos identifican la guardia, no certifican verdad semántica. No
permiten reconstruir citas al expirar contenido; la negación y las etapas
conservan sus limitaciones. No se implementó P1/P2.

Tests adversariales: ramas de etapa y números, negación, evidencia desconocida,
keys/valores sensibles, paths inválidos, hashes/duplicados, TTL independiente,
lectura sin lector de contenido, fallo de persistencia sin retry, bloqueo
histórico, not_run, contratos y preflight sin credenciales. La suite completa,
validate_data.py, compileall y hashes históricos se ejecutan antes de entregar.

Sin APIs, corrida nueva, comparación ChatGPT, cambios de referencias, Feature
Store o inicio de Phase 4C.3. No se autoriza inferencia futura.

### Resultados de validación de esta entrega

- `python -m pytest`: **753 aprobados**, 81,59 s; 32 pruebas P0 nuevas.
- `python scripts/validate_data.py`: correcto, 905 revisiones/811 artículos,
  cero hashes inválidos, linaje faltante o duplicados, cuatro snapshots válidos.
- `python -m compileall -q src scripts`: correcto.
- Preflight P0: validated_offline, cero llamadas, cargas de claves o escrituras.
- Hashes antes/después: cero cambios en 3.324 archivos de data/config/evaluation,
  incluidos los intentos, sidecars históricos inexistentes, ledger y referencias.
- Freeze SHA-256 conservado:
  `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
- Export histórico SHA-256 conservado:
  `c9181bee95769a0d13928d768a3490c83de2377ba93aa9f60eb4252d14479fa4`.
- No existe el árbol real de sidecars; toda persistencia de las pruebas fue
  temporal y sintética. No se leyó ni completó contenido histórico expirado.
