# Procedimiento contractual simplificado v1

Implementación offline preparada y probada; no se abrió ningún caso real adicional.

En el primer caso se hicieron manualmente copias de materiales, creación de
reserva, enlace de autorización, edición de mappings, archivos históricos,
proyecciones de estado para fingerprint, decisión y actualización de hashes.
El nuevo CLI automatiza esas tareas administrativas con los esquemas existentes.
El propietario sigue decidiendo cuándo empieza cada actividad, qué contenido
aprueba y si autoriza el cierre. No es revisión humana independiente.

## Preparación y apertura: actos distintos

Desde la raíz del repositorio, definir un acceso corto de PowerShell:

```powershell
$work = 'data/cache/news_development_pilot/contract-NUEVO-CASO-attempt01'
$source = 'data/cache/news_development_pilot/contract-manual-attempt01'
function cr { python tools/evaluation/pilot_contract_workflow.py --workspace $work @args }
cr prepare --source $source --case CASE_ID
```

`CASE_ID` y `$work` son placeholders que se reemplazarán después de autorizar la
preparación del caso elegido; no ejecutar ahora sobre los cinco casos pendientes.
Para el tercer caso y siguientes, usar como `$source` el workspace más reciente
con revisión ya completada. No bifurcar desde una selección anterior.

`prepare` genera un review_id nuevo, formularios/sesión sin iniciar, los templates
vacíos y `materials/CHATGPT-PACKET.md`: noticia ficticia completa, factual aprobado
íntegro, 13 dimensiones e incertidumbres, esquema de entrega y fuentes exactas del
contrato técnico v3. Se puede entregar este paquete en una sola conversación
manual de ChatGPT y recibir todos los mappings juntos. Los archivos bajo
`materials/` son de solo lectura lógica y están fijados por hash.

El propietario debe autorizar la apertura específica del case_id/review_id.
Copiar `OPENING-TEMPLATE.json` a un archivo versionado `owner-opening-v1.json`,
completar únicamente con esa autorización real y conservar null en fechas o
IDs de mensaje desconocidos. La plantilla lleva `explicitly_authorized=null`
y no es una autorización válida por sí misma.

```powershell
cr open --authorization "$work/owner-opening-v1.json"
```

Valida y conserva la autorización; **no empieza el reloj ni completa juicios**.
La identidad debe ser la etiqueta canónica del cierre factual, disponible en
su disposición, no un nombre inferido. El verificador exige ese mismo actor.

## Una sesión prospectiva y una entrega completa

El operador ejecuta cada comando en el momento real de la actividad. El reloj
captura UTC del sistema; no recibe fechas retrospectivas ni usa el reloj ficticio.

```powershell
cr clock start --phase material_reading --reviewer-id nacho --reviewer-name Nacho --context 'Propietario; revisión asistida por ChatGPT, no independiente.'
cr clock phase --phase contract_mapping
cr clock pause --reason ai_wait
```

Pausar antes de esperar a ChatGPT. Para descansos/interrupciones usar `break`,
`interruption` u `other`. Mientras se espera, el tiempo no cuenta como activo.
No marcar actividad humana porque ChatGPT esté trabajando. Si una tarea no se
realiza, no generar un intervalo ficticio para ella.

Entregar `materials/CHATGPT-PACKET.md` a ChatGPT manualmente, sin API. Pedir una
única propuesta JSON que complete `ANNOTATION-TEMPLATE.json`, respetando
`materials/SUBMISSION-SCHEMA.json`. Debe contener cada fact_id una vez, incluso
los no canónicos de must_not_omit, rationale y límites por hecho, resultados
permitidos y rationale global. No debe añadir hechos ni una decisión del dueño.
Guardar la respuesta como `annotation-v1.json` sin editar silenciosamente el
original; cualquier corrección se guarda con otro nombre/versionado.

```powershell
cr apply --annotation "$work/annotation-v1.json"
cr clock resume --phase evidence_check
# Tras verificar citas y el alcance técnico, al empezar la revisión del propietario:
cr clock phase --phase owner_review
# Al terminar realmente la sesión:
cr clock stop
cr approval-plan
```

`apply` incorpora la propuesta completa como borrador, valida todas las fuentes
y actualiza hashes/backups. No aprueba contenido ni cambia de fase temporal.
Si el reloj ya está activo, usar `phase`; `resume` requiere estar pausado.
`administration` es otra fase disponible si se realiza realmente. El propietario
puede revisar/corregir versiones completas del borrador antes de aprobarlas.

`approval-plan` es de lectura: exige sesión completada, todos los mappings y
tiempo real registrado en contract_mapping y owner_review. Devuelve fingerprint
oficial del objetivo `completed`, sin aplicarlo, y plantilla de decisión **no
aprobada** (`explicitly_approved=null`). Puede redirigirse a un archivo nuevo con
`>`; no sobrescribir planes anteriores. `indeterminate` es resultado del
instrumento, no estado ejecutable del payload v3.

## Aprobación del contenido y autorización de cierre: actos distintos

El propietario revisa todos los mappings y aprueba expresamente el contenido y
su fingerprint. Crear `owner-content-decision-v1.json` con el esquema/plantilla
devuelto por approval-plan, recogiendo exclusivamente esa decisión real.
`decided_at=null` si no hay una hora real de aprobación disponible. No usar la
hora de ejecutar el comando como hora atribuida al propietario.

```powershell
cr approve-content --decision "$work/owner-content-decision-v1.json"
```

Se valida con el adaptador original y se conserva una copia enlazada al input.
El formulario sigue `in_progress`. El borrador queda bloqueado frente a cambios;
si requiere una revisión posterior, detenerse y definir expresamente un nuevo
procedimiento/versionado, sin eludir esa aprobación.

Solo después de una **autorización expresa separada para aplicar el cierre**:

```powershell
cr finalize --fingerprint FINGERPRINT_APROBADO --authorized-by 'IDENTIDAD_CANONICA' --closure-source 'FUENTE_REAL_DE_LA_AUTORIZACION_SEPARADA' --authorize-final-closure
cr validate
```

No reutilizar como fuente la mera apertura o importación de mappings. El CLI
registra fuente, identidad y fingerprint de la autorización de cierre en un
recibo administrativo, con fecha/ID de mensaje desconocidos null. Sin la decisión
de contenido válida, la bandera explícita de cierre y el fingerprint exacto,
no aplica `completed`. Los otros casos no cambian.

## Trazabilidad, bloqueos y compatibilidad

`workflow.json` fija origen y materiales. `workflow-history/` conserva inputs
referenciados, snapshots antes/después, recibos de cada operación y confirmación
de aplicación por hash. Mantener los inputs versionados sin modificarlos:
editar un input anterior bloquea la auditoría. `clock/history/` y los eventos
temporales siguen siendo los del helper existente. `validate` audita también
backups, cadena temporal, eventos huérfanos y operaciones parciales sin leer
respuestas de proveedores.

Ante error de I/O o validación: no repetir comandos a ciegas ni editar hashes;
conservar todos los archivos y diagnosticar. No hay reparación, rollback o
reintento automático. Una operación parcialmente publicada queda bloqueada.
Uso local secuencial; no ejecutar comandos simultáneos sobre el workspace.

El reloj histórico y su CLI mantienen el comportamiento anterior. Solo este
flujo permite que otras revisiones de la selección ya estén `completed`; nunca
tolera otra en progreso. Los validadores económicos, sus versiones, contratos y
el fingerprint oficial no cambian. Ni preparar ni cerrar una revisión completa
el piloto integral, cambia fases oficiales o habilita inferencia.

La sesión y metadata temporal conservan retención de 90 días desde su fin; no se
extiende ese plazo ni se recuperan tiempos perdidos. El reloj no acredita
automáticamente atención humana ni elegibilidad de estadísticas de esfuerzo.
No se carga `.env`, no se usan claves y no se llaman proveedores. Las seis
aprobaciones factuales, su exclusión temporal y el primer caso contractual
aprobado permanecen intactos.

## Validación de esta entrega

- Suite completa: 1103 tests pasan; flujo nuevo y reloj: 62 tests pasan.
- `python scripts/validate_data.py`: correcto.
- `python -m compileall -q src scripts tools/evaluation/pilot_contract_workflow.py tools/evaluation/pilot_contract_clock.py`: correcto.
- Preflight histórico del adaptador: un caso contractual `completed`, cinco
  `unfilled`; reloj del primero `stopped`, sesión `completed`, 11 mappings.
- Integridad: 3749 archivos de `data`, `evaluation`, `config` y `src` sin cambios
  ni incorporaciones. El primer formulario conserva SHA-256
  `c76498d2a4d59d0993adf27ee50828391b8de54be0658c12419c836e99796de0`.

Las pruebas del flujo se realizaron exclusivamente en directorios temporales,
con fixtures estructurales y relojes sintéticos. No se ejecutó `prepare`, `open`,
`apply`, `approve-content`, `finalize` ni una acción temporal sobre casos reales.
La comprobación de los casos reales fue de lectura. No se generaron decisiones
ni mappings para los cinco pendientes.
