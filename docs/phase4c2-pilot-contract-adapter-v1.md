# Adaptador contractual del piloto de desarrollo — v1

Implementación offline autorizada, sin apertura de revisiones. Instrumento:
`news-pilot-contract-form-v2`; sesión: `news-pilot-contract-session-v1`.
Contrato técnico de referencia: `news-economic-validation-v3`, sin modificarlo.
El sufijo v2 distingue el formulario de revisión del histórico v1; no sustituye
el contrato económico v3 ni cambia el runtime de Nacho.

La instrucción del propietario autoriza implementar el adaptador y preparar
materiales. No autoriza abrir casos, completar juicios o ejecutar inferencias.
La fuente consta en
`evaluation/phase4c2_pilot_contract_adapter_v1/implementation-authorization.json`.
No se inventaron ID de mensaje, firma o timestamp. Ninguna fase oficial cambia.

## Archivos y preflight

- `tools/evaluation/pilot_contract_review.py`: verificador y modelos nuevos,
  separados de todos los validadores históricos.
- `evaluation/phase4c2_pilot_contract_adapter_v1/`: seis esquemas, autorización
  de implementación, referencia técnica fijada por hashes y manifiesto de entrega.
- `data/cache/news_development_pilot/contract-review-v2/`: seis formularios y seis
  plantillas temporales `unfilled`, con manifiesto de vínculos.
- `tests/unit/test_pilot_contract_review.py`: pruebas con fixtures técnicas en
  temporales; no son nuevos casos del piloto ni anotaciones de noticias.

Comprobación explícita, solo lectura, desde la raíz:

```powershell
python tools/evaluation/pilot_contract_review.py --validate data/cache/news_development_pilot/contract-review-v2
```

Resultado de preparación: `prepared_not_started=6`, `started=0`, `completed=0`,
cero mappings, cero llamadas e inferencias. El éxito significa que los materiales
y prerrequisitos son válidos; no significa que se haya realizado una revisión.

```powershell
python tools/evaluation/pilot_contract_review.py --validate data/cache/news_development_pilot/contract-review-v2 --require-completed
```

Este segundo comando debe bloquearse mientras falte completar cualquiera de las
seis revisiones. No omite controles ni escribe formularios. No se cargan `.env`,
credenciales, proveedores o agentes. Importar el módulo solo carga definiciones.

## Prerrequisitos y conservación factual

El manifiesto enlaza por SHA-256 la selección vigente
`data/cache/news_development_pilot/review-dispositions-v1/manifest.json`. Se valida
con el instrumento de disposiciones sin modificarlo, incluida su cadena histórica.
Los seis casos deben tener cierre `closed_content_only_untimed` válido. Un cambio
de selección, versión, documento de cierre o factual invalida los vínculos viejos;
no se selecciona silenciosamente otra versión ni se reutiliza un cierre abierto.

Cada formulario enlaza disposición, decisión de cierre y factual aprobados. Su
`factual_snapshot` conserva **el formulario íntegro**, con las 13 dimensiones,
todos los facts, sus significados, certeza, materialidad, notas, citas y offsets.
Se compara por JSON canónico con la fuente fijada por hash, distinguiendo también
tipos como true/1 y 0/0.0. No se permite corregir ni normalizar el factual en este
instrumento. Las seis plantillas retienen 74 entradas factuales y 159 citas; no
se cuentan como observaciones independientes.

`must_not_omit` no es una proyección de hechos. Para completar una revisión se
exige exactamente un mapping por **cada** fact_id, incluidos los no canónicos.
F001/F006 del primer caso permanecen en el snapshot y necesitarán mappings propios.
Su cobertura contextual aceptada para cierre no permite borrarlos de esta capa.

La referencia técnica fija por hash los archivos existentes de schemas, grounding,
replay y atribución económica. El adaptador comprueba versiones e integridad,
pero no ejecuta la interpretación ni cambia sus reglas para facilitar mappings.
Si esos archivos cambian, corresponde revisar la referencia y el instrumento;
no actualizar hashes automáticamente como si la revisión anterior siguiera vigente.

## Qué puede anotar el revisor

La capa editable contiene `mappings`, `allowed_outcomes` y `rationale`. Cada mapping
solo expresa fact_id, modo de representabilidad, explicación y límites reconocidos:

| Campo | Significado |
| --- | --- |
| `structured` | Representable preservando el significado y los límites de la fuente |
| `faithful_partial_only` | Solo parte representable fielmente; explicar la pérdida |
| `not_representable` | El contrato actual no permite expresarlo fielmente |
| `indeterminate` | No se pudo decidir la representabilidad; no forzar certeza |

Estos modos no son nuevos juicios sobre si ocurrió el hecho. No hay campos para
reescribir el acontecimiento, añadir cifras o asignar una certeza factual nueva.
Una salida técnica parcial o abstención no cambia la referencia factual.

`limits_acknowledged` debe coincidir con las limitaciones de certeza y dimensión
del hecho original: `uncertain_fact`, `indeterminate_fact`,
`insufficient_dimension`, `indeterminate_dimension`, según corresponda. Por ejemplo,
una ausencia de definición puede ser un hecho concluyente mientras su dimensión
de etapa siga indeterminada: se debe conservar esa segunda limitación.

El verificador rechaza alteraciones del snapshot, pérdida de hechos, límites
omitidos y campos de certeza añadidos a un mapping. No puede certificar la verdad
de la explicación libre ni detectar toda inferencia semántica errónea dentro de
ella. El propietario debe revisar esos razonamientos: `semantic_truth` permanece
`not_assessed`. El éxito técnico no certifica independencia, calidad semántica,
exposición económica o capacidad humana.

## Apertura futura: autorización distinta y específica

Toda anotación contractual requiere formulario `in_progress` y una sesión nueva
activa. Esta sesión requiere una autorización real posterior con esquema
`news-pilot-contract-opening-authorization-v1`, vinculada a:

- case_id y review_id nuevo;
- identidad de la disposición cerrada, hash factual y hash de decisión de cierre;
- responsable y fuente real de autorización, con timestamp/ID desconocidos null;
- permiso explícito de apertura, sin autorización de inferencia.

La autorización de implementación y la de cierre factual no cumplen ese esquema.
No existe hoy ninguna autorización de apertura ni se preparó una que afirme tenerla.
Un formulario o sesión `unfilled` no puede contener actividad, personas asignadas,
horarios o juicios. Las seis plantillas continúan vacías en esos campos.

La sesión contractual utiliza únicamente fases nuevas: `material_reading`,
`contract_mapping`, `evidence_check`, `owner_review`, `administration`. Esperas de
ChatGPT, pausas e interrupciones se registran como pausas, nunca como trabajo
humano activo. Se requieren identidad, contexto real de independencia, modo,
fuente del reloj y timestamps con zona. Etiqueta de modelo desconocida permanece
null; snapshot, parámetros y tokens API son null en esta revisión manual.

Los intervalos deben ser consecutivos, coherentes y no futuros. Totales y fases
deben concordar; los desconocidos son null. El cierre de una sesión exige fin,
intervalos y totales completos; una fase no realizada durante una sesión observada
puede registrarse como cero, pero una fase desconocida no se imputa como cero.
Se rechazan campos de reloj factual o adjudicaciones inventadas. No existe
`factual_closed_at` en la nueva sesión ni se deduce desde su comienzo.

La metadata temporal de la sesión contractual vence a los 90 días de su propio
`completed_at`. No se renueva con una aprobación posterior y no altera la retención
del factual o de las respuestas de proveedor. Las seis revisiones factuales siguen
excluidas de estadísticas medidas. Medir una futura sesión contractual tampoco
la hace automáticamente elegible para estimar capacidad: requiere otra evaluación
de alcance y calidad del cronometraje.

## Cierre contractual futuro

Completar un formulario requiere todos los fact_id, modos y límites válidos,
resultados permitidos y explicación global. Requiere además una sesión completada
con actividad de mapping y revisión del propietario registradas, y una decisión
explícita del propietario bajo `news-pilot-contract-owner-decision-v1`.

Esa decisión se vincula al fingerprint del formulario final, incluido el hash
de su sesión y todas sus fuentes; se excluye únicamente la referencia a la propia
decisión para evitar circularidad. Una edición posterior invalida el vínculo.
No se infiere aprobación del propietario por tener el reloj o los mappings llenos.
La procedencia conserva asistencia ChatGPT, ausencia de independencia humana y
ausencia de adjudicación. No se creó ninguna decisión de ese tipo en esta entrega.

Ni siquiera completar el instrumento significa completar el piloto integral,
congelar referencias, ejecutar el experimento o cambiar una fase oficial.

## Procedimiento sencillo con ChatGPT y el propietario — todavía no ejecutar

1. Obtener autorización posterior para abrir el primer caso
   **D-293a6cbca3479505** y un review_id nuevo. Registrar la fuente real y los
   vínculos actuales; no reutilizar esta instrucción de implementación.
2. Preparar entonces una copia de trabajo del paquete, conservar originales y
   actualizar únicamente rutas/hashes de los formularios y sesiones de trabajo
   en su manifiesto. Mantener las referencias factuales, cierres y referencia
   técnica. Dejar los otros cinco casos `unfilled`.
3. Al comienzo real, registrar revisor, contexto previo, modo y reloj. Capturar
   hora con zona y origen (por ejemplo, el operador ejecuta en ese momento
   `[DateTimeOffset]::Now.ToString('o')`). No usar el reloj ficticio 2031 del
   paquete como reloj humano. Cambiar sesión/formulario a `in_progress` solo
   después de contar con autorización de apertura válida.
4. En una conversación manual de ChatGPT, aportar el paquete ficticio original,
   el snapshot factual **completo**, la plantilla contractual y las reglas/esquemas
   técnicos v3 fijados en `technical-reference.json`. Pedir propuestas de
   representabilidad por todos los fact_id, sin reescribir hechos, pruebas o
   incertidumbres. No aportar predicciones de Nacho ni ejecutar un agente/API.
   Registrar solo la etiqueta visible del modelo si se conoce; la nueva conversación
   no convierte al propietario en revisor independiente.
5. El propietario revisa los mappings, especialmente omisiones, incertidumbres
   y diferencias entre nombres, participación, etapas y exposición. Registrar
   actividad humana, verificación y espera de IA por separado. Si se desconoce
   algún tiempo necesario, dejar la sesión en curso; no reconstruirlo después.
6. Registrar fin y totales reales. Obtener una aprobación expresa del contenido
   contractual final y su fingerprint, sin inventar fecha o identidad. Guardar
   primero la sesión; calcular `review_fingerprint` del contenido final sin
   referencia de decisión; guardar la decisión aprobada; adjuntar su referencia;
   calcular entonces el hash del formulario final y actualizar el manifiesto. Validar
   la copia de trabajo con `--validate`; usar `--require-completed` solo cuando
   se pretenda comprobar los seis casos completos.

Este procedimiento es una preparación operativa. No se ejecutó ninguno de sus
pasos de apertura, anotación, lectura cronometrada o aprobación contractual.

## Compatibilidad e integridad

El adaptador solo lee los instrumentos anteriores y no los modifica. El validador
contractual v1 sigue rechazando un factual `in_progress`; la vía nueva distingue
su cierre semántico lateral sin fingir un `completed` histórico. Las etiquetas
`contractual_adapter=not_implemented` de registros/herramientas históricos describen
su versión original; no se reescriben para representar esta implementación nueva.

No cambian el cierre factual, la lista canónica, las citas, la atribución económica,
los prompts, perfiles, presupuesto, referencias congeladas ni datos PIT. El
manifiesto técnico de la entrega fija nuevos artefactos, pruebas y preservación
de los anteriores. Véase [ADR-038](decisions/ADR-038-pilot-contract-review-adapter.md).
