# ADR-007: Corporate actions and price adjustment

## Status

Accepted

Point-in-time use of this decision is refined by [ADR-008](ADR-008-point-in-time-split-normalization.md).

## Context

Raw prices son necesarios para reconstruir fills y eventos reales, pero splits crean discontinuidades falsas para features. Los precios total-return del proveedor pueden mezclar dividendos y depender de una metodología externa que no controlamos.

## Decision

Persistir por separado OHLCV raw y corporate actions. Usar la convención interna `split_factor = acciones nuevas por acción antigua`, donde 2.0 es 2:1 y 0.5 es un reverse split 1:2. La acción en fecha D modifica solo observaciones anteriores a D: precios históricos se dividen y volumen se multiplica por el producto de factores futuros.

Construir una serie processed ajustada solo por splits. Mantener dividends como cash flows independientes; no incorporarlos a raw, fills ni split-adjusted. Conservar valores `adj*` del proveedor en raw cuando existan, pero no depender exclusivamente de ellos.

## Consequences

Raw conserva fidelidad para auditoría y ejecución simulada. Un nuevo split exige recalcular retrospectivamente la serie latest-basis del ticker. Esa reconstrucción retrospectiva no implica que el dataset sea point-in-time safe; ADR-008 define la vista usada para decisiones. El backtester futuro deberá aplicar dividendos explícitamente y versionar cualquier cambio de metodología.
