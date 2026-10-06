# Revisión de código en la captura — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** cuando la captura (`Right Shift + P`) muestra código ya escrito, Phonexi
da un veredicto (`==Correct==` o `==Bug==`) y explica qué hace el código o por qué
falla, leyendo el encabezado para saber qué debería hacer.

**Arquitectura:** solo cambian los prompts de captura en `phonexi/config.py`. Se
agrega una regla de revisión, en versión corta para la API (`PROMPT_CAPTURE`) y con
encabezados para `-cli` (`PROMPT_CAPTURE_CLI`). La detección es automática: el
modelo decide qué rama aplica según lo que ve. No hay atajo nuevo, ni cambios en
`listener.py`, `processor.py`, los motores ni la UI.

**Tech Stack:** Python 3.12, pytest. Motores: Groq/Gemini (API), agy y Claude Code (`-cli`).

**Spec:** diseño aprobado en el chat el 5 de octubre de 2026 (camino acotado, sin
documento de spec). Se reproduce en la sección **Diseño** de abajo.

## Diseño

Qué responde la captura según lo que hay en pantalla:

| En pantalla | Respuesta |
|---|---|
| Enunciado + función vacía (plantilla tipo LeetCode) | Resuelve, igual que hoy |
| Código con implementación (con o sin enunciado) | **Revisión** (nuevo) |
| Pregunta explícita sobre el código ("¿qué imprime?", complejidad, opción múltiple) | Contesta esa pregunta (nuevo, ver nota) |
| Pregunta conceptual | Respuesta corta, igual que hoy |

**Cómo revisa:** primero lee el encabezado (nombre, parámetros, tipo de retorno,
docstring o comentario de arriba, y el enunciado si existe) para deducir qué
*debería* hacer el código. Luego compara eso con lo que el cuerpo hace realmente.
El veredicto va siempre primero, incluso cuando el código es correcto.

**Formato API** (tope de 900 tokens en Groq): una frase con el veredicto. Si es
correcto, 2 o 3 viñetas sobre qué hace y cómo. Si hay bug, una viñeta por bug con
la línea, qué falla, por qué y una entrada que lo rompe, y después solo las
líneas corregidas.

**Formato `-cli`** (encabezados en inglés y el texto en el idioma de la pregunta):

```
# Verdict      → ==Correct== o ==Bug== + una frase
# What it does → 2-3 viñetas: propósito según el encabezado y cómo lo logra
# Issues       → solo si hay bug: línea, qué falla, por qué y una entrada que lo rompe
# Fix          → solo si hay bug: la función corregida completa
```

**Nota, agregado al escribir el plan:** el diseño aprobado no cubría las capturas
del tipo "¿qué imprime este código?". Con la regla tal cual, esa captura muestra
código ya escrito y recibiría una revisión en lugar de la respuesta. Por eso la
regla incluye una excepción: si la pantalla hace una pregunta concreta sobre el
código, se contesta esa pregunta. Esto también deja el camino libre a las reglas
de "qué imprime" y opción múltiple que siguen pendientes en la bitácora.

**Fuera de alcance:** atajo nuevo, cambios en la UI y el modo voz.

## Global Constraints

- Solo cambian `phonexi/config.py`, `tests/test_processor.py`, `tests/test_engines.py`, `README.md` y la bitácora.
- `PROMPT_VOICE` no recibe la regla de revisión (en voz no hay código en pantalla).
- Encabezados de `-cli` literales y en este orden: `# Verdict`, `# What it does`, `# Issues`, `# Fix`.
- Los marcadores del veredicto son literales: `==Correct==` y `==Bug==`.
- La versión API no lleva encabezados `#`; el fix trae solo las líneas corregidas.
- Ninguna regla compartida existente se quita ni se reescribe; `_REVIEW_RULE` / `_REVIEW_RULE_CLI` se insertan entre la regla de código y `_SHARED_RULES`.
- Commits sin línea `Co-Authored-By` ni atribución a IA, con el estilo del repo (`feat: ...`, `docs: ...`).
- Correr la suite como indica la bitácora: `python -m pytest -q -p no:faulthandler --ignore=tests/test_ui.py` y aparte `python -m pytest -q tests/test_ui.py` (el fallo intermitente "Can't find a usable tk.tcl" puede tumbar pytest completo).

## Review Focus

Son comportamientos del modelo que las pruebas unitarias no pueden fijar, porque
solo comprueban el texto del prompt. Se verifican en la prueba real (Task 2):

1. **Plantilla de LeetCode con la función vacía** (`pass` o solo la firma). Debe resolverse con el formato de siempre, no revisarse. Es el riesgo más alto: una regresión aquí rompe el uso principal de la captura. Caso C de la Task 2.
2. **"¿Qué imprime este código?"** Debe contestar la salida, no dar un veredicto. Caso D de la Task 2.
3. **Código correcto pero ineficiente** (por ejemplo, O(n²) donde existe O(n)). Lo esperable es `==Correct==` y mencionar la complejidad dentro de "What it does". El diseño no lo fija; anotar en la bitácora qué hace cada motor y decidir después si merece regla propia.
4. **Fragmento sin encabezado** (unas líneas sueltas, sin firma). La regla dice "si existe"; debe explicar qué hace el fragmento sin inventar una firma. Revisarlo si aparece en la prueba real.
5. **Idioma del veredicto en código sin texto en español.** La regla de idioma pide responder en el idioma de la pregunta. Con código puro, el modelo puede escribir `==Correct==` o `==Correcto==`; cualquiera de los dos sirve, solo se anota cuál usa.

---

### Task 1: Regla de revisión en los prompts de captura

**Files:**
- Modify: `phonexi/config.py` (después de `_CODING_RULE_CLI`, ~línea 91; y las líneas `PROMPT_CAPTURE` / `PROMPT_CAPTURE_CLI`, ~172-174)
- Modify: `README.md` (sección Features)
- Test: `tests/test_processor.py` (después de `test_process_sends_the_capture_prompt`, ~línea 861)
- Test: `tests/test_engines.py` (antes de `test_cli_capture_labels_brute_force_and_optimal`, ~línea 598)

**Interfaces:**
- Consumes: `PROMPT_CAPTURE`, `PROMPT_CAPTURE_CLI`, `PROMPT_VOICE` de `phonexi.config`; `system_prompt(voice=False)` de `phonexi.engines.base` (ya devuelve `PROMPT_CAPTURE_CLI`).
- Produces: constantes privadas `_REVIEW_INTRO`, `_REVIEW_RULE`, `_REVIEW_RULE_CLI` en `phonexi/config.py`. Los nombres públicos no cambian.

- [ ] **Step 1: Escribir las pruebas que fallan en `tests/test_processor.py`**

Insertar después de `test_process_sends_the_capture_prompt` (el archivo ya importa
`PROMPT_CAPTURE`, `PROMPT_CAPTURE_CLI` y `PROMPT_VOICE`):

```python
# ── a capture of written code gets a review, not a fresh solution ───────────

_CAPTURE_PROMPTS = [PROMPT_CAPTURE, PROMPT_CAPTURE_CLI]


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_capture_reviews_code_already_written(PROMPT):
    """Code with a body on screen is asked 'is this right?', not 'solve this'."""
    low = PROMPT.lower()
    assert "code that is already written" in low
    assert "takes precedence over the coding-problem rule" in low


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_review_reads_the_header_for_the_intent(PROMPT):
    """The name, parameters, return type and docstring say what the body should do."""
    low = PROMPT.lower()
    assert "read the header" in low
    assert "docstring" in low


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_review_opens_with_a_verdict(PROMPT):
    assert "==Correct==" in PROMPT
    assert "==Bug==" in PROMPT


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_review_shows_an_input_that_breaks_the_code(PROMPT):
    """'Off by one' alone is not something to say aloud; the failing input is."""
    assert "input that breaks it" in PROMPT.lower()


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_an_empty_stub_is_still_solved(PROMPT):
    """A LeetCode template has a signature and no body: that is a problem to solve."""
    assert "empty stub" in PROMPT.lower()


@pytest.mark.parametrize("PROMPT", _CAPTURE_PROMPTS, ids=["capture", "cli-capture"])
def test_an_explicit_question_about_the_code_is_answered(PROMPT):
    """'What does this print?' wants the output, not a verdict."""
    assert "asks a specific question about the code" in PROMPT.lower()


def test_voice_does_not_review_code():
    """Voice never shows code on screen."""
    assert "code that is already written" not in PROMPT_VOICE.lower()


def test_only_the_cli_review_uses_headings():
    """The API answer is capped at 900 output tokens on Groq."""
    assert "# Verdict" not in PROMPT_CAPTURE
    assert "# Verdict" in PROMPT_CAPTURE_CLI


def test_the_api_review_sends_only_the_corrected_lines():
    """A whole function again does not fit in 900 tokens next to the bullets."""
    assert "only the corrected lines" in PROMPT_CAPTURE.lower()
```

- [ ] **Step 2: Escribir la prueba del orden de encabezados en `tests/test_engines.py`**

Insertar antes de `test_cli_capture_labels_brute_force_and_optimal`:

```python
_REVIEW_SECTIONS = ["# Verdict", "# What it does", "# Issues", "# Fix"]


def test_cli_capture_reviews_written_code_in_four_sections():
    """Verdict first: the reader needs 'right or wrong' before the why."""
    from phonexi.engines.base import system_prompt
    prompt = system_prompt(voice=False)
    positions = [prompt.index(section) for section in _REVIEW_SECTIONS]
    assert positions == sorted(positions)
```

- [ ] **Step 3: Correr las pruebas nuevas y ver que fallan**

Run: `python -m pytest -q -p no:faulthandler tests/test_processor.py tests/test_engines.py -k "review or stub or verdict or breaks or reads_the_header or already_written or explicit_question or corrected_lines"`

(El filtro dice `reads_the_header` y no `header`: con `header` también entran las
pruebas de rate limit `..._reset_header` de `test_processor.py`, que ya pasan, y
los conteos de abajo dejarían de cuadrar.)

Expected: 15 fallan (6 parametrizadas × 2, más `test_only_the_cli_review_uses_headings`,
`test_the_api_review_sends_only_the_corrected_lines` y
`test_cli_capture_reviews_written_code_in_four_sections`) con `AssertionError` o
`ValueError: substring not found`. `test_voice_does_not_review_code` **pasa** desde
el inicio: es una guarda, no prueba la funcionalidad nueva.

- [ ] **Step 4: Agregar la regla en `phonexi/config.py`**

Insertar después del cierre de `_CODING_RULE_CLI` (antes de `_SHARED_RULES`):

```python
# A capture of code that is already written asks "is this right?", not "solve
# this". The header says what the body should do; the verdict leads.
_REVIEW_INTRO = (
    "- If the screenshot shows code that is already written (a function or class "
    "with a body, with or without a problem statement), review it instead of "
    "solving it; this takes precedence over the coding-problem rule. An empty stub "
    "(a signature with no body, or only 'pass' or a TODO) is still a problem to "
    "solve. If the screen asks a specific question about the code (what it prints, "
    "its complexity, which option is right), answer that question instead. To "
    "review, first read the header -- the name, parameters, return type, the "
    "docstring or the comment above it, and the statement if there is one -- to "
    "infer what the code should do, then check what the body really does.\n"
)

_REVIEW_RULE = _REVIEW_INTRO + (
    "  Open with the verdict as a key phrase, ==Correct== or ==Bug==, in one "
    "sentence. If correct: 2 or 3 bullets on what it does and how. If there is a "
    "bug: one bullet per bug naming the line, what fails and why, with an input "
    "that breaks it; then only the corrected lines as a fenced code block (```lang).\n"
)

# -cli has room for sections, in the spirit of the interview template.
_REVIEW_RULE_CLI = _REVIEW_INTRO + (
    "  Answer with these markdown headings, each on its own line, in this order "
    "and in English; the text under them follows the question's language. Start "
    "directly with the first heading:\n"
    "  # Verdict -- ==Correct== or ==Bug== as a key phrase, then one sentence.\n"
    "  # What it does -- 2 or 3 bullets: its purpose as the header states it, and "
    "how the body achieves it.\n"
    "  # Issues -- only if there is a bug: one bullet per bug naming the line, what "
    "fails and why, with an input that breaks it.\n"
    "  # Fix -- only if there is a bug: the whole corrected function as a fenced "
    "code block (```lang). No comments unless a line is non-obvious.\n"
)
```

Y cambiar las dos líneas de armado:

```python
PROMPT_CAPTURE = (
    _CAPTURE_INTRO + _LANGUAGE_RULE + _CODING_RULE + _REVIEW_RULE + _SHARED_RULES
)

PROMPT_CAPTURE_CLI = (
    _CAPTURE_INTRO + _LANGUAGE_RULE + _CODING_RULE_CLI + _REVIEW_RULE_CLI + _SHARED_RULES
)
```

`PROMPT_VOICE` no se toca.

- [ ] **Step 5: Correr las pruebas nuevas y ver que pasan**

Run: el mismo comando del Step 3.
Expected: 16 passed.

- [ ] **Step 6: Correr la suite completa**

Run: `python -m pytest -q -p no:faulthandler --ignore=tests/test_ui.py`
y luego `python -m pytest -q tests/test_ui.py`

Expected: todo en verde (400 previas + 16 nuevas = 416 entre las dos corridas).
Vigilar en especial `test_only_the_cli_capture_gets_the_template`, `test_voice_only_rules`
y las pruebas parametrizadas con `_BOTH_PROMPTS`, que comparan texto de los prompts.

- [ ] **Step 7: Una línea en `README.md`**

En la lista de Features, después de la línea de **Screenshot mode**:

```markdown
- **Code review on capture** — when the capture shows code that is already written, the answer opens with a verdict (correct or bug), reads the function's header to know what it should do, and explains what it does or why it fails with an input that breaks it. An empty stub is still solved as a problem
```

- [ ] **Step 8: Commit**

```bash
git add phonexi/config.py tests/test_processor.py tests/test_engines.py README.md
git commit -m "feat: review code already written on a capture"
```

---

### Task 2: Prueba real con los tres motores y bitácora

Esta tarea es manual: necesita la máquina de Aldo, sus sesiones de agy y Claude
Code, y una clave de API válida.

**Files:**
- Create: `docs/bitacora-<fecha de la prueba>.md` (o agregar una sección a la bitácora del día si ya existe)
- Los snippets de prueba van **fuera del repo**, en `%TEMP%\phonexi-review\`

**Interfaces:**
- Consumes: los prompts de la Task 1 a través del flujo normal (`python main.py` y `python main.py -cli`).
- Produces: nada en código.

- [ ] **Step 1: Revisar el modelo de visión de la API**

La bitácora del 5 de octubre anota que `.env` tiene `GROQ_MODEL_VISION=qwen/qwen3.6-27b`,
que ya no existe (404). Antes de probar la API, arrancar con `python main.py -model`
y elegir un modelo con `vision` (Gemini o un modelo de Groq vigente), o corregir `.env`.

- [ ] **Step 2: Crear los cuatro snippets en `%TEMP%\phonexi-review\`**

`a_correct.py`: correcto, se espera `==Correct==`.

```python
def is_palindrome(x: int) -> bool:
    """Return True if x reads the same backwards."""
    if x < 0:
        return False
    s = str(x)
    return s == s[::-1]
```

`b_bug.py`: bug de límite, se espera `==Bug==` con la entrada `nums=[5], target=5` o una equivalente.

```python
def binary_search(nums: list[int], target: int) -> int:
    """Return the index of target in the sorted list nums, or -1."""
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
```

`c_stub.py`: plantilla vacía, se espera que **resuelva** con el formato de siempre (plantilla de seis secciones en `-cli`).

```python
# Two Sum: given an array nums and a target, return the indices of the
# two numbers that add up to target. Exactly one solution exists.
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        pass
```

`d_print.py`: pregunta explícita, se espera la salida `[0, 2, 4]` y no un veredicto.

```python
# ¿Qué imprime este código?
print([i * 2 for i in range(3)])
```

- [ ] **Step 3: Capturar cada snippet con cada motor**

Abrir cada archivo en el editor y presionar `Right Shift + P` con:
1. `python main.py`: la API elegida en el Step 1.
2. `python main.py -cli`, fila `agy` (Gemini 3.8 Flash, effort por defecto).
3. `python main.py -cli`, fila `claude` (Claude Code).

Son 12 respuestas. Para cada una anotar:
- ¿Cayó en la rama correcta? (A y B revisión, C solución, D salida)
- En B, ¿nombró la línea del `while` y dio una entrada que lo rompe?
- En `-cli`, ¿salieron los cuatro encabezados en orden, y `# Issues` / `# Fix` solo en B?
- Tiempo aproximado hasta la respuesta completa.
- Puntos 3 y 5 del Review Focus: cómo escribió el veredicto (idioma).

- [ ] **Step 4: Ajustar el prompt solo si una rama falla**

Si un motor cae en la rama equivocada (sobre todo en C), ajustar el texto de
`_REVIEW_INTRO` siguiendo TDD: primero una prueba que fije la frase nueva, verla
fallar, cambiar el prompt, suite completa y repetir el caso que falló. Un commit
`fix: ...` por ajuste.

- [ ] **Step 5: Escribir la bitácora**

Seguir el estilo de `docs/bitacora-2026-10-05.md`: qué se hizo, cómo quedó en el
código, la tabla de resultados del Step 3 y las trampas encontradas.

- [ ] **Step 6: Commit**

```bash
git add docs/bitacora-<fecha>.md
git commit -m "docs: log the code-review capture test"
```
