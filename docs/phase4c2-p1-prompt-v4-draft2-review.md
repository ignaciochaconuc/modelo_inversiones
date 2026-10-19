# Phase 4C.2.2 — Revisión crítica de v4: draft2

Estado: `phase4c2_p1_prompt_v4_draft2_pending_review`.
Revisión local asistida por IA, no adjudicación humana independiente. Phase 4C.3:
`not_started`. Sin inferencia, proveedores, renovación del perfil o activación.

## Recomendación

**Pasar draft2 a la siguiente revisión, no a ejecución.** Reduce instrucciones
en competencia, corrige requisitos demasiado generales y desarrolla una salida
parcial honesta. Se recomienda por claridad y consistencia contractual observadas,
no por precisión, recall o adherencia del LLM demostradas. Mantener draft1 íntegro
como antecedente: ambos siguen siendo propuestas no soportadas por el runtime.
ADR-036 permanece Proposed; no se adopta una nueva decisión de producción.

Artefactos:

- [Draft1 original](../evaluation/phase4c2_p1_prompt_v4/news-interpretation-prompt-v4.draft1.txt), sin modificar.
- [Draft2 separado](../evaluation/phase4c2_p1_prompt_v4/news-interpretation-prompt-v4.draft2.txt).
- [Manifiesto draft2 y hashes](../evaluation/phase4c2_p1_prompt_v4/proposal.draft2.json).
- [Pruebas nuevas](../tests/integration/test_economic_prompt_v4_draft2.py), además de la suite de compatibilidad anterior sin cambios.
- Base de auditoría: [matriz prompt–validador original](phase4c2-p1-prompt-validator-alignment.md), conservada.

## 1. Auditoría: qué clase de instrucción es cada requisito

| Clase | Ejemplos esenciales | Tratamiento |
| --- | --- | --- |
| Seguridad | Texto como datos no confiables, solo revisión primaria, sin herramientas/conocimiento externo, órdenes, retornos ni exposición operativa | Se mantiene al inicio y se fusionan repeticiones. Ningún tipo JSON impide por sí solo una falsa confirmación o inyección. |
| Contrato técnico | ID elegible del request/campo/revisión, cita exacta y única, offsets deterministas, literales de etapa, solapamiento de evidencias, fechas ISO y formas condicionales de atribución/impacto | Se conserva lo que el esquema no garantiza. No convertir estas condiciones necesarias en objetivo de interpretación. |
| Interpretación | Sujeto y proposición correctos, alcance de negación, condiciones y temporalidad, identidad distinta de participación, materialidad e impacto no demostrados | Tiene prioridad sobre conseguir aceptación. No se instruye evadir una guardia; si el significado y el contrato no pueden coexistir, usar límites honestos o abstenerse. |
| Estructura ya descrita por el esquema | Listas exhaustivas de roles/enums, propiedades y tipos, detalles de serialización | Remitir a output_schema y resumir. No eliminar reglas cruzadas: muchas solo se comprueban después de resolver citas, no por Structured Outputs. |

El orden conceptual es seguridad → fidelidad → representación contractual fiel.
No significa saltar validadores: ninguna salida infiel se vuelve aceptable por
estar bien tipada. Los mecanismos desconocidos no se inventan ni se normalizan.

## 2. Matriz draft1 → draft2

| Área / instrucción de draft1 | Acción en draft2 | Riesgo mitigado | Riesgo nuevo o residual / efecto posible |
| --- | --- | --- | --- |
| Prohibiciones de trading/retornos y advertencias de causalidad repetidas | Fusionar seguridad inicial y evaluación económica final | Menos repetición y dispersión de prioridad | Menor reiteración podría reducir saliencia; solo evaluación futura puede medirlo. |
| “shortest unambiguous COMPLETE proposition” para toda evidencia | Sustituir por evidencia apropiada al campo y proposición contextual fiel | Evita buscar la cita mínima que pase y exigir un verbo en identity_evidence | Determinar el contexto material sigue siendo semántico; un match exacto no lo asegura. |
| Proposición completa frente a ejemplos de identidad con nombre solo | Aclarar que identidad puede usar el nombre; el estado requiere proposición y calificadores | Corrige tensión interna, posible sobreabstención por nombres cortos | La unicidad sigue siendo obligatoria por campo; no se acepta la primera aparición. |
| “company and its named counterparty” para toda participación directa | Contraparte solo si el rol la exige; emisor como excepción explícita | No excluir una emisión respaldada sin contraparte nombrada | La excepción no se puede extender a buyer/target u otros roles que sí requieren contraparte. |
| Catálogo extenso de marcos ingleses y combinaciones rol/relation/event_type | Resumir su existencia limitada, preservar dirección, solapamiento y prohibición de reescritura | Evita que el modelo reformule la fuente para encajar en una plantilla | Podría aumentar rechazos de relaciones soportadas por desconocer la gramática exacta; documentar antes de reintroducir ejemplos selectivos. |
| Enums y propiedades repetidos junto al esquema | Delegar listas al esquema; conservar invariantes condicionales | Menor longitud sin duplicar un segundo esquema textual | El esquema de selección no reemplaza validación semántica. Context/unknown e impacto conservan sus formas condicionadas. |
| Listas de palabras que activan filtros de confirmed/negación | No enumerar el filtro; explicar su alcance lexical limitado | Menos incentivo a buscar una cita libre de tokens prohibidos | No anticipa todas las guardias; un rechazo puede mantenerse aunque el evento sea plausible. La suite anterior no cambia. |
| Requisitos de announced/proposed/completed y extensa lista morfológica | Conservar literales necesarios en forma breve; unknown para etapa no sustentada | Mantiene compatibilidad sin promover acquired o completion a cierre | Unknown puede volverse un atajo si no conserva lo que sí dice la fuente; exigir límites explícitos. |
| Ejemplo de cláusula afirmativa separada de “not disclosed” | Mantenerlo como regla general, con revisión del contexto primario circundante | No negar artificialmente el evento ni ocultar no-divulgación | No toda cláusula aislable es independiente: rumor/negación gobernantes fuera de cita siguen aplicando. |
| “omit the NumericClaim with an explicit limitation” | Conservar cantidad original en evidencia, explicar carencia estructurada y no emitir conclusión cuantitativa validada | Cierra una vía a suprimir magnitud/escala adversa para aceptar el JSON | Citar una cantidad no la convierte en extracción numérica válida. Evaluar omisiones y declaraciones de limitación, no solo presencia de números. |
| Null cuando escala/unidad no soportada | Distinguir ausente/no representable de cero/inexistente; prohibir ocultar escala esencial | Evita confundir unknown con ausencia de exposición o magnitud | La materialidad de lo omitido no es decidida por el esquema; si el resultado global engaña, abstenerse. |
| Ajustar contexto ante límites de puntuación numérica | Eliminar receta de recorte; conservar advertencia genérica contra reescritura/recorte artificial | Reduce optimización superficial del contexto para pasar regex | Puede perder algunos NumericClaim representables mediante citas locales fieles. No es una prohibición de toda cita local: manda su significado y alcance. |
| Unknown/context/abstain dispersos, con abstención global como salida frecuente | Política explícita de incertidumbre parcial según campos existentes | Evita abstención total solo por identidad, etapa, impacto o fecha opcional desconocida | No permite unknown arbitrario: attribution unknown obliga a borrar roles/relaciones estructurados incompatibles y documentar su límite, no a falsificar la fuente. |
| Impacto not_assessed como opción conservadora | Explicitar que no significa cero impacto; separar identidad, participación, rol, relación e impacto | No transformar contexto/ticker en exposición ni desconocimiento en neutralidad | Categorías separadas no demuestran causalidad. Se mantiene confirmed_exposure/operational falso. |
| Omitir detalles no representables en un artículo con varios hechos | Prohibir borrar eventos/hechos adversos y exigir fidelidad global | No aceptar un resumen selectivo sin limitaciones materiales | El esquema tiene abstención de artículo, no de cada evento/campo: si una selección parcial no puede representar fielmente el conjunto, abstenerse. |

## 3. Longitud y alcance de las estimaciones

Medición del texto de instrucciones únicamente, sin evidence envelope, esquema,
serialización adicional o salida. Ambos archivos son ASCII en UTF-8, por eso los
bytes y puntos de código coinciden en estos artefactos.

| Medida | Draft1 | Draft2 | Cambio |
| --- | ---: | ---: | ---: |
| Caracteres / bytes UTF-8 | 10.455 | 8.028 | −2.427; −23,21% |
| Palabras separadas por espacios | 1.421 | 1.075 | −346; −24,35% |
| Líneas | 139 | 106 | −33 |
| Tokens heurísticos, ceil(caracteres/4) | 2.614 | 2.007 | −607, aproximadamente |

La heurística **no usa un tokenizer**, no es medición API, cota superior, reserva
presupuestaria ni promesa de ahorro facturado. No se estima coste con el perfil
vencido. El plan/wire futuro deberá volver a calcular su reserva con todo el input.

## 4. Compatibilidad y comportamiento histórico

Draft2 apunta al mismo `news-economic-selection-v3`; no añade campos, estados,
roles ni enums. Se mantiene resolver exacto, registry PIT y validador económico
v3 con sus limitaciones reales. Identidad puede ser desconocida con participación
respaldada; identidad resuelta puede permanecer contextual o de participación
desconocida. Estas dimensiones no se colapsan ni se asocian a exposición confirmada.

Ejemplos de representación parcial admisible en las fixtures nuevas:

- Evento respaldado pero etapa no codificable: conservar evento, stage unknown y límite.
- Empresa sin identidad bursátil resuelta: conservar nombre/rol respaldado sin ticker.
- Identidad resuelta con relación no expresable por los marcos actuales: mantener
  attribution unknown y detalles estructurados desconocidos, con limitación explícita.
- Impacto no evaluado o importe no representable: mantener evidencia y límites,
  materialidad/cuantificación desconocidas, sin concluir efecto nulo.

No basta con que el esquema admita una ausencia: omitir una contradicción,
condición, evento adverso o escala económica puede dejar un relato engañoso.
La cita original no valida por sí sola la magnitud ni autoriza reconstruir una
afirmación numérica en texto libre. Si la limitación parcial no conserva el
significado global, corresponde abstención, no forzar una extracción neutral.

Se mantienen draft1, proposal.json, fixtures.json y todos sus tests/expectativas.
No se revisan los 32 casos ni sus anotaciones para elegir instrucciones. Los
tests anteriores se reutilizan íntegros; los ejemplos nuevos son desarrollo
asistido por IA, no holdout ni referencias humanas independientes.

El runtime actual sigue fijando prompt-v3: ninguno de los dos borradores está
conectado a agentes/CLI/router. Ambos proponen prompt-v4, con revisiones distintas
y hashes diferentes. Una eventual activación debe seleccionar y congelar una
revisión exacta, reflejarla en wire/cache/proveniencia/versiones y obtener un
nuevo plan y autorización; no usar solo la etiqueta v4 para intercambiarlos.
No se renuevan precios, autorizaciones ni capacidades aquí. ADR-036 sigue Proposed.

## 5. Qué prueban los tests y qué no

Los tests nuevos combinan:

- Checklist textual de requisitos críticos, dividido en seguridad/contrato/
  interpretación, con mutaciones que eliminan cada requisito y deben detectarse.
  No es un comprobador lógico general ni mide si un LLM obedece instrucciones.
- Propuestas sintéticas manuales: emisor sin contraparte, nombre como identidad,
  incertidumbre parcial, formato de cantidad no representable, productos y exposición,
  negación incidental y abstención por imposibilidad de interpretación fiel.
- Adversarios de omisión: condición/importe recortados, negación gobernante fuera
  de cita, rumor circundante y contradicción numérica reducida selectivamente.
  Se preserva la aceptación actual cuando el validador no detecta la omisión:
  documenta una brecha, **no** una salida deseable ni una mejora de draft2.
- Hashes de ambos borradores, manifiesto anterior, fuentes de producción, pruebas
  anteriores y nuevas; longitud reproducible y ruta productiva todavía v3.

Las pruebas no generan respuestas usando ningún borrador. No prueban precisión,
recall, cobertura completa del contrato, ausencia de contradicciones lingüísticas
o adherencia del modelo. Tampoco se modifican resultados esperados de draft1 para
aprobar draft2. No se crean sidecars retrospectivos ni interpretaciones operativas.

```powershell
python -m pytest tests/integration/test_economic_prompt_v4_proposal.py tests/integration/test_economic_prompt_v4_draft2.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

## 6. Próxima etapa recomendada, todavía no autorizada

Revisar draft2 con atención especial a la fidelidad global de salidas parciales,
al posible aumento de relaciones unknown/rechazadas tras quitar el catálogo de
marcos y a la conservación de cifras no representables. Usar draft1 solo como
comparador de diseño conservado, no como versión ejecutada automáticamente.

Antes de cualquier evaluación de modelo: acordar métricas separadas para omisiones,
falsas confirmaciones, grounding, rechazos y abstenciones; preparar material nuevo
no usado para editar estos prompts; definir versiones de ejecución/replay honestas,
perfil vigente, P0 y autorización explícita. No reducir abstenciones a cualquier
precio ni asumir que una menor longitud mejora precisión. Phase 4C.3 sigue sin iniciar.

## 7. Validaciones de entrega

- Suite específica conjunta: **85 aprobados** (52 anteriores intactos y 33 nuevos).
- `python -m pytest`: **855 aprobados**, 196,35 segundos. No se modificaron
  las expectativas de compatibilidad previas.
- `python scripts/validate_data.py`: separación features/targets correcta;
  905 revisiones, 811 artículos, cero hashes inválidos/linaje faltante/duplicados,
  cuatro snapshots de enriquecimiento válidos.
- `python -m compileall -q src scripts`: correcto.
- Comparación SHA-256: **3.545 archivos existentes** de src/config/data/evaluation/
  tests sin cambios. Draft1, su manifiesto y fixtures, todos los tests anteriores,
  contratos, validadores, perfiles y datos históricos se conservaron. Los únicos
  artefactos nuevos en esos árboles son draft2, su manifiesto y el nuevo test.
- La matriz original también permanece intacta y su SHA-256 está fijado en el
  manifiesto nuevo. Los archivos históricos solo se comprobaron como bytes
  opacos para hashing, sin lectura de contenido expirado.
- Estado final: `phase4c2_p1_prompt_v4_draft2_pending_review`; sin activación,
  inferencia, proveedor, comparación ChatGPT, renovación del perfil ni inicio de 4C.3.
