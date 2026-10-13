# Paquete manual de revisión ChatGPT

Estado: `chatgpt_review_prepared_pending_execution`.
Son ocho bloques de cuatro casos ficticios, sin predicciones ni referencias reales.

Copiar el contenido completo de un Markdown por conversación nueva, **no en la
conversación de desarrollo**. Cada archivo ya contiene instrucciones, textos,
IDs/fingerprints y tabla neutral; no adjuntar el repositorio o resultados.

[B01](prepared/packets/B01.md) · [B02](prepared/packets/B02.md) ·
[B03](prepared/packets/B03.md) · [B04](prepared/packets/B04.md) ·
[B05](prepared/packets/B05.md) · [B06](prepared/packets/B06.md) ·
[B07](prepared/packets/B07.md) · [B08](prepared/packets/B08.md).

Guardar respuesta íntegra y una copia completada de la plantilla de procedencia
correspondiente en `data/cache/news_attribution_review/chatgpt-v1/`, no aquí.
No inventar modelo/snapshot/parámetros/tokens ni referencias humanas independientes.

```powershell
python tools/evaluation/prepare_chatgpt_review.py prepare
python tools/evaluation/prepare_chatgpt_review.py verify
```

Importación, errores, freeze y comparación posterior:
[procedimiento completo](../../docs/phase4c2-2-chatgpt-exploratory-review.md).
La revisión aún no se ejecutó. Sin API, claves, Finnhub ni predicciones de Nacho.
