# ADR-008: Point-in-time split normalization

## Status

Accepted

## Context

ADR-007 definió una serie histórica ajustada por splits conocidos. Recalcular toda la historia a la base accionaria más reciente es útil para visualización, pero aplica retrospectivamente splits futuros. Aunque muchas features relativas son invariantes a esa escala, ATR, MACD y otras variables nominales pueden cambiar y producir look-ahead en una decisión histórica.

## Decision

Separar dos representaciones:

1. **Latest-basis:** artefacto persisted en `processed/market/split_adjusted_latest`, reconstruido con todos los splits conocidos actualmente. Se identifica mediante `normalization_basis=latest` y no se considera automáticamente point-in-time safe.
2. **As-of:** vista construida para una decisión concreta. Incluye solo barras con `trading_date <= decision_date` y `available_at <= decision_time`. Un split participa únicamente si `effective_date <= decision_date` y `available_at <= decision_time`. Acciones sin disponibilidad conocida se excluyen conservadoramente.

Para cada barra histórica elegible, precios se dividen y volumen se multiplica por el producto de los splits elegibles posteriores a la barra. Dividendos continúan excluidos de ambos ajustes.

Phase 1B deberá construir features desde las columnas `split_adjusted_open`, `split_adjusted_high`, `split_adjusted_low`, `split_adjusted_close` y `split_adjusted_volume` de la vista as-of, nunca desde `adj*` de Tiingo ni ciegamente desde latest-basis.

## Consequences

Una misma barra puede tener distinta escala al consultarse en decisiones separadas, pero cada ventana permanece internamente comparable con la base conocida en ese momento. Los backtests deben construir o consultar la vista as-of para cada decision time. Latest-basis sigue disponible para exploración y auditoría, con etiquetado explícito para impedir su uso accidental.
