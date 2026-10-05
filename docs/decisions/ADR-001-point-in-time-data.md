# ADR-001: Point-in-time data

## Status

Accepted

## Context

Un backtest puede parecer rentable si utiliza publicaciones, revisiones o eventos que aún no estaban disponibles en el momento simulado. La fecha económica de un dato, su publicación, su disponibilidad para el sistema y su ingestión son hechos diferentes.

## Decision

Los registros externos conservarán, cuando corresponda, `observed_at`, `published_at`, `available_at` e `ingested_at`. Solo podrán participar en una decisión si `available_at <= decision_time`. Ingestión, joins, feature building y backtesting deben aplicar y probar esta regla.

## Consequences

Los datasets requieren más metadatos y validaciones temporales. No se puede reconstruir historia usando simplemente la versión más reciente. A cambio, los resultados son reproducibles y se reduce explícitamente el look-ahead bias.
