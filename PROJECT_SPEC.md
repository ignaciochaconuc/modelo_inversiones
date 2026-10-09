# Especificación funcional actual

## Objetivo y alcance

El proyecto establece la base de un sistema multiagente para análisis y gestión táctica de inversiones de corto/medio plazo. Combinará información cuantitativa y análisis de IA con predicción, construcción de cartera, control de riesgo, backtesting y ejecución progresivamente habilitada.

La versión 1 cubre aproximadamente 100 acciones líquidas de Estados Unidos. Opera conceptualmente con frecuencia diaria, horizonte predictivo principal de 10 días bursátiles y estrategia Long + Cash. Crypto no pertenece a V1; una expansión futura deberá mantener datos y modelos predictivos separados de equities.

## Convenciones operativas

- Decisión: después del cierre del mercado estadounidense.
- Ejecución simulada: apertura de la siguiente sesión bursátil.
- Posiciones máximas: 10–15; la configuración actual fija 15.
- Peso máximo por activo: 10%.
- Exposición máxima: 100%.
- Short selling: no permitido.
- Leverage: no permitido.
- Cash: permitido.
- Benchmark: SPY.

Los valores configurables viven en `config/settings.yaml`, `config/universe.yaml` y `config/risk_limits.yaml`.

## Datos y Feature Store

Toda observación externa puede conservar `observed_at`, `published_at`, `available_at` e `ingested_at`. Para una decisión solo son elegibles registros cuyo `available_at <= decision_time`. Esta condición es obligatoria en datasets históricos y backtests.

El Feature Store representa una fila por `ticker + decision_date`. Su almacenamiento inicial es Parquet y su capa de consulta DuckDB; no se usa PostgreSQL. `FeatureRow` define identificación, variables cuantitativas y estructuradas de agentes, categorías de régimen y targets opcionales.

Phase 1B añade `decision_time` explícito, fijado inicialmente a las 20:15 America/New_York. Los campos de mercado se llaman `split_adjusted_open/high/low/close/volume` y siempre representan la vista interna as-of; se eliminan nombres ambiguos asociados a `adjClose` del proveedor. Sector, industry y market cap permanecen NULL hasta disponer de fuentes históricas point-in-time.

El histórico raw comienza conceptualmente en 2009-01-01 y las filas de features en 2010-01-01, dejando warm-up real sin backfill. Las posiciones históricas usan `close / max_252 - 1`, `close / min_252 - 1` y percentil trailing con rank promedio para ties. `percentile_volatility_252d` posiciona la volatilidad de 20 sesiones actual dentro de 252 observaciones válidas de esa serie.

La elegibilidad informa disponibilidad de 20, 60, 120 y 252 observaciones. `history_count` cuenta para cada decisión todas las barras históricas válidas que ya estaban disponibles; no se reinicia por segmentos ni splits. `model_eligible` exige 252 sesiones previas —253 observaciones incluyendo la actual— y features esenciales completas, incluido benchmark. No constituye una señal de estrategia.

Las familias de features son: identificación; OHLCV; retornos; momentum; riesgo/volatilidad; tendencia técnica; volumen/liquidez; posición histórica; mercado/sector; News; Analyst; Earnings; Fundamental; Macro; y Event. La lista canónica está en `src/investment_system/data/schemas/features.py`.

### Market data de Phase 1A

Tiingo EOD es el proveedor principal inicial. Su adapter traduce nombres externos a `MarketBar`; ninguna otra capa conoce campos propios de Tiingo. La API key se obtiene de `TIINGO_API_KEY` y los tests usan transporte simulado.

Se conservan por separado OHLCV raw, corporate actions normalizadas y OHLCV ajustado exclusivamente por splits. La convención interna es `split_factor = acciones nuevas / acciones antiguas`: 2.0 representa 2:1 y 0.5 un reverse split 1:2. La fecha efectiva ya contiene precios post-split; solo las filas anteriores se ajustan. Precios históricos se dividen por el producto de splits aplicables y volumen se multiplica. Los dividendos permanecen como cash flows y no alteran precios ni volumen.

Hay dos representaciones: `split_adjusted_latest` persiste toda la historia en la base más reciente y no es point-in-time safe por sí sola; `build_split_adjusted_series_as_of()` construye la ventana válida para una decisión usando únicamente barras y acciones disponibles. Phase 1B deberá alimentar features con `split_adjusted_open/high/low/close/volume` provenientes de la vista as-of, nunca con `adj*` del proveedor.

Features como retornos, momentum, RSI, distancias relativas y ratios de volumen son invariantes ante un reescalado uniforme. ATR, MACD, sus señales y dollar volume son nominales. Se conservan ATR/MACD originales para interpretabilidad y se añaden `atr_pct`, `macd_pct`, `macd_signal_pct` y `macd_histogram_pct` para inputs invariantes a escala.

Como Tiingo EOD no aporta un timestamp histórico exacto de publicación por barra, `available_at` se deriva de `trading_date` y `providers.tiingo.assumed_eod_available_time` (20:00 America/New_York inicialmente). Es una hipótesis conservadora y configurable, distinta de `observed_at` (16:00 inicialmente). El cutoff conceptual de decisión es 20:15.

El upsert usa `ticker + trading_date + provider` para barras y `ticker + effective_date + action_type + provider` para acciones. Un overlap configurable reemplaza correcciones y la serie split-adjusted completa se reconstruye. El calendario XNYS proviene de `exchange-calendars`. El universo fijo de desarrollo no es point-in-time e introduce survivorship bias.

## Targets

- `target_return_5d`
- `target_return_10d`
- `target_return_20d`
- `target_positive_5d`
- `target_positive_10d`
- `target_positive_20d`
- `target_rank_5d`
- `target_rank_10d`
- `target_rank_20d`

El horizonte de referencia es 10 sesiones, pero regression, classification y ranking soportan simétricamente 5, 10 y 20. Los retornos son los targets primarios; positive y rank se derivan del retorno del mismo horizonte. Targets y features permanecen disjuntos y los targets no pueden participar en una decisión.

Targets se guardan en un dataset físico separado y usan una base latest-basis exclusivamente para que splits futuros dentro del horizonte no creen retornos falsos. Cada horizonte persiste su `target_end_date_hd`, la sesión bursátil exacta obtenida del calendario; si falta la barra de esa sesión, el label queda NULL y no salta a otra observación. Son price returns y no incorporan dividendos. Cada rank usa rank cross-sectional promedio del retorno correspondiente, normalizado a [0,1], y queda NULL si hay menos de 20 activos training-eligible en la fecha.

Phase 1D.1 añade integridad conservadora para corporate actions complejas. Los
eventos se persisten por separado y nunca modifican raw. Features contienen
flags point-in-time; labels contienen flags por horizonte cuando el futuro cruza
un evento excluido. El ranking ignora esos labels. `training_eligible` se calcula
solo al unir features y targets y permanece separado de `model_eligible`.

## Agentes

- **NewsAgent:** impacto, novedad, polaridad, tipo y horizonte de noticias.
- **AnalystAgent:** consenso, cambios, upgrades/downgrades, precios objetivo y revisiones; prioriza el cambio sobre el nivel absoluto.
- **EarningsAgent:** modos PRE_EARNINGS y POST_EARNINGS para expectativas, sorpresas, guidance, márgenes y sentiment.
- **FundamentalAgent:** separa crecimiento, rentabilidad, balance, valoración y momentum fundamental.
- **MacroAgent:** produce contexto global y regímenes de growth, inflation, rates, liquidity y risk.
- **EventAgent:** mide proximidad, impacto e incertidumbre de eventos; no recomienda compras o ventas.

Cada agente entrega simultáneamente una explicación humana y features estructuradas, junto con confianza, fuentes y timestamps. Actualmente todos son stubs sin búsquedas ni APIs.

## LLM y control de costos

`LLMRouter` selecciona proveedor/modelo por agente y tarea, usando `config/models.yaml`. Los clientes de OpenAI y Ollama son stubs deliberados. El pricing es configurable y no incluye precios reales hardcodeados.

Cada llamada puede registrar tokens, cache, costo estimado, latencia, estado, agente, tarea, ticker, análisis y trade. Se contemplan agregaciones diarias, mensuales, por agente, ticker, análisis y trade.

## Modelos previstos

`TargetSpec` selecciona task y horizonte sin interpretar nombres manualmente. Phase 3B implementa baselines simples: predictores ingenuos, OLS, Ridge, Logistic L2, momentum y scoring de ranking derivado de regresiones lineales. Phase 3C añade perfiles congelados de Random Forest, XGBoost y LightGBM para regresión, clasificación y rank directo, además de ranking derivado de predicted return. Phase 3D.1–3D.4 compara RF-Small 20d y Ridge alpha=100 mediante expanding-window causal y frecuencias congeladas, con purge dinámico antes de cada activación. El período 2016–2021 es pseudo-out-of-sample y excluye labels que alcanzan TEST. Modelos finales, sensibilidad de ventana, ablations, evaluación sellada e inferencia integrada permanecen sin implementar.

## Cartera y riesgo

El optimizador futuro buscará maximizar retorno esperado menos penalizaciones por riesgo y costos de transacción, respetando Long + Cash, máximo de posiciones, peso por activo y ausencia de leverage. Actualmente solo existen modelos de entrada/salida y una interfaz.

El Risk Manager es una autoridad separada que puede `APPROVE`, `REDUCE` o `BLOCK`. Las reglas previstas cubren tamaño y número de posiciones, exposición, drawdown, event risk, pérdida diaria, volatilidad y cash. La implementación actual aplica reglas básicas de long-only, número de posiciones, peso y exposición; las demás permanecen configuradas para desarrollo posterior.

## Backtesting, paper trading y ejecución

Phase 2A.2 reproduce decisiones point-in-time después del cierre y fills en la
apertura siguiente. `HistoricalBacktestEngine` recibe `TargetAllocation` por
fecha, genera cantidades con el raw close disponible a las 20:15 ET y ejecuta
solo en el raw open de `next_session`. No contiene estrategia. Las ventas se
procesan antes que las compras y una compra se reduce si gap, slippage o comisión
superan el cash disponible; nunca se usa leverage.

Cada sesión procesa corporate actions complejas y splits antes del open, captura
el entitlement de dividendos, ejecuta fills pendientes en el open, valora al
close, acredita dividendos después del close y produce un snapshot final. Un open
ausente produce una ejecución `UNFILLED` con `missing_execution_open` y no se
arrastra. Para valoración, un close ausente puede usar el precio válido anterior
con marca stale; sin precio previo el run falla. Todos los precios de órdenes,
fills y snapshots son raw, nunca `adjusted_*`.

Splits con fracciones deshabilitadas conservan la parte entera y liquidan la
fracción como cash-in-lieu al raw open post-split, documentado como proxy. Tiingo
EOD `divCash` se interpreta como ex-date. La cantidad elegible se captura después
de splits efectivos y antes de fills de apertura; por eso ventas en ex-date
conservan el derecho y compras en ex-date no lo adquieren. El cash se acredita
tras el cierre como proxy conservador mientras payment date no esté disponible.
Una acción corporativa compleja no modelable sobre una posición mantenida
invalida el run. Allocation, order y fill poseen IDs deterministas enlazados.

Phase 2B.1 agrega treatments económicos revisados, tipados y versionados sin
relajar ese bloqueo por defecto. En spin-offs con due bills, `record_date` es la
fecha legal y `entitlement_date` observa la posición regular-way inmediatamente
antes de distribución, porque el engine no simula mercados ex-distribution ni
when-issued. MDLZ 2012 distribuye 1 KRFT por cada 3 acciones mantenidas al cierre
de 2012-10-01; KRFT es auxiliar, no invertible. ABT distribuye 1 ABBV por acción
mantenida al cierre de 2012-12-31 antes de la distribución de 2013-01-01; ABBV
puede ser simultáneamente security recibido y miembro normal de
`development_fixed`. Ambos securities distribuidos conservan basis no asignado
hasta una futura convención fiscal. TMUS 2013 aplica factor 0.5
y acredita USD 4.0491 por acción pre-split como `RECAPITALIZATION_CASH`. Los
treatments consumen las acciones genéricas equivalentes del proveedor para no
duplicarlas, emiten `CorporateActionTransformation`, usan solo raw prices para
valorar/ejecutar y nunca modifican la historia de precios. NAV sigue siendo la
fuente de performance; si falta basis, el total de trading P&L queda explícitamente
no disponible. Datos ausentes de un security distribuido invalidan el run.

Phase 2B.1.2 modela la distribución Google 2014 como la misma economía genérica
`parent remains + distributed security`: ownership regular-way de GOOGL se
observa al cierre de 2014-04-02 y genera 1 GOOG Class C por GOOGL Class A antes
del open siguiente. La lineage de Tiingo está restated según la instrucción de
Nasdaq: GOOGL contiene Class A histórica y GOOG comienza con Class C when-issued
el 2014-03-27. El pseudo-dividendo GOOGL se consume; no existe split del
proveedor. Ambas clases siguen siendo activos independientes del universo.

Phase 2B.1.3 generaliza esa economía a una distribución de uno o más securities
en un solo evento revisado. La historia Tiingo de `RTX` conserva el lineage de
UTC y no genera una venta/compra por rename. La posición padre permanece 1:1 y,
según ownership regular-way al cierre de 2020-04-02, recibe 1 CARR y 0.5 OTIS
antes del open de 2020-04-03. CARR y OTIS son auxiliares no invertibles, con
basis no asignado; el único pseudo-dividendo RTX de USD 40.58 se consume y no
hay split. El ratio 2.3348 corresponde exclusivamente a antiguos accionistas
RTN y no se aplica a este lineage.

El accounting usa costo promedio y excluye comisiones del costo unitario: el
`fill_price` determina average cost y la comisión reduce cash/NAV. Una venta
realiza `(fill_price - average_cost) × quantity - commission`; el P&L no realizado
es `(market_price - average_cost) × quantity`. No se implementan lotes fiscales
ni FIFO.

Phase 2A.3 transforma `BacktestResult` en `BacktestMetrics` sin modificar el
engine. NAV es la fuente de verdad de performance. CAGR usa días calendario y
365.25; volatilidad, Sharpe, Sortino y turnover anualizado usan 252 sesiones.
Sharpe asume risk-free 0. Sortino usa MAR 0 y la desviación downside RMS de
`min(return, 0)`. Maximum drawdown se reporta como retorno no positivo e incluye
peak, trough y recovery cuando existe.

Turnover diario es gross notional efectivamente ejecutado en la sesión dividido
por el NAV final de esa sesión; órdenes unfilled no participan. Comisiones y
slippage se reportan para auditoría, pero no se vuelven a descontar del NAV.
Dividendos y cash-in-lieu permanecen separados del trading P&L.

El benchmark de reporting simula SPY con el mismo capital y costos: decisión al
cierre de la primera sesión, compra al raw open siguiente, splits explícitos y
dividend entitlement post-split/pre-open. El cash se acredita post-close y se
reinvierte causalmente en el next open. No usa precios ajustados. Esta utilidad
interna permanece separada de `SpyBuyAndHoldStrategy`, aunque ambas comparten el
mismo constructor causal de allocations para evitar divergencias económicas.

Phase 2B implementa tres generadores deterministas de `TargetAllocation`:

- SPY buy-and-hold: 100% SPY desde la primera decisión, con reinversión causal de
  dividendos en la apertura siguiente y la misma economía que el benchmark.
- Equal-weight: rebalanceo diario entre todas las filas `model_eligible` del
  `development_fixed`, excluyendo SPY. No aplica max 15 posiciones ni 10% porque
  representa el universo naïve diversificado.
- Momentum: rebalanceo diario top 10 por `momentum_20d` descendente, desempate por
  ticker ascendente, 10% por activo y cash no redistribuido cuando hay menos de 10.

Las estrategias cross-sectional leen solo features de su `decision_date` y
validan su `decision_time`; no cargan targets, no imputan momentum faltante y no
reconstruyen features desde raw. El runner persiste reportes completos o fallos
diagnósticos, pero nunca presenta un run truncado como exitoso. Phase 2B no es
ML, no usa optimizer ni integra Risk Manager.

Paper trading corresponde a Phase 8. La ejecución real supervisada y una eventual ejecución automática corresponden a Phases 9 y 10. No existe conexión con brokers ni autorización para órdenes reales.

## Auditoría

Toda decisión futura debe poder reconstruirse mediante features usadas, versión del modelo, predicción, asignación propuesta, decisión de riesgo, acción final, outputs de agentes, fuentes y costo. `DecisionAuditRecord` y `AuditLogger` proporcionan el contrato y persistencia JSONL inicial.
