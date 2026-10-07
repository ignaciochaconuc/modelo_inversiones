# ADR-011: Semántica temporal y corporate actions del backtester

## Estado

Aceptado.

## Contexto

Un backtest diario puede introducir look-ahead si dimensiona con el open futuro,
rellena una apertura ausente o mezcla precios raw y ajustados. El orden de splits,
fills, valoración y dividendos también cambia el resultado económico. La fuente
actual identifica `effective_date`, pero no garantiza payment date ni el precio
real de liquidación de fracciones.

## Decisión

El motor recibe allocations externas por fecha y permanece independiente de la
estrategia. Recorre sesiones XNYS. Para cada sesión D ejecuta, en orden:

1. corporate actions complejas y splits efectivos antes de la apertura;
2. captura de cantidades con derecho a dividendos;
3. órdenes de la decisión anterior en el raw open;
4. mark-to-market al raw close;
5. dividendos de D después del cierre;
6. snapshot final disponible a las 20:15 America/New_York;
7. conversión de la allocation de D en órdenes para `next_session(D)`.

El raw close de D dimensiona las órdenes y debe satisfacer
`available_at <= decision_time`. El raw open siguiente es la única base del fill.
Un open ausente produce `UNFILLED/missing_execution_open` sin rollover. Un close
ausente puede reutilizar el último precio válido únicamente para valoración y se
marca stale; sin precio previo, el run falla.

Las ventas se ejecutan antes que las compras y en orden de ticker. Una compra se
reduce al máximo financiable, respetando la política fraccional, sin cash negativo
ni leverage. Slippage modifica el precio en contra de la operación y la comisión
se carga separadamente.

Los splits usan `new shares / old shares`. Con fracciones deshabilitadas se
conservan shares enteras y se acredita cash-in-lieu usando el raw open post-split
como proxy auditable; sin ese open el run falla. Tiingo EOD `divCash` se
interpreta como ex-date. El entitlement se captura después de aplicar los splits
efectivos de esa fecha y antes de los fills de apertura: una venta en ex-date
conserva el derecho y una compra en ex-date no lo adquiere. El cash se acredita
después del cierre como proxy conservador mientras payment date no forme parte
del pipeline, por lo que no financia fills de esa apertura. Un evento complejo
marcado como no ajustable sobre una posición mantenida invalida el run con ticker,
fecha y event ID; no se aplican heurísticas.

P&L usa costo promedio, no FIFO. Allocation, order y fill se enlazan mediante IDs
hash deterministas. `risk_decision_id` es solo un vínculo futuro; este simulador
no altera la autoridad del Risk Manager ni crea una ruta de ejecución real.

## Consecuencias

- Dos ejecuciones con los mismos inputs producen resultados e IDs equivalentes.
- Gaps, costos, redondeo y faltantes pueden alejar los pesos finales del target.
- Cash-in-lieu y timing de dividendos son aproximaciones declaradas hasta disponer
  de datos más precisos.
- Un corporate action complejo puede impedir completar un backtest, priorizando
  integridad económica sobre continuidad artificial.
