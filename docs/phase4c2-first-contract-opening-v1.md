# Primera apertura contractual: autorización reservada, reloj sin iniciar

Caso autorizado: `D-293a6cbca3479505`.
Review ID: `contract-D-293a6cbca3479505-b33eb3a505444869`.
Carpeta independiente: `data/cache/news_development_pilot/contract-manual-attempt01/`.

La autorización nueva del propietario se registró bajo
`news-pilot-contract-opening-authorization-v1` en
`opening/D-293a6cbca3479505.authorization-v1.json`. Su fuente es esta instrucción
expresa de apertura, distinta de la implementación y del cierre factual. No se
inventaron timestamp o ID de mensaje; `authorized_at` y `source_message_id` son
null. No se añadió ninguna firma. Se comprobó el cierre lateral, la aprobación,
el hash factual, la decisión de cierre y la selección vigente.

## Estado exacto de la preparación

Los seis formularios de trabajo y sus sesiones siguen `unfilled`, con cero
mappings y sin juicios del propietario. Los cinco casos no autorizados conservan
sus estados y no reciben permisos de apertura. El historial factual permanece
`in_progress` y excluido de estadísticas medidas. No se hicieron lecturas o
análisis contractuales en nombre del propietario.

El esquema de sesión existente exige que `review_id` y `opening_authorization`
estén vacíos mientras la sesión esté `unfilled`. Por eso se conserva una **reserva
externa** en `opening/reservation.json`, sin modificar el esquema ni simular inicio.
Al ejecutar start con reloj y procedencia reales, el helper enlazará esa reserva
a la sesión. Registrar la autorización no constituye actividad humana medida.

## Materiales exactos para ChatGPT

Adjuntar `CHATGPT-PACKET.md` de la carpeta de trabajo. Reúne, para lectura:

1. Paquete original completo, headline, summary, evidencia y reloj virtual.
2. Factual aprobado íntegro: once hechos, citas, offsets y trece dimensiones.
3. Código de schemas, grounding, replay y atribución económica que define la
   referencia `news-economic-validation-v3`, con sus hashes. Es texto de consulta,
   no una solicitud de ejecutar esos archivos.
4. Plantilla contractual vacía e instrucciones neutrales de representabilidad.

Las fuentes también están separadas en `materials/`:
`NEWS.md`, `NEWS-PACKET.json`, `FACTUAL-APPROVED.json`,
`TECHNICAL-REFERENCE.json`, `reference-source/*.py` y `CONTRACT-TEMPLATE.json`.
Las nueve copias de fuente conservan los bytes y hashes originales. El documento
Markdown es una presentación, no reemplaza las fuentes originales.

La plantilla material es una copia al preparar el paquete. El registro editable
vivo está en `forms/D-293a6cbca3479505.json`. Puede adjuntarse también después de
iniciar el reloj para mostrar sus referencias actuales. ChatGPT debe proponer
únicamente campos de representabilidad; no completar estados, autorizaciones,
tiempos, hashes o aprobación del propietario. Todos los fact_id se revisan,
incluidos F001/F006 y los no canónicos. No hay respuestas esperadas, predicciones
de Nacho ni juicios contractuales ya rellenados.

## Preflight sin empezar

Desde la raíz del repositorio:

```powershell
$contractWork = 'data/cache/news_development_pilot/contract-manual-attempt01'
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork status
python tools/evaluation/pilot_contract_review.py --validate $contractWork
```

El primero valida además la autorización reservada y debe informar
`authorized_waiting_for_real_start`. El segundo informa seis plantillas sin
iniciar. No imprime una hora de inicio ni escribe actividad. El review_id está
reservado, pero todavía no se ha insertado en la sesión temporal.

## Inicio real — solo cuando el propietario vaya a comenzar

Preparar primero los comandos; no abrir el material para leerlo antes de iniciar
el reloj si se pretende medir esa lectura. La familiaridad con el factual previo
debe declararse; esta no es una primera lectura humana independiente.

```powershell
$contractWork = 'data/cache/news_development_pilot/contract-manual-attempt01'
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork start --phase material_reading --reviewer-id nacho --reviewer-name Nacho --context 'Propietario del proyecto; conoce el desarrollo; revision asistida por ChatGPT, no independiente.'
```

Los identificadores y el nombre son declaraciones del operador al ejecutar el
comando; deben corresponder a quien realmente revise. Si se conoce la etiqueta
visible del modelo, puede añadirse `--model-label` con esa etiqueta exacta. Si no
se conoce, permanece null; no se infiere snapshot, parámetros o tokens.

Ese comando captura prospectivamente la hora UTC del reloj del equipo con zona
explícita. No acepta un argumento para fechar retrospectivamente el evento. La
fuente es `manual_clock` por acción del operador local, no una hora verificada
por ChatGPT o la plataforma. Solo entonces actualiza sesión y formulario a
`in_progress`, enlaza la autorización y reserva, y actualiza sus hashes.

No se ejecutó este comando sobre el caso real durante la preparación.

## Cambios de fase, pausas y fin

Ejecutar cada comando al producirse realmente el cambio. Para esperar una respuesta
de ChatGPT, pausar; la espera no es tiempo humano activo:

```powershell
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork pause --reason ai_wait
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork resume --phase contract_mapping
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork phase --phase evidence_check
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork phase --phase owner_review
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork phase --phase administration
```

Otras pausas admitidas: `break`, `interruption`, `other`. Usar pause/resume para
interrupciones o trabajo que continuará después. Usar phase solo para cambiar de
una fase activa a otra; no recategorizar intervalos pasados.

Cuando finalicen realmente las actividades de esa sesión:

```powershell
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork stop
python tools/evaluation/pilot_contract_review.py --validate $contractWork
```

Stop cierra el reloj, no completa ni aprueba el formulario contractual. No permite
reanudar esa sesión ya finalizada. Mientras se vaya a continuar la misma sesión,
usar pause. La aprobación final del contenido contractual sigue requiriendo su
decisión específica y todos los controles del adaptador.

El helper registra intervalos y eventos encadenados por hashes en `clock/` y
conserva copias anteriores de los registros de trabajo. No modifica mappings,
hechos, incertidumbres o aprobaciones. Calcula duración solo de los intervalos
capturados. Las fases no observadas permanecen null durante la sesión; al cerrar
una línea temporal íntegra, las fases no realizadas en esa sesión tienen duración
cero dentro de ese alcance observado. No se imputan los 20/30 segundos factuales.
Los comandos y su procesamiento forman parte del alcance observado; el reloj
local no certifica por sí solo atención humana o elegibilidad para estimar esfuerzo.

## Integridad, límites y datos pendientes

`tools/evaluation/pilot_contract_clock.py` es un helper adicional del operador;
el adaptador, su esquema, los validadores y contratos históricos permanecen
intactos. El helper valida la copia antes y después de cada acción, exige la
autorización del caso reservado y mantiene los otros cinco `unfilled`.
La actualización de hashes no modifica los campos semánticos. Ante un error de
persistencia o reloj incoherente, se bloquea la operación y se conservan los
registros; no se reconstruyen intervalos automáticamente.

Los eventos, backups y sesión son metadata de revisión, con la misma limitación
temporal de 90 días desde el fin de sesión. El helper no renueva ese plazo ni
ofrece acceso alternativo a sesiones vencidas. No hay respuestas de proveedor o
noticias Finnhub en este paquete; no se altera su política de retención.

Ahora faltan la ejecución efectiva del start por el propietario, procedencia del
revisor y reloj reales, y la posterior revisión contractual. Todos los campos
temporales actuales permanecen null. La preparación no autoriza inferencias,
agentes, APIs, evaluaciones v3/v4 o cambios oficiales de fase. No se aprobaron
mappings ni se iniciaron casos durante esta entrega.
