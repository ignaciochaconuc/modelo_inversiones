# B04 — Corrección editorial trazable, pendiente de admisión

Estado: `corrected_artifact_validated_pending_versioned_import_protocol`.
No se importa B04 al conjunto principal ni se congelan referencias.

## Corrección autorizada

El propietario Nacho autorizó corregir exclusivamente la primera letra de una
cita en el caso `S-40501aee7851586a`, unidad `U4`, dimensión
`corporate_identity.evidence[0].quote`:

`an industry table includes a company named Marlow`
→ `An industry table includes a company named Marlow`.

Origen: `data/cache/news_attribution_review/chatgpt-v1/responses/B04.txt`.
Derivado: `responses/B04-corrected-v1.txt`, en el mismo directorio de revisión.
Registro: `corrections/B04-editorial-v1.json`.

SHA-256 original:
`3cf681fcdb7581acdd14cdb8cf82e54d585bec6c4027a109879043b9553c1097`.
SHA-256 corregido:
`eb69939d6d8854fb7f6ddb237c89eb9026d0c8e9be9cb3f6208a6237e10c385c`.

Una sustitución de byte ASCII `61` → `41`, offset de base cero documentado en
el registro. Longitud, CRLF, formato, todos los demás bytes y valores JSON se
conservan. El helper exige hash original fijo, campo/caso/unidad correctos y una
sola localización literal; no elige una coincidencia ambigua. Comprueba la cita
nueva en la fuente original y ejecuta el validador completo sin excepciones.

Responsable de ejecución: Codex, por instrucción explícita de Nacho. El timestamp
de transformación es el de creación del artefacto medido por el helper en UTC;
no es un timestamp de generación de ChatGPT ni sustituye las horas de evaluación
declaradas previamente por el propietario. No hay inferencia nueva. No cambian
identidades, roles, etiquetas, estados, conclusiones u otras evidencias.

## Por qué la importación permanece pendiente

El importador actual `chatgpt-attribution-review-v1` conserva un único
`raw_response_utf8`/hash y solo reconstruye JSON o retirada del fence; no tiene
una transformación editorial diferenciada entre original y derivado. Pasar la
copia corregida como response al importador normal la presentaría como el texto
original recibido del evaluador. Una nota de procedencia o sidecar no sustituye
la reconstrucción obligatoria en import/freeze.

No se modifica ese importador, el validador, el protocolo congelado, la plantilla
de procedencia ni los contratos/prompts de producción. El helper nuevo solo
prepara el artefacto y su auditoría; **no concede admisibilidad ni importa**.
No se crea `provenance/B04.json` ni `imports/B04.json` bajo un formato que perdería
la distinción de origen. La copia sigue siendo candidata pendiente, no referencia
principal admitida. Los imports anteriores y el primer B01 contaminado no cambian.

## Mecanismo versionado propuesto — no implementado ni aprobado

Una futura versión explícita del instrumento de importación/freeze podría:

1. Conservar por separado original íntegro/hash/procedencia del evaluador,
   derivado íntegro/hash, anotación validada y registro de corrección.
2. Exigir autorización, responsable, motivo, ubicación JSON y byte offset,
   valores exactos antes/después y fecha real de transformación. No usar un
   timestamp nuevo como generación del evaluador ni inventar parámetros API.
3. Reconstruir la operación exacta desde el original; verificar original y
   derivado, unicidad del campo/ubicación y que ningún otro byte/valor cambió.
   Las correcciones deben ser propuestas explícitamente, nunca normalizaciones
   automáticas de citas rechazadas o alteraciones de etiquetas semánticas.
4. Ejecutar todos los validadores originales sobre el derivado, sin ampliar
   aceptación factual/semántica. Si no se valida, no admitir el resultado.
5. Incorporar los fingerprints de ambos artefactos y operación a una identidad
   de registro nueva, con `source_kind=post_evaluation_editorial_correction`;
   no reescribir registros históricos v1. Freeze/replay deben recalcular el
   derivado y verificar toda la cadena, no solo leer el sidecar.
6. Separar estadísticas de respuestas originales rechazadas y referencias
   corregidas; no ocultar el error de cita ni considerar la corrección una nueva
   inferencia, evaluación independiente o mejora de generalización.

Esa decisión requiere autorización/versionamiento del instrumento y tests
adversariales antes de usarlo. No se eluden sus controles actuales en esta tarea.

## Limitaciones y reproducción

Aunque la corrección es editorial y literal, modifica una respuesta tras verla.
Debe declararse al analizar calidad del evaluador y conteos de rechazo. La copia
validada no demuestra entailment, calidad semántica, independencia humana ni
comportamiento de Nacho. Si los casos guían mejoras, siguen siendo desarrollo,
no un holdout independiente tras la corrección. Ninguna integración a inversiones.

```powershell
python tools/evaluation/prepare_b04_editorial_correction.py
```

Rerun idéntico conserva copia y registro existentes, incluyendo transformed_at.
No sobrescribe diferencias. Los tests usan fixtures mecánicas, no referencias
semánticas del corpus.

Validaciones ejecutadas:

- Copia corregida: validación completa original aprobada; cuatro casos, 14
  menciones, 112 dimensiones. Una diferencia de byte, offset 32258; original
  de 64386 bytes y los 1579 saltos CRLF preservados.
- `python -m pytest`: 649 pruebas aprobadas, incluidas seis nuevas de integridad
  mecánica de la corrección (CRLF/LF, hash, unicidad, fuente y reglas originales).
- `python scripts/validate_data.py`: correcto; 905 revisiones/811 artículos,
  cero hashes inválidos, linaje faltante o duplicados; cuatro snapshots válidos.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Helper repetido idénticamente, sin cambiar copia ni timestamp del registro.
- Hashes antes/después: cero cambios en archivos existentes de la revisión,
  producción, scripts/config, paquetes/protocolos y ADRs inspeccionados; solo
  se añaden la copia corregida y el registro de transformación en la revisión.
Sin llamadas externas, claves, predicciones, freeze, cambios Phase 4B o inicio 4C.3.
