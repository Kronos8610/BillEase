# Radiografía de BillEase

> Auditoría técnica del repositorio y propuesta de mejora: organización de ficheros,
> optimización y rediseño de interfaz.
> Informe visual completo (con maquetas del rediseño): [`radiografia-billease.html`](radiografia-billease.html)

**Alcance revisado:** 3.987 líneas de Python, 11 módulos, 5 tablas SQLite.
Todos los defectos están reproducidos contra la base de datos de ejemplo incluida en el repositorio.

| Métrica | Valor |
|---|---|
| Líneas de código | 3.987 |
| Líneas de QSS embebido (84 llamadas a `setStyleSheet`) | 981 — **24 % del proyecto** |
| Funciones en `db.py` que abren su propia conexión | 22 |
| Importaciones locales dentro de funciones | 20 |
| Tests automáticos | 0 |

---

## 1. Cómo funciona hoy

```
main_start.py
   └─ ¿existe BillEase.db?
        ├─ NO → ui/login_ui.RegisterWindow  (alta del autónomo + CREATE TABLE)
        └─ SÍ → ui/aplication.MainWindow    (sin pantalla de acceso)
                 └─ QStackedWidget con 4 páginas instanciadas de golpe
                      homePage · crearFactura · crearCliente · crearServicio
                      + editarFactura (QDialog modal)
                           └─ database/db.py → SQLite
```

**Tres observaciones estructurales:**

1. **El arranque decide por un fichero con ruta relativa.** Ejecutar la aplicación desde
   otra carpeta crea una base de datos nueva y vacía sin avisar.
2. **No hay sesión.** El README publica unas credenciales, pero `db.login()` no se invoca
   desde ningún sitio del proyecto. La contraseña se guarda en texto plano.
3. **No hay capa entre la interfaz y el SQL.** Los widgets desempaquetan tuplas por índice
   (`cliente[2]` es el nombre, `cliente[6]` el NIF), así que añadir una columna a una tabla
   rompe pantallas que no se tocaron.

Funciones de `db.py` sin una sola llamada en el resto del proyecto:
`login`, `obtener_datos_autonomo` (además rota, ver defecto 07) y `register_cliente`
(duplicado de `agregar_cliente`).

---

## 2. El modelo de datos

| Columna | Tipo declarado | Qué ocurre en la práctica |
|---|---|---|
| `Autonomo.codigo_postal` | `REAL` | `'08001'` se guarda como `8001.0`; el PDF imprime «CP: 28001.0» |
| `Autonomo.telefono`, `Cliente.telefono` | `REAL` | `'+34612345678'` → `34612345678.0`; desaparece el prefijo |
| `Factura.fecha` | `DATE` | Se guarda el texto `'15/01/2025'`; imposible ordenar o filtrar por fecha |
| `Factura.total` | `REAL` | Guarda la **base imponible**, no el total; el PDF imprime base × 1,21 |
| `Factura.Cod_cliente` | `REAL` | Clave ajena en coma flotante apuntando a un `INTEGER` |
| `Detalle_linea.*` | `REAL` | Clave primaria compuesta en `REAL`: números de línea con decimales |
| `Autonomo.contrasena` | `TEXT` | Texto plano |
| `Autonomo` (tabla) | — | Sin clave primaria; nada impide dos autónomos |

**Las claves ajenas están declaradas pero SQLite no las aplica.** Cada conexión nueva arranca
con `PRAGMA foreign_keys = OFF` y el proyecto abre 22 sin activarlo nunca:

```
foreign_keys por defecto: 0
INSERT con Num_Factura=9999 (inexistente):  ACEPTADO    ← línea huérfana admitida
Facturas del cliente 1 antes de borrarlo: 2 → después: 2  ← el ON DELETE CASCADE no se ejecuta
```

---

## 3. Registro de defectos

### Críticos

**01 · El total guardado y el total impreso no coinciden**
`crearFactura.py` · `homePage.py`
`handle_guardar_factura` guarda en `Factura.total` la suma de líneas **sin IVA**;
`generar_factura_pdf` recalcula el subtotal, le añade un 21 % fijo y lo imprime como TOTAL.

```
Nº | total en BD | suma líneas | total del PDF
 7 |      180,00 |      180,00 |        217,80
 6 |      830,00 |      830,00 |       1004,30
 3 |     1420,00 |     1420,00 |       1718,20   ← 298,20 € de diferencia
```

*Arreglo:* columnas `base`, `tipo_iva` e `importe_total` y un único punto de cálculo en el
dominio. El tipo debe ser dato de la línea: hoy no se puede emitir al 10 %, al 4 % ni exento.

**02 · El PDF se sale del papel a partir de ~25 conceptos**
`homePage.py :: generar_factura_pdf`
Dibujo con coordenadas absolutas restando 20 pt por línea, sin `showPage()` intermedio ni
control del margen inferior. Medido con una factura de 30 líneas instrumentando `drawString`:

```
Textos dibujados con coordenada Y NEGATIVA (fuera del papel): 21
Y mínima alcanzada: -243,1
Páginas del PDF resultante: 1
```

Se pierden conceptos **y el cuadro de totales**, y la aplicación anuncia «PDF generado
correctamente». *Arreglo:* `platypus` (`SimpleDocTemplate` + `Table` con `repeatRows=1`).

**03 · Contraseña en claro y base de datos real versionada**
`BillEase.db` está en git con la contraseña sin cifrar (`'Pass1234'`) y con NIF, direcciones,
teléfonos y correos de cinco clientes: datos personales bajo el RGPD en un repositorio público.
*Arreglo:* hash `argon2`/`bcrypt`, sacar el `.db` de git, base real en `%LOCALAPPDATA%\BillEase\`.

**04 · Códigos postales y teléfonos se corrompen al guardarse**
Consecuencia directa de los tipos `REAL`:

```
'08001'        → 8001.0           # Barcelona pierde el cero inicial
'+34612345678' → 34612345678.0    # desaparece el prefijo
en el PDF:  'CP: 28001.0'   'Teléfono: 612345678.0'
```

*Arreglo:* `TEXT` con `CHECK(length(cp)=5)`.

**05 · La numeración de facturas no es una serie fiscal**
El número es el `AUTOINCREMENT` de SQLite: borrar una factura deja un hueco permanente en la
serie (el reglamento de facturación exige numeración correlativa), no hay prefijo ni ejercicio
(`2025-001`) y no queda rastro de lo eliminado. Una factura emitida no se borra: se rectifica.

### Altos

**06 · Los datos del cliente escritos en «Crear Factura» se descartan en silencio**
La sección «Datos del Cliente» son seis campos editables; al guardar sólo se usa
`cliente_datos[0]`, el identificador. Además la factura lee los datos del cliente en vivo,
así que cambiar una dirección reescribe retroactivamente todas sus facturas antiguas.

**07 · `obtener_datos_autonomo()` consulta columnas que no existen**
Pide `CP` y `Tel`; se llaman `codigo_postal` y `telefono`. La excepción se traga con un `print`:

```
Error al obtener datos del autónomo: no such column: CP
resultado: None
```

Sólo pasa desapercibido porque nadie la llama. Patrón general: 22 funciones devuelven
`None`/`False` ante cualquier fallo, así que la interfaz nunca sabe *por qué* algo no se guardó.

**08 · Las fechas son texto `dd/mm/aaaa` sin validar**
Ordenar por fecha ordena alfabéticamente. El resumen trimestral de IVA es imposible.
*Arreglo:* ISO-8601 en base, formato español en pantalla, `QDateEdit` en lugar de
`QLineEdit` + `QCalendarWidget` manual.

**09 · Una conexión por pregunta y N+1 al pintar la lista**

```
Facturas: 7 → conexiones sqlite abiertas: 8
(con 500 facturas serían 501 por cada refresco)
```

*Arreglo:* una conexión por proceso con `row_factory = sqlite3.Row` y un `JOIN`.

**10 · La lista se construye con widgets: no escala**
Cada fila es un `QWidget` con seis hijos y tres hojas de estilo propias. Con 1.000 facturas
son ~7.000 widgets vivos, sin orden, filtro, paginación ni búsqueda.
*Arreglo:* `QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel`.

**11 · El menú lateral es prácticamente ilegible**

```
Texto botones menú   #950952 sobre #66023C    1,49:1   ✘ FALLA (AA pide 4,5:1)
Título «BillEase»    #F3E0EC sobre #66023C   10,18:1   ✔ pasa
```

Además el fondo del menú nunca llega a dibujarse: un `QWidget` plano ignora
`background-color` del QSS salvo que se active `WA_StyledBackground`, de modo que lo que se
ve no es lo que el código pide (se aprecia en la captura del propio README).

**12 · Los validadores rechazan NIF y CIF válidos**

```
NIE  X1234567L (residente extranjero)       → False
CIF  G2866715B (asociación, control letra)  → False
CIF  G28667152 (mismo NIF, control cifra)   → True
Tel  '612 34 56 78' (con espacios)          → False
```

`NIFValidator` sólo acepta «8 dígitos + letra», así que **un cliente con NIE no se puede dar
de alta**. `CIFValidator` obliga a control numérico en los tipos C, D, F, G, J, U y V, cuando
la AEAT admite ahí las dos formas.

### Medios

**13 · El mensaje «no hay elementos» se sale del layout** — `homePage.limpiar_items()`:
`takeAt(0)` saca el contenedor del layout pero no le quita el padre, así que
`if self.no_items_container.parent() is None` nunca es cierta y no se vuelve a añadir.

**14 · Los colores viven en un módulo que importa PyQt6** — `utils/globals.py` define fuentes,
así que importa Qt; como el generador de PDF importa de ahí los colores, generar una factura
arrastra toda la biblioteca gráfica y probarla sin entorno gráfico es imposible.

**15 · 981 líneas de estilo copiadas y pegadas** — 84 `setStyleSheet` con f-strings
multilínea; el bloque del botón rojo de borrar aparece idéntico tres veces en el mismo fichero.

**16 · Higiene del repositorio** — 28 `.pyc` versionados de dos versiones de Python, sin
`.gitignore` (se borró en `01bd34e`), sin `requirements.txt`, sin tests. `test.py` no es una
prueba: **inserta un autónomo ficticio** en la base real. El README documenta un `seed_db.py`
que no existe.

---

## 4. Reorganización de ficheros

La regla: la interfaz no escribe SQL, el dominio no sabe que existe Qt, y el PDF se puede
generar desde una terminal sin pantalla.

```
billease/
├── app.py                 arranque, inyección de dependencias, tema
├── config.py              rutas (%LOCALAPPDATA%)
├── core/                  sin Qt, sin SQL
│   ├── models.py          dataclasses Factura, Cliente, Servicio, Linea
│   ├── numbering.py       serie fiscal por ejercicio
│   ├── taxes.py           IVA, retención IRPF
│   └── validators/        nif.py  cif.py  iban.py
├── data/                  único sitio con SQL
│   ├── connection.py      1 conexión + PRAGMAs (foreign_keys, WAL)
│   ├── migrations/        001_init … 004_iva
│   └── repositories/      facturas.py  clientes.py  servicios.py
├── documents/             sin Qt: testeable
│   └── invoice_pdf.py     platypus + paginación real
├── ui/
│   ├── shell.py           ventana + navegación
│   ├── models/            QAbstractTableModel
│   ├── widgets/           controles compartidos (hoy duplicados 4 veces)
│   └── views/             facturas/  clientes/  servicios/
├── theme/
│   ├── tokens.py          color y espaciado (sin dependencias)
│   └── app.qss            1 hoja, no 84
└── tests/                 pytest + pytest-qt
```

| Movimiento | Efecto |
|---|---|
| Sacar el PDF de `homePage.py` | 952 → ~200 líneas |
| Fusionar crear y editar factura en `InvoiceEditor(modo=…)` | −480 líneas (hoy 1.176 casi idénticas) |
| Repositorios que devuelven objetos, no tuplas | 0 índices mágicos |
| Migraciones numeradas | Corregir los tipos `REAL` sin que nadie pierda su base |
| Núcleo sin Qt | Tests en milisegundos, sin pantalla → CI posible |

---

## 5. Optimización

| Cambio | Cómo | Ganancia |
|---|---|---|
| Conexión única + `row_factory` | Abrir una vez, activar `foreign_keys` y `journal_mode=WAL` | 501 → 1 conexión |
| `JOIN` en el listado | Factura, cliente y suma de líneas en una consulta | N+1 → 1 |
| Índices que faltan | `Factura(Cod_cliente)`, `Factura(fecha)`, `Detalle_linea(cod_servicio)` | 3 índices |
| Modelo/vista | `QTableView` recicla celdas y aporta orden y filtro | 7.000 → ~40 widgets |
| Una hoja de estilo global | Qt reanaliza el QSS en cada `setStyleSheet` | −981 líneas |
| Páginas perezosas | Hoy las 4 pantallas se crean y consultan al arrancar aunque no se abran | arranque −4 consultas |
| Empaquetado | PyInstaller + MSI, base en `%LOCALAPPDATA%` | `.exe` distribuible |

---

## 6. Rediseño de interfaz

> **Decisiones de producto (v2.1).**
> — **Los conceptos se escriben, no se eligen.** Desaparecen el catálogo de servicios, la tabla
>   `Servicio` y la pantalla «Crear Servicio» (238 líneas). Cada línea guarda su propio texto,
>   su cantidad y su unidad (`ud`, `h`, `m²`), de modo que se puede describir un trabajo entero:
>   *«Suministro y montaje de armario empotrado de dos módulos con puerta corredera, acabado en
>   blanco lacado. Medidas 2,00 × 2,40 m…»*. Un `QCompleter` sugiere lo ya escrito, pero nunca obliga.
> — **Sin IRPF.** Los documentos llevan base imponible, IVA y total. La retención queda como
>   casilla opcional en «Mis datos», desactivada de partida.
> — **El papel conserva la plantilla v1** (monocromo y matricial); Fluent se aplica solo a la
>   aplicación.

> **Dirección definitiva: Fluent (Windows 11).** La propuesta v2 está en
> [`rediseno-fluent.html`](rediseno-fluent.html): superficies en capas, esquinas de 8 px,
> Segoe UI Variable y azul de acento, con maquetas de la aplicación en claro y oscuro y de los
> documentos impresos —presupuesto y factura— **sin marcas de agua**.
> Lo que sigue es la primera propuesta (Nothing), que se conserva como registro.

### v1 · Nothing adaptado al escritorio

El lenguaje de Nothing (monocromo, rejilla de puntos, un único rojo, tipografía matricial)
encaja bien con un programa de facturación: es un dominio de cifras y estados, no de color.
**El matiz:** la tipografía de puntos es preciosa en titulares y catastrófica en una tabla de
importes. La propuesta la usa donde brilla y deja los datos en una grotesca legible.

**Principios**

- **Monocromo con un solo acento.** El rojo se reserva para tres cosas: el punto de la marca,
  la sección activa y lo vencido. Si todo es rojo, nada lo es.
- **El punto como unidad.** Rejilla de fondo, iconos geométricos elementales, cifras
  matriciales. Sin emojis: los cuatro actuales (🏠 📄 ➕ 🔧) se ven distintos en cada Windows.
- **La línea antes que la caja.** Hoy todo es una tarjeta blanca redondeada, así que nada
  destaca; aquí separan filetes de 1 px y la caja se reserva para el resumen de la factura.

**Tipografía** — `Doto` (matricial, Google Fonts) para logotipo, números de factura e importes
destacados · `Archivo` o `Segoe UI Variable` para el texto · `JetBrains Mono` con
`tabular-nums` para rótulos, NIF e importes en tabla.

**Paleta y contraste**

| Rol | Hex | Contraste sobre `#0A0A0B` |
|---|---|---|
| Fondo | `#0A0A0B` | — |
| Panel | `#131315` | — |
| Línea | `#232327` | — |
| Apagado | `#8A8A92` | 5,8:1 ✔ |
| Texto | `#F2F2F4` | 17,7:1 ✔ |
| Acento (rellenos, indicadores, cifras grandes) | `#D71921` | 3,8:1 ✔ para su uso (AA pide 3:1) |
| Acento texto pequeño («Vencida») | `#E8393F` | 4,8:1 ✔ |

Frente al **1,49:1** del menú actual.

**Además de la estética:** ancho máximo de contenido ~1.100 px (hoy un campo de código postal
mide 1.400 px en un monitor ancho), un solo desplazamiento vertical en lugar de los dos
anidados de «Crear Factura», estados vacíos con una acción, atajos (`Ctrl+N`, `Ctrl+F`, `Esc`)
y tema claro además del oscuro.

Las tres maquetas —listado de facturas, editor de factura y la factura impresa— están en el
[informe visual](radiografia-billease.html).

---

## 7. Plan de ejecución

**Fase 1 · Parar la hemorragia** (~2 días)
Unificar el cálculo del total (01) y paginar el PDF (02) · sacar `BillEase.db` y
`__pycache__` de git, añadir `.gitignore` y `requirements.txt` · hash de contraseña y base en
`%LOCALAPPDATA%` · migración 001: CP y teléfono a `TEXT`, fechas a ISO, `foreign_keys=ON`.

**Fase 2 · Poner una estructura debajo** (~1 semana)
Nuevo árbol y capa de repositorios con `sqlite3.Row` · `core/` sin Qt (IVA, numeración,
validadores con NIE y CIF corregidos) · fusionar crear/editar factura · primeros tests.

**Fase 3 · Rediseñar** (~1 semana)
`theme/tokens.py` + `app.qss` · `QTableView` con búsqueda, orden y estado de cobro ·
aplicar el lenguaje visual · tema claro y oscuro, atajos, estados vacíos.

**Fase 4 · Lo que hace que se use** (~1 semana)
Resumen trimestral de IVA y anual de ingresos · estados pagada/pendiente/vencida y logotipo
en el PDF · copias de seguridad y exportación CSV · PyInstaller e instalador para Windows.
