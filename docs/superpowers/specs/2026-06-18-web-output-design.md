# Phonexi — Salida web (`-w` / `--web`)

## Problema

El popup tkinter aparece en la pantalla. En entrevistas donde la empresa pide
**compartir pantalla** o donde solo hay **un monitor**, ese popup queda expuesto.

Solución: un flag `-w`/`--web` que, en vez de abrir el popup, sirve las
respuestas en un **servidor local**. El usuario las lee en su **celular**
(misma red WiFi), escaneando un **QR ASCII** que se imprime en la terminal al
arrancar. Nada aparece en la pantalla compartida.

Los hotkeys no cambian: `RShift+P` (screenshot), `RAlt+P` (audio toggle), `Esc`.

## Alcance

- Flag `-w`/`--web`. Mutuamente excluyente con el popup: en modo web no se crea
  ninguna ventana tkinter.
- `--primary` se ignora en modo web (no aplica sin monitor).
- Salida idéntica en contenido al popup: markdown + syntax highlighting.

Fuera de alcance (YAGNI): autenticación, HTTPS, múltiples sesiones, historial
persistente, acceso desde fuera de la LAN.

## Arquitectura

### Flag y arranque (`main.py`)

`main.py` se ramifica según `args.web`:

- **Modo web:**
  1. Construye `WebServer`, lo arranca en thread daemon.
  2. Detecta IP LAN; imprime QR ASCII de `http://<ip-lan>:<puerto>` + las URLs
     (`http://<ip-lan>:<puerto>` y `http://localhost:<puerto>`).
  3. Corre el `HotkeyListener` en el thread principal (bloqueante). Sin tkinter.
- **Modo popup (default):** igual que hoy (tk root + mainloop).

### Componentes

**`phonexi/webserver.py` (nuevo)**

- `WebServer` — envuelve `http.server.ThreadingHTTPServer`.
  - `GET /` → sirve la página HTML (string embebido): tema oscuro, JS abre
    `EventSource('/events')` y renderiza con marked.js + highlight.js (CDN).
  - `GET /events` → respuesta `text/event-stream` (SSE). Mantiene la conexión
    abierta; al conectar un cliente nuevo le manda el último estado guardado.
  - Broadcast thread-safe: una `queue.Queue` por cliente conectado. Métodos para
    publicar eventos (`publish(event_type, payload)`) que encolan en todos los
    clientes y guardan el último evento.
  - Selección de puerto: intenta 8000, luego 8001–8010; reporta el usado.
- `WebView` — objeto ligero que el listener usa con la **misma interfaz** que
  `ResultWindow`:
  - `show_status(msg)` → `publish("status", {"text": msg})`
  - `show_and_collect(iterator)` → consume el iterator, junta el texto completo,
    `publish("response", {"markdown": full})`, devuelve el string.
  - `show_error(msg)` → `publish("error", {"text": msg})`
  - `close()` → no-op (el server persiste; no hay ventana que destruir).

**`phonexi/listener.py` (refactor mínimo)**

- Hoy instancia `ResultWindow(self._tk_root, ...)` directo y en `_close_current`
  hace `self._current_window._win.destroy()`.
- Cambio: el listener recibe un `view_factory` (callable que devuelve una vista
  nueva). 
  - Tk: `lambda: ResultWindow(root, use_primary)`.
  - Web: `lambda: WebView(server)`.
- `_close_current()` llama `view.close()`.
- Se agrega `close()` a `ResultWindow` que hace `self._win.destroy()`.
- Ambas vistas cumplen: `show_status` / `show_and_collect` / `show_error` /
  `close`.
- El listener marshalea sus callbacks vía `_schedule(fn, *args)`: con tkinter
  usa `tk_root.after(0, ...)` (igual que hoy); sin tkinter (web, `tk_root=None`)
  llama `fn(*args)` directo (el `WebServer` ya es thread-safe). Reemplaza todos
  los `self._tk_root.after(0, ...)` actuales.

### Detección de IP LAN

Función `lan_ip() -> str`: abre un socket UDP a un destino externo (sin enviar
datos) y lee `getsockname()[0]`. Si falla, devuelve `"localhost"` con warning.

## Flujo de datos (eventos SSE)

Formato por evento: `event: <tipo>\ndata: <json>\n\n`

| Evento     | Payload                       | Cuándo |
|------------|-------------------------------|--------|
| `status`   | `{"text": "🎙 Listening..."}` | inicio captura / "Analyzing..." / pregunta transcrita (`❓ ...`) |
| `response` | `{"markdown": "<respuesta>"}` | respuesta completa del LLM |
| `error`    | `{"text": "<mensaje>"}`       | error Groq / captura / etc. |

Nota: la pregunta transcrita (modo audio) llega como evento `status` —
el listener ya la enruta por `show_status`, no se agrega un evento separado.

El cliente JS escucha cada tipo y actualiza el DOM. `response` se renderiza con
marked.js (markdown) + highlight.js (código, tema oscuro tipo Dracula).

**Estado y reconexión:** el server guarda el último evento publicado. Un cliente
que conecta tarde (o reconecta tras caída de WiFi) recibe ese último estado al
abrir `/events`. `EventSource` reconecta automáticamente.

## Manejo de errores

- Puerto 8000 ocupado → intenta 8001–8010; si todos fallan, error claro y salida.
- IP LAN no detectable → `localhost` + warning (QR apuntará a localhost).
- Errores Groq existentes (`GroqNotConfiguredError`, `GroqAPIError`, genéricos)
  → evento `error` al celular (mismo mapeo que hoy al popup).

## Tests (pytest, TDD)

- Formato de evento SSE: prefijos `event:` / `data:`, terminación doble `\n`,
  payload JSON válido.
- Broadcast: un evento publicado llega a las colas de múltiples clientes.
- Estado: un cliente nuevo recibe el último evento guardado al conectarse.
- `WebView.show_and_collect`: consume el iterator, junta el texto, emite
  `response`, devuelve el string completo.
- `WebView` cumple la interfaz (`show_status`/`show_error`/`close` sin reventar).
- `lan_ip()`: devuelve IP válida; fallback a `localhost` si el socket falla.
- Selección de puerto: salta al siguiente si el primero está ocupado.
- Tests tkinter actuales: intactos.

## Dependencias

- Nueva: `qrcode>=7.4` (modo ASCII en terminal, sin Pillow).
- Stdlib: `http.server`, `socketserver`, `json`, `socket`, `queue`, `threading`.
- Cliente: marked.js + highlight.js vía CDN.
