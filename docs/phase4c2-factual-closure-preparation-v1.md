# Preparación del cierre factual sin cronometraje — v1

Estado: borradores para revisión; ninguna decisión del propietario registrada ni
aplicada. Modo solicitado: `closed_content_only_untimed`. Fuente de esta preparación:
archivos locales y esquema versionado; no se consultó GitHub ni ninguna API.

Las seis aprobaciones completas mantienen sus hashes y procedencia asistida por
ChatGPT, con propietario no independiente y sin adjudicación. Se verificaron
paquetes, fingerprints, evidencias, offsets Unicode y las 13 dimensiones de cada
formulario. No se volvieron a generar anotaciones ni se amplió su aprobación.

## Resumen para la decisión del propietario

| Orden / caso | Versión aprobada | Dimensiones / citas | Obligaciones canónicas | Preparación de cierre |
| --- | --- | --- | --- | --- |
| 1 — D-293a6cbca3479505 | Borrador v2 | 13 / 11 | 3 | Bloqueada por cobertura de F001 y F006 |
| 2 — D-a8db3a0c74d93eb8 | Propuesta v2 | 13 / 22 | 5 | Pendiente de aprobación expresa del cierre |
| 3 — D-fbf4c5c9e02691b3 | Propuesta v1 | 13 / 26 | 6 | Pendiente de aprobación expresa del cierre |
| 4 — D-40e8a2188273506b | Propuesta v2 | 13 / 31 | 8 | Pendiente de aprobación expresa del cierre |
| 5 — D-1211fcda178c57ab | Propuesta v1 | 13 / 40 | 8 | Pendiente de aprobación expresa del cierre |
| 6 — D-6c6ef03a91cca2a9 | Propuesta v1 | 13 / 29 | 8 | Pendiente de aprobación expresa del cierre |

Todas las dimensiones están evaluadas, incluidas las insuficientes o
indeterminadas con sus notas. La incertidumbre documentada es compatible con
cerrar contenido: no se transforma en certeza. Los cinco casos sin bloqueo
reutilizan las coberturas ya documentadas sobre el mismo hash aprobado; no
son cinco cierres registrados. El primer caso conserva íntegra su aprobación
semántica, aunque falta resolver el requisito de cobertura del cierre.

## Pendiente detectado en el primer caso

`must_not_omit` contiene F002, F003 y F004: fecha de publicación, vigencia no
informada y ausencia de previsión de producción. Sin embargo:

- F001 está marcado `material=true` y sitúa la entrada del boletín del horno
  asociada a Yrvexil Bioceramics, sin afirmar aprobación o entrada en vigor.
- F006 también está marcado material y conserva la identidad nominal de esa
  empresa, sin acreditar identidad bursátil.

Las tres obligaciones canónicas no conservan expresamente ese sujeto/contexto
nominal. No se encontró una justificación previa suficiente para asignar ambos
hechos a esas tres obligaciones. El borrador deja ambas coberturas pendientes;
no elige IDs arbitrarios para superar el control estructural. Las otras nueve
entradas materiales tienen cobertura propuesta por repetición de fechas,
negaciones y ausencia de previsión. Esta propuesta parcial tampoco es una nueva
adjudicación del propietario.

Este hallazgo no deshace su aprobación ni declara falsos los hechos. Antes de
cerrar el primer caso debe resolverse expresamente esa cobertura. Una posible
corrección posterior sería una v3 limitada a la lista canónica y su justificación
(preservando v2 y todas las afirmaciones), con una obligación para el sujeto/evento
y cobertura explícita de la identidad. Si se modifica el formulario, necesitará
el nuevo hash y una aprobación de esa versión. No se creó v3 ni se decidió ahora
si F006 requiere obligación propia o puede justificarse como desglose de F001.

## Alcance y límites que conservaría cada cierre

1. Primer caso: la fecha citada es publicación, no vigencia acreditada; no hay
   previsión de producción. Etapa del permiso, participación, roles, relaciones,
   identidad bursátil e impacto siguen insuficientes. La cobertura anterior es
   condición pendiente, además de la aprobación de cierre.
2. Segundo caso: 640 toneladas en enero–marzo y 640.000 USD brutos por cada mes,
   antes de transporte. No se conoce el neto, el año, composición o contraparte.
   Relación e impacto siguen insuficientes. No distribuir toneladas por mes.
3. Tercer caso: este paquete sí define R7 como aceptación física y liberación
   operativa. No prueba producción efectiva ni plena capacidad. Fecha específica,
   relación empresarial e impacto siguen insuficientes; no inventar volumen,
   ingresos o retorno.
4. Cuarto caso: el artículo atribuye a 2031-03-21 la vigencia del permiso; la hora
   de publicación de metadata tiene otra función y no fija una hora efectiva.
   Participación, roles, relación, vínculo bursátil e impacto siguen insuficientes.
   F006 cuenta como obligación propia en la v2 aprobada.
5. Quinto caso: los 640.000 USD brutos son para los tres meses combinados. No hay
   reparto mensual de las 640 toneladas. Relación e impacto siguen insuficientes;
   neto, beneficio, margen, año, fechas diarias y contraparte no documentados.
6. Sexto caso: R7 no está definido en este paquete. La etapa permanece
   indeterminada; roles, relación, fechas e impacto son insuficientes. No importar
   el glosario del tercero ni inferir aceptación, operación o producción.

En todos: identidad del registry y exposición económica son dimensiones distintas;
la ausencia de información no prueba inexistencia. El cierre futuro sería solo
del contenido factual asistido de desarrollo, sin ground truth humano independiente,
medición completa, cierre integral, freeze o permiso contractual.

## Borradores y esquema de destino

Carpeta separada:
`data/cache/news_development_pilot/closure-preparation-v1/`.
Contiene seis `CASE_ID.draft.json`, un índice y un manifiesto de verificación.
Cada borrador enlaza por hash la anotación aprobada, su aprobación, la disposición
abierta, la autorización metodológica y, cuando existe, la auditoría de cobertura.
Incluye las incertidumbres y una plantilla con los campos del esquema destino
`news-pilot-factual-closure-decision-v1`.

El esquema de una decisión efectiva exige `explicitly_approved=true`. Por eso no
se puede crear hoy una decisión válida sin atribuir una aprobación inexistente.
Se prepararon plantillas deliberadamente incompletas y no ejecutables: quedan
null `explicitly_approved`, `decided_by`, `decision_source`,
`factual_evidence_reviewed`, `uncertainty_preserved` y `unresolved_semantic_changes`.
Son campos reservados para el acto futuro del propietario, no declaraciones
efectuadas ahora. `decided_at` también queda null: no se inventó hora o fecha.

Se comprobó que las seis plantillas son rechazadas como decisiones efectivas por
esos seis campos pendientes, sin relajar el esquema. El primer caso añade una
carencia de cobertura que se registra aparte: el modelo estructural no certifica
que un mapa de IDs sea semánticamente suficiente. No se construyeron disposiciones
cerradas ni siquiera para una simulación de estas decisiones reales.

## Qué se necesita antes de aplicar

El propietario puede aprobar expresamente el cierre sin tiempos de los casos
2–6 identificados por sus IDs, versiones y hashes de este paquete, manteniendo
sus incertidumbres y exclusión temporal. Ese mensaje futuro será la fuente real
de la decisión. La solicitud actual únicamente autoriza preparar y presentar.
Para el primero se necesita además resolver la cobertura descrita, sin alterar
silenciosamente su versión aprobada.

Tras una autorización posterior, correspondería registrar decisiones nuevas con
procedencia real y nuevas disposiciones enlazadas mediante `supersedes`, conservando
las disposiciones abiertas originales. Ningún formulario histórico cambiaría a
`completed`; el adaptador contractual seguiría ausente. Esta entrega no realiza
ninguno de esos pasos.

Los tiempos siguen: desconocido; ≈1 minuto estimado; 30, 20, 30 y 20 segundos
declarados sin cronometraje completo. Los seis intentos permanecen excluidos de
estadísticas medidas. No se recuperan inicios, finales, pausas, duración activa o
adjudicaciones. No se cambian los estados oficiales de fases ni se ejecutan
inferencias, nuevas evaluaciones del modelo o llamadas externas.

## Versiones y hashes que serían objeto del cierre

| Caso | SHA-256 del contenido ya aprobado |
| --- | --- |
| D-293a6cbca3479505 | `9072b179f81639e507d0c05c84fbe495f17de3647984591c335d99c32ecb396b` |
| D-a8db3a0c74d93eb8 | `77e82bca3bd1358f54faffd59babfe12b62b0ca40eb1131437cb100433260ec6` |
| D-fbf4c5c9e02691b3 | `5c0ff99410a3371b5cfdcd49e9134842bd4dcca9333ecec2bfcb2da33a2b457b` |
| D-40e8a2188273506b | `67ab00ba7c50a6415820a77b57901dcb3b6a372cb986c7f7451325a21cbeea65` |
| D-1211fcda178c57ab | `62806d79ae2f8455a0408cf2b34e681599b94fd2cd2219f7ca2ee1e02129552d` |
| D-6c6ef03a91cca2a9 | `3d8bfb39f17fc3f5e0430220d2c6f5dfe82e1a862bcf7426147aec347a837afe` |

Los hashes de los borradores identifican una preparación, no una decisión
aprobada; completar una decisión futura producirá bytes y hash diferentes.
