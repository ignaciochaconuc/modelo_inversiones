# Phase 4C.2.2 — Experimento pareado v3 versus v4 draft2

Estado: `phase4c2_v3_v4_experiment_design_pending_review`.
**Diseño propuesto, no autorización ni experimento ejecutable.** Corpus reservado,
referencias y predicciones todavía no creados/congelados. Phase 4C.3: `not_started`.

## 1. Pregunta, alcance y tratamiento

¿Mejora v4 draft2 la fidelidad de una interpretación financiera respecto de v3,
manteniendo el mismo modelo, evidencia, registry, esquema, reglas y presupuesto
por solicitud? Aceptación técnica no es la variable de selección única.

Se comparan dos nuevas inferencias por caso, una por prompt, nunca los resultados
históricos contra resultados nuevos. Los 32 casos anteriores y ambos smokes son
desarrollo; sus referencias congeladas permanecen intactas y no son este holdout.
El experimento propuesto es **exploratorio, sintético y no operativo**. Incluso si
supera sus gates no valida rentabilidad, seguridad poblacional o producción.

El plano de control puede verificar referencias y cuotas, pero el intérprete solo
recibe texto sintético, IDs primarios elegibles, registry neutral y el esquema.
No recibe referencias, clases esperadas, estratos ocultos, reglas de scoring,
otras respuestas ni la familia contrafactual. No hay memoria compartida entre casos.

Artefacto de diseño: [design.json](../evaluation/phase4c2_v3_v4_experiment_design_v1/design.json).
Versionamiento detallado: [plan separado](phase4c2-v3-v4-versioning-plan.md).
Este protocolo complementa, no reescribe, [4C.1](phase4c1-evaluation.md).

## 2. Propuesta de corpus, sin contaminar el reservado

120 textos/casos nuevos: **24 desarrollo + 96 reservados**, separados por familia,
no mediante partición de paráfrasis del mismo ejemplo. Cada familia tiene dos
variantes contrafactuales, cambiando una condición semántica relevante. Hay 12
familias de desarrollo y **48 familias reservadas**; estas últimas son las unidades
de dependencia estadística, no 96 observaciones independientes.

| Estrato principal | Desarrollo | Reservado | Cobertura adicional necesaria |
| --- | ---: | ---: | --- |
| Anunciado | 2 | 8 | Anuncio confirmado, cierre pendiente, condiciones |
| Completado | 2 | 8 | Cierre del evento frente a cierre de una actuación distinta |
| Propuesto | 2 | 8 | Intención, propuesta, acuerdo y rumor |
| Etapa desconocida | 2 | 8 | Variantes morfológicas y evidencia parcialmente codificable |
| Negación | 2 | 8 | Evento negado, negación incidental y alcance fuera de la cita |
| Condición temporal | 2 | 8 | Futuro, condicional, rumor atribuido y estado ambiguo |
| Participación directa | 2 | 8 | Comprador/objetivo, emisor sin contraparte, suministro/contratos |
| Relación indirecta | 2 | 8 | Propiedad, suministro, competencia/licencia; dirección de relación |
| Contexto e identidad | 2 | 8 | Empresa reconocida sin participación, productos y plataformas |
| Números | 2 | 8 | Locales, signos, unidades, escala, período y cifras contradictorias |
| Fechas y PIT | 2 | 8 | ISO/textual, fecha de otro hecho, registry futuro/ambiguo |
| Evidencia insuficiente | 2 | 8 | Abstención adecuada, incertidumbre parcial y múltiples eventos |
| **Total** | **24** | **96** | 12/48 familias, dos variantes por familia |

Por estrato reservado: cuatro familias, una de evidencia clara, otra adversarial,
otra con límite de representación contractual y otra ambigua/insuficiente. Las
variantes pueden invertir un hecho o su modalidad; no se fuerza que siempre haya
una respuesta afirmativa y otra negativa. Tags secundarios deben cruzar etapas,
entidades, cantidades y abstención. Es una muestra enriquecida, no prevalencias
de noticias reales. No ampliar artificialmente N contando cada entidad como noticia.

Autores del reservado distintos, cuando sea posible, de quienes editaron prompts.
Reciben objetivos semánticos neutrales y criterios de cobertura, no prompts,
regex, tests de producción, predicciones ni errores de los smokes. Evitar adaptar
la redacción a los marcos léxicos del validador. Si no existe esa separación,
registrar autoría asistida/posible sesgo y limitar las conclusiones.

Antes del freeze verificar originalidad textual, entidades, hechos y familias
respecto de desarrollo antiguo/nuevo: hashes detectan igualdad, no bastan para
descartar paráfrasis. Revisión manual de similitud y log de exclusiones, sin
consultar predicciones. No reutilizar un caso cambiando solo nombres o cantidades.
No usar noticias Finnhub, anotaciones ChatGPT anteriores ni TEST oficial.

Los casos incluyen headline/summary ficticios, IDs/hash de evidencia y revisión,
family_id privado, decisión virtual explícita y registry de identidades inventadas
con known_at/effective_from. No inventar publicación histórica ni tickers reales.
La futura adaptación aplica el mismo cutoff y filtrado causal a ambos brazos;
un dato/alias futuro no se presenta como elegible. La plantilla de autoría no
contiene respuestas esperadas, palabras obligatorias de etapa ni salida de Nacho.

## 3. Referencias: hechos semánticos separados de representabilidad

Antes de predicciones, anotar por dimensión: hechos/eventos y calificadores;
identidad, participación, rol y relación/dirección; etapa/estado/negación; fechas;
cantidades/unidad/escala/período; hechos materiales que no deben omitirse; impacto
solo potencial; suficiencia y alternativas válidas de abstención o salida parcial.
Usar conjuntos de respuestas aceptables, no un JSON esperado literal único.

La **referencia factual** no se deriva de regex ni de la respuesta de un prompt.
Una capa separada clasifica qué campos admite expresar el contrato actual y dónde
solo cabe unknown/null con límite explícito. No cambiar el hecho de la referencia
para que coincida con el validador. Distinguir incertidumbre real de una pérdida
por representación. Una cita de un importe, sin reconocimiento de su significado
y limitación estructurada, no es automáticamente extracción numérica correcta.

Preferencia: dos revisores humanos separados, primero ciegos a ambos prompts,
predicciones e identidad del brazo. Anotación independiente y adjudicación antes
del freeze; conservar desacuerdos y casos no concluyentes. Si no están disponibles,
usar referencias `ai_assisted_exploratory_evaluation`, preferiblemente con otra
familia de modelo, aislada de desarrollo y sin predicciones. Registrar etiqueta
real, snapshot/parámetros/costes/tokens cuando existan, instrucciones, fingerprints
y timestamps con procedencia. Desconocidos son null, no snapshots inferidos.
Misma familia o historial contaminado se declara; ninguna IA equivale a verdad
humana independiente. No hay llamada o evaluador seleccionado/autorizado aquí.

Después, evaluación ciega de las salidas anonimizadas: IDs de brazo aleatorios por
caso, orden aleatorio, sin prompt/modelo ni scores previos. Dos revisiones si hay
recursos, o evaluación IA explícitamente asistida. Estilo/longitud pueden revelar
indicios: el cegamiento no se garantiza absolutamente. La revisión posterior del
propietario de desacuerdos/críticos se registra aparte; si vio los brazos, no es
adjudicación humana independiente ni ciega. No editar referencias para concordar.

## 4. Congelación y preregistro, ANTES de toda predicción reservada

1. Aprobar diseño, endpoints, umbrales, hipótesis, ventanas de revisión y versiones.
2. Implementar y probar offline las extensiones propuestas, sin activar inferencia.
   Desarrollo admite correcciones de infraestructura; candidato draft2 no se edita.
3. Generar/revisar corpus independiente y referencias; separar familias completas.
   Exigir al menos **87/96** casos con referencia concluyente para el endpoint
   principal antes de ejecutar. Dimensiones ambiguas siguen explícitamente abiertas.
4. Freeze inmutable con SHA-256 externo de: casos, textos, registry/cutoffs,
   familias/estratos privados, referencias/procedencia, equivalencias de evaluación,
   métricas/denominadores, seeds, prompts exactos, código, esquema y settings.
   No sobrescribir si existe. Este freeze **no existe todavía** y no sustituye
   references-frozen.json de los 32 casos.
5. Congelar orden y ambos planes. Revisar perfil/modelo/precios vigentes, reservar
   toda la corrida y obtener autorización nueva específica. Hoy el perfil vencido
   bloquea la ejecución; no se actualiza en esta tarea.
6. Ejecutar solo tras esos gates, sin reintentos, cambios de prompts, referencias,
   validadores, selección de casos o criterios a partir de resultados reservados.

Si el desarrollo motivara cambiar draft2, crear otro candidato y otro preregistro
antes de crear/exponer el reservado. Si se modifica después de ver sus respuestas,
retirar ese reservado a desarrollo y obtener otro conjunto; jamás llamarlo holdout
independiente de la revisión que produjo el cambio. Erratas se registran como
eventos inmutables: referencia original como análisis principal, análisis de
sensibilidad con errata revisada aparte, y bloqueo de adopción si el error cambia
la decisión hasta una nueva revisión. No elegir retrospectivamente la referencia
que favorece un brazo.

## 5. Ejecución futura pareada y P0

Mismo modelo/alias y, si es verificable, snapshot; mismo adaptador, parámetros,
output_schema estricto, límite de salida 2048, un intento, sin herramientas y
sin retries/cache recovery. Modelo provisional por continuidad: gpt-5.6-luna,
reasoning none, ambos **pendientes de reverificación**, no afirmación vigente de
compatibilidad o acceso. No inferir snapshot a partir del alias. Si la identidad
o parámetros efectivos difieren, detener; no mezclar silenciosamente bloques.

Si el proveedor no permite fijar/verificar snapshot, declarar ese factor no
controlado: un alias igual no demuestra backend idéntico. Intercalar brazos
reduce confusión temporal, pero no la elimina ni prueba causalidad del prompt.

96 casos × 2 brazos = **192 llamadas reservadas**, con los dos requests por caso
idénticos salvo instrucciones y metadata de versión necesaria. No meter la salida
del primer brazo en el segundo. Balancear 48 casos v3-primero y 48 v4-primero,
orden por seed 20261019 y estratos, intercalados temporalmente. Separar variantes
de la misma familia en el orden; no ejecutar todos los v3 y luego todos los v4.
Tiempo, carga y caché del proveedor siguen siendo posibles factores de confusión.

La semilla de orden/análisis no se envía como parámetro del modelo ni garantiza
generación determinista. Un único intento por brazo/caso no estima variabilidad
intraprompt: replay exacto y repetibilidad de nuevas inferencias son conceptos
distintos. No añadir réplicas sin un diseño y autorización separados.

P0 obligatorio en ambos brazos. Conservar contrato news-evaluation-diagnostics-v1,
política diagnostic-metadata-retention-v1, fuente/request/wire/settings hashes,
outcome, etapas/subcódigos y asociación inequívoca con cada intento. El wrapper
actual necesita adaptación explícita para nuevas settings/versions: no asumir
que admite v4 ni 96 casos ya. Véase el plan de versionamiento.

Por brazo, un run_id eval-UUID distinto. Manifest experimental vincula
(experiment_id, case_id, family_id privado, arm_id, run_id, record_id, sidecar_id,
wire/settings/prompt hashes). Un mismo case_id en los dos runs no colisiona.
Manifest por brazo/experimento nuevo; el actual está fijado a 32, no se rellena
con duplicados ni se reutilizan sus autorizaciones. Cada not_run mantiene razón
cerrada y carece de IDs de intento ficticios. Interpreted, abstained, rejected,
technical_error y not_run se preservan; una llamada posible sin persistencia
no se etiqueta como no ejecutada con certeza.

Detener ambos brazos ante persistencia fallida, sidecar incompleto, coste/categoría
desconocidos, overrun, expiración de autorización/precios o identidad inesperada.
Conservar ledger, intentos ya escritos y reservas; sin reintento ni reemplazo de
respuestas. Casos semánticamente rechazados con coste conocido no se borran.

### Retención y revisión dentro de TTL

Contenido: 24 horas desde la persistencia de cada respuesta. Diagnóstico: 90 días
desde creación, sin extensión. No leer intentos/outputs expirados por otra vía.
P0 preserva la guardia fallida, **no sustituye** la evaluación semántica textual.

Planificar seis microbloques de 16 casos (32 llamadas) con igual balance; todas
las referencias ya congeladas antes del primero. Revisores ciegos independientes
pueden puntuar cada microbloque mientras sigue la ejecución, sin que el equipo
de prompts vea los resultados ni ajuste el experimento. Antes de cada microbloque
confirmar capacidad de revisión dentro del vencimiento individual más temprano.
El análisis comparativo se abre solo después de cerrar las anotaciones previstas.

Antes del freeze debe existir un calendario realista de anotación/recursos:
los bloques y pausas también deben caber en la vigencia de precios/modelo y de
la autorización. Si no cabe, rediseñar antes de ejecutar; no prolongar una
corrida parcial cambiando el perfil o autorización en mitad del experimento.

Si no se puede revisar a tiempo, detener llamadas futuras; lo expirado queda no
revisable. No ampliar TTL ni trasladar respuestas/citas a referencias, backups o
reportes para eludirlo. Juicios de salidas: texto/rationale/citas bajo 24 horas;
solo códigos, flags, contadores e IDs sanitizados en un futuro artefacto separado
de revisión semántica de 90 días, sin introducir texto libre en sidecars P0.
Corpus y referencias de texto sintético propio anteriores a la inferencia tienen
política separada del contenido del proveedor; no son una copia de sus respuestas.

## 6. Métricas predefinidas y denominadores

N=96 por brazo siempre se informa. N_attempted, N_paired_attempted, N_reviewed,
N_ref_conclusive, número de familias y exclusiones se publican separadamente.
No convertir un fallo técnico en abstención ni un unknown en hecho correcto.

| Dimensión | Métrica y denominador predefinidos |
| --- | --- |
| Aceptación técnica | (interpreted + abstained) / intentos; adicionalmente /96. Desglosar transporte, JSON, esquema, grounding, validación, persistencia y no ejecutados. |
| Citas/evidencia | Referencias exactas/únicas/primarias / todas las citas propuestas accesibles; rechazos de grounding por caso y subcódigo. Separar localización literal y respaldo semántico de la afirmación. Citas no parseables: error estructural, no denominador cero presentado como perfección. |
| Etapas y estados | Casos con falsa confirmación de cierre/estado / casos con referencia concluyente de esa dimensión; además matriz de confusión, calificadores perdidos y unknown contractual frente a incertidumbre real. Revisar también afirmaciones narrativas. |
| Identidad | Entidades mal vinculadas al registry/security / oportunidades de identidad de referencia; reportar falsos vínculos nuevos por entidad propuesta. Unknowns y omisiones separados. |
| Participación/rol/relación | Casos con atribución, dirección o rol incorrectos / casos elegibles de referencia; métricas por mención además, sin equiparar ticker con exposición. Directo, indirecto y contextual no se colapsan. |
| Omisión material | Obligaciones semánticas materiales omitidas sin tratamiento fiel / obligaciones concluyentes prefijadas. También tasa por caso: no permitir reducir afirmaciones para mejorar precisión. Cita completa sola no reemplaza reconocimiento/limitación de un hecho relevante. |
| Abstención | Correctas / casos de insuficiencia concluyente; injustificadas / casos con representación fiel al menos parcial admisible. Informar razones, pérdidas de eventos y unknowns por campo. Casos ambiguos no se fuerzan. |
| Números y tiempo | Errores de lexema/magnitud/unidad/escala/período y fecha/cutoff / oportunidades concluyentes respectivas; cobertura estructurada sobre representables y manejo de no representables aparte. Conversiones no autorizadas, datos futuros o fecha publicada usada como evento son errores distintos. |
| Economía e incertidumbre | Inferencias/impactos sin respaldo, materialidad injustificada, falsa neutralidad y exposición confirmada; hechos frente a inferencias explícitas. No métricas de retorno ni alpha. |
| Coste/consumo | Tokens input/read/write/output conocidos, latencia mediana/p95, costes/reservas por intento, brazo, caso planificado y par completo. Reportar cada categoría desconocida y gasto de fallos; no imputar cero ni descuentos supuestos de caché. |

**Endpoint principal, F_case:** 1 para una interpretación técnicamente aceptada
fiel a todas las obligaciones materiales concluyentes del caso, con parcialidad
explícita cuando procede, o una abstención justificada por referencia; 0 para
atribución/facto/omisión material incorrectos, abstención injustificada, rechazo,
error o caso no ejecutado. No basta un texto con menos afirmaciones. Informar
por separado cobertura informativa para que acertar abstenciones no oculte pérdida
de extracción. No usar coincidencia literal de JSON como métrica semántica.

E se fija por referencias concluyentes antes de inferir, común a ambos brazos.
Referencias no concluyentes quedan fuera de esa dimensión, con sus cuentas,
razones y análisis de límites; no se excluye un caso por una mala respuesta.
Errores/no ejecutados conocidos cuentan como 0 en F_case sobre E; para contenido
no revisable por TTL no se inventa etiqueta semántica: presentar límites mejor/
peor caso, cobertura faltante y no autorizar adopción por evidencia insuficiente.
Riesgos por caso sobre denominadores comunes son los gates; ratios por citas o
entidades propuestas son descripciones complementarias sensibles a omisiones.

## 7. Análisis pareado y criterios de decisión propuestos

Emparejar por case_id + source fingerprint + registry/cutoff fingerprint, nunca
por orden, outcome o similitud de respuesta. Para cada familia, promediar las
diferencias F_case(v4)-F_case(v3) de sus casos elegibles; el endpoint es la media
de esas diferencias familiares con igual peso por familia. Informar también
diferencia por caso y todos los estratos, sin seleccionar el más favorable.

Intervalo exploratorio 95% por bootstrap de **familias**, 10.000 réplicas,
seed 20261019, manteniendo ambos brazos y variantes juntos. Conclusiones
condicionales a este corpus; no un intervalo de prevalencia de noticias reales.
Métricas secundarias exploratorias completas, sin búsqueda de p<0,05 ni múltiples
tests usados para escoger un ganador. No se declara potencia confirmatoria.

Gates a aprobar antes del freeze, no ajustables tras resultados:

1. Cero errores críticos aceptados de v4: falsa finalización/negación invertida,
   identidad/participación económica inventada, cita/revisión fabricada aceptada,
   PIT roto, impacto/exposición operativa o directiva prohibida. Inyección con
   acción no autorizada, filtración o fallo de trazabilidad bloquea adopción y
   detiene la corrida aunque la aceptación aumente.
2. Integridad, coste conocido y replay verificable; al menos 87 pares intentados
   y cobertura de revisión semántica ≥90% de casos elegibles en ambos brazos.
   Incompletitud se informa; no se completan casos con datos inventados.
   Todos los escenarios de seguridad identificados antes del freeze requieren
   revisión concluyente de ambos brazos; no tratar los no revisados como seguros.
3. Delta principal ≥0,05 y límite inferior del intervalo exploratorio >0;
   sin empeoramiento de tasas por caso en denominadores comunes de identidad,
   participación, omisión material, números o tiempo; y sin caída de cobertura
   informativa fiel. Si un componente no es concluyente, decisión inconclusa.
   La selección debe mantenerse bajo los límites conservadores de datos faltantes
   (v4 peor caso, v3 mejor caso), no solo tras eliminar pares incompletos.
4. Si solo mejora aceptación, coste o longitud, no adoptar. Si mejora fidelity
   sin evidencia suficiente para esos gates, mantener como candidato pendiente.

Superar gates permite recomendar v4 **solo para continuidad experimental**, no
default productivo ni fin de revisión semántica. Si falla v4 no se declara v3
seguro automáticamente. Cero fallos observados en 48 familias sintéticas no prueba
ausencia de errores raros. Para conclusiones sólidas: nuevo corpus independiente
representativo, referencias humanas verificables, cálculo de tamaño/potencia
previo con supuestos de discordancia/efecto e independencia entre familias,
replicación con identidad de modelo controlada y confirmación sin retuning.
No hay base hoy para una afirmación estadística poblacional o de generalización.

## 8. Presupuesto preliminar: escenario, no tarifa vigente

No se consultó proveedor ni se renovaron precios. Solo para planificación se usan
las tarifas históricas del perfil **vencido el 2026-10-15T20:39:20Z**, USD/millón:
input 0,20; cache read 0,02; cache write 0,25; output 1,20. No son verificación
vigente ni autorización. Toda ejecución exige revisar tarifas/capacidades después.

Cota de planificación por wire: 48.000 tokens de entrada conservadores, calculables
con bytes UTF-8 del wire completo +256 según reservation_bound, no caracteres/4;
salida máxima 2.048. Todavía no hay wires para medir: **48.000 es un límite de
diseño**, no observación. Si el preflight real lo excede, bloquear y revisar el
plan antes de inferir; no truncar evidencia ni quitar casos para encajar.

Reserva = (48.000 × max(0,20;0,02;0,25) + 2.048 × 1,20)/1.000.000
= **US$0,0144576 por llamada**. Categorías de entrada disjuntas, sin asumir ahorro
de caché ni sumar cache write de nuevo sobre todo input. Categoría desconocida:
reserva completa y detención, no coste cero.

| Alcance | Llamadas máximas | Reserva ilustrativa | Cap de aplicación propuesto |
| --- | ---: | ---: | ---: |
| Reservado: 96 × 2 | 192 | US$2,7758592 | US$3,20 |
| Desarrollo opcional: 24 × 2 | 48 | US$0,6939648 | US$0,80 separado |
| Ambos, si se autorizan por separado | 240 | US$3,469824 | US$4,00 |

Un límite por solicitud US$0,05 puede mantenerse si la nueva verificación lo
permite; el presupuesto global anterior US$1,60 **no se reutiliza**. No hay
autorización emitida. No incluye jueces/referencias IA pagados, impuestos, FX u
otras tarifas; esos costes necesitan estimación y autorización separadas. Cap y
reserva son controles de aplicación, no garantía de factura ni precios actuales.

Distribución propuesta: cada brazo reservado tiene 96 llamadas, reserva
US$1,3879296 y cap nuevo US$1,60; desarrollo opcional, 24 llamadas por brazo,
reserva US$0,3469824 y cap US$0,40. La coincidencia numérica con un límite anterior
no reutiliza su autorización. El coordinador debe hacer cumplir también los
caps agregados US$3,20/US$0,80 y detener ambos brazos ante una incidencia.

## 9. Entrega actual y pendientes explícitos

Se entrega diseño, blueprint, métricas, gates, propuesta de versionamiento e
identidades exactas de prompts. No se crea contenido reservado expuesto al equipo
de prompts ni se afirma que existe un freeze nuevo. Faltan aprobación del diseño,
autoría/revisión separadas, corpus/referencias congelados, implementación versionada
offline, perfil vigente y nueva autorización. No hay comando real listo para
ejecutar: el CLI actual es de 32 casos/v3 y no implementa este experimento.

## 10. Validación de esta entrega de diseño

- `python -m pytest`: **855 aprobados**, 202,91 segundos; no se añadieron ni
  modificaron tests/expectativas o código de producción para aprobar el diseño.
- `python scripts/validate_data.py`: separación features/targets correcta;
  905 revisiones, 811 artículos, cero hashes inválidos/linaje faltante/duplicados
  y cuatro snapshots de enriquecimiento válidos.
- `python -m compileall -q src scripts`: correcto.
- Verificación aritmética offline con Decimal: cuotas 24/96, 12/48 familias,
  192 llamadas propuestas y reserva ilustrativa US$2,7758592. Se verificaron
  también límites por brazo y el presupuesto opcional, sin consumir créditos.
- Hash v3 calculado dos veces con distintos textos ficticios de diseño: idéntico;
  candidato draft2 coincide con su manifiesto. Ninguno se ejecutó.
- SHA-256 antes/después: los 3.548 archivos existentes revisados de src/config/
  data/evaluation/tests permanecen sin cambios. Los artefactos nuevos de diseño
  no son un freeze de corpus ni una autorización; el manifiesto distingue hashes
  reales de diseño de los hashes de corpus/referencias todavía null.
- Cero API, inferencias, anotaciones generadas o lectura de contenido histórico
  expirado. No se renovó el perfil ni se iniciaron etapas posteriores.
