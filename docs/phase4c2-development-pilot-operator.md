# Piloto de revisión de desarrollo — materiales y operador

Estado: `phase4c2_development_pilot_packets_prepared_pending_review`.
**Solo preparación: piloto, anotaciones, mediciones e inferencias no ejecutados.**

## Materiales y frontera de cegamiento

Directorio: `evaluation/phase4c2_development_pilot_v1/`.

- `review-order.json`: orden opaco reproducible de los seis casos del plan original.
- `packets/<case_id>.md` y `.json`: seis paquetes autocontenidos, con textos
  originales, evidencia por campo, reloj/cutoff, identidad elegible e instrucciones
  factuales neutrales de `news-semantic-review-instrument-v1`.
- `forms/factual/`, `forms/contract/`, `forms/timing/`: 18 formularios vacíos,
  vinculados al fingerprint del paquete. Ningún campo semántico está seleccionado.
- `schemas/`: tres JSON Schemas cerrados con campos obligatorios y enums.
- `manifest.json`: hashes de materiales, herramienta, tests y esta guía; no es
  freeze de referencias ni autorización de inferencia.

El operador entrega al anotador solo el paquete del caso actual, el formulario
factual y el de tiempos. **No entregar** corpus completo, diseño privado,
authoring, auditorías, plan de selección, prompts, código de validación o historia
de desarrollo. El JSON de cada paquete no contiene familia, estrato, intención,
salidas esperadas, versiones de prompt ni reglas internas de validadores.

El orden se reconstruye con prioridad SHA-256 y semilla fija
`development-pilot-order-20261019-v1`, tomando la primera permutación admisible:
entre variantes de una familia hay al menos **dos casos intermedios**. El
verificador usa el diseño privado únicamente para comprobar separación, nunca
lo añade al paquete. El estilo/texto puede revelar relación; no se garantiza
cegamiento absoluto. Si el propietario conoce el desarrollo, registrar ese
contexto, no presentarlo como revisor humano independiente.

## Inicio rápido (todavía no ejecutar la revisión)

Comprobaciones de solo lectura que sí pueden realizarse ahora:

```powershell
python tools/evaluation/development_pilot_review.py --verify-packages
python tools/evaluation/development_pilot_review.py --forms evaluation/phase4c2_development_pilot_v1/forms --allow-incomplete
```

Ambos deben informar seis casos y **cero completados**. `--allow-incomplete`
permite comprobar estructura de material vacío/en curso; no lo convierte en
referencia ni omite validaciones de citas, fingerprints, tiempos o procedencia.
Sin esa opción, los formularios actuales se bloquean por revisión incompleta.
El CLI no escribe archivos, importa referencias, congela ni genera juicios.

Para un piloto posterior confirmado: copiar los formularios a un directorio
nuevo de trabajo por revisor, fuera del directorio preparado; no editar los
originales. Usar un identificador de revisión diferente por caso/revisor.
Confirmar persona, disponibilidad y modalidad antes de empezar. No se asignó
automáticamente ninguna tarea u horario a Nacho ni a otro revisor.

## Cómo anotar, en dos pasos separados

### 1. Factual

Usar `forms/factual/<case_id>.json`, esquema `news-pilot-factual-form-v1`.
Cambiar status a in_progress solo al comenzar realmente. Registrar hechos
atómicos en facts: fact_id local F001, F002..., dimension, meaning, certainty
(conclusive/uncertain/indeterminate), material (true/false/null si indeterminado)
y una o más citations. No confundir una cita existente con que respalde el hecho.

Cada cita requiere evidence_id, field, start, end y quote; offsets de caracteres
Unicode Python half-open `[start,end)`, no bytes ni unidades UTF-16. Copiar la
cadena original, sin corregir mayúsculas, espacios o normalización Unicode.
Se admiten ocurrencias repetidas si el revisor indica sus offsets exactos;
este formulario humano no es el resolver de citas sin offsets del LLM.

Completar las 13 dimension_assessments: recorded con fact_ids de esa dimensión;
insufficient, indeterminate o not_applicable con nota explícita. No usar
not_applicable para borrar un hecho ya enlazado. Identidad, participación, rol,
relación y ticker se anotan como dimensiones distintas. Etapas, cifras/unidades/
períodos, fechas, negaciones y posibles impactos van en los hechos de su dimensión,
sin inventar información. En must_not_omit listar IDs de obligaciones que el
revisor considera materiales; el verificador no toma esa decisión.

Antes de marcar completed: revisar evidencia, conservar incertidumbre y cerrar
esta fase en el registro de tiempos. Para obtener el hash literal del factual:

```powershell
(Get-FileHash -LiteralPath 'C:\ruta\trabajo\factual\CASE_ID.json' -Algorithm SHA256).Hash.ToLowerInvariant()
```

Sustituir ruta e ID por los reales. Ese hash se registra luego en el formulario
contractual; cualquier edición posterior del factual cambia el hash y bloquea
su vínculo. No congelar automáticamente este borrador como referencia definitiva.

### 2. Representabilidad contractual

Solo tras cerrar la anotación factual, abrir `forms/contract/<case_id>.json`,
esquema `news-pilot-contract-form-v1`. Consultar por separado la documentación
del contrato económico actual, no durante el primer paso factual. La versión
de referencia es news-economic-validation-v3; no se instala ni ejecuta v3/v4.

Registrar factual_record_sha256 y una mapping por cada fact_id, con mode
structured/faithful_partial_only/not_representable/indeterminate y rationale.
Indicar allowed_outcomes y rationale globales como juicios del revisor, no
respuestas del modelo. No cambiar el significado de los hechos para acomodarlo
al contrato ni reemplazar incertidumbre factual por una restricción técnica.
Si falta certeza sobre el contrato, conservar indeterminate; no adivinar reglas.

Los formularios son una adaptación operativa versionada del instrumento, no los
contratos productivos ni las clases del taller restringidas a simulación. No hay
conversión automática a ground truth, comparación con Nacho o importación/freeze.

## Tiempos y procedencia, sin rellenar de memoria como si fueran verificados

En `forms/timing/<case_id>.json` registrar identidad real y review_id, review_kind,
independence, execution_mode=manual_no_api, timestamp_source y timestamp_basis.
Owner_declared/manual_clock no equivalen a timestamps verificados de plataforma.
Una etiqueta de modelo observada no demuestra snapshot; model_snapshot,
api_parameters y api_tokens deben seguir null en este instrumento sin API.
Para revisión humana, model_label sigue null. El nombre de un humano nunca se
atribuye a un evaluador IA. La herramienta valida declaraciones, no identidades
del mundo real ni independencia; una declaración debe tener sustento verificable.

Registrar started_at/completed_at reales con zona horaria y factual_closed_at.
Intervalos consecutivos, sin solapes ni huecos: kind=active con phase
reading/factual_annotation/citation_check/contract_review/discrepancies/
adjudication/administration; o kind=pause, phase=null y pause_reason
break/interruption/queue/other. Intervalos parciales se dejan en in_progress.
Active_seconds, pause_seconds y phase_seconds deben concordar con los intervalos;
no atribuir cero a fases no medidas. Mantener null mientras no estén medidas.

Registrar discrepancias sin forzar acuerdo. Si no hubo adjudicación real, usar
not_performed o deferred cuando corresponda, sin tiempo/IDs inventados.
Performed exige tiempo de adjudicación y al menos dos review_ids previos distintos,
sin incluir la propia revisión. Estos son vínculos declarados: el operador debe
conservar y verificar sus registros originales; esta herramienta no certifica
la existencia o independencia de revisores de otros directorios. Con un único
propietario, no presentar un segundo pase como dos humanos o tercer adjudicador.

El verificador rechaza tiempos sin zona, futuros, intervalos incoherentes,
revisión contractual anterior al cierre factual y sumas incompatibles. No puede
certificar que un reloj declarado sea verdadero. Las métricas de tiempo quedan
como metadata por 90 días desde completed_at; no extender ese plazo. Fuentes y
anotaciones factuales propias previas a inferencias tienen política separada.
No hay respuestas de proveedor aquí: cuando existan, su contenido seguirá bajo
TTL individual de 24h y nunca se copiará a estas referencias para preservarlo.

## Validar posteriormente una copia completada

```powershell
python tools/evaluation/development_pilot_review.py --forms C:\ruta\trabajo
```

El directorio de trabajo debe contener exactamente factual/contract/timing con
los seis case_id, sin archivos extra. Cada revisor usa su propio directorio.
El comando reconstruye y verifica primero los materiales originales; después
comprueba formularios cerrados, relaciones, citas y tiempos. Una validación
correcta siempre informa semantic_truth=not_assessed: **no comprueba entailment,
verdad, exhaustividad, materialidad, independencia ni corrección de una etapa**.
Los errores CLI son códigos genéricos, sin imprimir citas, nombres o juicios;
los errores detallados de tests solo usan fixtures ficticias aparte del piloto.

Pruebas offline usan seis registros P-SIM ficticios nuevos en tmp, no anotan los
seis casos del piloto. Los materiales originales y formularios preparados quedan
vacíos. No se crea el reservado, se autoriza inferencia o inicia Phase 4C.3.

## Validaciones de preparación

- Suite completa: **925 passed**, 237,00 segundos; incluye 39 tests nuevos.
- Verificación de paquetes y validación con allow-incomplete: seis casos,
  **cero completados**, semantic_truth=not_assessed, cero juicios/inferencias.
- Validación de los formularios vacíos como completados: **bloqueada**, según
  lo previsto. No se rellenaron para superar ese control.
- `python scripts/validate_data.py`: correcto; features/targets disjuntos,
  905 revisiones, 811 artículos, cero errores raw/linaje/duplicados y cuatro
  snapshots íntegros. Compilación de src/scripts/tools/evaluation: correcta.
- El manifiesto original del corpus conserva SHA-256
  `a661f3c9f2b3e12d152c78b56b98e7a6f7673a6ed675d1d84fa9849dfec59b3c`
  y todos sus pins; su verificador de 24 casos también pasa.
- Los 3.679 archivos preexistentes inventariados bajo src/scripts/config/data/
  evaluation/tests/tools/docs conservan sus hashes. Solo se agregaron materiales,
  esquemas, herramienta, tests y esta guía. No se leyó contenido histórico
  expirado ni se modificaron perfiles, contratos, prompts o referencias.

El reloj 2031 de las noticias es ficticio: nunca copiarlo como tiempo real del
revisor. No hay persona, inicio, final, pausa, juicio o independencia preasignados.
