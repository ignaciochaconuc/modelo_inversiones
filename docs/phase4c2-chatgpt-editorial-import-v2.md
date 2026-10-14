# Phase 4C.2.2 — Importación editorial trazable v2

Extensión de instrumentos offline, no contratos/prompts/algoritmos de producción.
Phase 4C.3 sigue `not_started`. No se congelan referencias reales en esta tarea.

## Decisión y contrato mínimo

`chatgpt-attribution-review-v2` añade una ruta opt-in `import-editorial`.
`import-response` sigue produciendo v1; B01/B02/B03 conservan bytes, IDs y lectura.
El validador `validate_annotations()` no cambia: exige citas exactas por caso/
campo, todas las dimensiones, IDs y fingerprints del corpus original.

La política `quote-initial-ascii-case-v1` permite exclusivamente intercambiar la
mayúscula/minúscula ASCII de la **primera letra de una cita**, con el resto idéntico.
No elimina espacios, normaliza Unicode, hace fuzzy matching o cambia palabras,
negaciones, cifras, roles, identidades, valores, estados, racionales/conclusiones.
Se admite una lista no vacía de operaciones expresamente autorizadas; ninguna
operación se descubre o aplica automáticamente a partir de errores de validación.
Un quote-before repetido/escapado sin localización literal inequívoca se rechaza
en esta versión conservadora; soportarlo requeriría otra política explícita.

Archivos separados:

- Lista de cambios `chatgpt-editorial-change-list-v1`, con política, bloque/hash
  del paquete, hashes de ambas respuestas, puntero JSON, identidad de caso/unidad/
  evidencia, valor antes/después, offset y byte exactos, editor, motivo y tiempo.
- Autorización `chatgpt-editorial-authorization-v1`, aprobación explícita, acción,
  propietario, responsable de registro, contexto de autorización, hashes exactos
  de lista/respuestas y fingerprint de **la lista permitida completa**.
- Registro v2, con `original_provider_response` y
  `editorially_corrected_annotation` separados, ambos íntegros con SHA-256,
  lista/autorización íntegros con hashes, procedencia del evaluador original,
  anotación validada y rechazo original conservado. `new_chatgpt_generation=false`.

No usar la ruta original v1 para presentar un derivado como respuesta original.
Los tiempos del evaluador permanecen declarados por el propietario, no timestamps
de plataforma. transformed_at corresponde al editor; recorded_at a captura de
autorización. owner_authorized_at puede ser null si no se conoce el instante de
la instrucción del propietario: no se inventa ese tiempo.

## Verificación y freeze compatible

Import/`verify-import`/freeze recalculan los hashes de textos y artefactos,
comprueban scope de autorización y lista permitida, reconstruyen cada cambio desde
los bytes originales, verifican unicidad de campos/offsets y comparan íntegramente
el derivado y el JSON esperado. Solo cambian los campos quote declarados; cualquier
otro byte o valor JSON invalida la cadena, aunque se recalculen hashes del derivado
y del registro externo. Se ejecuta después la validación completa original.

Para B04 también se conserva y verifica el manifiesto editorial previo íntegro:
su hash, valores y todas las localizaciones/responsables/timestamps deben coincidir
con la nueva lista autorizada. No se actualiza su estado histórico pendiente.
El nuevo registro es la evidencia de admisión posterior, no una reescritura.

Freeze admite mezcla v1/v2 y reconstruye toda cadena v2 antes de escribir. Si hay
v2, el contenedor nuevo declara v2; todo-v1 conserva estructura/versionamiento
previo. Los records v1 no se migran ni reciben identidades nuevas. Todavía se
exigen B01–B08 completos y no se ejecuta freeze de los datos reales ahora.
La comparación existente sigue leyendo cases; retener además clasificación y
rechazo del original al reportar calidad del evaluador y ajustes editoriales.

Hashes y atestaciones **no son firmas digitales**: la autorización inicial consta
en la instrucción explícita del propietario en la conversación, registrada por
Codex y ligada a los artefactos. El programa verifica esa declaración/hash, no
autentica por sí solo una identidad humana si alguien falsifica toda la custodia.
El almacenamiento/retención y revisión de autorización siguen a cargo del dueño.

## B04: autorización e importación

Original, copia corregida y `corrections/B04-editorial-v1.json` permanecen intactos.
Se añaden lista/autorización versionadas, procedencia y un import v2, solo después
de pasar regresiones y de comprobar autorización expresa del propietario.

```powershell
python tools/evaluation/prepare_b04_editorial_authorization.py --confirm-owner-authorized-import
python tools/evaluation/prepare_chatgpt_review.py import-editorial --block B04 --original data/cache/news_attribution_review/chatgpt-v1/responses/B04.txt --corrected data/cache/news_attribution_review/chatgpt-v1/responses/B04-corrected-v1.txt --correction-manifest data/cache/news_attribution_review/chatgpt-v1/corrections/B04-editorial-change-list-v1.json --authorization data/cache/news_attribution_review/chatgpt-v1/corrections/B04-editorial-import-authorization-v1.json --provenance data/cache/news_attribution_review/chatgpt-v1/provenance/B04.json --destination data/cache/news_attribution_review/chatgpt-v1/imports/B04.json
python tools/evaluation/prepare_chatgpt_review.py verify-import --block B04 --record data/cache/news_attribution_review/chatgpt-v1/imports/B04.json
```

La bandera registra una autorización previamente recibida; no concede permiso por
sí sola ni sustituye aprobación del propietario. El helper no modifica el manifiesto
anterior y no realiza inferencia. La procedencia de B04 usa las declaraciones ya
confirmadas: Nacho, 2026-10-14 16:36–16:39 -03:00, sesión nueva, sin predicciones,
etiqueta visible GPT-6, sin API y snapshot/parámetros/tokens null.

## Limitaciones metodológicas

La respuesta original contiene un error y sigue rechazada por el validador.
La anotación admitida es un derivado editorial, no un éxito original del evaluador
ni una inferencia nueva. Reportar ambos estados y no ocultar ese error en métricas.
La operación no certifica entailment, calidad semántica, causalidad, generalización
o ground truth humano independiente. Cambios guiados por estos casos son desarrollo;
no presentar luego los mismos como holdout independiente.

Protocolo humano/4C.1, corpus/fingerprints, Finnhub restringido, producción, PIT,
budgets, router, claves, snapshots y smokes históricos no cambian. La propuesta
previa de B04 se conserva como historia; este documento registra su autorización
e implementación posterior.

## Estado y validaciones de entrega

B04: **importado como anotación corregida editorialmente v2**, no como respuesta
original exitosa ni nueva generación. Record ID:
`7bd32b56feea22649090bdf2d578c330d8619a12acbb25c7d3ec8292505b55c4`.
El original conserva `quote_not_in_declared_case_field`; el derivado pasa la
validación completa de cuatro casos. Sus bytes coinciden con los archivos intactos.

- `python -m pytest`: **675 passed**, 44,85 s; 26 regresiones nuevas adversariales.
- Focal importador/cadena: 58 passed, incluidos los 32 tests anteriores.
- `python scripts/validate_data.py`: correcto; 905 revisiones, 811 artículos,
  cero hashes inválidos, linaje faltante o duplicados; cuatro snapshots válidos.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Verificación individual real B01/B02/B03 v1 y B04 v2: correcta; IDs anteriores
  intactos. Freeze mixto se probó solo con fixtures sintéticas temporales.
- Hashes antes/después: cero cambios en archivos existentes de revisión, incluida
  la terna B04 original/derivado/manifiesto previo. Producción, configuración,
  paquetes originales, ADRs, datos/modelos/reportes y caché histórica de inferencias
  inspeccionados permanecen sin cambios. Se añaden cuatro archivos locales:
  lista autorizada, autorización, procedencia e import B04.

No se realizaron inferencias, llamadas externas, predicciones ni freeze real.
Phase 4C.3 permanece `not_started`; no se declara cierre semántico de 4C.2.
