# Phase 4C.2 — Corrección focalizada H01 — v1

## Autoridad y alcance

Corrección autorizada por el propietario mediante «Corrección focalizada de H01:
sanitización del contexto de excepciones» en esta conversación. Este registro es
asistido por ChatGPT y pertenece al desarrollo; no es un nuevo dictamen externo,
aprobación de cierre o autorización de fase. No se inventan firmas, identificadores
de mensaje o timestamps de aprobación.

Se modifica únicamente el cliente OpenAI y se añaden regresiones y este suplemento.
No cambian prompts, contratos económicos, reglas semánticas/PIT, DTOs, presupuesto,
retención, expedientes, instrumentos temporales, planes experimentales o ADR-032.
No hay inferencias reales, evaluaciones semánticas ni llamadas externas.

## Causa raíz y reproducción previa

`OpenAIClient.complete()` convertía excepciones de transporte y parseo dentro del
propio `except` mediante `raise LLMProviderError(...) from None`. Eso suprime la
cadena del traceback habitual, pero conserva la excepción privada en `__context__`.

Con `httpx.MockTransport` y una clave ficticia, las regresiones verificaron:

- `ReadTimeout`/`ConnectTimeout` y `ConnectError`/`ReadError` conservaban el request
  autenticado en la excepción privada, aunque el mensaje público fuera seguro.
- Un cuerpo no JSON conservaba `JSONDecodeError.doc`; errores de estructura del
  envelope también permanecían encadenados.
- Antes del cambio: siete regresiones fallaron por contexto no nulo y siete
  controles de HTTP/respuesta válida pasaron. No se utilizaron credenciales reales.

Esto confirma H01; no demuestra que hubiera ocurrido una filtración histórica en
logs o persistencia. No se consultaron respuestas reales ni contenido expirado.

## Corrección mínima

Los manejadores guardan exclusivamente un código fijo de transporte o un booleano
de parseo fallido. La excepción pública se construye y lanza **fuera del manejador
original**, como en `core/environment.py:load_repository_environment`.
No se copia la excepción privada ni se alteran sus atributos.

Se preservan `LLMProviderError`, `args`, mensajes y códigos `timeout`, `disconnect`
y `invalid_provider_envelope`, `retryable=True` y `response=None` en esas ramas.
Las categorías HTTP, respuestas correctas, telemetry, wire y políticas de caller
permanecen iguales. No se añaden retries al cliente; reserva y retry siguen siendo
responsabilidad de la orquestación existente.

No cambia una decisión arquitectónica: se cumple la garantía existente de errores
seguros de ADR-028 y de `LLMProviderError`; no se crea otro contrato o ADR.

## Regresiones offline

Archivo: `tests/integration/test_openai_exception_context.py`, catorce escenarios:

- Cuatro errores de transporte: tipo público, código, retry, ausencia de causa y
  contexto, atributos explícitos seguros, silencio de logs/stdout/stderr y una
  sola llamada al transporte simulado. El objeto privado original no se modifica.
- JSON inválido con marcadores sintéticos: el cuerpo no se encadena ni se altera
  en el objeto HTTP original.
- Dos envelopes inválidos: se preserva la categoría pública de error de parseo.
- Seis estados HTTP: se mantienen códigos, retry y ausencia de encadenamiento.
- Respuesta válida: contenido, modelo, timestamp y tokens de entrada/lectura de
  caché/escritura/salida; un único envío simulado, JSON estricto y flags de transporte.

Las aserciones comprueban `__context__ is None`, `__cause__ is None`, atributos
contractuales sin objetos HTTP/excepciones privadas, y ausencia de marcadores en
mensaje, representación de atributos y traceback formateado sin captura de locales.
La fixture sustituye la clave del proceso por un valor sintético y no carga `.env`.
Las fixtures globales bloquean red y DNS; toda persistencia de tests de runtime
se realiza en temporales.

Comandos ejecutados, primero focalizados y después suite completa:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest -p no:cacheprovider tests/integration/test_openai_exception_context.py tests/integration/test_news_interpretation_runtime.py tests/integration/test_news_cache_write_accounting.py --tb=short -q
python -B -m pytest -p no:cacheprovider -o addopts='' -q
```

Resultado focalizado: **68 pruebas correctas** en tres suites, incluidas las catorce regresiones H01.
Resultado de la suite completa: **1188 passed in 241.09s (0:04:01)**.
No se atribuyen estos resultados a un proveedor real ni a una revisión independiente.

## Integridad y compatibilidad

SHA-256 del cliente anterior:
`7f739aea7d5c8d15b7e502b074479f4803da05640dd6b564c8fa48df5b912e37`.

SHA-256 del cliente corregido:
`7e218a89e36e2c91b5a2e611f0683ee6259fcc4ed574d2753f33b23cb917990c`.

Inventario previo protegido: 4656 archivos, excluyendo únicamente el cliente que
se autoriza modificar y las dos rutas nuevas de este cambio. SHA-256 agregado:
`239720869388bbb6258bdfd679dabf201c212c7fbcc6040e39553cddb4962e94`.
Algoritmo: SHA-256 de la concatenación de JSON compactos UTF-8 ensure_ascii de
`[ruta_relativa_posix, sha256_archivo]`, ordenados por `pathlib.Path`, sin `.git`.
Verificado al finalizar: los 4656 archivos conservan sus hashes. Incluye factuales, cierres, relojes, normas,
prompts, validadores, settings y expedientes históricos.

El inventario del expediente externo v1 permanece intacto: su hash del cliente
corresponde deliberadamente a la versión **anterior**. No regenerarlo como si su
auditoría hubiera cubierto el código corregido. Entregar este suplemento y el diff
para una posterior revisión; cualquier plan futuro de inferencia debe fijar el
código vigente y obtener su propia autorización. No se reutiliza una autorización
de ejecución ni se modifica un resultado histórico para adaptarlo al cambio.

## Límites y estado pendiente

La garantía comprobada cubre el contexto/causa originados por los manejadores
corregidos y los atributos contractuales de sus excepciones públicas. No implica
borrado de memoria, eliminación de claves necesarias durante el transporte ni
sanitización de volcados de proceso o introspección de variables locales de todos
los frames Python. No exportar `f_locals` o tracebacks con captura de locales como
telemetría segura. Tampoco certifica cadenas añadidas por un caller externo.
Las respuestas tipadas que otros errores públicos conservan deliberadamente para
contabilidad/procedencia mantienen su contrato; no se eliminan en este cambio.

La corrección de H01 no satisface por sí sola los requisitos pendientes de ADR-032,
no completa evaluación semántica externa ni rehabilita tiempos. Mantener:

- `integral_pilot_completed=false`.
- `semantic_truth=not_assessed`.
- `factual_timing_rehabilitated=false`.
- Phase 4C.2 `implemented_pending_external_review`.
- Phase 4C.3 `not_started`.

Fuentes consultadas: `src/investment_system/llm/openai_client.py`,
`llm/openai_settings.py`, `core/environment.py`, las tres suites focalizadas,
`docs/decisions/ADR-028-real-news-inference-and-cost-governance.md` y las garantías
de errores de `docs/phase4c2-review.md:104–118`. Ninguna de esas normas se reescribe.
