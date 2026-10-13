# Phase 4C.2.2 — Revisión exploratoria manual con ChatGPT

Estado: **`chatgpt_review_prepared_pending_execution`**.
Clasificación: `chatgpt_assisted_exploratory_review`.
Cero respuestas reales importadas, cero predicciones Nacho y cero llamadas API.

## Alcance

Instrumento nuevo y separado del protocolo humano y del plan API anterior. Los
32 casos originales, textos, IDs, fingerprints y evidencia neutral no cambian.
Tampoco producción, contratos, prompts, configuración, algoritmos, smokes,
ledger, Phase 4B o TEST oficial. Los tests simulan instrumentos, no referencias
semánticas reales ni predicciones de Nacho. Phase 4C.3 sigue `not_started`.

No se consulta documentación externa, se carga `.env` ni se instancia proveedor,
SDK o cliente de red. La herramienta utiliza archivos locales y biblioteca
estándar. No hace ninguna llamada a ChatGPT: el propietario copiará los textos
manualmente cuando decida ejecutar la revisión. No se requiere API key.

"Gratuita" significa **sin llamadas pagadas a APIs** en este flujo. No se afirma
que una suscripción ChatGPT sea gratuita, que exista determinada cuota o que la
conversación tenga telemetría/API equivalente. Esos costes/límites no se conocen.

## Paquete ciego listo para copiar

Directorio: `evaluation/phase4c2_chatgpt_review_v1/prepared/packets/`.
Ocho archivos `B01.md`–`B08.md`, cuatro casos cada uno. Cada Markdown incluye las
instrucciones completas, titular/resumen ficticios, case_id, evidence_id y
fingerprint originales, y la misma tabla neutral completa de diez entradas.
Se mantiene el orden opaco del paquete original, sin ordenar por stratum o por
resultado esperado. La tabla no se filtra por nombres: no revela la selección
ni incorpora aliases o tickers nuevos a producción.

No enviar `operator/`, producción, tests, manifest de muestreo, predicciones,
auditorías de smokes o este historial de desarrollo al evaluador. Los paquetes
solo contienen evidencia e instrucciones de anotación. Sus JSON auxiliares son
copias estructuradas para verificar integridad; no incluyen respuestas esperadas.

**No usar esta conversación de desarrollo como evaluador ciego**: ya contiene
reglas/resultados. Usar una conversación limpia por bloque, sin adjuntos del
repo, instrucciones/contexto de Nacho ni búsqueda/herramientas. El propietario
debe comprobar el contexto disponible y declarar limitaciones de memoria/
configuración que no pueda verificar. El cegamiento se declara y documenta;
los hashes no prueban que ChatGPT carezca de otro contexto.

## Cómo ejecutar manualmente

1. Verificar los paquetes. Copiar íntegramente `B01.md` en una conversación nueva.
2. Pedir solo la anotación prevista en el propio bloque, sin sugerir resultados
   correctos o informar qué acepta Nacho. Guardar la primera respuesta completa,
   sin editar, como UTF-8 en `data/cache/news_attribution_review/chatgpt-v1/responses/B01.txt`.
3. Copiar la plantilla `templates/B01.provenance.json` a un directorio privado
   `provenance/`, y completar procedencia real. No editar las plantillas congeladas.
4. Repetir B02–B08 en sesiones separadas. Mantener errores, truncamientos,
   ambigüedades y abstenciones; no escoger retrospectivamente la respuesta más
   concordante. Si necesita aclaración/reintento, conservar el original y la
   interacción adicional y versionar el intento, antes de revelar predicciones.
   Los instrumentos actuales importan una respuesta íntegra por bloque; no fusionan
   varias respuestas ni silenciosamente reparan una incompleta.
5. Importar/validar cada respuesta; congelar conjuntamente las ocho antes de
   ejecutar o revelar Nacho. No autorizar inferencia de Nacho por completar esta
   preparación. Actualmente no se ejecutan pasos de revisión ni predicciones.

## Anotación y procedencia

Respuesta estructurada: block_id, limitations y cuatro cases. Cada caso conserva
case_id/fingerprint y anota events, units, uncertainties y status
annotated/nonconclusive/abstained/technical_error. Cada mención tiene ocho
dimensiones separadas: identidad, participación, rol, relación, ticker, estado,
etapa e impacto. Conclusiones, incertidumbre, insuficiencia y no aplicabilidad
permanecen explícitas. No hay roles de producción obligatorios ni expectativa
de aceptar la sintaxis de los validadores. Inferencia potencial no es exposición
confirmada ni estimación de retorno.

La plantilla de procedencia registra:

- interface `chatgpt_conversation`, responsable real de la captura (no adjudicador
  humano ficticio), block_id, hash exacto del paquete y referencia de conversación
  opcional/privada;
- started_at/completed_at reales, con zona horaria, no fechas inventadas por ChatGPT;
  por ejemplo usar el offset real de America/Santiago al momento de la revisión;
- visible_model_label solo si se observa en la interfaz, y `model_label_visibility`
  visible_label o not_exposed; desconocido permanece null. Un label visible no
  demuestra backend/snapshot idéntico;
- model_snapshot, api_parameters y api_tokens **null**. No inferir temperatura,
  reasoning, semilla, versión interna o tokens por el texto de la respuesta;
- api_calls/paid_api_cost_usd cero para este flujo manual; coste de suscripción
  separado, desconocido/no medido. No equiparar falta de telemetría con gratuidad
  universal;
- declaración explícita de conversación limpia y ausencia de outputs del sistema,
  limitaciones reales del contexto y de la respuesta. No inventar independencia.

El importador conserva bytes UTF-8 originales mediante texto íntegro + SHA-256,
JSON anotado, fingerprint del paquete, procedencia, transformación y record_id.
Solo se permite JSON completo o un único fence JSON externo, cuya retirada queda
registrada. No extracción heurística, fuzzy matching, normalización de citas,
corrección semántica, merge ni selección silenciosa del primer caso coincidente.

## Validación y freeze offline

Se comprueban hashes originales/paquetes, cuatro casos exactos sin duplicados,
fingerprints, campos estructurales, ocho dimensiones, IDs, citas presentes en el
campo/caso declarado e índices válidos de identidad. JSON duplicado/NaN,
truncamiento, casos omitidos, citas fabricadas y procedencia incompatible se
rechazan. Una cita presente **no demuestra entailment**: la validación no certifica
que una entidad tenga ese rol o impacto, ni convierte un dato de la tabla en
exposición. Se requiere interpretación cualitativa posterior.

`record-failure` registra explícitamente un bloque inutilizable como cuatro
errores técnicos, sin etiquetas. Conserva su respuesta original y causa sanitizada;
no transforma automáticamente un fallo en abstención o anotación positiva.

El freeze requiere ocho imports, reconstruye las transformaciones, verifica
hashes/procedencia y conserva fallos/no concluyentes. Se escribe de forma inmutable;
repetición idéntica devuelve el mismo hash/timestamp, diferencias no sobrescriben.
La firma humana/realidad de una conversación no puede comprobarse automáticamente:
los artefactos son evidencia de custodia declarada, no prueba criptográfica de
ejecución de ChatGPT ni referencia humana independiente.

## Comandos

Desde la raíz, preparación y verificación seguras:

```powershell
python tools/evaluation/prepare_chatgpt_review.py prepare
python tools/evaluation/prepare_chatgpt_review.py verify
```

Solo después de obtener realmente la respuesta B01 y completar su procedencia:

```powershell
python tools/evaluation/prepare_chatgpt_review.py import-response --block B01 --response data/cache/news_attribution_review/chatgpt-v1/responses/B01.txt --provenance data/cache/news_attribution_review/chatgpt-v1/provenance/B01.json --destination data/cache/news_attribution_review/chatgpt-v1/imports/B01.json
```

Repetir para B02–B08. Una respuesta truncada no debe "arreglarse" para pasar:

```powershell
python tools/evaluation/prepare_chatgpt_review.py record-failure --block B01 --reason response_truncated --response data/cache/news_attribution_review/chatgpt-v1/responses/B01.txt --provenance data/cache/news_attribution_review/chatgpt-v1/provenance/B01.json --destination data/cache/news_attribution_review/chatgpt-v1/imports/B01.json
```

No reemplazar un import existente: guardar intentos nuevos/versionados aparte.
Imports debe contener únicamente B01.json–B08.json. Tras reunir todos:

```powershell
python tools/evaluation/prepare_chatgpt_review.py freeze --imports data/cache/news_attribution_review/chatgpt-v1/imports --destination data/cache/news_attribution_review/chatgpt-v1/references-frozen.json
```

Los comandos de import/freeze se prueban ahora solo con fixtures simuladas en
directorios temporales; no hay respuestas reales ni referencias congeladas nuevas.

## Comparación posterior, todavía bloqueada por outputs inexistentes

Una futura exportación de Nacho requiere autorización/ejecutor separado y los
contratos originales. Debe contener los 32 cases, outcome, units normalizadas por
dimensión y, si hubo intento, attempt_started_at, record_id y output_fingerprint.
No generar unidades artificiales para rechazos o errores. Alinear manualmente
eventos/menciones con referencias ya selladas, conservando omisiones/unidades extra.

Archivo alignment: reference_freeze_sha256, system_file_sha256 y matches con
case_id, reference_unit_id, system_unit_id. No se copian valores de referencia a
la alineación: el comparador los lee del freeze. Se rechaza ejecución anterior
al freeze y se conservan los 32 casos/estados. Roles en lenguaje natural pueden
ser equivalentes sin igualdad literal; ese desacuerdo requiere revisión, no una
modificación retroactiva de referencias.

```powershell
python tools/evaluation/prepare_chatgpt_review.py compare --reference-freeze data/cache/news_attribution_review/chatgpt-v1/references-frozen.json --system-file data/cache/news_attribution_review/chatgpt-v1/nacho-outputs.json --alignment data/cache/news_attribution_review/chatgpt-v1/alignment.json --destination data/cache/news_attribution_review/chatgpt-v1/comparison.json
```

Se reportan dimensiones separadas, acuerdo/desacuerdo literal contra ChatGPT,
omisiones, unidades extra, no concluyentes, abstenciones, rechazos, errores,
unresolved y not_run, además de fallos del evaluador. La cola del propietario
conserva los 32 casos y prioriza discordancias/atribuciones críticas. La revisión
del propietario después de ver outputs es no ciega/no independiente, documentada
en un estrato separado, sin sustituir referencias iniciales.

Las plantillas pendientes no se importan como resultados. No calcular precisión,
recall o generalización contra "verdad humana". Este flujo no garantiza un evaluador
de familia diferente a Nacho; comparte el entorno OpenAI y el backend puede no
conocerse. El corpus es IA-autorado y la muestra es pequeña/enriquecida:
hay sesgos compartidos y respuestas plausibles equivocadas. El flujo mide
concordancia exploratoria y facilita revisión de evidencia, no calidad poblacional,
causalidad o alpha. Alto acuerdo no cierra automáticamente 4C.2 ni habilita 4C.3.
Si se ajusta usando estos casos, pasan a desarrollo; una repetición es regresión,
no evaluación independiente.

## Contenido y conservación

No hay noticias Finnhub en el paquete. Continúa prohibida su revisión externa
hasta verificar derechos. No se usan smokes como holdout ni se reabre TEST.
Respuestas/capturas/procedencia completas viven bajo `data/cache/`, ya ignorado
por Git, con retención y acceso acordados por el propietario; no publicar enlaces
privados, datos personales o secretos. No se modifica `.env` ni se leen claves.
No se borra ni prolonga la retención de ningún artefacto histórico.

## Validaciones de entrega

- `python -m pytest`: **643 passed**, 41,86 s; 32 pruebas nuevas mecánicas con
  fixtures simuladas, sin etiquetas para los 32 casos originales.
- Regresión focal tras endurecer validación de procedencia: 32 passed, 2,25 s.
- `python scripts/validate_data.py`: correcto; 905 revisiones, 811 artículos,
  cero hashes inválidos, linaje faltante o duplicados; cuatro snapshots válidos.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Preparación reproducida de forma idéntica y verificada: ocho bloques, 32 casos;
  se reconstruye exactamente el corpus original desde los paquetes.
- Integridad SHA-256 antes/después: **3.392 archivos protegidos, 18 grupos,
  cero cambios**. Incluye producción, configuración, protocolos humano/IA,
  casos originales, comparadores anteriores, datos, smokes y ledger históricos.

Las respuestas/freeze de los tests viven exclusivamente en directorios temporales.
No se generaron ni importaron referencias reales. No hay red, API, claves,
predicciones, revisión externa Finnhub o avance a Phase 4C.3 en esta tarea.
