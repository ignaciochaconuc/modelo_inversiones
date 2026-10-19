# Preparación metodológica v3/v4 — instrumento y capacidad de revisión

Estado propuesto: `phase4c2_v3_v4_methodology_prepared_pending_review`.
**Experimento no ejecutable.** El identificador final solicitado llegó truncado
después de `p`; este nombre es provisional, no se atribuye al propietario.
Sin inferencias, autorización, activación de v4 ni inicio de Phase 4C.3.

## 1. Dictamen y alcance

Se puede comenzar después la **autoría de los 24 casos de desarrollo**, marcados
como desarrollo y sin inferencia, usando este instrumento para entrenar el flujo.
Esta entrega no crea esos 24 ni los 96 reservados: sus ocho ejemplos nuevos son
un taller aparte, excluido de ambos conjuntos. No comenzar todavía la autoría o
freeze de los 96 hasta asignar y probar responsables, modo de referencia/revisión,
calendario TTL y presupuestos separados, y aprobar las aclaraciones pendientes.

No es necesario fingir dos humanos independientes: una alternativa IA puede
admitirse como evaluación exploratoria asistida, con procedencia real, aislamiento
de predicciones/prompts y capacidad medida. Hoy no hay evaluador, personal ni
horas comprometidas que permitan declarar viable esa alternativa.

La revisión conserva el protocolo y el plan de versiones originales, ambos
fijados por hash. No modifica delta mínimo 0,05, cero errores críticos, mínimo
87 referencias/pares, cobertura ≥90%, bootstrap familiar de 10.000 réplicas o
sus criterios de selección. Tampoco cambia el tamaño, las familias ni los seis
microbloques. El margen operativo de tiempo es un supuesto de planificación,
no un cambio de umbral estadístico.

## 2. Riesgos/contradicciones identificados

| Riesgo del diseño | Resolución o bloqueo previo al reservado | Estado |
| --- | --- | --- |
| Dos revisiones y adjudicación sin personas/horas confirmadas | Exigir calendario y responsables reales; no asumir dos humanos donde no existen | **Bloqueante, abierto** |
| 192 salidas × dos revisiones no caben automáticamente en 24h | Forecast por respuesta, ventanas y dependencias; medir tiempo humano/operador en taller y desarrollo antes del freeze | **Bloqueante, abierto** |
| Verdad factual frente a restricciones léxicas | Dos formularios distintos; hecho no cambia al marcarlo no representable. Congelar ambos antes de respuestas | Mecánica ensayada, revisión sustantiva pendiente |
| F_case: errores técnicos son 0, ausencia de revisión no es error semántico probado | Rejected/technical_error/not_run con inventario íntegro son 0 sobre E; revisión indeterminada/expirada queda desconocida y genera límites conservadores | Ensayado sin cambiar endpoint |
| Dimensión indeterminada frente a caso elegible | Fijar obligaciones materiales y certeza antes de predecir; ambigüedad material excluye caso de E, sin elegir brazo; incertidumbre parcial admisible no implica excluir todo caso | Requiere rúbrica aprobada; taller muestra ambos casos |
| Bootstrap familiar frente a variaciones del mismo ejemplo | Primero promediar diferencias dentro de familia, después familias con igual peso | Ensayo 3/8, distinto de 3/7 por caso |
| Cita presente pero hecho material omitido | Valorar reconocimiento/limitación y significado global, no solo presencia de quote | Rúbrica propuesta; juicio independiente pendiente |
| Selección de evidencia puede ocultar negación/rumor circundante | Leer fuente primaria completa y juzgar alcance; no usar aceptación del validador como etiqueta de verdad | Rúbrica, no cambio de validador |
| Ceguera vulnerable a metadata, familia y estilo | IDs por caso aleatorizados, mapa separado, sin familia/brazo/modelo/prompt; no garantizar aislamiento por estilo | Metadata probada; ceguera real no certificada |
| Referencia original con errata puede ser materialmente falsa | Mantener historial; original para trazabilidad, sensibilidad con adjudicación independiente; si afecta selección, bloquear sin elegir versión favorable | Sigue pendiente aprobación de política de erratas del protocolo |
| Nuevo runtime/96 casos/P0 todavía no implementados | No reutilizar CLI de 32 ni DTOs v3 bajo v4; ejecutar implementación/compatibilidad y nueva autorización en otra tarea | **Bloqueante, abierto** |
| Jueces/referencias IA no presupuestados | Caps y permisos distintos de las predicciones de Nacho; desconocido no es cero | **Bloqueante si se elige IA**, abierto |
| Perfil vencido/alias sin snapshot | No renovar aquí; verificar documentalmente antes de ejecución; intercalado no garantiza backend idéntico | **Bloqueante para inferencia**, abierto |

El taller no sustituye revisión externa ni aprobación de los criterios propuestos.
No resuelve por código si un hecho es verdadero: valida localización, integridad,
denominadores y la aplicación de juicios explícitos, no su corrección semántica.

## 3. Instrumento versionado y separación de etapas

Versión: **news-semantic-review-instrument-v1**.
[Formularios y dimensiones](../evaluation/phase4c2_semantic_review_workshop_v1/instrument.json).
[Ejemplos del taller](../evaluation/phase4c2_semantic_review_workshop_v1/examples.json).
[Mecánica offline](../tools/evaluation/semantic_review_workshop.py).

El módulo ejecutable acepta únicamente `simulated_development`: no es un
importador de respuestas reales, no se conecta al runner y no genera referencias
atribuidas a humanos. Los formularios operativos definen procedencia requerida,
pero su importación real/validación de roles sigue pendiente de implementación
y revisión antes del experimento. Es una frontera explícita, no funcionalidad
productiva ni soporte de ejecución v4.

### A. Anotación factual, ciega y previa a predicciones

El anotador recibe solo fuente primaria completa, tabla neutral elegible y cutoff
virtual, instrucciones semánticas neutrales y un ID. No recibe prompts, regex,
resultados, estratos, familia ni lo que respondió otro anotador. Registra hechos
atómicos, certeza conclusive/indeterminate y qué hechos son materialmente necesarios.
Cada hecho lleva dimensión, significado, y cita/campo/offsets Unicode verificados;
la igualdad de texto comprueba ubicación, no entailment.

Separar acontecimientos y sujetos; anuncio de cierre, cierre real y mera intención;
participación directa de relaciones indirectas y menciones contextuales; identidad
corporativa del rol económico y de su security/ticker. No convertir ausencia de
información en negación o cero impacto. Registrar cantidades con magnitud/unidad/
escala/período y ambigüedades, y fechas del evento separadas de publicación.

Dimensiones: events, event_stage, evidence, identity, participation, role,
relationship, ticker_link, quantities, dates, negation, impact, material_omissions.
Suficiencia/abstención se evalúa aparte; no es una tasa de aceptación de JSON.
Las oportunidades/obligaciones quedan fijadas antes de observar las salidas.

### B. Capa contractual separada

Otro registro enlaza fact_id y versión de contrato con structured,
faithful_partial_only, not_representable o indeterminate, más rationale.
No sobrescribe significado, certeza o citas de la capa factual. Define resultados
admisibles del artículo: interpretación fiel al menos parcial, abstención necesaria,
o indeterminación explícita. No imponer un JSON esperado ni convertir el verbo
de la fuente al vocabulario del validador para crear una referencia favorable.

Que un campo no sea representable no siempre obliga a abstención global. Si
evento, evidencia original y limitación conservan significado/materialidad,
permitir salida parcial. Si omitir la parte cambia el sentido y no cabe una
limitación honesta, abstenerse. La aprobación humana de esta frontera sigue pendiente.

### C. Discrepancias de referencias y freeze

Conservar ambos registros y sus hashes. Desacuerdos requieren tercer juicio
explícito, o indeterminación; nunca tomar silenciosamente el primero. Un acuerdo
no se reemplaza por otra etiqueta sin una errata versionada. Fijar corpus,
referencias/capa contractual, procedencia y E antes de predicciones. El taller
usa un freeze distinto, con etiqueta inequívoca de desarrollo simulado y escritura
exclusiva: jamás sustituye el freeze histórico o el futuro reservado.

### D. Puntuación individual de salida anonimizada

El revisor recibe fuente, referencia factual/capa contractual ya congeladas y una
salida con blind_id; no recibe la contraparte, etiqueta v3/v4, modelo, familia,
prompts ni resultados del otro revisor. Los paquetes son efímeros y no se exportan
con respuestas. El mapa privado fija case_id, brazo y hash de respuesta, con sus
timestamps. La primera anotación individual se cierra antes de adjudicar.

Para cada dimensión usar pass/fail/indeterminate/not_applicable; registrar matched,
omitted y unsupported contra oportunidades prefijadas. No dividir afirmaciones
inventadas por cero oportunidades para declararlas correctas; informar extras.
Un pass no admite omisiones/afirmaciones incorrectas ocultas. Indeterminate no es
pass; not_applicable no puede borrar una obligación o referencia ambigua.

Buscar específicamente falsas finalizaciones, inversión de negación, identidad o
participación inventadas, citas fabricadas, información futura y salida operativa.
Revisar texto narrativo además de campos. Identificar omisiones materiales incluso
si existe una cita larga. Ticker presente no significa exposición. Parcialidad
con límite explícito puede ser fiel; un unknown sin reconocer un hecho esencial no.

Abstenciones: justified, unjustified, indeterminate o not_applicable. Justified
requiere evidencia/representabilidad que haga imposible una interpretación fiel;
no usarla para ocultar un error técnico. Unknown en fecha/identidad/impacto opcional
no basta por sí solo para justificar abstención completa.

### E. Adjudicación y análisis

Conservar puntuaciones iniciales, hashes y tercer juicio. Mantener desacuerdo no
resuelto como indeterminate. El adjudicador no sustituye unilateralmente un acuerdo.
Después se revela el mapa de brazos y se calcula F_case por caso/familia con E
común. Contar rechazos/no ejecutados como fallos técnicos conocidos, no como
abstenciones. Mantener desconocidos y límites v4-peor/v3-mejor, sin eliminar pares
por el outcome. El taller no ejecuta gates de adopción ni bootstrap: esas extensiones
del comparador experimental siguen pendientes y no se inventa una decisión.

## 4. Ejemplos de capacitación, no casos del experimento

| Ejemplo nuevo | Decisión que debe practicar el revisor |
| --- | --- |
| Neravelle anuncia compra condicionada | completed es falsa confirmación; announced con condiciones es interpretación fiel parcial |
| Compra cerrada, importe no divulgado | La negación incidental no niega el cierre; abstenerse solo por “not” es pérdida injustificada |
| Orvessa Desk mencionado incidentalmente | Identidad neutral de Orvessa no prueba que compró, participó o tiene exposición FIC-ORV |
| EUR 7,5m y condición de volumen | Verdad: grafía/ambigüedad original. Contrato: parcial con evidencia/límite, no transformar a 75 ni borrar condición |
| Propuesta para “next Tuesday” sin publicación | No inventar ISO; conservar timing textual como limitado, sin falsa finalización |
| Empresa/evento no identificados | Abstención justificada distinta de inventar una noticia neutral |
| Fuentes discrepan sobre actor | Indeterminación explícita, sin consenso artificial |
| Error técnico o caso no ejecutado | No puntuarlo como abstención semántica; F_case técnico es 0 cuando pertenece a E |

Estos ocho casos y dieciséis salidas son inventados por IA como fixtures de
instrumentos. No hubo generación LLM ni anotadores humanos reales. Incluyen un
desacuerdo factual y otro de puntuación deliberados, con adjudicaciones simuladas.
No son referencias externas, holdout ni material de los 24/96 futuros.

## 5. Capacidad operativa y TTL: resultado actual no ejecutable

[Plan de capacidad](../evaluation/phase4c2_semantic_review_workshop_v1/capacity.json).
Fuente del compromiso actual: **ningún revisor, adjudicador o slot confirmado**.
Nacho conserva autoridad de aprobación; no se le atribuyen horas, tareas de
revisión ni independencia que no confirmó. Los roles de coordinador TTL,
anotadores factuales, revisor contractual, revisores de salidas y adjudicador están
pendientes de asignación. El operador y el equipo de prompts no son adjudicación
humana independiente si han observado brazos/predicciones.

Supuestos explícitos, no mediciones: 12 min por salida/revisor, 6 min por adjudicación,
dos juicios y adjudicación de **todas** las salidas como cota adversarial, +25%
contingencia. Para 192 salidas: 384 tareas primarias =76,8 horas-persona;
adjudicación=19,2 horas; total con margen=**120 horas-persona**. No incluye crear
referencias ni administrar los paquetes. Dos personas con ocho horas no bastan.

El simulador recibe los 192 timestamps de persistencia de seis bloques (32 salidas
cada uno), disponibilidad por persona, dos pools distintos y un pool de adjudicación.
Cada tarea debe terminar dentro de su slot y **antes de expires_at menos 60 minutos**.
La adjudicación solo empieza tras ambos juicios. Se prueban tanto la ausencia de
capacidad como un ejemplo con 6+6 revisores y tres adjudicadores ficticios: con
bloques separados una hora y ventanas de 16h termina a las 8h15m02s desde el inicio.
Ese cálculo **no certifica existencia ni disponibilidad de quince personas**.

Alternativa viable solo tras verificación: referencias/revisión asistidas por IA
aislada, con modelo/procedencia reales, revisión focalizada del propietario y tiempo
de operador medido. Si usa APIs, requiere presupuesto y autorización separados;
si es ChatGPT manual, no inferir snapshot/parámetros/tokens API y contabilizar
tiempo humano/suscripción por separado. No se probó un modelo ni su velocidad.

Antes del freeze: piloto cronometrado del instrumento con datos de desarrollo,
medir colas, duración/adjudicaciones y disponibilidad real; después congelar el
calendario. Las disponibilidades deben cubrir precios/autorización vigentes,
microbloques y contingencias. No prometer revisión después de expirar una respuesta.

Antes de cada bloque el coordinador TTL comprueba cola pendiente y forecast con
los tiempos reales. Si se pierde un revisor, se incumple el margen, falta capacidad,
vence perfil/autorización o falla coste/persistencia/P0: **no iniciar nuevas llamadas**,
conservar estado y registrar no ejecutados. Un sustituto necesita independencia,
formación y slot confirmados; no reducir revisiones o casos silenciosamente.
Lo ya expirado es no revisable y limita el análisis, nunca se recupera por backups.

## 6. Retención y auditoría

Contenido/respuestas/paquetes/rationales/citas de salidas: 24h individuales.
Metadata cerrada de revisión, mapas opacos y hashes: 90 días sin prórroga; P0
mantiene su propio contrato y retención, sin agregarle texto de evaluación.
Las fuentes/referencias sintéticas previas tienen política separada; no se usan
como contenedor de respuestas del proveedor. La auditoría tardía lee solo metadata
sanitizada y sus hashes, no reconstruye citas después del TTL.

El taller nunca escribe cuerpos de respuestas en los exports: solo referencias
pre-output propias y metadata. Destruye objetos con cuerpos antes del resumen
post-TTL. El fixture versionado incluye frases simuladas de prueba, no respuestas
de ningún proveedor. No hay importación de intentos reales ni backfill.
El CLI self-test usa un directorio temporal propio, no escribe en data/cache y
solo imprime contadores/fingerprints sin texto. No se borran artefactos existentes.

## 7. Presupuestos separados y responsables pendientes

[Registro de presupuestos](../evaluation/phase4c2_semantic_review_workshop_v1/budgets.json).

| Partida | Base y límite | Estado |
| --- | --- | --- |
| Predicciones Nacho | Escenario histórico vencido: reservado US$3,20; desarrollo opcional US$0,80 separado | No vigente, no autorizado, cero ejecutado |
| Referencias IA | Modelo, llamadas, tarifa, estimación y cap null | No cotizado ni autorizado; no asumir coste cero |
| Revisión de salidas IA | 192 salidas, posibles juicios múltiples/adjudicación; tarifa/cap null | No cotizado ni autorizado; separado de generar referencias |
| Trabajo humano | 120h estimadas solo para revisión adversarial; horas/tarifa comprometidas null | Cero coste API no implica trabajo gratis o disponible |
| Suscripción/impuestos/FX/storage | null hasta elección de modalidad | No incluidos en los caps de Nacho |

Fórmula para presupuestar cada flujo IA por separado, después de verificar tarifas:
sumar por llamada entrada no cacheada, lectura/escritura de caché y salida según
las categorías reales, más reservas conservadoras y límites propios. No atribuir
tokens medidos a ChatGPT manual ni usar el cap de Nacho para pagar jueces. No se
consultó proveedor ni se renovaron tarifas en esta entrega.

## 8. Ejecución offline del taller y recomendación de avance

```powershell
python tools/evaluation/semantic_review_workshop.py --self-test
python -m pytest tests/unit/test_semantic_review_workshop.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts tools/evaluation
```

El resultado simulado esperado es delta familiar **3/8**, con 7 casos elegibles
en cuatro familias (uno indeterminado excluido por referencia, no por respuesta).
No representa superioridad real de v4. El mismo taller con juicio material abierto
produce límites 1/4–3/8; no se inventa una etiqueta para cerrar ese intervalo.

**Avanzar a los 24 de desarrollo:** sí como autoría y ensayo metodológico sin
inferencia, manteniendo procedencia asistida y sin prometer referencias humanas.
**Avanzar a los 96 reservados:** todavía no. Exigir responsables/modo de revisión,
capacidad medida, presupuestos separados, aprobación de rúbrica/erratas, autoría
separada y las dependencias técnicas del plan de versiones antes de su creación.
**Ejecutar el experimento:** no. Faltan además perfil vigente, nuevo runtime/runner,
freeze real y autorización específica. Los umbrales existentes no se cambian.

El taller tampoco implementa un importador operativo para revisiones reales ni
un registro de ciclo de vida para salidas que expiren sin revisión. Ese registro
deberá distinguir falta de revisión de un juicio semántico indeterminado, sin
crear anotaciones retrospectivas ni leer respuestas vencidas. Es otra dependencia
bloqueante para la ejecución; el taller solo demuestra juicios simulados emitidos
dentro del TTL y su auditoría posterior mediante metadata.

## 9. Validaciones y conservación

- Suite completa: **869 passed** (225,02 segundos); incluye 14 tests nuevos del taller.
- Self-test: 16 salidas simuladas, un desacuerdo factual y uno de puntuación,
  delta familiar 3/8, cero llamadas y ninguna escritura en datos de producción.
- `python scripts/validate_data.py`: correcto; features/targets separados,
  905 registros normalizados, 811 artículos, cero errores de lineage/raw y
  cuatro snapshots verificados.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Los 3.558 archivos preexistentes bajo src/config/data/evaluation/tests/tools
  conservan sus hashes respecto del inventario previo a esta tarea. Se agregaron
  únicamente instrumentos/fixtures/tests/herramienta de desarrollo; no se
  interpretó contenido histórico expirado.
- Los 18 pins del manifiesto del diseño original coinciden. El freeze histórico
  conserva SHA-256 `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`;
  las salidas históricas conservan
  `c9181bee95769a0d13928d768a3490c83de2377ba93aa9f60eb4252d14479fa4`.

El [manifiesto metodológico](../evaluation/phase4c2_semantic_review_workshop_v1/methodology-manifest.json)
fija por hash esta entrega y sus dependencias; no es un freeze del reservado ni
una autorización. PROJECT_SPEC incorpora solo un enlace de estado. No se tocaron
prompts, validadores, contratos productivos, perfiles vencidos ni referencias
históricas. Phase 4C.3 continúa sin iniciar.
