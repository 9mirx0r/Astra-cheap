# Guía rápida de Astra-Ultra

Astra-Ultra es una skill para OpenAI Codex y sus modelos públicos, incluidos
`o1`, `o3`, `o3-mini` y `gpt-4o`. Reduce el contexto repetido y mantiene las
pruebas y la aplicación de parches fuera del modelo.

## Uso en Codex

Podés invocarla en una tarea con:

```text
Usá $astra-ultra para esta tarea.
```

La skill también puede actuar de forma indirecta cuando el entorno la carga
como parte de la configuración del proyecto.

## Cinco mecanismos

1. **Cuantización de prefijos (`astra_prefix_lock.py`):** alinea el texto
   estático a bloques de 128 tokens después del umbral de caché. El resultado
   es una ayuda para estabilizar el prefijo, no una garantía de cache hit.
2. **Mapa del repositorio (`astra_repomap.py`):** rankea archivos y símbolos
   con PageRank dentro de un presupuesto de tokens.
3. **Esqueletos AST (`astra_ast.py`):** conserva clases, firmas, tipos y
   docstrings, pero reemplaza los cuerpos por `...` o `pass`.
4. **Filtro de salida (`astra_sanitizer.py`):** guarda el log completo en disco
   y muestra un resumen acotado con las últimas 25 líneas del fallo.
5. **Ejecución en dos fases (`astra_governor.py`):** las herramientas
   deterministas localizan el problema y el modelo recibe sólo las páginas
   necesarias para producir el parche.

## Comandos

```bash
# Ver el mapa de símbolos del proyecto
astra-ultra map --root . --budget 1024

# Ver el esqueleto de un archivo
astra-ultra skeleton --source src/app.py

# Alinear un prompt a bloques de 128 tokens
astra-ultra lock quantize --input prompt.txt --boundary 128

# Obtener orientación de esfuerzo para un modelo público
astra-ultra govern --model o3-mini --effort high
```

## Verificación

El runtime limita paths modificables, aplica el parche con Git, ejecuta el
comando de tests declarado y puede ejecutar una aceptación independiente. La
suite local contiene 119 tests deterministas:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
