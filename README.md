# 🧾 BillEase — Gestión de Facturas para Autónomos

> Aplicación de escritorio sencilla, moderna y pensada para que cualquier autónomo pueda gestionar sus facturas, presupuestos y clientes sin complicaciones.

---

## 📌 ¿Qué es BillEase?

**BillEase** es una aplicación de escritorio desarrollada en **Python** con interfaz gráfica **PyQt6** y base de datos **SQLite**.

Está diseñada para autónomos que necesitan una herramienta ligera y fácil de usar para:

- Tener sus datos **cifrados**: el fichero no se puede leer sin su contraseña
- Registrar y gestionar sus clientes
- Crear y editar facturas y presupuestos profesionales
- Escribir cada concepto con su cantidad, su unidad y su precio
- Saber qué está cobrado y qué queda por cobrar
- Sacar el **resumen de IVA de cada trimestre** para el modelo 303
- Ver cómo queda una factura **antes** de generarla
- Que cada PDF caiga solo en su carpeta, sin elegirla cada vez
- Exportar facturas en **PDF** y los datos en **CSV** para la gestoría

No requiere conexión a internet, ni servidores externos. Todo queda guardado localmente en tu ordenador.

---

## 💻 Requisitos del sistema

| Requisito | Versión mínima |
|-----------|---------------|
| Python    | 3.11 o superior |
| Sistema operativo | Windows, macOS o Linux |

---

## ⬇️ Descargar el programa ya hecho

Si solo quieres **usar** BillEase en un ordenador con Windows, no hace falta instalar
Python ni clonar nada:

1. Entra en la pestaña **Actions** del repositorio y elige **Windows** en la lista de
   la izquierda.
2. Abre la última ejecución con el círculo verde y baja hasta **Artifacts**:
   - **BillEase-instalador** — el instalador, para dejarlo instalado como cualquier
     otro programa.
   - **BillEase-portable** — la carpeta suelta, para llevarla en un pendrive y abrir
     `BillEase.exe` sin instalar nada.
3. GitHub te lo da en `.zip`. **Descomprímelo antes de ejecutarlo**: desde dentro del
   zip, Windows no deja.

Lo construye una máquina Windows de GitHub en cada cambio, con las pruebas pasadas
antes. También se puede lanzar a mano con el botón **Run workflow**.

> Windows SmartScreen avisará la primera vez («Windows protegió tu PC»): el ejecutable
> no está firmado con un certificado, que cuesta dinero y hay que renovar cada año.
> *Más información* → *Ejecutar de todas formas*. Es el aviso que sale con cualquier
> programa sin firmar, no un problema del programa.

Para publicar una versión con enlace permanente, basta con una etiqueta:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

y los dos ficheros quedan colgados en **Releases**.

---

## ⚙️ Instalación para desarrollar

### 1. Clona el repositorio

```bash
git clone https://github.com/Kronos8610/BillEase.git
cd BillEase
```

### 2. Crea el entorno e instala las dependencias

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
```

> Las versiones están fijadas en `requirements.txt`. SQLite viene incluido con Python.

### 3. Ejecuta la aplicación

```bash
python main_start.py
```

La primera vez que arranques la aplicación, se mostrará un formulario de **configuración inicial** donde introducirás tus datos como autónomo (nombre, NIF, dirección, etc.). Esta información aparecerá en todas tus facturas.

### 🔐 ¿Están seguros los datos?

Sí, con dos matices que conviene decir claros.

**Lo que protege.** La base de datos se cifra con **AES-256-GCM**, y la clave que
la abre está envuelta con tu contraseña usando **Argon2id**. Con BillEase cerrado,
en el disco solo hay un fichero del que no se puede sacar ni un NIF: ni con un
visor de SQLite, ni copiándolo a otro ordenador, ni rescatándolo de un disco
viejo. Mientras el programa está abierto, la base vive **en memoria**; nunca se
escribe una copia en claro, ni siquiera temporal.

**Lo que no protege.** Un programa malicioso que corra con tu sesión mientras
tienes BillEase abierto ve los datos, porque en ese momento los estás usando tú.
Contra eso valen el antivirus y el sentido común. Y cifrar no evita *perder*
datos: para eso están las copias de seguridad, que se guardan también cifradas.

**El código de recuperación.** Al cifrar, el programa enseña **una sola vez** un
código de 32 caracteres. Es la única forma de recuperar tus facturas si olvidas
la contraseña: apúntalo en un papel y guárdalo lejos del ordenador. No cambia
aunque cambies la contraseña, así que abre también las copias antiguas.

| | |
|---|---|
| Cifrado | AES-256-GCM (autenticado: si tocan un byte, se nota) |
| Contraseña | Argon2id, 64 MiB · 3 pasadas · 4 hilos |
| Cambiar la contraseña | Instantáneo: se reenvuelve la clave, no se recifran los datos |
| Copias de seguridad | Cifradas también |
| Sacar los datos | Ajustes → «Sacar una copia sin cifrar», previa contraseña |

> **¿Por qué no SQLCipher?** Es la opción habitual, pero no publica ruedas para
> Windows en ninguna versión: habría que compilar una biblioteca en C para poder
> facturar. El cifrado va aquí dentro, con `cryptography` y `argon2-cffi`, que sí
> las publican.

Para comprobarlo tú mismo, sin fiarte del README:

```bash
python tools/verify.py --cifrado    # busca tus datos dentro del fichero cifrado
```

### ¿Dónde se guardan los datos?

La base de datos vive en la carpeta de datos de tu usuario, no junto al programa:

| Sistema | Ruta |
|---------|------|
| Windows | `%LOCALAPPDATA%\BillEase\billease.db` |
| macOS | `~/Library/Application Support/BillEase/billease.db` |
| Linux | `~/.local/share/BillEase/billease.db` |

Así la aplicación encuentra tus datos la abras desde donde la abras. Si vienes de una
versión anterior, el `BillEase.db` que tuvieras junto al programa se traslada solo la
primera vez (el original se conserva renombrado, no se borra).

Al arrancar se aplican las **migraciones** pendientes, guardando antes una copia de
seguridad con la fecha en el nombre. La variable de entorno `BILLEASE_DB` permite apuntar
a otro fichero, útil para pruebas.

### Generar el ejecutable a mano (Windows)

Lo normal es dejárselo a GitHub —ver «Descargar el programa ya hecho» arriba—, pero
también se construye en tu propia máquina. **Tiene que ser Windows**: PyInstaller no
compila para otro sistema que el suyo, así que desde Linux o macOS no sale un `.exe`.

```bash
pip install pyinstaller
pyinstaller billease.spec          # deja dist\BillEase\BillEase.exe
```

Y para el instalador, con [Inno Setup 6](https://jrsoftware.org/isdl.php):

```bash
iscc installer\billease.iss        # deja installer\Output\BillEase-instalador-1.0.0.exe
```

El instalador copia el programa en «Archivos de programa», que es de solo lectura para el
usuario. **Los datos no van ahí**: viven en `%LOCALAPPDATA%\BillEase\`, así que
desinstalar no borra ninguna factura.

---

## 🗂️ Base de datos de prueba (opcional)

La base de datos **no se versiona**: es un fichero de trabajo, y además guardaría tus
datos reales en el repositorio. Si quieres probar el programa con contenido, genera una
base de demostración con datos ficticios:

```bash
python tools/seed_demo.py
```

Crea la base con 5 clientes y 7 facturas, en el esquema antiguo, y le aplica las
migraciones: los 8 servicios del catálogo acaban convertidos en el texto de cada
concepto. Para empezar de cero, borra el fichero y arranca la aplicación: te pedirá
tus datos de autónomo.

Para medir con una base grande:

```bash
python tools/seed_demo.py --facturas 1000 --forzar
```

Las credenciales de la base de demostración son:

| Campo | Valor |
|-------|-------|
| **Email** | carlos.garcia@billease.es |
| **Contraseña** | Pass1234 |

---

## 📸 Capturas de pantalla

![Vista de Facturas](assets/listado_facturas.png)

> **La interfaz**, siguiendo el lenguaje visual de Windows 11:
>
> - **Navegación lateral** con las tres secciones —Facturas, Presupuestos y Clientes—, con
>   iconos propios y la sección abierta señalada. Se salta con `Ctrl+1`, `Ctrl+2` y `Ctrl+3`.
> - **Buscador** (`Ctrl+F`) que filtra por cualquier columna, sin distinguir mayúsculas ni
>   tildes: *perez* encuentra a *Pérez*.
> - **Tabla** que ordena por cualquier columna —los importes como importes y las fechas como
>   fechas— y que pinta igual de rápido con siete facturas que con mil.
> - **Barra de acciones** que solo ofrece lo que se puede hacer con la fila elegida.

Los presupuestos llevan su estado en una píldora de color, y se convierten en factura de
un clic:

![Vista de Presupuestos](assets/listado_presupuestos.png)

El tema sigue al de Windows, y se puede cambiar a mano desde la propia navegación:

![La misma pantalla en tema oscuro](assets/listado_facturas_oscuro.png)

---


## 🚀 ¿Qué incluye la aplicación?

### 🏠 Panel principal
Listado de facturas, presupuestos y clientes, con búsqueda, orden por columna y las
acciones de cada documento: generar el PDF, editarlo, cambiar el estado de un presupuesto,
facturarlo o borrarlo.

### 🏗️ Dirección de la obra
Cada factura y cada presupuesto llevan **dónde se hace el trabajo**, que no
tiene por qué ser la dirección del cliente: se le factura a la oficina una obra
hecha en otra calle. En el documento sale entre los datos de las partes y los
conceptos, que es donde se busca.

### 🏦 Dónde se cobra
Tu **entidad e IBAN** salen impresos debajo del total, **solo en las facturas**
—un presupuesto todavía no se cobra—. El IBAN se comprueba con su dígito de
control antes de guardarlo: uno mal escrito no se nota hasta que el banco
devuelve el dinero.

### 📄 Crear factura
Formulario completo para crear facturas. Selecciona un cliente existente y **escribe
cada concepto**: la descripción entera del trabajo, su cantidad, su unidad (ud, h, m²…)
y su precio. El total se calcula mientras escribes, con IVA desglosado. No hay catálogo
que rellenar antes: el programa sugiere lo que ya has escrito otras veces, pero nunca
obliga a elegir de una lista.

![Crear factura](assets/crear_factura.png)

### 👤 Crear cliente
Registro de clientes con soporte para **persona física** (NIF) y **persona jurídica** (CIF), con validación automática del formato fiscal español.

![Crear cliente](assets/crear_cliente.png)

### 📝 Presupuestos
Presupuestos con su propia serie (`P-2025-001`) y sus estados —borrador, enviado,
aceptado, rechazado—. No caducan solos: una oferta sigue en pie hasta que alguien
la acepta, la rechaza o la borra. Un presupuesto aceptado se convierte en factura
con un clic: copia los conceptos y le asigna su número de la serie de facturación.


### ✏️ Editar factura
Permite modificar cualquier factura existente: cambiar el cliente, la fecha, los conceptos y las cantidades.

Las ventanas de crear factura, presupuesto y cliente se **maximizan**: con el botón de
la barra de título, con doble clic en ella o con **F11**. Con veinte conceptos en
pantalla se agradece. Se abren ya grandes —la de cliente con los campos y las
etiquetas a cuerpo mayor, que no hay que leerla con lupa— y el contenido no se estira
sin fin aunque la pantalla sea enorme: se queda centrado y legible.

### 🔑 Acceso y contraseña
El programa pide la contraseña al abrir, y esa misma contraseña descifra los
datos. Tras tres intentos fallidos hay que esperar, y la espera crece. Si la
olvidas, el código de recuperación entra y te deja poner una nueva.

### 👁 Vista previa
Enseña el documento tal y como va a salir impreso, sin tener que generarlo, buscar el
fichero y abrirlo con el lector de PDF. Está en la barra de la lista, antes de «Generar
PDF», y también en **Ctrl+P**.

Lo que se ve **es** el PDF, no un dibujo parecido: se maqueta el fichero de verdad y se
pinta con el motor de PDF de Qt, así que no hay dos maquetadores que puedan discrepar.
Se pasan páginas, se acerca y se aleja, y desde la propia ventana se guarda —el mismo
fichero que estabas mirando, copiado, no vuelto a generar—.

El PDF temporal se borra al cerrar la ventana. Lleva dentro el NIF del cliente y lo que
se le cobra, y eso no se queda en la carpeta temporal después de echar un vistazo.

![Vista previa](assets/vista_previa.png)

### 📥 Exportar a PDF
Genera el PDF de cualquier factura o presupuesto con los datos del emisor, del cliente,
la dirección de la obra, el desglose de conceptos, la base, el IVA y el total. Si has
puesto logotipo, encabeza el documento.

No lleva fechas de plazo: ni vencimiento en la factura ni validez en el presupuesto.

El papel va a dos tintas: la oscura hace la estructura y el teja resalta lo que se busca
—el total, la obra, el rótulo del cliente—. Las filas alternas van tintadas para que el
ojo siga el renglón hasta el importe, y el total va en una pastilla de color, que es la
cifra que se mira al coger la hoja. El color está en filetes y en una sola pastilla, así
que gasta poco tóner y la factura se sigue leyendo entera impresa en blanco y negro.

Debajo del total, solo en las facturas, van la entidad y el IBAN de **Ajustes → Mis
datos**: el cliente sabe a dónde transferir sin tener que preguntarlo. Un presupuesto no
los lleva, porque todavía no se cobra: lleva «SIN VALOR CONTABLE» debajo del rótulo.

![Factura en PDF](assets/factura_pdf.png)

### 📊 Resumen trimestral de IVA
Lo facturado y el IVA repercutido de cada trimestre y del año entero, que es lo que pide
el modelo 303. Los presupuestos quedan fuera: una oferta no es un ingreso. Se exporta a
CSV para mandárselo a la gestoría.

![Resumen trimestral](assets/resumen_trimestral.png)

### 💶 Estados de cobro
Cada factura dice si está **cobrada** o **pendiente**, y nada más. Aquí no se trabaja
con plazos de vencimiento: una factura no cambia de estado porque pase el tiempo, solo
cuando dices que ha entrado el dinero. Y se puede deshacer, porque un recibo devuelto
existe.

### ⚙️ Ajustes: mis datos, logotipo, carpetas, copias y exportación
Tus datos de emisor —incluidos la entidad y el IBAN— se corrigen aquí: hasta ahora
una errata en el NIF obligaba a empezar de cero. Además, tu logotipo en el papel,
una copia de seguridad al cerrar —y cuando quieras—, y la exportación a CSV de
documentos, conceptos y clientes. Restaurar una copia guarda antes lo que hubiera,
así que equivocarse no es un camino de ida.

**Dónde se guardan los PDF**: una carpeta para las facturas y otra para los
presupuestos. Al generar el PDF va derecho a la suya, con su número de nombre y sin
preguntar nada. Si ya hay un fichero con ese nombre, pregunta antes de pisarlo; si la
carpeta ha dejado de existir —un disco externo sin poner—, lo dice y pregunta dónde
guardar, sin tocar el ajuste. Dejando una en blanco se sigue preguntando cada vez,
como antes.

![Carpetas de los PDF](assets/carpetas_pdf.png)

![Ajustes](assets/ajustes.png)

---

## 🗃️ Estructura del proyecto

```
BillEase/
├── main_start.py        # Punto de entrada de la aplicación
├── requirements.txt     # Dependencias con versiones fijadas
├── tools/               # Utilidades de desarrollo
│   ├── seed_demo.py     # Genera una base de datos de demostración
│   ├── baseline.py      # Congela el inventario de referencia
│   ├── verify.py        # Verifica los invariantes de la base
│   ├── check_contraste.py  # Ningún texto por debajo de 4,5:1 (WCAG)
│   ├── check_estilos.py    # Una sola hoja de estilos, ningún emoji
│   └── inventario.py    # Lectura del inventario (compartido)
├── docs/                # Auditoría, rediseño y ruta de trabajo
├── tests/               # Pruebas automáticas
├── core/                # Dominio: sin Qt y sin SQL
│   ├── models.py        # Documento, Linea, Cliente, Autonomo
│   ├── money.py         # Aritmética con Decimal
│   ├── taxes.py         # Base, IVA y total: el único cálculo
│   ├── numbering.py     # Serie fiscal por ejercicio
│   ├── quotes.py        # Presupuestos y su conversión en factura
│   ├── cobros.py        # Cobrada o pendiente
│   ├── reports.py       # Resumen de IVA por trimestre y por año
│   ├── cifrado.py       # AES-256-GCM + Argon2id, sin saber de SQL
│   ├── fechas.py        # ISO en la base, formato español en pantalla
│   ├── security.py      # Contraseña cifrada con Argon2
│   └── validators/      # NIF, NIE, CIF, teléfono, CP, IBAN
├── data/                # Único sitio con SQL
│   ├── connection.py    # Una conexión, con claves ajenas activadas
│   ├── schema.py        # Esquema de partida
│   ├── backup.py        # Copias de seguridad, con la API de copia de SQLite
│   ├── caja.py          # La base cifrada: en memoria mientras se usa
│   ├── migrations/      # 001 … 010
│   └── repositories/    # documentos, clientes, autonomo
├── documents/
│   ├── invoice_pdf.py   # Factura y presupuesto, sin Qt
│   ├── armado.py        # De la base al diccionario que pide el PDF
│   └── export_csv.py    # CSV para Excel en español
├── ui/                  # Pantallas
│   ├── shell.py         # Ventana principal y navegación lateral
│   ├── iconos.py        # Los iconos, en SVG propio (ya no hay emojis)
│   ├── models/          # QAbstractTableModel: listados y búsqueda
│   ├── views/           # listado · documento_editor · cliente_editor · registro
│   │                    # resumen · ajustes · acceso · seguridad · vista_previa
│   └── widgets/         # concepto.py (sugerencias) · pildora.py (estados)
│                        # ventana.py (maximizar y ancho máximo)
├── theme/               # Todo el color, en un sitio
│   ├── tokens.py        # Paleta clara y oscura, sin dependencias
│   └── app.qss          # Una hoja de estilos, no 84 llamadas sueltas
├── .github/workflows/
│   └── windows.yml      # Construye el .exe y el instalador en GitHub
├── billease.spec        # Receta de PyInstaller
└── installer/
    └── billease.iss     # Instalador para Windows (Inno Setup)
```

---

## 🛠️ Tecnologías utilizadas

| Tecnología | Uso |
|------------|-----|
| **Python 3** | Lenguaje principal |
| **PyQt6** | Interfaz gráfica de escritorio |
| **SQLite** | Base de datos local |
| **ReportLab** | Generación de PDFs |
| **Qt PDF** | Pintar la vista previa en pantalla |

---

## 🧰 Desarrollo

```bash
python tools/seed_demo.py                 # base de demostración con datos ficticios
python tools/seed_demo.py --sin-migrar    # …en el esquema original, para probar migraciones
python -m data.migrations --dry-run       # qué migraciones faltan
python -m data.migrations                 # aplicarlas (deja copia de seguridad)
python tools/verify.py --totales --post-migracion
python tools/verify.py --pintar           # 1.000 facturas: cuánto tarda el listado
python tools/verify.py --fiscal --copia   # el IVA cuadra y la copia se restaura
python tools/verify.py --cifrado          # nada legible sin la contraseña
python tools/check_contraste.py           # legibilidad de los dos temas
python tools/check_estilos.py             # una sola hoja de estilos, ningún emoji
pytest                                    # pruebas automáticas
```

`tools/verify.py` compara la base contra `tests/fixtures/baseline.json` y devuelve 0 si
todo está en verde. Es la puerta de verificación que usa cada fase del plan de trabajo.

**Documentación técnica** — en [`docs/`](docs/):

| Documento | Contenido |
|---|---|
| [`ANALISIS.md`](docs/ANALISIS.md) | Auditoría del código: 16 defectos verificados |
| [`RUTA.md`](docs/RUTA.md) | Plan de trabajo en 7 fases con sus verificaciones |
| [`rediseno-fluent.html`](docs/rediseno-fluent.html) | Propuesta de rediseño de la interfaz |

---

## 🔮 Futuras mejoras

> Estas mejoras están planificadas y ordenadas en [`docs/RUTA.md`](docs/RUTA.md).

Estas son algunas funcionalidades que se plantean incorporar en próximas versiones de BillEase:

### 🔒 Seguridad y cifrado de datos
- ~~Cifrado de la base de datos local~~, ~~contraseña con hash~~ y ~~acceso protegido~~ — **ya disponibles**
- Bloqueo automático tras un rato sin usar el programa
- Registro de accesos y de cambios en documentos emitidos

### 🔍 Búsqueda y filtros
- ~~Buscador en tiempo real~~ y ~~ordenación de columnas~~ — **ya disponibles**
- Filtros por fecha, importe, estado o tipo de cliente

### 🎨 Personalización de la interfaz
- ~~Modo claro y modo oscuro~~ — **ya disponible**, siguiendo al tema de Windows
- Selección del color de acento
- Posibilidad de cambiar el tamaño de fuente de la aplicación
- Guardado automático de las preferencias visuales del usuario

### 👤 Ajustes de usuario
- ~~Perfil del autónomo editable~~, ~~cambio de contraseña~~ y ~~logotipo propio~~ — **ya disponibles**
- Varios perfiles de emisor para quien factura con más de una actividad

### 📊 Estadísticas e informes
- ~~Resumen trimestral y anual de facturación~~ y ~~exportación a CSV~~ — **ya disponibles**
- Panel de estadísticas con gráficos de ingresos por mes

### 📄 Mejoras en la generación de PDF
- ~~Logotipo del autónomo en la cabecera~~ y ~~numeración automática `2025-001`~~ — **ya disponibles**
- ~~Número de cuenta bancaria en la factura~~ y ~~dirección de la obra~~ — **ya disponibles**
- Plantillas de diseño seleccionables para las facturas (hoy hay una, a dos tintas)

### 📧 Envío de facturas
- Envío directo de facturas por email desde la aplicación
- Historial de facturas enviadas por correo

### 🗄️ Gestión avanzada de datos
- ~~Copias de seguridad automáticas~~ y ~~facturas cobradas / pendientes~~ — **ya disponibles**
