# Diagnóstico offline del stop contractual — v1

Caso: `D-293a6cbca3479505`. Review:
`contract-D-293a6cbca3479505-b33eb3a505444869`.

## Evidencia local y alcance de la conclusión

La inspección encontró el reloj **ya detenido**, con sesión `completed`,
no pausada. El último evento existente es `stop`, fechado por el reloj del
operador en `2026-11-07T15:18:22.650696+00:00`. No se ejecutó `stop`, `resume`
ni ninguna acción temporal durante este diagnóstico.

Se verificaron los seis eventos encadenados, sus hashes, la continuidad de los
hashes de sesión antes/después, los backups de sesión y sus referencias desde
los formularios archivados. No hay eventos huérfanos ni archivos `.pending`.
SHA-256 de la sesión actual:
`35488235aa0f9d87e89884484f08f988209415ca65fa628f1355d272dc6245cd`.

Intervalos activos registrados relevantes, en UTC:

| Fase | Inicio | Fin | Segundos registrados |
| --- | --- | --- | --- |
| contract_mapping | 14:35:22.143994 | 14:38:05.911148 | 163.767154 |
| owner_review | 15:17:27.288401 | 15:18:22.650696 | 55.362295 |

Todos corresponden al 2026-11-07. La última pausa `ai_wait` terminó al reanudar
`owner_review` a las 15:17:27.288401Z. Estos son registros existentes del reloj
local, no una certificación independiente de atención humana.

## Condición exacta y limitación retrospectiva

Después del preflight, `record()` exige `session.status == "in_progress"`
para cualquier acción distinta de `start`. Con el estado actual,
un nuevo `stop` falla con **`ValueError("clock_not_running")`**, antes de
agregar intervalos o escribir archivos. Es una transición inválida de una
sesión ya terminada. No es ausencia de `contract_mapping` ni de `owner_review`.
Incluso sin `owner_review`, detener el reloj de un formulario aún `in_progress`
es válido; completar el formulario es una operación diferente con más requisitos.

El CLI anterior ocultaba todas las excepciones bajo
`contract_clock_validation_failed`: ese defecto de observabilidad impedía
distinguir transiciones, integridad y errores de I/O. No existe un registro de
la excepción del comando fallido mencionado por el propietario; no se puede
atribuir retrospectivamente una causa inequívoca a aquella invocación usando
solo su mensaje genérico. La causa anterior es la reproducible para el estado
actual. La cadena válida acredita que existe un stop persistido, pero no si
el mensaje referido provino de un segundo intento o de otra invocación.

## Corrección mínima

El CLI conserva el error genérico y el código de salida 2, agregando
`error_code` desde una lista cerrada de identificadores seguros. Errores de
esquema e I/O reciben categorías fijas; mensajes no reconocidos permanecen
`unclassified_clock_failure`. No se imprimen excepciones, inputs, rutas ni
trazas. No cambia ninguna transición, contrato, intervalo, regla de aceptación
o procedimiento de persistencia. No se hacen reintentos ni reparaciones.

Las pruebas usan únicamente fixtures temporales: segundo stop sin escrituras,
stop durante `ai_wait` sin inventar revisión del propietario, errores de
transición, integridad histórica y sanitización adversarial del CLI.

## Procedimiento seguro

```powershell
$contractWork = 'data/cache/news_development_pilot/contract-manual-attempt01'
python tools/evaluation/pilot_contract_clock.py --workspace $contractWork status
python tools/evaluation/pilot_contract_review.py --validate $contractWork
```

En este caso **no repetir stop ni reabrir el reloj**: ya terminó. El formulario
permanece `in_progress`, con 11 mappings y `owner_decision=null`; no tiene
aprobación contractual final. Los otros cinco casos permanecen `unfilled`.
El siguiente paso es revisar el contenido y obtener una decisión expresa del
propietario, mediante el procedimiento del adaptador, sin reconstruir tiempos.
Si hace falta actividad humana adicional, primero debe definirse su registro
prospectivo compatible; no se puede agregarla retrospectivamente a esta sesión.

Para futuras sesiones aún activas o pausadas, el operador ejecutará stop solo
al terminar realmente. Si se bloquea, consultar `error_code` y status, conservar
los archivos y resolver la condición sin reintentos automáticos ni edición de
eventos. Una sesión detenida no equivale a un formulario contractual aprobado,
un piloto integral completado o un cambio oficial de fase.

## Validaciones de la entrega

- Tests del reloj: 32 pasan; suite completa: 1073 pasan.
- `python scripts/validate_data.py`: correcto, incluidos hashes y linaje de noticias.
- `python -m compileall -q src scripts tools/evaluation/pilot_contract_clock.py`: correcto.
- Preflight del adaptador: un formulario `in_progress`, cinco `unfilled`, cero
  formularios completados; reloj consultado únicamente en modo lectura.
- Comparación SHA-256 de 3741 archivos bajo `data`, `evaluation`, `config` y
  `src`: sin cambios respecto del inicio del diagnóstico. Esto incluye los
  eventos, backups, sesión, formularios y evidencias factuales existentes.
