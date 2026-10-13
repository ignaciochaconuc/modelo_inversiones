# Revisión ciega de atribución — guía del revisor

Este panel contiene exclusivamente textos ficticios, de autoría asistida por IA.
No representa operaciones de empresas reales. Usted no recibirá predicciones,
reglas de implementación, categorías de muestreo ni resultados de desarrollo.
No consulte al implementador sobre respuestas esperadas ni busque estas empresas.

## Primera pasada: solo evidencia textual

Reciba únicamente `prepared/reviewer/blind_synthetic_evidence.json` y una copia
privada de `references/human_a.template.json` o `human_b.template.json`.
Trabaje individualmente, sin ver las anotaciones del otro revisor ni salidas del
sistema. Identifique todos los acontecimientos y menciones relevantes, incluidas
las que no pueden resolverse. No limite la revisión a un listado de entidades
propuesto por un modelo. Tampoco fuerce un acontecimiento compartido en un digest.

Para cada acontecimiento registre estado, etapa y evidencia. Para cada mención,
registre por separado:

| Dimensión | Pregunta de adjudicación |
| --- | --- |
| corporate_identity | ¿El texto identifica una empresa, producto, plataforma u otra entidad? ¿Qué identidad es explícita y qué queda desconocido? |
| participation | ¿Es un participante directo, una relación indirecta respaldada, contexto o una relación desconocida? |
| role | ¿Qué función realiza en ese acontecimiento? Se admite texto libre; no hay obligación de escoger un rol soportado por software. |
| relationship | ¿Qué vínculo se afirma, con quién y con qué grado de certeza? |
| ticker_link | Completar solo en la segunda pasada; no inferir un valor bursátil por familiaridad del nombre. |
| impact_support | ¿Hay impacto observado explícito, una inferencia potencial razonable, solo contexto o información insuficiente? ¿Demuestra el texto exposición económica confirmada? |
| event_state | ¿Hecho reportado, rumor, propuesta, expectativa, negación o desconocido? |
| event_stage | ¿Anuncio, acuerdo, aprobación, cierre efectivo u otra etapa? |

No equipare automáticamente impacto posible con causalidad, exposición confirmada
o estimación de retornos. Puede concluir que un impacto no está demostrado aun
cuando exista un participante y un ticker identificables. No rellene lagunas con
conocimiento externo. Clasifique por separado hechos, inferencias y desconocidos.

## Forma de registrar referencias

En `events` use IDs locales estables y descripción breve propia. En `units` use
una fila por mención/dimensión; mantenga el mismo `unit_id` para la misma mención.
Formato de fila (ilustrativo, sin respuesta esperada):

```json
{
  "unit_id": "event-1:mention-1",
  "dimension": "participation",
  "reference_status": "conclusive_or_uncertain_or_insufficient",
  "reference_value": null,
  "reference_evidence": [],
  "rationale": null
}
```

Una referencia de evidencia usa `evidence_id`, campo, `start`, `end` y fragmento
exacto. Offsets Unicode half-open: `text[start:end]` debe coincidir con el
fragmento. No copie más texto del necesario. Si dos lecturas son plausibles,
documente ambas y marque incertidumbre; no convierta incertidumbre en negativo.
Cada caso mantiene su `evidence_fingerprint` original.

## Segunda pasada: evidencia neutral de identidad

Después de sellar la primera pasada, reciba
`prepared/reviewer/identity_lookup.synthetic.json`. Es una tabla ficticia de
evidencia para esta evaluación, NO el registry de producción. El cutoff virtual
es `2026-10-13T00:05:00Z`: considere separadamente vigencia y conocimiento a ese
momento. Varias clases de acciones pueden impedir una vinculación única. Ausencia
de una entrada no demuestra ausencia de identidad corporativa, solo falta de
resolución bursátil en este contexto. No infiera un fabricante por un producto
ni herede la security de una matriz para una subsidiaria.

Anote `ticker_link` distinguiendo identidad corporativa, security disponible,
participación y evidencia de exposición. Todos los símbolos de la tabla son
ficticios y no operativos. Registre qué entrada respalda su conclusión y su
incertidumbre; no cambie silenciosamente referencias de la primera pasada.

## Proveniencia y entrega

Declare reviewer_id verificable, `reviewed_at` con zona horaria, asistencia
utilizada, independencia respecto del desarrollo y si vio salidas del sistema.
Si utilizó ChatGPT u otra IA para adjudicar, declare esa asistencia: la referencia
no pertenece al estrato humano independiente. El origen IA del texto ficticio
no sustituye la declaración de asistencia del revisor.

Entregue versiones nuevas firmadas/atestadas al custodio; no sobrescriba las
plantillas ni referencias anteriores. Los revisores A/B deben permanecer
independientes hasta sellar ambas entregas. Un tercero resolverá desacuerdos
con racionales y evidencia, conservando las respuestas iniciales.

No abra archivos `operator/` ni `system/`. No solicite noticias Finnhub: su
presentación externa no está autorizada en esta preparación.
