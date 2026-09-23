# Ruta de trabajo de BillEase

> Siete fases en orden obligatorio, cada una con su puerta de verificación.
> Versión marcable (guarda el progreso): [`ruta-de-trabajo.html`](ruta-de-trabajo.html)
> Auditoría de partida: [`ANALISIS.md`](ANALISIS.md) · Rediseño: [`rediseno-fluent.html`](rediseno-fluent.html)

---

## Línea base

Cifras de `BillEase.db` tal y como está hoy en el repositorio. **Todas las puertas comparan
contra ellas**: si una migración las mueve, algo se ha perdido.

| | |
|---|---|
| Autónomos | 1 |
| Clientes | 5 |
| Facturas | 7 |
| Servicios | 8 |
| Líneas de detalle | 16 |
| Suma de bases | 3.768,50 € |

Dos invariantes más, que hoy se cumplen:

- La **suma de las líneas coincide con la suma de los totales guardados** (3.768,50 € en ambos casos).
- La serie de facturas va **de la 1 a la 7 sin huecos**.

Y un hecho que hace posible la migración a conceptos en texto libre: **las 16 líneas apuntan a un
servicio que existe**, así que se puede copiar la descripción sin perder nada.

```bat
python tools\baseline.py --escribir     :: → tests/fixtures/baseline.json
python tools\seed_demo.py --salida tests\fixtures\baseline.db
```

El JSON se versiona (son cifras, no datos personales); la base de referencia **no**: se
regenera con `seed_demo.py`, que produce filas idénticas a las de la base original. Así
ningún `.db` vuelve al repositorio. El sha256 del fichero de partida
(`6d8bcf2b41614593…`) queda anotado dentro del JSON como procedencia.

---

## Cinco reglas que no se saltan

1. **Una fase, una rama, un pull request.** Si la fase 2 sale mal se revierte sin arrastrar la 1.
2. **La puerta anterior en verde antes de empezar la siguiente.** Todas las comprobaciones, no «casi todas».
3. **Cada fase deja la aplicación ejecutable.** `python main_start.py` abre, lista facturas y genera un PDF al terminar cualquier fase.
4. **Primero el test, después el arreglo.** Se escribe la prueba que falla, se arregla, la prueba pasa.
5. **La base de datos nunca se toca sin copia.** Toda migración se prueba antes sobre `tests/fixtures/baseline.db` y se ejecuta con `--dry-run` primero.

---

## Fase 0 · Red de seguridad — ≈ 3 h

**Objetivo:** poder medir y poder volver atrás. No se cambia ni una línea de comportamiento.
**Cierra:** defecto 16, y la parte de repositorio del 03.

**Se toca:** `.gitignore` · `requirements.txt` · `tools/inventario.py` · `tools/baseline.py` ·
`tools/verify.py` · `tools/seed_demo.py` · `tests/fixtures/` · `README.md` ·
elimina `__pycache__/`, `BillEase.db` y `test.py` del control de versiones

1. Entorno virtual y `requirements.txt` con versiones fijadas: PyQt6, reportlab, argon2-cffi, pytest, pytest-qt.
2. `.gitignore` de Python y `git rm -r --cached __pycache__ BillEase.db`.
3. `tools/inventario.py` lee el inventario de cualquier base; `tools/baseline.py` lo congela en `tests/fixtures/baseline.json`.
4. `tools/verify.py` comprueba ese inventario contra cualquier base — la herramienta de todas las puertas siguientes.
5. `test.py` se convierte en `tools/seed_demo.py`, que regenera la base de demostración entera con datos ficticios.
6. El README documenta el nuevo arranque (entorno virtual, `requirements.txt`, `seed_demo.py`).

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python tools\baseline.py --escribir
python tools\verify.py                    :: → 8/8 invariantes OK
git ls-files | findstr pycache            :: → sin resultados
git ls-files | findstr BillEase.db        :: → sin resultados
python main_start.py                      :: abre igual que antes
```

**Puerta 0**
- [ ] `pip install -r requirements.txt` instala todo en una máquina limpia
- [ ] `verify.py` da verde sobre la base actual
- [ ] Ni `__pycache__` ni `BillEase.db` aparecen en `git ls-files`
- [ ] `seed_demo.py` regenera una base con las mismas filas que la original
- [ ] La aplicación arranca y genera un PDF como siempre

---

## Fase 1 · Que el papel y la pantalla digan lo mismo — ≈ 2 días

**Objetivo:** cerrar los dos defectos que hoy producen documentos incorrectos, **sin tocar el
esquema** para que la aplicación siga funcionando entera.
**Cierra:** defectos 01 y 02.

**Se toca:** `core/taxes.py` · `documents/invoice_pdf.py` · `tests/test_taxes.py` ·
`tests/test_pdf.py` · `ui/homePage.py`

1. `core/taxes.py`: único sitio donde se calcula base, IVA y total, con `Decimal` y redondeo a dos decimales. Sin Qt, sin SQL.
2. Sacar `generar_factura_pdf` a `documents/invoice_pdf.py` y reescribirlo con `platypus`: `SimpleDocTemplate` + `Table` con `repeatRows=1` y pie «página N de M».
3. La lista muestra Base y Total, ambas calculadas por `core/taxes.py`.
4. El PDF deja de recalcular por su cuenta: recibe los importes ya calculados.

```bat
pytest tests\test_taxes.py -q
::  690,00 al 21 %             → 834,90
::  537,50 al 21 %             → 112,88 de IVA (redondeo hacia arriba)
::  tipos 21 / 10 / 4 / exento → sin excepciones

pytest tests\test_pdf.py -q
::  factura de 40 conceptos    → 2 páginas o más
::  ningún texto con y < 0     → hoy salen 21
::  concepto de 400 caracteres → no se recorta
::  total del PDF == core.taxes

python tools\verify.py --totales          :: → lista y PDF coinciden en las 7
```

**Puerta 1**
- [ ] Las 7 facturas muestran el mismo total en la lista y en el PDF
- [ ] Un PDF de 40 conceptos ocupa varias páginas y ninguno se pierde
- [ ] El cuadro de totales aparece siempre, sea cual sea el número de líneas
- [ ] `homePage.py` ya no contiene código de PDF
- [ ] `pytest` pasa sin PyQt6 instalado

---

## Fase 2 · La base de datos deja de corromper datos — ≈ 3 días

**Objetivo:** migraciones numeradas, reversibles y probadas sobre la copia antes de tocar nada real.
**Cierra:** defectos 04, 05, 08 y el hash del 03.

**Se toca:** `config.py` · `data/connection.py` · `data/migrations/001…006` ·
`core/security.py` · `core/fechas.py` · `database/db.py` · `main_start.py`

> **Ajuste sobre el plan.** La tabla `Servicio` **no** se elimina aquí: las pantallas de
> crear y editar factura todavía la usan, y la regla 3 dice que cada fase deja la
> aplicación ejecutable. La migración 005 da a cada línea su propia descripción —que es
> el cambio de datos— y la fase 4 retira el catálogo cuando ninguna pantalla lo lea.

1. `data/connection.py`: una conexión por proceso con `PRAGMA foreign_keys=ON`, `journal_mode=WAL` y `row_factory = sqlite3.Row`.
2. **001** códigos postales y teléfonos a `TEXT` con `CHECK`.
3. **002** fechas a ISO-8601 (`15/01/2025` → `2025-01-15`).
4. **003** columnas `base`, `tipo_iva`, `importe_total`; el valor actual pasa a `base`.
5. **004** serie fiscal (`serie`, `ejercicio`, `numero`) con índice único; las 7 facturas quedan como 2025-001 … 2025-007.
6. **005** las líneas guardan `descripcion` y `unidad`, copiando el texto del servicio al que apuntaban.
7. **006** contraseña con `argon2`; la base se mueve a `%LOCALAPPDATA%\BillEase\`.

```bat
:: Siempre sobre la copia primero
python -m data.migrations --base tests\fixtures\baseline.db --dry-run
python -m data.migrations --base tests\fixtures\baseline.db
python tools\verify.py --base tests\fixtures\baseline.db --post-migracion
::  ✓ conteos 1 / 5 / 7 / 16 idénticos
::  ✓ suma de bases 3.768,50 €
::  ✓ facturas 2025-001 … 2025-007, sin huecos
::  ✓ 0 líneas con descripción vacía
::  ✓ typeof(cod_postal) = 'text' en las 5
::  ✓ PRAGMA foreign_keys = 1
::  ✗ INSERT de línea huérfana → IntegrityError (debe fallar)

pytest tests\test_migrations.py -q
::  migrar dos veces da el mismo resultado (idempotencia)
::  la contraseña ya no se puede leer en claro
```

> **Riesgo.** Es la única fase que puede perder datos. No se ejecuta sobre la base real hasta que
> la copia migre limpia dos veces seguidas, y la migración guarda `BillEase.db.bak` antes de empezar.

**Puerta 2**
- [ ] La copia migra con los 7 invariantes en verde
- [ ] Migrar dos veces seguidas no cambia nada (idempotente)
- [ ] Una línea huérfana ya *no* se puede insertar
- [ ] «08001» se guarda y se lee como «08001», no como 8001.0
- [ ] Las 16 líneas conservan su descripción tras eliminar `Servicio`
- [ ] La contraseña está hasheada y el acceso sigue funcionando
- [ ] La aplicación arranca contra la base migrada

---

## Fase 3 · Dominio y repositorios, con red de pruebas — ≈ 4 días

**Objetivo:** que la interfaz deje de escribir SQL y de desempaquetar tuplas por índice.
**Cierra:** defectos 07, 09 y 12.

**Se toca:** `core/models.py` · `core/numbering.py` · `core/validators/` · `data/repositories/` ·
elimina `database/db.py`

1. `core/models.py` con *dataclasses*: `Documento`, `Linea`, `Cliente`. Se acabó el `cliente[6]`.
2. `core/numbering.py`: siguiente número de la serie por ejercicio, y anulación en lugar de borrado.
3. Validadores: NIE (X/Y/Z → 0/1/2 antes del módulo 23), CIF con letra de control en los tipos que la admiten, teléfono normalizado antes de validar.
4. `data/repositories/`: un `JOIN` devuelve factura y cliente juntos; adiós al N+1.
5. Las pantallas pasan a llamar a repositorios.

```bat
pytest -q --cov=core --cov=data          :: → cobertura de core ≥ 80 %
::  X1234567L (NIE)           → válido
::  G2866715B (CIF con letra) → válido
::  '612 34 56 78'            → válido tras normalizar
::  anular la última factura  → la serie no reutiliza el número

findstr /s /m "sqlite3" *.py | findstr /v "^data\\"   :: → sin resultados
python tools\verify.py --conexiones      :: → 1 (hoy son 8)
```

**Puerta 3**
- [ ] Cobertura de `core/` por encima del 80 %
- [ ] Se puede dar de alta un cliente con NIE
- [ ] No queda ningún `sqlite3` fuera de `data/`
- [ ] Pintar la lista abre una conexión, no ocho
- [ ] Ninguna pantalla accede a una tupla por índice numérico

---

## Fase 4 · Conceptos en texto libre y presupuestos — ≈ 4 días

**Objetivo:** escribir el trabajo entero en lugar de elegirlo de una lista, y poder emitir
presupuestos que se convierten en factura.
**Cierra:** defecto 06 y la retirada del catálogo.

**Se toca:** `ui/views/documento_editor.py` · `core/quotes.py` · elimina `crearFactura.py`,
`editarFactura.py` y `crearServicio.py`

1. Un único editor `DocumentoEditor(tipo=factura|presupuesto, modo=nuevo|edición)`, que sustituye a las 1.176 líneas casi idénticas de crear y editar factura.
2. Cada concepto es un bloque con descripción larga, cantidad, unidad (ud, h, m²) y precio; importe y total se recalculan al escribir.
3. `QCompleter` con los conceptos ya escritos: sugiere, nunca obliga.
4. Los datos fiscales del cliente pasan a solo lectura y se congelan en el documento al emitirlo.
5. Presupuestos con serie propia, fecha de validez y conversión a factura en un clic.

```bat
set QT_QPA_PLATFORM=offscreen
pytest tests\test_editor.py -q
::  dos conceptos de 1.240,00 y 195,00  → total 1.736,35
::  concepto de 400 caracteres          → se guarda entero
::  editar datos del cliente            → imposible (solo lectura)
::  presupuesto aceptado → factura      → copia líneas y asigna número
::  emitir dos veces seguidas           → números consecutivos

python tools\verify.py --abrir-todas     :: → las 7 facturas se abren y se imprimen
```

**Puerta 4**
- [ ] Se escribe un concepto largo y sale entero en el PDF
- [ ] El total en pantalla coincide con el del PDF al céntimo
- [ ] Las 7 facturas antiguas se abren y se imprimen sin fallo
- [ ] Un presupuesto se convierte en factura con su número de serie
- [ ] Ya no existe ninguna pantalla de servicios

---

## Fase 5 · La interfaz Fluent — ≈ 5 días

**Objetivo:** aplicar el rediseño aprobado sobre una base que ya funciona.
**Cierra:** defectos 10, 11, 13, 14 y 15.

**Se toca:** `theme/tokens.py` · `theme/app.qss` · `ui/shell.py` · `ui/models/` · `ui/widgets/` ·
elimina `utils/globals.py`

1. `theme/tokens.py` sin dependencias (lo usan la interfaz *y* el PDF) y una sola `app.qss`.
2. `QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel`: búsqueda, orden por columna y píldoras de estado.
3. Navegación lateral nueva, con iconos SVG propios en lugar de emojis.
4. Tema claro y oscuro siguiendo al sistema, fondo Mica en Windows 11, atajos `Ctrl+N` / `Ctrl+F` / `Esc`.
5. Ancho máximo de contenido y estados vacíos con una acción.

```bat
python tools\check_contraste.py          :: → todos los pares ≥ 4,5:1 (hoy el menú da 1,49:1)
python tools\check_estilos.py            :: → setStyleSheet ≤ 5 (hoy 84), 0 emojis en ui/

set QT_QPA_PLATFORM=offscreen
pytest tests\test_ui_smoke.py -q

python tools\seed_demo.py --facturas 1000
python tools\verify.py --pintar          :: → < 300 ms y < 100 widgets vivos
```

**Puerta 5**
- [ ] Ningún par de colores por debajo de 4,5:1
- [ ] Menos de 5 llamadas a `setStyleSheet` en todo el proyecto
- [ ] Con 1.000 facturas la lista se pinta al instante
- [ ] La búsqueda y el orden por columna funcionan
- [ ] Tema claro y oscuro, siguiendo al de Windows
- [ ] Cero emojis en la interfaz

---

## Fase 6 · Entrega — ≈ 3 días

**Objetivo:** que sea un programa que se instala, no una carpeta que se ejecuta.

1. Resumen trimestral de IVA y anual de ingresos — ya es posible con las fechas en ISO.
2. Estados de cobro (cobrada, pendiente, vencida) y logotipo propio en el documento.
3. Copia de seguridad automática al cerrar y exportación a CSV.
4. `PyInstaller` + instalador, con la base en `%LOCALAPPDATA%\BillEase\`.

```bat
pyinstaller billease.spec
:: En una máquina limpia, sin Python instalado:
::  instalar → abrir → crear cliente → crear factura → PDF
::  la base aparece en %LOCALAPPDATA%\BillEase\billease.db
::  cerrar y reabrir → los datos siguen ahí
::  resumen del 1.º trimestre → cuadra con la suma manual
```

**Puerta 6**
- [ ] El instalador funciona en una máquina sin Python
- [ ] La base vive en `%LOCALAPPDATA%`, no junto al ejecutable
- [ ] El resumen de IVA cuadra con la suma a mano
- [ ] Hay copia de seguridad automática y se puede restaurar

---

## Resumen

| Fase | Qué cierra | Defectos | Esfuerzo |
|---|---|---|---|
| 0 · Red de seguridad | Poder medir y volver atrás | 16, 03 (repo) | ≈ 3 h |
| 1 · Papel y pantalla | Documentos correctos | 01, 02 | ≈ 2 días |
| 2 · Base de datos | Datos que no se corrompen | 04, 05, 08, 03 | ≈ 3 días |
| 3 · Dominio y repositorios | Arquitectura y pruebas | 07, 09, 12 | ≈ 4 días |
| 4 · Conceptos y presupuestos | Escribir en vez de elegir | 06 | ≈ 4 días |
| 5 · Interfaz Fluent | El rediseño | 10, 11, 13, 14, 15 | ≈ 5 días |
| 6 · Entrega | Instalable | — | ≈ 3 días |

**Total: ≈ 21 días de trabajo efectivo**, con la aplicación utilizable al final de cada fase.
