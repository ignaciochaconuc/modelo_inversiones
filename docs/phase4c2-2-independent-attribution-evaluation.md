# Phase 4C.2.2 — Preparación de revisión externa de atribución

Estado: **`prepared_pending_content_rights_review`**, conforme a la instrucción
posterior del propietario. No equivale al cierre técnico de 4C.2 ni a haber
realizado una evaluación. La implementación conserva
`implemented_pending_external_review`; 4C.3 permanece `not_started`.

## Autoridad y alcance

El propietario no autoriza compartir titulares/resúmenes Finnhub con revisores
externos hasta verificar derechos. El contenido sigue en su almacenamiento local
original: no se copia, exporta, publica ni incorpora a paquetes de revisión.
Solo se prepara selección real por identificadores, hashes y tiempos sanitizados.
Los instrumentos se prueban con textos ficticios nuevos. No se ejecuta inferencia,
se consulta un proveedor, se carga `.env` o se usa TEST oficial Phase 3.

Se conserva byte a byte el protocolo congelado
`docs/phase4c1-evaluation.md`; este documento es un instrumento suplementario,
no su reemplazo. Código de producción, contratos, prompts, configuración,
algoritmos Phase 4B y evidencia histórica no se modifican. Las únicas adiciones
son documentación, corpus/instrumentos de evaluación y pruebas mecánicas offline.

## Muestras y selección

| Ámbito | Panel sintético nuevo | Candidatos reales, solo metadatos |
| --- | ---: | ---: |
| Adquisiciones | 3 | 3 |
| Contratos | 3 | 3 |
| Alianzas | 3 | 3 |
| Productos | 3 | 3 |
| Plataformas | 3 | 3 |
| Subsidiarias | 3 | 0 |
| Competencia | 3 | 3 |
| Regulación | 3 | 3 |
| Menciones incidentales | 3 | 3 |
| Ambigüedad/múltiples eventos/estado/impacto | 5 | no estrato adicional |
| **Total** | **32** | **24** |

Sintéticos: nuevas empresas ficticias, formas pasivas, transacciones pendientes
y completadas, negaciones, shortlist sin adjudicación, contratos con dirección
no especificada, producto sin fabricante, licencia pagada, subsidiaria/matriz,
competidores y comparadores, propuesta regulatoria, biografía, digest, varias
securities y una entrada de identidad conocida después del cutoff virtual.
Incluyen evidencia afirmativa y negativa, así como información insuficiente;
no se asignan todavía etiquetas de referencia ni tamaños de clases semánticas.
Autoría IA declarada; distintos de los tests sintéticos históricos y smokes.
Las pruebas nuevas inspeccionan integridad/formato, no adjudican sus respuestas.
Este panel no es un holdout real ni prueba de generalización.

Real: 905 revisiones locales; latest eligible por artículo al cutoff estricto
`2026-10-12T13:17:53Z`. Se excluyen 153 artículos lógicos usados en revisiones
4B/pilotos y los smokes, además de textos idénticos en otras revisiones/artículos.
Quedan 658 artículos elegibles. Se enriquecen por pistas léxicas independientes
de predicciones actuales, tres por estrato, pools raros primero y orden hash con
seed `attribution-independent-review-20261013-v1`. No se elige según aceptación
del intérprete ni se ejecuta clustering nuevo. Las pistas NO son etiquetas.
No hay candidatos léxicos de subsidiarias: no se promete cobertura real allí.
El manifiesto conserva pools, exclusiones y fingerprint de archivos usados para
detectar casos anteriormente inspeccionados, sin exportar sus contenidos.

Las revisiones son nuevas respecto de los casos de desarrollo revisados, no
nuevas descargas. La desunión verificable es por artículo lógico, revisión y
texto exacto; no certifica ausencia universal de paráfrasis o conocimiento previo.
No se considera inspeccionado todo el snapshot original, solo los casos/pilotos
efectivamente revisados. Las exclusiones quedan auditables.

## Separación, cegamiento y proveniencia

Artefactos bajo `evaluation/phase4c2_attribution_v1/prepared/`:

- `reviewer/blind_synthetic_evidence.json`: IDs opacos y evidencia ficticia;
  sin strata, predicciones, scores, versiones del modelo o reglas internas.
- `reviewer/identity_lookup.synthetic.json`: evidencia neutral ficticia para
  segunda pasada. No es configuración ni registry de producción.
- `references/human_a.template.json` y `human_b.template.json`: 32 formularios
  vacíos cada uno; cero referencias humanas realizadas.
- `references/ai_assisted.template.json`: estrato separado y vacío; nunca
  convertir asistencia de IA en referencia humana independiente.
- `system/system_outputs.template.json`: archivo independiente con 56 casos
  `not_run`, cero intentos, sin salidas inventadas ni costes supuestos cero.
- `operator/real_candidate_metadata.json`: 24 revisiones seleccionadas, hashes,
  disponibilidad/cutoff y estado de derechos; no textos, URLs, tags de ticker
  ni nombres de fuentes.
- `operator/synthetic_selection.json`, `alignment.template.json` y manifiesto:
  custodia, strata, alineación pendiente y hashes reproducibles.

El custodio entrega únicamente el paquete `reviewer/` y la guía del revisor,
más una plantilla individual. No entrega fuente de selección, manifiesto,
predicciones ni documentos de implementación. Cegamiento por separación de
paquetes/personas: no son controles criptográficos de acceso. No compartir
el repositorio completo con quien deba permanecer ciego.

Dos humanos ajenos al desarrollo anotan individualmente hechos e identidades
textuales; luego reciben evidencia neutral de securities. Declaran identidad,
tiempo real UTC-aware, asistencia, conflictos e independencia y acceso previo a
salidas. El custodio verifica esas declaraciones, conserva la evidencia de
atestación y sella los archivos con SHA-256. Desacuerdos se adjudican por un
tercero manteniendo versiones iniciales, incertidumbre y racionales. Referencias
asistidas por IA se archivan y analizan por separado; hoy ambos estratos están
vacíos. Autoría del corpus y asistencia del adjudicador son campos distintos.

Guardar referencias completadas, firmas y futuras respuestas restringidas bajo
`data/cache/news_attribution_review/`, ignorado por Git. No reemplazar plantillas
vacías ni evidencia congelada. Fijar retención y política de acceso antes de
recibir datos personales o respuestas; no prolongar TTL histórico de los smokes.

## Comparación reproducible, todavía no ejecutable con resultados reales

1. Verificar fingerprints y disjunción; aprobar criterios y plan externo antes
   de cualquier inferencia o exposición del modelo a estos casos.
2. Sellar referencias antes de revelar outputs. Registrar entidad/evento/rol/
   relación/ticker/impacto como dimensiones separadas, no un score agregado.
3. Las salidas reales de casos nuevos **no existen**: se prepara una plantilla,
   no predicciones simuladas atribuidas al sistema. Una futura ejecución requiere
   autorización distinta, configuración/capacidades/precios vigentes, presupuesto,
   retención, un plan congelado de intentos y uso del router existente. No cambiar
   contratos/prompts para este corpus. No realizarla con esta herramienta.
4. Exportar posteriormente los registros originales y consumidor tipado con
   fingerprints a un archivo independiente. Conservar `interpreted`, abstenciones,
   rechazos, errores de transporte, desconocidos y `not_run` por caso; no excluir
   intentos costosos/fallidos ni convertirlos en respuestas semánticas negativas.
5. Un custodio alinea manualmente acontecimientos/menciones de referencias y
   salidas mediante evidencia y IDs, conservando omisiones y extras como unidades
   explícitas. No hacer fuzzy matching, elegir silenciosamente coincidencias ni
   usar la lista del modelo para definir el denominador humano.
6. Completar `alignment.template.json`, fijando SHA-256 de los archivos de
   referencia y sistema. Cada unidad incluye `case_id`, `unit_id`, `dimension`,
   `reference_status`, `reference_value`, `system_value`, `system_outcome`,
   `reference_evidence`, `reviewer_id`, `reviewed_at`, `assistance`,
   `independence_attestation`, `has_seen_system_outputs`, `provenance_verified`.
   El custodio verifica la correspondencia con los archivos sellados y firma la
   alineación. El helper no certifica identidad humana, correspondencia semántica
   ni firmas: estas son tareas de custodia verificables, no booleans autodeclarados
   que deban aceptarse sin revisión.
7. `compare` produce conteos deterministas por dimensión/unidad, contabiliza
   inconclusos y todos los estados técnicos, y bloquea referencias concluyentes
   sin proveniencia declarada. No estima precision/recall poblacional, retornos
   ni generalización. Reportar además distribución **por caso** (los conteos de
   unidades no son denominadores de noticias), desacuerdo humano y cobertura.

Evidencia: IDs de campo y offsets Unicode half-open; fragmentos exactos mínimos.
Identidad corporativa no equivale a security ni participación; rol/evento no
equivale a impacto o exposición. Conservar categorías fact/inference/unknown,
anuncio versus cierre, negaciones, estados y PIT del protocolo original.
No mezclar paneles sintético, real, desarrollo, calibración o asistencia IA.

## Derechos: procedimiento obligatorio antes de incorporar noticias reales

No se ha autorizado un paquete real externo ni se proporciona aquí un exportador
de contenido Finnhub. El custodio deberá:

1. Obtener evidencia escrita de derechos/licencia aplicables a cada fuente y
   campo (proveedor agregador no implica autorización del editor), uso, destinatarios,
   presentación, copias, retención y redistribución.
2. Registrar authority/reviewer, documento verificable, tiempos de vigencia,
   jurisdicción/condiciones relevantes y decisión; recibir autorización explícita
   del propietario. No interpretar la presencia local como permiso de exportación.
3. Verificar disponibilidad/PIT, hash y licencia por revisión seleccionada.
   No ampliar una caducidad ni consultar/descargar fuentes para rellenar resúmenes.
4. Si se aprueba, crear una nueva versión de instrumento/paquete real restringido,
   mínimo texto necesario, IDs opacos, acceso controlado y expiración compatible
   con derechos. Distribuir solo evidencia, sin strata/predicciones/registry no
   neutral. Usar referencias separadas del panel ficticio y mantener originales.
5. Si se deniega, mantener metadatos o retirar casos documentadamente; no sustituir
   contenido real por paráfrasis presentadas como fuente original. Cualquier
   alternativa de fuente abierta requiere autorización y nuevo freeze.
6. Tras revisión/expiración eliminar únicamente copias de trabajo autorizadas,
   con inventario validado y aprobación; conservar trazabilidad sanitizada. No
   purgar ni alterar datos originales o smokes en esta tarea.

## Sesgos y criterios de aceptación propuestos

Muestras pequeñas y enriquecidas, noticias en inglés, universo parcial de tickers,
una captura retrospectiva acotada, resúmenes truncados, registry parcial y
disponibilidad local distinta de publicación histórica. Los sintéticos son de
autoría del agente implementador; pueden ser más explícitos y no reflejan estilo
real. La selección léxica puede omitir positivos o sobrerrepresentar contexto.
No hay etiquetas, predicciones, evaluaciones humanas ni métricas actuales.

Propuesta a aprobar externamente **antes** de resultados:

- Gate procedural: derechos reales aprobados; dos revisores independientes y
  adjudicación trazable; freeze de evidencia/referencias, versiones y política de
  inferencia; cero fuga del paquete ciego o alteración de artefactos históricos.
- Gate de cobertura: referencias concluyentes positivas y negativas en las
  dimensiones clave; al menos 12 participantes directos y 12 menciones sin
  participación, 6 relaciones indirectas y casos de ticker desconocido/ambiguo,
  distribuidos en múltiples artículos. Son mínimos propuestos, no clases ya
  observadas ni potencia estadística; completar corpus real nuevo si no bastan.
- Gate crítico: ninguna promoción observada de contexto/producto a participante
  o exposición confirmada sin respaldo, ticker inventado, futuro/PIT, rumor a
  hecho o anuncio a cierre. Todo fallo bloquea la recomendación de cierre hasta
  revisión atribuida; no ajustar y reevaluar el mismo conjunto como holdout.
- Gate semántico: reportar por dimensión y por estrato errores, omisiones,
  abstenciones e inconclusos. Umbrales cuantitativos/potencia deberán acordarse
  externamente; no elegirlos después ni inferir calidad poblacional del panel.

Si estos casos guían cambios, pasan a desarrollo y se selecciona evaluación
nueva. Aprobar la preparación no cierra 4C.2. Derechos bloqueados, outputs ausentes
y referencias pendientes impiden todavía una recomendación de cierre técnico.

## Reproducción offline

Desde la raíz del repositorio:

```powershell
python tools/evaluation/prepare_attribution_review.py prepare
python tools/evaluation/prepare_attribution_review.py verify
python -m pytest
```

Rerun idéntico permitido; diferencias requieren nueva versión, nunca sobrescritura.
Los archivos de referencias/outputs deben permanecer vacíos durante preparación.
Una futura comparación, solo con referencias/outputs sellados y alineación
verificada, usa:

```powershell
python tools/evaluation/prepare_attribution_review.py compare --alignment data/cache/news_attribution_review/alignment-approved.json
```

La plantilla actual bloquea la comparación: `aligned_after_reference_freeze=false`.
No hay comando para ejecutar inferencia ni exportar textos reales.

## Validaciones ejecutadas

- `python -m pytest`: **603 passed**, 39,95 s; incluye 17 pruebas nuevas de
  instrumentos. Regresión focal posterior al último ajuste del verificador:
  17 passed, 0,75 s. No hay etiquetas semánticas adjudicadas por estos tests.
- `python scripts/validate_data.py`: correcto; 905 revisiones, 811 artículos,
  cero hashes inválidos, linaje faltante o duplicados; cuatro snapshots válidos.
- `python -m compileall -q src scripts tools/evaluation`: correcto.
- Preparación reproducida sin sobrescribir archivos; verificador confirma nueve
  artefactos, selección/linaje/exclusiones reales y freeze de producción,
  configuración y protocolo.
- SHA-256 antes/después: **3.369 archivos protegidos, 13 grupos, cero cambios**.
  Incluye `src`, `scripts`, `config`, fixtures históricos, ADRs, raw/processed,
  features/targets, reports/cache históricos y protocolo/auditoría originales.
  Ambos smokes y ledger siguen intactos; no se prolonga TTL ni se leen sus
  respuestas para preparar predicciones.

No hubo contenido Finnhub exportado, inferencias ni consultas a proveedores.
No iniciar 4C.3. Esta preparación no recomienda aún cerrar técnicamente 4C.2.
