# Guía Rápida de Astra-Ultra

**Astra-Ultra** es una skill personal y modular para **OpenAI Codex** y sus modelos (**Luna 5.6**, **Terra**, **o1**, **o3-mini**, **o3** y **GPT-4o**). Su propósito es sencillo: **reducir el consumo de tokens hasta un 80% manteniendo el 100% de la calidad de tu código**.

---

## 1. Cómo Usarlo en Codex

Podés invocarlo explícitamente en cualquier tarea diciendo:

```text
Usá $astra-ultra para esta tarea.
```

O simplemente describí lo que necesitás de forma natural. La economía de tokens y el cuidado de tu cuota es responsabilidad del agente, no tuya: no tenés que hablar de forma comprimida ni omitir detalles importantes.

---

## 2. Los 5 Mecanismos Clave (En palabras simples)

1. **Bloqueo de Caché y Cuantización a 128 Tokens (`astra_prefix_lock.py`):**
   OpenAI almacena en caché instrucciones estáticas en múltiplos de 128 tokens a partir de 1,024 tokens. Astra-Ultra congela las cabeceras fijas y alinea el texto estático para asegurar que el **90%+ de tus llamadas aprovechen el 50% de descuento en tokens de entrada**.

2. **Mapa del Repositorio en <1,024 Tokens (`astra_repomap.py`):**
   En lugar de volcar carpetas enteras en el chat, calcula qué archivos y funciones son las más importantes usando PageRank y las resume en menos de 1,024 tokens.

3. **Esqueletos AST (`astra_ast.py`):**
   Si el modelo necesita ver una clase o API, lee la estructura completa con tipos y docstrings pero sin los cuerpos de las funciones (`...`), consumiendo menos de 50 tokens por archivo.

4. **Filtro de Ruido en Terminal (`astra_sanitizer.py`):**
   Cuando corrés tests (`pytest`, `cargo`, `npm`), no deja que 5,000 líneas de logs inunden el contexto. Guarda el log completo en el disco y te muestra solo el resumen y las últimas 25 líneas con el error exacto.

5. **Protocolo Asimétrico para Luna 5.6 High (`astra_governor.py`):**
   Los modelos de razonamiento profundo gastan miles de tokens pensando. Poner a Luna 5.6 High a buscar archivos gasta tu límite de 5 horas enseguida. Astra-Ultra hace la búsqueda con herramientas livianas y le entrega a Luna **solo la función de 30 líneas con el bug en 1 único turno** para que resuelva la lógica matemática o concurrente.

---

## 3. Comandos Útiles de Consola

Si querés usar las herramientas por tu cuenta desde la terminal:

```bash
# Ver el mapa de símbolos optimizado del proyecto
astra-ultra map --root . --budget 1024

# Ver el esqueleto limpio de cualquier archivo
astra-ultra skeleton --source src/app.py

# Alinear un prompt al bloque de 128 tokens de OpenAI
astra-ultra lock quantize --input prompt.txt --boundary 128

# Ver el protocolo asimétrico de razonamiento para Luna 5.6 High
astra-ultra govern --asymmetric
```

---

## 4. Garantía de Calidad

- **Cero distorsión de sintaxis:** No usamos compresión agresiva destructiva (como LLMLingua) que rompe indentación o tipos.
- **80 tests deterministas:** Cada herramienta está respaldada por una suite de pruebas unitarias que podés correr en cualquier momento con `python -m unittest discover -s tests`.
