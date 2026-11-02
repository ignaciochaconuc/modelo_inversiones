# Piloto — separar aprobación factual y cronometraje (propuesta v1)

Estado: `proposed_pending_owner_approval`. No implementada ni activada.
Versión: `news-pilot-semantic-timing-separation-proposal-v1`.
Alcance exclusivo: ensayo manual de desarrollo. No modifica el experimento
reservado, sus gates, contratos productivos, formularios originales ni validadores.

## Decisión basada en los instrumentos actuales

El protocolo experimental, §3, admite referencias asistidas por IA con procedencia
real y valores desconocidos null. Eso permite conservar un borrador factual sin
cronometraje. No lo convierte en referencia humana independiente ni aprobada.

La guía operativa del piloto, sección factual, pide cerrar esa fase en el registro
de tiempos antes de marcar completed. `validate_timing` exige identidad, inicio y
duraciones según estado; `validate_forms` exige los seis casos, procedencia y
formularios completos para el cierre integral. El verificador factual aislado
solo comprueba estructura/evidencia. Por tanto:

- **Conservar v2 como ensayo asistido no medido:** permitido, se mantiene.
- **Darlo por aprobado por el propietario:** todavía no; falta decisión explícita.
- **Registrar un cierre semántico sin fingir medición:** requiere una adaptación
  operativa explícita; el instrumento integral no define ese resultado separado.
- **Contarlo como piloto medido o capacidad de revisión:** no permitido.

No se modificaron los documentos o programas anteriores. Esta propuesta no
permite saltarse sus errores de procedencia ni convertir allow-incomplete en
aceptación. No se exige recuperar datos que no existen ni se imputan ceros.

## Cambio propuesto, aún pendiente de aceptación

Separar tres ejes en un futuro sidecar versionado, sin alterar el factual histórico:

| Eje | Valores propuestos | Qué NO significa |
| --- | --- | --- |
| Aprobación de contenido | pending_owner_approval / owner_approved_content / revisions_requested | No certifica verdad independiente ni aprobación del protocolo |
| Elegibilidad temporal | unknown_excluded / prospectively_measured_pending_validation / eligible_measured_scope | No atribuye tiempos ausentes ni capacidad suficiente |
| Cierre integral | incomplete / complete_under_existing_requirements | No se completa por aprobar solo el contenido |

Un futuro registro owner_approved_content deberá citar case_id, hash EXACTO del
factual, responsable real, decisión explícita y su fuente, alcance de aprobación,
asistencia IA y límites de independencia. No generar hoy un registro aprobado.
La aprobación del contenido y la aceptación de esta propuesta son decisiones
distintas. Los desconocidos siguen null; no inventar snapshot o identidad.

La fecha de una aprobación realmente documentada es un evento nuevo, nunca una
reconstrucción del inicio/fin de la revisión anterior. El factual v2 y sus copias
históricas permanecen intactos. No cambiar automáticamente su status a completed,
rellenar factual_closed_at ni modificar el validador antiguo: la nueva distinción
se representaría en el sidecar y requeriría implementación/revisión offline futura.

La aprobación del propietario no es adjudicación humana independiente ni convierte
duplicados dimensionales en once hechos económicos independientes. No es freeze,
referencia reservada, permiso de inferencia o autorización de fase contractual.

## Disposición actual de D-293a6cbca3479505

Hash v2: `9072b179f81639e507d0c05c84fbe495f17de3647984591c335d99c32ecb396b`.
Se mantiene in_progress, pendiente de aprobación del propietario, con origen
ChatGPT asistido, sin independencia humana o adjudicación atribuidas. Se añade
solo una disposición local que excluye expresamente el intento del cronometraje.
No se cambia la anotación, el timing vacío ni la procedencia histórica.

No utilizable para estimar duración, media/mediana/p95 o capacidad. Tampoco debe
desaparecer de los recuentos de intentos cualitativos: informar por separado
casos ensayados y casos con mediciones válidas. Una futura aprobación semántica
no rehabilita sus tiempos desconocidos. El experimento sigue no ejecutable hasta
cerrar sus dependencias; no se rebaja el requisito de revisión dentro del TTL.

## Siguiente caso y cronometraje prospectivo

El siguiente ID en el orden ciego original es **D-a8db3a0c74d93eb8**, posición 2.
Su copia de trabajo está preparada en
`data/cache/news_development_pilot/manual-20261102-attempt02/`, con el paquete
original y factual/timing vacíos. No se inició reloj, no se llenó ningún hecho
y no se creó formulario contractual. Los IDs de familia/estrato no se entregan.

Instrucciones mínimas:

1. Antes de abrir el texto del paquete, confirmar quién hará la revisión, su
   modalidad real, contexto previo e instrumento de reloj. No declarar que el
   propietario es independiente del desarrollo. Leer primero START.md.
2. En el momento real de empezar, iniciar un cronómetro local y anotar fecha/hora
   con zona y origen del reloj. En PowerShell, ejecutado por el operador entonces:
   `[DateTimeOffset]::Now.ToString('o')`. Verificar la zona del equipo; no copiar
   el reloj ficticio de la noticia ni la fecha del nombre de la carpeta.
3. Abrir solo el paquete de este caso. Registrar por separado lectura, anotación
   factual y comprobación de citas; guardar comienzo/fin de cada intervalo y
   pausas reales, incluidos espera/interrupción. No generar respuestas de IA.
4. Al terminar la sesión factual, registrar su fin y tiempo activo observado,
   no el tiempo transcurrido en días entre mensajes. Conservar notas/registro
   del reloj. Completar solo fases medidas; otras siguen null, no cero.
5. Mantener anotación en curso hasta aprobación expresa. No abrir contrato o
   inventar discrepancias/adjudicación. Un formulario de tiempos parcial no es
   una medición de todo el piloto; el CLI integral sigue exigiendo su inventario.

El cronometraje nuevo no sustituye el anterior. La práctica y la familiaridad
con el instrumento deben declararse; una medición de un caso no permite afirmar
capacidad para 192 salidas. Ningún dato temporal fue prellenado en esta entrega.

## Revisión factual del primer caso por el propietario

Leer el paquete primario y confrontar cada meaning con sus citas: fecha publicada
versus vigencia, datos ausentes versus valores cero, incertidumbre y materialidad.
Revisar también posibles omisiones, no solo si las citas existen. Los hechos
añadidos por dimensión se solapan: comprobar contenido, no contar su multiplicación
como evidencia nueva. Si hay cambios, solicitar otro borrador y conservar v2.

Si realmente está conforme, una decisión futura puede decir: «Apruebo el contenido
factual v2 de D-293a6cbca3479505 identificado por [hash], como revisión asistida,
sin aprobar una medición temporal ni revisión contractual». No se presume esa
decisión a partir de la petición actual. No se rellenará fecha u hora anterior.

## Validación y trazabilidad

La propuesta y sus dependencias se fijan en manifest.json del directorio de la
enmienda. Ese manifiesto no es aprobación ni freeze de referencias. Se comprueba
la integridad de los materiales originales, del factual v2 y de las copias del
siguiente caso. No se modifica código, esquemas originales o reglas de aceptación.
No hay llamadas API, inferencias, nuevas referencias o Phase 4C.3.
