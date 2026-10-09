# Roadmap

Los estados describen planificación, no autorizan iniciar una fase. Cada fase requiere instrucción explícita.

## Phase 0 — Architecture + Feature Store

**Status:** mostly complete

**Objetivo:** establecer contratos, configuración, protección point-in-time y almacenamiento local.  
**Entregables:** schemas, FeatureRow, Parquet/DuckDB, features cuantitativas base, agentes/LLM/modelos como interfaces, costos, cache, riesgo básico, auditoría, tests y documentación.  
**Finalización aproximada:** contratos estables, suite verde y revisión de los detalles pendientes de Phase 0 sin conexiones externas.

## Phase 1A — Tiingo market data ingestion

**Status:** complete

**Objetivo:** incorporar OHLCV diario, corporate actions y series split-adjusted reproducibles.  
**Entregables:** adapter Tiingo, configuración temporal, calendario XNYS, storage incremental idempotente, CLI, universo fijo de desarrollo y tests mockeados.  
**Finalización aproximada:** cumplida para el alcance local; una descarga real requiere una API key del usuario.

## Phase 1B — Quantitative ingestion pipeline

**Status:** complete

**Objetivo:** conectar datos processed con construcción incremental del Feature Store.  
**Entregables:** selección point-in-time, cobertura/calidad ampliada y pipeline de features para el universo. Massive puede evaluarse más adelante solo como fuente de referencia histórica de tickers.  
**Finalización aproximada:** feature store reproducible para el universo sin look-ahead ni dependencia de la composición actual para backtests válidos.

### Phase 1B.1 correctness review

**Status:** complete

Se corrigieron conteos históricos globales, segmentación por barras retrasadas, targets por sesiones exactas y reemplazo autoritativo de rangos persistidos.

### Phase 1A.1 correction

**Status:** complete

Se separaron latest-basis y normalización split-adjusted as-of, se desacoplaron features de `adjClose` del proveedor y se añadieron anomalías no destructivas para fechas ausentes durante refresh.

### Phase 1C — Real Data Pilot

**Status:** complete for the four-ticker pilot

El runner acotado para SPY, AAPL, MSFT y NVDA valida cobertura raw, corporate actions, ventanas de splits, invariantes point-in-time, features de benchmark, outliers, targets y rendimiento. Produce `data/reports/real_data_pilot.json` sin cambiar fórmulas, schema, elegibilidad ni el universo principal. Los tests permanecen completamente offline. El piloto real fue ejecutado hasta 2026-10-05; esa sesión aún estaba antes del cutoff durante la consulta y quedó clasificada como pendiente, no como gap histórico inesperado.

La revisión de rendimiento reemplazó rescans por fecha en segmentación y conteos históricos por eventos de disponibilidad, y vectorizó los factores de splits. El benchmark sintético y el reporte reproducible permiten detectar regresiones antes de ampliar el universo.

### Phase 1D — Full Development Universe Dataset

**Status:** complete

El workflow reutiliza Tiingo, ingesta incremental, normalización as-of, Feature Store y targets existentes para los 101 activos configurados. Aísla fallos por ticker, valida calidad transversal y rankings, conserva la advertencia de survivorship bias y permite reanudar lotes sin repetir series locales completas.

### Phase 1D.1 — Corporate Action Integrity

**Status:** complete

Aliases provider-specific conservan la identidad interna; una tabla separada
clasifica eventos complejos sin alterar raw. Features usan flags point-in-time,
targets marcan horizontes que cruzan exclusiones y el ranking usa solo labels
training-valid. El reporte separa warm-up esperado y outliers explicados de los
movimientos aún no explicados.

## Phase 2 — Backtesting engine

**Status:** complete for the current fixed-universe real-data scope

**Objetivo:** simular decisiones after-close y ejecución next-open.  
**Entregables:** loop temporal, fills, costos, cartera, benchmark, métricas y auditoría.  
**Finalización aproximada:** backtests deterministas con pruebas explícitas de ausencia de leakage.

### Phase 2A.1 — Backtesting contracts + portfolio accounting

**Status:** complete

Schemas específicos separan target weights, órdenes, fills, posiciones por
unidades, snapshots y resultados. `PortfolioLedger` implementa accounting
long-only determinista, mark-to-market estricto, splits y dividendos. No incluye
loop temporal, estrategias, benchmark, optimizador, ML ni PaperExecutor.

### Phase 2A.2 — Temporal backtesting engine

**Status:** complete

Motor genérico por sesiones XNYS que convierte allocations fechadas en órdenes
al raw close y fills exclusivamente en el raw open de la sesión siguiente.
Incluye costos, restricciones de cash, ventas antes de compras, estados unfilled,
valoración stale explícita, splits/cash-in-lieu, dividendos, invalidación por
acciones complejas, P&L por costo promedio e IDs deterministas. No incluye
estrategias, optimizer, integración con Risk Manager, ML ni PaperExecutor.

### Phase 2A.3 — Backtest metrics + benchmark reporting

**Status:** complete

`BacktestResult` se convierte en un reporte versionado y serializable con
performance basada en NAV, drawdown, ratios risk-adjusted, ejecuciones, costos,
turnover por notional ejecutado, exposición, P&L y corporate actions. El
benchmark interno simula SPY con raw prices, splits, dividendos reinvertidos
causalmente y los mismos costos. No es una estrategia reutilizable.

### Phase 2B — Baselines

**Status:** complete for the current fixed-universe real-data scope

Implementa SPY buy-and-hold con dividendos reinvertidos causalmente, equal-weight
diario del universo elegible y momentum 20d top-10 diario. Todos producen
`TargetAllocation` y reutilizan engine y reporting sin acceder a targets.

La validación local 2010-01-01 a 2026-10-02 completa SPY, momentum y equal-weight.
Tras Phase 2B.1.3, equal-weight supera MDLZ, ABT/ABBV, Google y RTX/UTC sin
encontrar otro evento complejo no revisado. Phase 2 queda validada de extremo a
extremo para el universo fijo, proveedor y ventana actuales; esto no elimina el
survivorship bias documentado ni autoriza Phase 3.

### Phase 2B.1 — Reviewed complex corporate actions

**Status:** complete for the current fixed-universe real-data scope

Añade contratos económicos event-specific para MDLZ/KRFT y TMUS/MetroPCS,
entitlements fechados, securities auxiliares, cash de recapitalización y registros
de transformación deterministas. El default para cualquier otro evento complejo
sigue siendo `UnmodelledCorporateActionError`. KRFT se ingirió únicamente como
dependencia auxiliar y no pertenece al universo invertible. La validación real
debe detenerse ante el siguiente evento complejo no revisado. Las revisiones
2B.1.1–2B.1.3 cubren todos los blockers encontrados en el rerun actual sin
cambiar esta política.

### Phase 2B.1.1 — Regular-way spin-off entitlement + ABT/ABBV

**Status:** complete

Separa `record_date` legal de la observación de entitlement regular-way. MDLZ
ahora observa ownership al cierre de 2012-10-01. ABT/ABBV reutiliza el treatment
genérico de spin-off con record date 2012-12-12, entitlement 2012-12-31,
distribución 1:1 el 2013-01-01 y procesamiento pre-open 2013-01-02. ABBV mantiene
basis no asignado, consume el pseudo-dividendo Tiingo y continúa siendo miembro
normal del universo invertible; no se agregaron excepciones por ticker. El rerun
confirmó que ABT ya no bloquea. Google fue revisado posteriormente en Phase
2B.1.2 sin cambiar la política conservadora.

### Phase 2B.1.2 — Google 2014 Class C distribution

**Status:** complete

Reutiliza la distribución genérica para mantener GOOGL Class A y añadir GOOG
Class C 1:1. Se verificó la lineage restated de Tiingo/Nasdaq, el entitlement
regular-way al cierre de 2014-04-02, la ausencia de split y el pseudo-dividendo
GOOGL consumido. GOOG y GOOGL siguen siendo activos invertibles independientes;
no se añadió lógica hardcodeada por ticker. El rerun confirmó que Google ya no
bloquea y avanzó hasta RTX 2020-04-03, revisado posteriormente en Phase 2B.1.3.

### Phase 2B.1.3 — UTC / RTX 2020 Carrier + Otis distributions

**Status:** complete

Generaliza el treatment de distribución a múltiples securities dentro de un
solo evento económico y migra limpiamente MDLZ, ABT y Google. El lineage UTC se
conserva bajo RTX 1:1, con entitlement regular-way al cierre de 2020-04-02; el
evento añade 1 CARR y 0.5 OTIS por parent antes del open siguiente. CARR y OTIS
son dependencias auxiliares, no miembros del universo, y conservan basis no
asignado. Se consume el único pseudo-dividendo RTX de USD 40.58, sin split. El
ratio 2.3348 de legacy RTN queda explícitamente fuera. El rerun completo de SPY,
Momentum y Equal Weight finaliza sin otro blocker; Phase 2 queda validada para
el alcance real actual.

## Phase 3 — Baseline predictive models

**Objetivo:** establecer benchmarks simples para regresión, clasificación y ranking.  
**Entregables:** splits temporales, pipelines, métricas, versionado y baselines lineal/logístico antes de modelos complejos.  
**Finalización aproximada:** evaluación out-of-sample reproducible y comparación contra baselines ingenuos.

### Phase 3A — Supervised Dataset + Temporal Validation

**Status:** complete

Implementa targets simétricos de regression, classification y ranking para 5,
10 y 20 sesiones, con `target_end_date` exacta y schema
`corporate-action-safe-target-v3`. `TargetSpec` resuelve label y elegibilidad; el
join Feature Store + Target Store es one-to-one y construye `X` solo desde la
allowlist canónica. El fixed holdout oficial separa fechas completas, purga por
`target_end_date < next_split_start` y soporta embargo XNYS configurable con
default cero. Se incorporan manifest reproducible, contratos de métricas y schema
de predicción OOS desacoplado de portfolio/risk/execution. No se entrenan modelos.

### Phase 3A.1 — Target Store v3 real-data rebuild

**Status:** complete

El Target Store real fue reconstruido localmente para los 101 activos de
`development_fixed`, sin descargas, con schema
`corporate-action-safe-target-v3`. La validación exhaustiva comprobó 405.704
filas, targets/end dates XNYS/positive/ranking simétricos, contaminación por
acciones corporativas, manifests v3 y smoke tests supervisados sin usar test
para selección. SPY permanece exclusivamente como benchmark y se retiraron sus
filas target v2 obsoletas. El reporte reproducible vive en
`data/reports/phase3a1_target_validation.json`.

### Phase 3B — Predictive baselines

**Status:** complete for TRAIN/VALIDATION model selection; TEST remains sealed

`quantitative-baseline-v1` fija 52 features cuantitativas y
`baseline-standard-v1` aplica log1p de liquidez, imputación mediana y scaling
ajustados solo en TRAIN. Se compararon baselines ingenuos, OLS, Ridge y Logistic
L2 para 5/10/20d, además de momentum, predicted-return ranking y regresión
directa de rank. La selección utilizó exclusivamente VALIDATION 2019–2021; los
69 experimentos y sus predicciones/coeficientes/manifests viven en
`data/reports/models/phase3b`. TEST 2022+ permanece sellado (`test_used=false`).
No se eligió un horizonte final ni se inició evaluación final, portfolio o
Phase 3C.

### Phase 3C — Nonlinear Predictive Models

**Status:** complete for TRAIN/VALIDATION nonlinear model selection; TEST remains sealed

Se compararon Random Forest, XGBoost y LightGBM con tres perfiles congelados por
familia sobre las mismas 52 features, targets y split de Phase 3B.
`tree-preprocessing-v1` aplica `log1p` de liquidez e imputación por mediana de
TRAIN, sin scaling ni selección de features. La corrida real produjo 81 fits y
108 evaluaciones, incluidos 27 rankings derivados sin reentrenamiento, además
de importancia nativa y por permutación para 27 ganadores family/task/horizon.
Regression y ranking mejoraron materialmente los mean IC de 3B en 5/10/20d;
classification no mejoró ROC-AUC en ningún horizonte. 20d conserva la señal
predictiva más fuerte, pero no se declaró modelo final ni se hizo portfolio
backtest. Los artefactos viven en `data/reports/models/phase3c`; TEST 2022+
permanece sellado (`test_used=false`). Esta subfase no abrió TEST ni ejecutó
portfolio/backtesting.

### Phase 3D — Walk-Forward Robustness

**Status:** complete — final development candidate frozen; TEST remains sealed

Phase 3D.1–3D.4 implementan infraestructura expanding-window causal, purge
dinámico por `target_end_date_20d`, comparación de frecuencias monthly,
quarterly, semiannual y annual, control Ridge alpha=100 frente a RF-Small 20d y
diagnóstico de model age. El período 2016–2021 es pseudo-out-of-sample
walk-forward, no un holdout externo; los labels que cruzan 2022 se excluyen.

La corrida real produjo 228 retrainings y 1.155.952 predicciones. Annual fue la
frecuencia raw-best y operacional para ambos modelos. RF-Small mantuvo una
ventaja material y más estable sobre Ridge bajo las cuatro frecuencias. Los
buckets de model age fueron no monotónicos y no justifican retraining mensual.
Los artefactos viven en `data/reports/models/phase3d`. Permanece pendiente la
selección final del candidato de desarrollo.

Phase 3D.5 mantuvo congelados RF-Small, las 52 features, preprocessing y
frecuencia annual, variando únicamente la ventana TRAIN. En 18 fits reales,
expanding obtuvo mean Rank IC 0.063825 frente a 0.061038 para trailing-8y y
0.058946 para trailing-5y; reprodujo exactamente el artifact previo y fue tanto
raw-best como seleccionada bajo tolerancia 0.003. No hay evidencia material y
estable de concept drift que justifique eliminar historia antigua. Los nuevos
artefactos viven en `data/reports/models/phase3d/window_sensitivity`. TEST 2022+
sigue sellado; no se implementaron ablations, candidato final ni Phase 3E.

Phase 3D.6 ejecutó 66 fits RF-Small annual/expanding para `full` y diez
ablations leave-one-family-out. `full` reprodujo exactamente las cuatro métricas
de 3D.5. Volatilidad fue el único strong contributor y liquidez/volumen resultó
moderadamente útil. Ninguna familia cumplió las condiciones completas de
`harmful_candidate`; por tanto no se justifica 3D.6.1 y el candidato oficial de
52 features permanece intacto rumbo a 3D.7. Los artefactos están en
`data/reports/models/phase3d/feature_ablations`. TEST continúa sellado y no se
inició selección final ni Phase 3E.

Phase 3D.7 consolidó exclusivamente evidencia persistida de 3B–3D.6 y congeló
`development-candidate-v1`: regression `target_return_20d`, RF-Small,
`quantitative-baseline-v1` completo, `tree-preprocessing-v1`, retraining annual
y ventana expanding desde 2010-01-04. Los 50 checks de identidad, schemas,
features y reproducción cruzada pasaron; el fingerprint es
`65bbec61f8fda0df24097267b777c882fec4410cecbeb89ff909622a1f8ef467`.
El candidato está `selected_for_final_holdout_evaluation`, no production-ready
ni aprobado para trading. TEST no fue abierto ni se entrenó todavía un modelo
final 2010–2021. Phase 3 continúa incompleta: cualquier evaluación holdout exige
autorización explícita y una fase posterior.

## Phase 4 — News Agent

**Objetivo:** convertir noticias point-in-time en análisis explicable y features estructuradas.  
**Entregables:** fuente, deduplicación/cache, scoring, citas, router y costos.  
**Finalización aproximada:** resultados validados, trazables y sin acceso a ejecución.

## Phase 5 — Analyst + Earnings Agents

**Objetivo:** incorporar cambios de consenso y análisis pre/post earnings.  
**Entregables:** datos de analistas, revisiones, calendarios/resultados, modos PRE/POST y features correspondientes.  
**Finalización aproximada:** timestamps auditables y evaluación incremental sobre el baseline.

## Phase 6 — Fundamental + Macro + Event Agents

**Objetivo:** añadir calidad/valoración, regímenes globales y riesgos de eventos.  
**Entregables:** fuentes point-in-time, scores separados, regímenes y flags de eventos.  
**Finalización aproximada:** features estables, documentadas y evaluadas sin mezclar análisis con órdenes.

## Phase 7 — Portfolio optimization + Risk Manager

**Objetivo:** transformar forecasts en propuestas long-only y aplicar autoridad de riesgo.  
**Entregables:** objetivo retorno/riesgo/costo, restricciones, estado de cartera y reglas completas de APPROVE/REDUCE/BLOCK.  
**Finalización aproximada:** ninguna propuesta puede llegar a ejecución sin decisión de riesgo testeada.

## Phase 8 — Paper trading

**Objetivo:** operar el pipeline completo con dinero simulado.  
**Entregables:** adaptador paper, scheduler, reconciliación, monitoreo y auditoría.  
**Finalización aproximada:** operación estable durante un período acordado, sin órdenes reales.

## Phase 9 — Supervised live trading

**Objetivo:** permitir ejecución real con aprobación humana explícita.  
**Entregables:** integración segura con broker, gestión de secrets, controles operacionales, kill switch y aprobación.  
**Finalización aproximada:** revisión de seguridad/riesgo y trazabilidad completa con exposición limitada.

## Phase 10 — Potential automated execution

**Objetivo:** evaluar ejecución automática bajo límites estrictos.  
**Entregables:** gobernanza, monitoreo, alertas, fail-safe, rollback y aprobación operacional formal.  
**Finalización aproximada:** solo tras evidencia suficiente de fases anteriores y autorización explícita; puede decidirse no implementarla.

## Expansión futura — Crypto

**Objetivo:** explorar crypto sin contaminar supuestos de equities.  
**Entregables:** universo, calendario 24/7, datos, riesgo y modelos predictivos separados.  
**Finalización aproximada:** arquitectura y validación específicas; no reutilizar modelos de equities sin evidencia.
