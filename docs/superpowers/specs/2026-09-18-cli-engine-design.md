# Phonexi — Motor CLI local (`--engine`)

> **Estado: idea, pendiente de spike.** El diseño está planteado pero tres
> decisiones dependen de mediciones que todavía no se hacen (ver *Preguntas
> abiertas*). Nada implementado. Escrito el 18 de septiembre de 2026.

## Problema

Phonexi depende de una sola API externa. Todo pasa por Groq: la visión del
screenshot, la transcripción Whisper y la respuesta de texto. Eso implica una
`GROQ_API_KEY`, un límite de 14,400 peticiones al día, y que cada respuesta
sale de un modelo sobre el que no se elige nada más que el nombre.

En la máquina del usuario ya viven agentes de línea de comandos con sesión
propia y suscripción propia: `claude` (Claude Code) y `agy` (Antigravity CLI).
Son más capaces que el modelo del free tier y no consumen cuota de Groq.

## Idea

Dar la opción de que el motor que responde sea un CLI local, **reutilizando
toda la herramienta que ya existe**. No es un modo nuevo ni un flujo nuevo:
son los mismos hotkeys, la misma captura, la misma transcripción y las mismas
vistas. Lo único que cambia es quién contesta.

```
hotkey → screenshot / audio → [ MOTOR ] → vista (popup o web)
         └─ intacto ─┘         ↑           └─ intacto ─┘
                        groq | claude | agy
```

## Por qué encaja sin romper nada

`processor.py` ya dejó la costura hecha: `process()` y `process_text()`
devuelven `Iterator[str]`, y tanto `ResultWindow` como `WebView` consumen eso
en `show_and_collect()`. Cualquier motor que sepa ceder tokens encaja sin que
`listener.py` ni las vistas se enteren — es la misma jugada que ya se hizo con
`view_factory` para el modo web.

## Alcance

- Flag `--engine groq|claude|agy`, con `groq` de default. Combina con `-P`,
  `-w` y `-c` como las demás.
- Capa `phonexi/engines/`, simétrica a la capa `backends/` de la rama
  `linux-port`.
- El motor CLI se amarra para que no actúe como agente: sin herramientas más
  allá de lo mínimo (ver *Riesgos*).
- Los tests cubren el motor CLI con mocks del subproceso, igual que hoy se
  mockea Groq.

Fuera de alcance (YAGNI): descubrir CLIs automáticamente, elegir motor por
hotkey en caliente, fallback automático entre motores, configurar el motor
desde la página web, historial persistente de conversación.

## Arquitectura

```
phonexi/engines/
├── base.py       # Protocol Engine
├── __init__.py   # get_engine("groq" | "claude" | "agy")
├── groq.py       # el código actual de processor.py, movido tal cual
└── cli.py        # maneja el subproceso (claude o agy)
```

### Interfaz

La interfaz es chica porque `processor.py` ya la definió de facto:

```python
class Engine(Protocol):
    def answer_image(self, path: Path, briefing: str | None) -> Iterator[str]: ...
    def answer_text(self, q: str, context, briefing: str | None) -> Iterator[str]: ...
```

`HotkeyListener` recibe el motor inyectado, igual que hoy recibe `view_factory`
y `briefing`. `main.py` resuelve el motor desde el flag antes de registrar los
hotkeys — mismo criterio que `-c`: si el motor no sirve, se sabe al arrancar y
no a media entrevista.

Los errores se vuelven neutrales al proveedor: `EngineNotConfiguredError` y
`EngineError` en lugar de `GroqNotConfiguredError` y `GroqAPIError`.

### Mecánica del motor CLI

Levanta el subproceso en modo no interactivo y lee NDJSON línea por línea,
cediendo cada delta de texto conforme llega:

```
Popen([cli, "-p", prompt, "--output-format", "stream-json"], stdout=PIPE)
  → por cada línea: json.loads → si trae delta de texto → yield
```

### Mapeo de lo que ya existe

| Pieza actual | En el motor CLI |
|---|---|
| `PROMPT` y briefing `-c` | `claude`: `--system-prompt` / `--append-system-prompt`. `agy`: **sin bandera equivalente**, habría que anteponerlos al prompt |
| Screenshot | A Groq se le manda el PNG en base64; al agente se le pasa **la ruta** y él la lee con su herramienta — un viaje extra |
| Follow-ups (`Context`) | Los CLIs traen `--continue` nativo, pero se mantiene `Context` para que ambos motores se comporten igual y el motor siga siendo stateless |
| Transcripción Whisper | Sin resolver — ver *Preguntas abiertas* |

### Banderas verificadas (18 de septiembre de 2026)

- `claude` 2.1.277 — `-p/--print`, `--output-format stream-json`, `--model`,
  `--system-prompt`, `--append-system-prompt`, `--allowed-tools`,
  `--disallowed-tools`, `--continue`, `--resume`.
- `agy` (binario Go) — `-p/--print`, `--output-format`, `--model`,
  `--json-schema`, `--continue`, `--conversation`, `--mode`, `--sandbox`,
  `--agent`. **No se le vio bandera de system prompt.**

## Riesgos

### Son agentes, no chat completions

El riesgo principal. Un CLI de agente puede decidir ejecutar comandos, buscar
en la web o tocar archivos. En una entrevista se quiere una respuesta y nada
más, no que se ponga a explorar. El motor CLI debe arrancar amarrado desde el
primer día: `--disallowed-tools` en `claude` dejando solo lectura para el caso
del screenshot, y `--sandbox` con `--mode` en `agy`.

### Latencia

Phonexi existe para responder en segundos. Cada pregunta levanta un proceso
nuevo, y el screenshot además paga el tool call de leer la imagen. Groq
responde casi al instante; esto puede no hacerlo. Es lo primero que hay que
medir.

### El modo voz puede quedar híbrido

El flujo de voz hace **dos** llamadas a Groq, no una: Whisper transcribe y
luego el LLM responde. Si ningún CLI acepta un `.wav`, Whisper se queda aunque
la respuesta la dé el CLI. Eso sigue siendo útil, pero no es reemplazo total.

## Preguntas abiertas (se resuelven con el spike)

1. **¿El streaming es incremental de verdad?** Si `--output-format stream-json`
   suelta todo al final en vez de ir entregando, `Iterator[str]` sigue
   funcionando pero se pierde la sensación de respuesta viva.
2. **¿La imagen sale a un costo tolerable?** Si no, el modo screenshot se queda
   en Groq y solo el de voz gana la opción CLI.
3. **¿Alguno transcribe `.wav`?** Decide si Whisper se queda o no.
4. **¿Están `claude` y `agy` en la máquina Windows?** Phonexi corre en Windows;
   el diseño se está explorando en una Mac.

## Qué NO cambia

Los hotkeys, `screenshot.py`, `audio.py`, `listener.py`, `ui.py`,
`webserver.py`, el modo web con SSE y QR, el flag `-c` y su validación al
arrancar, y el comportamiento por default: sin `--engine`, Phonexi sigue
usando Groq exactamente como hoy.

## Nota sobre plataformas

`main` es Windows puro: `ctypes.windll` en `screenshot.py` y `pyaudiowpatch`
(WASAPI) en `audio.py`. En macOS el screenshot es adaptable — `mss` soporta
Mac, solo cambia cómo se obtiene la posición del cursor — pero el audio no:
macOS no permite capturar audio del sistema sin un dispositivo virtual tipo
BlackHole. Esa restricción es del sistema operativo, no del código.

Nada de esto bloquea este diseño: la capa de motores es Python puro con
`subprocess`, se escribe y se testea con mocks en cualquier plataforma. Solo
la prueba de punta a punta necesita Windows.
