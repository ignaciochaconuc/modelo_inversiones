# Phase 4C.2.2 — Corpus de desarrollo v3/v4, 24 casos

Estado: `phase4c2_v3_v4_development_corpus_prepared_pending_review`.
Autoría sintética de desarrollo, no evaluación independiente ni autorización.
**24 casos, 12 familias, cero reservados, referencias definitivas o predicciones.**
Phase 4C.3 continúa sin iniciar. No se ejecutó v3/v4, no se renovaron perfiles y
no se consultó ningún proveedor ni se cargaron credenciales.

## 1. Alcance, archivos y procedencia

Se aplica la cuota de desarrollo del [protocolo original](phase4c2-v3-v4-experimental-protocol.md),
sin cambiar métricas, umbrales, prompts, esquema económico ni validadores.
La [preparación metodológica](phase4c2-v3-v4-methodology-readiness.md) continúa
vigente: el experimento reservado sigue **no ejecutable** por falta de capacidad
confirmada y dependencias de runtime/revisión/autorización.

Directorio: `evaluation/phase4c2_development_corpus_v1/`.

| Archivo | Uso y frontera |
| --- | --- |
| authoring.json | Autoría, reloj, historias y único cambio controlado; privado, nunca input del modelo |
| corpus.json | 24 sobres opacos con request causal, revisión primaria y evidencia por campo |
| registry.json | Inventario neutral ficticio; no pasar globalmente al modelo |
| private-design.json | Familias, variantes, estratos, intención y ambigüedad; solo control de calidad |
| originality-audit.json | 1.920 comparaciones contra 80 textos fuente permitidos; sin predicciones ni referencias históricas |
| review-template.json | Formularios vacíos de hechos y, separadamente, representabilidad; no son referencias |
| pilot-plan.json | Muestra propuesta de seis casos y mediciones aún vacías; no piloto ejecutado |
| manifest.json | SHA-256 de artefactos y dependencias; no freeze del reservado ni de referencias |

Autor: Codex, asistente IA en el hilo de desarrollo, el **2026-10-19** según la
fecha del entorno. Snapshot desconocido/null; no se atribuye identidad humana ni
aislamiento frente al desarrollo. Es autoautoría y autoauditoría asistida por IA,
no revisión independiente. No hay timestamps de anotadores, tokens ni mediciones
inventados. Los casos son desarrollo por diseño, no un nuevo holdout.

## 2. Doce familias contrafactuales

Dos variantes por fila. Headline, prefijo de summary y reloj permanecen iguales;
se sustituye exclusivamente el sufijo de summary documentado en el archivo privado.
La transformación es explícita y reproducible, no edición de noticias históricas.

| Estrato | Historia nueva | Condición semántica modificada |
| --- | --- | --- |
| Anunciado | Qevrith, horno antiguo | Aviso formal de retiro versus asunto pendiente de votación |
| Completado | Zhulvane y cooperativa, concesión de horno | Entrega física y operación versus mero sellado administrativo |
| Propuesto | Draxuvo, dragado del canal | Solicitud de subvención no vinculante versus adjudicación vinculante |
| Etapa desconocida | Umqerra, refit R7 | Código sin definición versus glosario con significado operativo |
| Negación | Vuqelith, inspección de esterilidad | Suspensión de lotes versus negación de esa suspensión; privacidad del inspector constante |
| Condición temporal | Xemvori, rescate de notas | Certificado de escrow pendiente versus recibido; pago futuro en ambos |
| Participación directa | Pluvarek y Qosdelun, reparaciones | Garantía financiera versus mera distribución de circular sin obligación |
| Relación indirecta | Truxevan y Oqzarin, incendio/insumo | Dependencia exclusiva actual versus compra antigua sin órdenes actuales |
| Contexto e identidad | Duzqarel y Helqorin, terreno municipal | Autor de plano usado como contexto versus coarrendatario responsable de renta |
| Números | Bravqulin, residuos textiles | Mismo importe/lexema: tres meses agregados versus cada mes |
| Fechas y PIT | Yrvexil, permiso de horno | Fecha de vigencia del permiso versus solo fecha de publicación |
| Evidencia insuficiente | Extracto de autorización retirada | Sin titular/objeto versus recuperación del encabezado que los identifica |

Ningún par cambia únicamente nombres o cifras. El tema común y la condición
controlada son deliberados; las variantes no son observaciones independientes.
Compartir headline/prefijo dentro de la familia no es un fallo de originalidad.
Cada caso tiene case_id opaco D-<hash16>; family_id privado DF-<hash16>. El orden
público por ID evita adyacencia por familia, pero **no constituye el orden futuro
de inferencia** ni garantiza que el estilo impida reconocer contrafactuales.

Ambigüedades intencionales, no errores a resolver inventando información:

- R7 sin glosario deja abierta la etapa, no la identidad del proyecto.
- Next week no es una fecha ISO literal; no se fuerza normalización.
- Enero–marzo no incluye año: no atribuir automáticamente el año de publicación.
- Fecha publicada no implica fecha de entrada en vigor del permiso.
- El extracto sin caption no identifica ni titular ni objeto de autorización.

Las notas privadas de autor expresan intención de cobertura, **no adjudicaciones
factuales**. Un revisor debe comprobarlas contra los textos; si detecta ambigüedad
accidental, registrar discrepancia y proponer otra versión antes de cualquier uso.
No se usa aceptación técnica de un validador como garantía semántica.

## 3. Evidencias, registry y causalidad

Los textos son inglés empresarial original de esta tarea. No proceden de Finnhub,
noticias reales, respuestas de Nacho ni referencias ChatGPT de los 32 casos.
`synthetic_record(..., ticker="")` evita expresamente su default histórico AAPL:
no hay ticker directo/provider impuesto ni ticker real en los registros emitidos.
El helper y los contratos existentes no fueron modificados.

Cada sobre contiene un NewsRecord y dos TextEvidence completos: headline y summary.
Sus 48 evidence_id se derivan del contrato existente (news_id, revision_id, campo,
texto y disponibilidad); se verifican request_id, content_hash y fingerprints.
No se proporcionan spans seleccionados, conclusiones ni citas esperadas al modelo.
Una futura evaluación deberá usar solo request y evidencia derivados, nunca
private-design, authoring, review-template, auditorías o referencias. No hay
loader/runner real nuevo ni activación de prompt en esta entrega. El request
conserva el envelope histórico news-interpretation-v1; no declara que v4 ya esté
soportado por el runtime. La futura selección de prompt será explícita y versionada.

El registry tiene **16 entradas para 15 entidades**, todas sintéticas y sin aliases,
roles, relaciones o impactos. SYNTH-DEV24-* son identificadores de prueba largos
y explícitamente no bursátiles, no símbolos utilizables en mercados ni Feature
Store. No se pretende haber verificado externamente que un nombre inventado jamás
coincida con alguna razón social; no se hizo búsqueda externa. La combinación de
namespace ficticio, evidencia de autoría y prohibición operativa evita representar
esas identidades como instrumentos reales. Cooperativa y consejo municipal no
reciben securities inventados: pueden mantenerse como nombres no resueltos.

El inventario completo se conserva para auditoría, pero el request incluye solo
entradas cuyo nombre se menciona literalmente en ese texto y que cumplen PIT.
En el extracto sin actor no se filtra el nombre desde el diseño privado a través
del registry. Para Yrvexil, una entrada es conocida **después** del cutoff y otra
solo es efectiva al día siguiente: ambas quedan excluidas de ambos requests.

Reloj enteramente virtual del **2031-03-21**, expresamente ajeno a publicaciones
históricas observadas: published 10:00Z, first_seen/available 10:02Z, ingested
10:03Z, decision 10:04Z. No se colapsan sus significados. La fecha de evento del
NewsRecord sigue null; el texto puede contener fechas que después se anotarán.
Los filtros requieren known_at <= decision_time y vigencia en la fecha primaria
según el contrato actual. Tests cubren el límite inclusivo known_at y exclusión
de vigencias futuras; el reloj no representa conocimiento real de hechos futuros.

## 4. Auditoría de originalidad

Fuentes permitidas: únicamente campos headline/summary y sus IDs de los 32
synthetic_sources, los 40 fixtures P1 y los ocho ejemplos del taller. El extractor
no consulta etiquetas, reglas, salidas simuladas, respuestas de Nacho, referencias
congeladas, smokes, Finnhub o TEST. Los archivos mixtos P1/taller se leen para
extraer únicamente esos campos; no se usan sus campos de expectativas como datos
de adaptación. Se conservan hashes de los tres archivos fuente.

Se compararon 24 × 80 = **1.920** pares mediante:

1. Tokens Unicode NFKC y comparación exacta normalizada.
2. Jaccard de tokens y de bigramas con nombres/números enmascarados, para detectar
   cambios cosméticos sobre una misma plantilla.
3. Longitud de tramo literal común.
4. Un vocabulario de temas transparente para localizar vecinos conceptuales;
   no es un embedding, entailment ni una certificación semántica.
5. Autoinspección conceptual del autor, resumida abajo y en cada nota privada.

Resultado: cero textos exactos, cero reutilizaciones de nombres completos y
cero alertas de plantilla. Máximos: Jaccard léxico 0,157895; bigramas enmascarados
0,051282; tramo común **tres tokens**. La coincidencia temática llega a 1 porque
se exigen dimensiones comunes: **no se oculta ni se interpreta como independencia**.
Los umbrales de triage superficial (.38/.52/12 tokens) son del instrumento de
originalidad, no umbrales de scoring/adopción del experimento.

| Dimensión compartida con material anterior | Diferencia narrativa/causal inspeccionada |
| --- | --- |
| Anuncio y compra condicionada (M01/taller) | Aviso laboral de retiro de horno y voto de directorio, sin adquisición |
| Cierre de activos y revisión previa (M02/P1) | Concesión operativa, llaves/custodia frente a sello de expediente |
| Shortlist/consulta/propuesta (C02/R02/P1) | Solicitante de subvención frente a adjudicación y reembolso de dragado |
| Morfología de etapas (P1) | Un código R7 opaco y su definición explícita, no conjugación de un verbo |
| Negación de compra/importe no divulgado | Alcance sobre suspensión de lotes y privacidad del inspector |
| Adquisición futura/rumor | Certificado de escrow como condición de instrucción de pago, no pago realizado |
| Comprador/proveedor (C01) | Obligación de indemnizar frente a circular reenviada sin obligación |
| Matriz/filial/licencias (S01/F01) | Insumo exclusivo interrumpido frente a muestras antiguas sin exposición actual |
| Plataforma/benchmark/incidental | Plano catastral frente a responsabilidad de renta en arrendamiento |
| Cifra de ingresos/decimal (P1/taller) | Misma cifra física/monetaria y cambio de agregación temporal, sin cambio de números |
| Fecha textual de financiación (P1) | Referente de fecha ISO y disponibilidad temporal de una identidad |
| Update genérico/actor disputado (taller) | Línea de índice regulatorio concreta y recuperación de su caption |

No se afirma disjunción conceptual absoluta: etapas, negación, identidad y PIT
deben solaparse por cobertura. La auditoría no halló una historia o plantilla
reutilizada; **falta revisión independiente de esa conclusión y del significado
contrafactual**. Si alguien detecta una reutilización sustantiva, bloquear el uso
de esa familia y versionar su sustitución; no conservarla como holdout independiente.
No se adaptaron textos tras ejecutar v3/v4 ni se optimizaron contra sus resultados.

## 5. Aplicación posterior del instrumento y piloto cronometrado

`review-template.json` incluye 24 formularios factuales vacíos y 24 capas
contractuales vacías, separadas. source_fingerprint identifica el sobre completo
del caso; el futuro importador deberá verificarlo y adaptar el formulario, no
confundirlo con el formato restringido de simulación del taller. No se asignaron
revisores, certeza, hechos, expected outputs ni resultados admisibles. No hay
referencias definitivas, freeze de referencias ni adjudicación humana fingida.

Propuesta **no ejecutada**: seis casos, las dos variantes de tres familias:
unknown_stage, numeric_fidelity y dates_and_pit. IDs exactos en pilot-plan.json.
Muestreo deliberado de carga/ambigüedad, no muestra aleatoria representativa.

1. Confirmar operador y modalidad real de revisión. No suponer dos humanos.
   Dos revisiones del mismo propietario son un ensayo de flujo, no independencia.
   Una IA requerirá procedencia honesta y autorización distinta si hubiera API;
   esta tarea no la autoriza ni ejecuta.
2. Preparar orden ciego por ID, separar variantes y ocultar familias/estratos/notas.
   Entregar solo fuente, evidencia, reloj/identidad elegible e instrucciones
   neutrales del instrumento. Registrar versión y hashes antes de anotar.
3. Cronometrar por separado carga, lectura, anotación factual, chequeo de citas,
   capa contractual y resolución de discrepancias. Registrar reloj con zona,
   inicio/fin, origen del timestamp, pausas, tiempo activo y cola. Nunca rellenar
   mediciones antes de realizarlas. No freeze automático ni aprobación implícita.
4. Si hay dos revisores realmente distintos, cerrar primero ambos juicios;
   cronometrar adjudicación de cada desacuerdo, manteniendo no concluyentes. Si
   solo hay un propietario, adjudicación real queda **no medida**, no cero ni una
   diferencia ficticia presentada como humana. El taller puede probar el mecanismo
   con discrepancias simuladas separadas, no medir independencia semántica.
5. Reportar mediana, máximo y cada observación; con seis casos el p95 interpolado
   no es una cota fiable. Usar máximo observado más margen conservador y repetir
   si hay colas o gran variación. Separar tiempos de hechos/contrato/adjudicación;
   no inferir tiempo de revisar respuestas a partir de anotar fuentes.
6. Para estimar revisión de salidas, hacer aparte un ensayo cronometrado con las
   respuestas **simuladas del taller**, sin generar predicciones de estos 24 casos.
   Ese ensayo mide trabajo, no precisión de Nacho. Tras medir, recalcular las
   seis ventanas con dos brazos, dos revisiones, contingencias y adjudicación.
7. Mantener los bloqueos: sin personas/slots/mediciones confirmados el reservado
   sigue no ejecutable. No crear/congelar sus 96 casos con esta entrega. Ante
   presión sobre el TTL individual de 24h, detener futuras llamadas; nunca guardar
   copias permanentes, extender TTL ni anotar una respuesta ya expirada.

El piloto factual usa fuentes sintéticas propias previas a predicciones y no
consume TTL de respuestas inexistentes. Una futura revisión de contenido real
del proveedor sí estará limitada a 24h; solo metadata cerrada de revisión/P0
admite su política independiente de 90 días. Separar costes de predicción,
referencias IA, jueces IA y trabajo humano. No se actualizan tarifas vencidas.

## 6. Verificación reproducible y límites

```powershell
python tools/evaluation/development_corpus.py --verify
python -m pytest tests/unit/test_development_corpus.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts tools/evaluation
```

El verificador es de solo lectura y no tiene opción de inferencia, importación
de referencias o escritura de corpus. Reconstruye los derivados desde autoría,
valida hashes contra el manifiesto y recalcula la auditoría; cualquier divergencia
bloquea. Los IDs de evidencia son los contratos originales, no un esquema nuevo.
Los tests de textos y contrafactuales verifican integridad/intención mecánica;
no prueban que un LLM seguirá el prompt ni que cada juicio semántico sea correcto.

El manifiesto identifica esta **versión de autoría de desarrollo**, no hace
inmutables referencias inexistentes. Para corregir después, conservar esta versión
y producir otra con cadena y hashes explícitos, no sobrescribir silenciosamente.
No hay promoción operativa, conexión con Feature Store o decisión de inversión.

## 7. Resultado de las validaciones de esta entrega

- `python -m pytest`: **886 passed**, 234,28 segundos; incluye 17 tests nuevos.
- Preflight de solo lectura: 24 casos, 12 familias/estratos y 48 evidencias;
  reconstrucción exacta, cero predicciones, llamadas o casos reservados.
- `python scripts/validate_data.py`: correcto; features/targets separados,
  905 revisiones, 811 artículos, cero hashes raw inválidos, linajes faltantes o
  duplicados; cuatro snapshots de enriquecimiento íntegros.
- Compilación de src/scripts/tools/evaluation: correcta.
- Los 3.600 archivos preexistentes inventariados en src/scripts/config/data/
  evaluation/tests/tools conservan sus hashes. No se leyó contenido histórico
  expirado para diagnóstico ni se consultaron predicciones/referencias previas.
- Los 18 pins del diseño original y los 12 del manifiesto metodológico siguen
  coincidiendo. Sus estados de corpus no creado describen aquellas entregas
  históricas: no se reescriben. Este nuevo manifiesto registra solo los 24 de
  desarrollo; reservado, referencias definitivas e inferencia siguen ausentes.

Revisión independiente de originalidad/contrafactuales y piloto cronometrado:
**pendientes**, sin personas, horarios o tiempos atribuidos ficticiamente.
