# Primera aprobación contractual aplicada — v1

Se aplicó exclusivamente la autorización expresa del propietario para
`D-293a6cbca3479505`, review
`contract-D-293a6cbca3479505-b33eb3a505444869`.

## Vínculo autorizado

Fingerprint contractual recalculado con la función oficial antes de escribir y
comprobado nuevamente después de incorporar la decisión:

`b04d2b77f21c187c517783a50e6a6e834d26eb280499fdde715ce89101387cdd`.

Decisión nueva, contrato `news-pilot-contract-owner-decision-v1`:

`data/cache/news_development_pilot/contract-manual-attempt01/owner-decisions/D-293a6cbca3479505.owner-decision-v1.json`

SHA-256:
`9eaa703f92fb49a3261405bdf0635c140235fb1a8d059500f7f6ac961d104b42`.

La fuente es la instrucción expresa del propietario en esta conversación,
titulada «Phase 4C.2 — Aprobación contractual definitiva del primer caso».
Se conserva el identificador canónico de aprobador del historial:
`Project owner, current conversation participant`. `decided_at` queda `null`:
no se dispone de timestamp de aprobación. No se inventaron firma o identificador
de mensaje; el esquema de decisión no contiene campos para ellos. El registro
de aplicación deja explícita su ausencia.

Es revisión manual asistida por ChatGPT y propietario no independiente, sin
adjudicación independiente. No es inferencia ni evaluación del modelo.

## Modificación y preservación

En el formulario se cambiaron únicamente `status` a `completed` y la referencia
content-addressed de `owner_decision`. Se actualizó exclusivamente su referencia
en el manifiesto. Los once mappings, sus justificaciones, el rationale y los
resultados `interpreted`, `indeterminate` permanecen intactos; F006 sigue
`structured`, los otros diez `faithful_partial_only`.

Las expresiones de borrador o provisionalidad dentro de las justificaciones se
conservaron como parte del contenido exacto autorizado; no se reescribieron para
registrar la aprobación. La nueva decisión expresa documenta su aprobación final.

SHA-256 del formulario final:
`c76498d2a4d59d0993adf27ee50828391b8de54be0658c12419c836e99796de0`.

La sesión ya estaba `completed`, con reloj `stopped`. Su SHA-256 permanece:
`35488235aa0f9d87e89884484f08f988209415ca65fa628f1355d272dc6245cd`.
Antes de escribir se verificaron los seis eventos, hashes, continuidad, backups
de sesiones y formularios, referencias de manifiestos archivados y ausencia de
eventos huérfanos o archivos pendientes. No se ejecutó `stop` ni otra acción temporal.

Historial añadido en:
`data/cache/news_development_pilot/contract-manual-attempt01/contract-approval-v1/`:

- `before/form.json` y `before/manifest.json`: copias exactas previas.
- `integrity-baseline.json`: hashes de los 3875 archivos existentes comprobados.
- `application-record-v1.json`: enlaces antes/después, decisión, validación y límites.

Solo cambiaron los dos archivos operativos expresamente autorizados. Los
factuales, aprobaciones anteriores, cierres laterales, evidencia, reloj, contrato
técnico v3 y estados oficiales permanecen intactos. Los seis factuales históricos
siguen `in_progress`; ninguno se rehabilitó para estadísticas temporales.

## Estado y validación

| Caso | Estado contractual |
| --- | --- |
| D-293a6cbca3479505 | completed |
| D-a8db3a0c74d93eb8 | unfilled |
| D-fbf4c5c9e02691b3 | unfilled |
| D-40e8a2188273506b | unfilled |
| D-1211fcda178c57ab | unfilled |
| D-6c6ef03a91cca2a9 | unfilled |

El preflight del adaptador pasa. La validación global `--require-completed`
sigue bloqueada por `contract_review_not_completed`, como corresponde a los
otros cinco casos sin iniciar. El piloto integral y el experimento v3/v4
permanecen sin completar. No se inició ninguna revisión adicional ni Phase 4C.3.

No hubo llamadas API, agentes, inferencias, cambios de prompts, validadores o
referencias técnicas. No se detectaron discrepancias de integridad ni del
fingerprint autorizado.

Validaciones finales: `python -m pytest` — 1073 tests pasan;
`python scripts/validate_data.py` y `python -m compileall -q src scripts` —
correctos. La auditoría posterior confirma los 3875 archivos existentes: solo
formulario y manifiesto cambiaron, con copias previas verificadas por SHA-256.
