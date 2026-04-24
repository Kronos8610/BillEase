# 🧾 BillEase — Gestión de Facturas para Autónomos

> Aplicación de escritorio sencilla, moderna y pensada para que cualquier autónomo pueda gestionar sus facturas, clientes y servicios sin complicaciones.

---

## 📌 ¿Qué es BillEase?

**BillEase** es una aplicación de escritorio desarrollada en **Python** con interfaz gráfica **PyQt6** y base de datos **SQLite**.

Está diseñada para autónomos que necesitan una herramienta ligera y fácil de usar para:

- Registrar y gestionar sus clientes
- Crear y editar facturas profesionales
- Mantener un catálogo de servicios con precios
- Exportar facturas en formato **PDF** listas para enviar

No requiere conexión a internet, ni servidores externos. Todo queda guardado localmente en tu ordenador.

---

## 💻 Requisitos del sistema

| Requisito | Versión mínima |
|-----------|---------------|
| Python    | 3.10 o superior |
| Sistema operativo | Windows, macOS o Linux |

---

## ⚙️ Instalación

### 1. Clona el repositorio

```bash
git clone https://github.com/Kronos8610/BillEase.git
cd BillEase
```

### 2. Instala las dependencias

```bash
pip install PyQt6 reportlab
```

> Solo necesitas instalar **dos librerías**. El resto (SQLite, etc.) viene incluido con Python.

### 3. Ejecuta la aplicación

```bash
python main_start.py
```

La primera vez que arranques la aplicación, se mostrará un formulario de **configuración inicial** donde introducirás tus datos como autónomo (nombre, NIF, dirección, etc.). Esta información aparecerá en todas tus facturas.

---

## 🗂️ Base de datos de prueba (opcional)

Si quieres explorar la aplicación con datos ficticios ya cargados, ejecuta:

```bash
python seed_db.py
```

Esto creará una base de datos con clientes, servicios y facturas de ejemplo.

Las credenciales de acceso generadas son:

| Campo | Valor |
|-------|-------|
| **Email** | carlos.garcia@billease.es |
| **Contraseña** | Pass1234 |

---

## 🚀 ¿Qué incluye la aplicación?

### 🏠 Panel principal
Vista general con listado de facturas, clientes y servicios. Permite eliminar registros y acceder rápidamente a todas las funciones.

### 📄 Crear factura
Formulario completo para crear facturas. Selecciona un cliente existente, añade tantas líneas de concepto como necesites eligiendo servicios del catálogo, y el total se calcula automáticamente.

### 👤 Crear cliente
Registro de clientes con soporte para **persona física** (NIF) y **persona jurídica** (CIF), con validación automática del formato fiscal español.

### 🔧 Crear servicio
Catálogo de servicios con descripción, precio y observaciones. Los servicios creados estarán disponibles al generar cualquier factura.

### ✏️ Editar factura
Permite modificar cualquier factura existente: cambiar el cliente, las fechas, los conceptos y las cantidades.

### 📥 Exportar a PDF
Genera un PDF profesional de cualquier factura con los datos del emisor, del cliente, el desglose de conceptos, subtotal, IVA (21%) y total.

---

## 🗃️ Estructura del proyecto

```
BillEase/
├── main_start.py        # Punto de entrada de la aplicación
├── seed_db.py           # Script para generar datos de prueba
├── ui/                  # Pantallas e interfaces gráficas
│   ├── aplication.py    # Ventana principal y menú lateral
│   ├── login_ui.py      # Registro inicial del autónomo
│   ├── homePage.py      # Panel principal y generación de PDF
│   ├── crearFactura.py  # Formulario de nueva factura
│   ├── editarFactura.py # Edición de factura existente
│   ├── crearCliente.py  # Formulario de nuevo cliente
│   └── crearServicio.py # Formulario de nuevo servicio
├── database/
│   └── db.py            # Toda la lógica de base de datos (SQLite)
├── validators/
│   └── Validator.py     # Validadores de formularios (NIF, CIF, email…)
└── utils/
    └── globals.py       # Colores y fuentes globales de la interfaz
```

---

## 🛠️ Tecnologías utilizadas

| Tecnología | Uso |
|------------|-----|
| **Python 3** | Lenguaje principal |
| **PyQt6** | Interfaz gráfica de escritorio |
| **SQLite** | Base de datos local |
| **ReportLab** | Generación de PDFs |

---

## 📄 Licencia

Este proyecto ha sido desarrollado como Trabajo de Fin de Grado (TFG). Uso libre para fines educativos.
