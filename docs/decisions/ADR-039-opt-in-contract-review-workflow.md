# ADR-039 — Flujo operativo contractual offline opt-in

## Estado y alcance

Implementado por instrucción del propietario para simplificar las cinco revisiones
restantes. No autoriza abrirlas, generar juicios, aprobarlas ni cambiar fases oficiales.

## Decisión

Añadir un CLI de orquestación que reutiliza los contratos de ADR-038, el adaptador
de lectura y el reloj prospectivo. Los formularios v2, sesiones v1, autorizaciones
de apertura v1 y decisiones del propietario v1 no cambian. `Submission` es solo
un sobre de transporte que reutiliza los tipos de mappings/outcomes existentes,
no un contrato económico nuevo. Los recibos administrativos no adjudican hechos.

Cada nuevo caso usa un workspace independiente, generado desde el último
manifiesto ya validado. Solo el caso elegido tiene copias operativas nuevas;
los demás conservan referencias a sus formularios originales, sin escrituras.
El origen queda fijado por hash. Preparar materiales no reserva tiempo ni abre
una revisión. Una apertura válida tampoco inicia el reloj: necesita otra acción
real y prospectiva del operador.

El reloj acepta el parámetro interno opt-in `allow_completed_other_cases=True`
solo cuando lo invoca el nuevo flujo. Admite otros casos `completed` o `unfilled`,
nunca otro `in_progress`. El valor predeterminado y CLI histórico siguen
exigiendo todos los otros casos `unfilled`. No cambian validadores semánticos,
intervalos, retención o criterios del formulario contractual.

Se importan todos los fact_id juntos como borrador, sin aprobarlos. Se validan
inventario, versiones, evidencias/factual completo y límites de incertidumbre.
Tras detener prospectivamente la sesión y contar con mapping y owner_review
registrados, se calcula el fingerprint oficial sobre una proyección final en
memoria. La aprobación de contenido exige una decisión real aportada por el
propietario; se registra sin completar el formulario. El cierre necesita además
una autorización explícita separada con identidad, fuente y ese fingerprint.
Ninguna opción reconstruye fechas, emite aprobaciones o imputa actividad humana.

## Consecuencias y límites

Se preservan los inputs versionados y recibos con backups antes/después y hashes.
Ante persistencia incompleta, archivos alterados o eventos huérfanos se bloquea
el flujo; no se reparan ni reintentan operaciones automáticamente. No se ofrece
un mecanismo de recuperación silenciosa. Uso secuencial por un operador, sin
concurrencia; para continuar hay que seleccionar el workspace más reciente ya
cerrado, no bifurcar desde un manifiesto viejo.

El reloj local sigue sin certificar atención humana ni elegibilidad estadística.
Sesiones y su metadata temporal mantienen el límite de 90 días desde el fin;
no se exportan referencias de aprobación de sesiones expiradas. No se consulta
ningún proveedor, key o respuesta de inferencia. La revisión factual sin tiempo
no se rehabilita para estadísticas. La primera aprobación contractual y todo su
historial quedan intactos.

Guía operativa: [flujo simplificado](../phase4c2-contract-workflow-v1.md).
