import sqlite3

def crear_base_de_datos():
    # Conexión a la base de datos (la crea si no existe)
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()

    # Crear tabla Autónomo 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Autonomo (
            DNI            TEXT NOT NULL UNIQUE,
            nombre         TEXT NOT NULL,
            apellido       TEXT NOT NULL,
            direccion      TEXT,
            codigo_postal  REAL,
            telefono       REAL,
            email          TEXT UNIQUE,
            contrasena     TEXT NOT NULL     
        );
    """)

    # Crear tabla Cliente
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Cliente (
            Cod_cliente           INTEGER PRIMARY KEY AUTOINCREMENT,
            TIPO_CLIENTE          BOOLEAN, /* FALSE- JURIDICO, TRUE FISICO*/
            nombre_o_razon_social TEXT NOT NULL,
            direccion             TEXT,
            telefono              REAL,
            cod_postal            TEXT,
            CIFNIF                TEXT NOT NULL UNIQUE,
            observaciones         TEXT,
            email                 TEXT
        );
    """)

    # Crear tabla Factura
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Factura (
            Num_factura    INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha          DATE NOT NULL,
            total          REAL NOT NULL,
            Cod_cliente    REAL NOT NULL,
            observaciones  TEXT,
            FOREIGN KEY (Cod_cliente) REFERENCES Cliente (Cod_cliente) ON DELETE CASCADE
        );
    """)

    # Crear tabla Servicio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Servicio (
            Cod_servicio   INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion    TEXT NOT NULL,
            precio         REAL NOT NULL,
            observaciones  TEXT
        );
    """)

    # Crear tabla Detalle_linea
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Detalle_linea (
            Num_Factura         REAL,
            Num_Linea           REAL,
            NumServicios        REAL NOT NULL,
            precioPorServicio   REAL NOT NULL,
            cod_servicio        REAL NOT NULL,
            PRIMARY KEY (Num_Factura, Num_Linea),
            FOREIGN KEY (Num_Factura) REFERENCES Factura (Num_factura),
            FOREIGN KEY (cod_servicio) REFERENCES Servicio (Cod_servicio)
        );
    """)

    # Confirmar cambios y cerrar conexión
    conn.commit()
    conn.close()
    print("Base de datos 'BillEase.db' creada correctamente con sus tablas.")

def register_autonomo(dni, nombre, apellido, direccion, codigo_postal, telefono, email, contrasena):
    """
    Inserta un nuevo autónomo en la tabla Autonomo.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Autonomo (
                DNI, nombre, apellido, direccion, codigo_postal, telefono, email, contrasena
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (dni, nombre, apellido, direccion, codigo_postal, telefono, email, contrasena))
        conn.commit()
        print("Autónomo registrado correctamente.")
        return True
    except Exception as e:
        print(f"Error al registrar autónomo: {e}")
        return False
    finally:
        conn.close()

def login(email, contrasena):
    """
    Verifica las credenciales de un autónomo en la base de datos.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM Autonomo WHERE email = ? AND contrasena = ?
        """, (email, contrasena))
        usuario = cursor.fetchone()
        if usuario:
            print("Login exitoso.")
            return True
        return False
    except Exception as e:
        print(f"Error en login: {e}")
        return False
    finally:
        conn.close()
def register_cliente(tipo_cliente, nombre_o_razon_social, direccion, telefono, cod_postal, cifnif, observaciones=""):
    """
    Inserta un nuevo cliente en la tabla Cliente.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Cliente (
                TIPO_CLIENTE, nombre_o_razon_social, direccion, telefono, cod_postal, CIFNIF, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tipo_cliente, nombre_o_razon_social, direccion, telefono, cod_postal, cifnif, observaciones))
        cliente_id = cursor.lastrowid
        conn.commit()
        print(f"Cliente {cliente_id} registrado correctamente.")
        return cliente_id
    except Exception as e:
        print(f"Error al registrar cliente: {e}")
        return None
    finally:
        conn.close()

def insertar_factura(fecha, total, cod_cliente, observaciones=""):
    """
    Inserta una nueva factura en la tabla Factura.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Factura (
                fecha, total, Cod_cliente, observaciones
            ) VALUES (?, ?, ?, ?)
        """, (fecha, total, cod_cliente, observaciones))
        factura_id = cursor.lastrowid
        conn.commit()
        print(f"Factura {factura_id} registrada correctamente.")
        return factura_id
    except Exception as e:
        print(f"Error al registrar factura: {e}")
        return None
    finally:
        conn.close()

def insertar_servicio(descripcion, precio, observaciones=""):
    """
    Inserta un nuevo servicio en la tabla Servicio.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Servicio (
                descripcion, precio, observaciones
            ) VALUES (?, ?, ?)
        """, (descripcion, precio, observaciones))
        servicio_id = cursor.lastrowid
        conn.commit()
        print(f"Servicio {servicio_id} registrado correctamente.")
        return servicio_id
    except Exception as e:
        print(f"Error al registrar servicio: {e}")
        return None
    finally:
        conn.close()

def insertar_detalle_linea(num_factura, num_linea, num_servicios, precio_por_servicio, cod_servicio):
    """
    Inserta un nuevo detalle de línea en la tabla Detalle_linea.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Detalle_linea (
                Num_Factura, Num_Linea, NumServicios, precioPorServicio, cod_servicio
            ) VALUES (?, ?, ?, ?, ?)
        """, (num_factura, num_linea, num_servicios, precio_por_servicio, cod_servicio))
        conn.commit()
        print("Detalle de línea registrado correctamente.")
        return True
    except Exception as e:
        print(f"Error al registrar detalle de línea: {e}")
        return False
    finally:
        conn.close()

def obtener_clientes():
    """
    Realiza un SELECT de todos los clientes en la tabla Cliente.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Cliente")
        clientes = cursor.fetchall()
        return clientes
    except Exception as e:
        print(f"Error al obtener clientes: {e}")
        return []
    finally:
        conn.close()

def obtener_facturas_cliente(cod_cliente):
    """
    Obtiene todas las facturas de un cliente específico.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM Factura WHERE Cod_cliente = ?
        """, (cod_cliente,))
        facturas = cursor.fetchall()
        return facturas
    except Exception as e:
        print(f"Error al obtener facturas: {e}")
        return []
    finally:
        conn.close()

def obtener_detalles_factura(num_factura):
    """
    Obtiene todos los detalles de una factura específica.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.*, s.descripcion 
            FROM Detalle_linea d
            JOIN Servicio s ON d.cod_servicio = s.Cod_servicio
            WHERE d.Num_Factura = ?
        """, (num_factura,))
        detalles = cursor.fetchall()
        return detalles
    except Exception as e:
        print(f"Error al obtener detalles de factura: {e}")
        return []
    finally:
        conn.close()

def obtener_todas_facturas():
    """
    Obtiene todas las facturas de la base de datos ordenadas por número de factura descendente.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM Factura
            ORDER BY Num_factura DESC
        """)
        facturas = cursor.fetchall()
        return facturas
    except Exception as e:
        print(f"Error al obtener facturas: {e}")
        return []
    finally:
        conn.close()

def obtener_cliente_por_id(cod_cliente):
    """
    Obtiene los datos de un cliente por su ID.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM Cliente WHERE Cod_cliente = ?
        """, (cod_cliente,))
        cliente = cursor.fetchone()
        return cliente
    except Exception as e:
        print(f"Error al obtener cliente: {e}")
        return None
    finally:
        conn.close()

def agregar_cliente(cifnif, nombre_o_razon_social, direccion, cod_postal, telefono, observaciones, tipo_cliente=True, email=""):
    """
    Agrega un nuevo cliente a la base de datos
    
    Args:
        cifnif (str): NIF o CIF del cliente
        nombre_o_razon_social (str): Nombre o razón social del cliente
        direccion (str): Dirección postal del cliente
        cod_postal (str): Código postal
        telefono (str): Número de teléfono
        observaciones (str): Observaciones adicionales 
        tipo_cliente (bool, optional): True para persona física, False para jurídica
        
    Returns:
        int: ID del cliente añadido o None si falla
    """
    conn = None
    try:
        conn = sqlite3.connect('BillEase.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO Cliente (
                TIPO_CLIENTE,
                nombre_o_razon_social,
                direccion,
                telefono,
                cod_postal,
                CIFNIF,
                observaciones,
                email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tipo_cliente, nombre_o_razon_social, direccion, telefono, cod_postal, cifnif, observaciones, email))
        
        cliente_id = cursor.lastrowid
        conn.commit()
        print(f"Cliente {cliente_id} registrado correctamente.")
        return cliente_id
    except Exception as e:
        print(f"Error al agregar cliente: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()
def obtener_factura_por_id(num_factura):
    """
    Obtiene una factura específica por su ID
    
    Args:
        num_factura (int): ID de la factura a buscar
        
    Returns:
        tuple: Datos de la factura o None si no se encuentra
    """
    import sqlite3
    try:
        conn = sqlite3.connect("BillEase.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM Factura 
            WHERE Num_factura = ?
        """, (num_factura,))
        
        factura = cursor.fetchone()
        conn.close()
        
        return factura
    except Exception as e:
        print(f"Error al obtener factura: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def obtener_todos_servicios():
    """
    Obtiene todos los servicios disponibles en la base de datos.
    
    Returns:
        list: Lista de tuplas con los datos de los servicios (Cod_servicio, descripcion, precio, observaciones)
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Servicio ORDER BY descripcion")
        servicios = cursor.fetchall()
        return servicios
    except Exception as e:
        print(f"Error al obtener servicios: {e}")
        return []
    finally:
        conn.close()

def eliminar_factura(num_factura):
    """
    Elimina una factura y sus detalles de línea asociados de la base de datos.
    
    Args:
        num_factura (int): ID de la factura a eliminar
        
    Returns:
        bool: True si la eliminación fue exitosa, False en caso contrario
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        # Comenzar una transacción
        conn.execute("BEGIN TRANSACTION")
        
        # Primero eliminar los detalles de línea asociados (por la restricción de clave foránea)
        cursor.execute("DELETE FROM Detalle_linea WHERE Num_Factura = ?", (num_factura,))
        
        # Luego eliminar la factura
        cursor.execute("DELETE FROM Factura WHERE Num_factura = ?", (num_factura,))
        
        # Confirmar la transacción
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al eliminar factura: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def eliminar_cliente(cod_cliente):
    """
    Elimina un cliente de la base de datos.
    
    Args:
        cod_cliente (int): ID del cliente a eliminar
        
    Returns:
        bool: True si la eliminación fue exitosa, False en caso contrario
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Cliente WHERE Cod_cliente = ?", (cod_cliente,))
        conn.commit()
        return cursor.rowcount > 0  # Devuelve True si se eliminó al menos una fila
    except Exception as e:
        print(f"Error al eliminar cliente: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def eliminar_servicio(cod_servicio):
    """
    Elimina un servicio de la base de datos.
    
    Args:
        cod_servicio (int): ID del servicio a eliminar
        
    Returns:
        bool: True si la eliminación fue exitosa, False en caso contrario
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Servicio WHERE Cod_servicio = ?", (cod_servicio,))
        conn.commit()
        return cursor.rowcount > 0  # Devuelve True si se eliminó al menos una fila
    except Exception as e:
        print(f"Error al eliminar servicio: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def verificar_servicio_en_uso(cod_servicio):
    """
    Verifica si un servicio está siendo utilizado en alguna factura.
    
    Args:
        cod_servicio (int): ID del servicio a verificar
        
    Returns:
        bool: True si el servicio está en uso, False en caso contrario
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM Detalle_linea 
            WHERE cod_servicio = ?
        """, (cod_servicio,))
        count = cursor.fetchone()[0]
        return count > 0
    except Exception as e:
        print(f"Error al verificar servicio: {e}")
        return True  # Por seguridad, si hay error asumimos que está en uso
    finally:
        conn.close()

def obtener_datos_autonomo():
    """
    Obtiene los datos del autónomo registrado en la base de datos.
    
    Returns:
        tuple: Datos del autónomo o None si no se encuentra
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DNI, Nombre, Apellido, Direccion, CP, Tel, Email FROM Autonomo LIMIT 1")
        autonomo = cursor.fetchone()
        return autonomo
    except Exception as e:
        print(f"Error al obtener datos del autónomo: {e}")
        return None
    finally:
        conn.close()

def actualizar_factura(num_factura, fecha, total, cod_cliente, observaciones=""):
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Factura
               SET fecha = ?, total = ?, Cod_cliente = ?, observaciones = ?
             WHERE Num_factura = ?
        """, (fecha, total, cod_cliente, observaciones, num_factura))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error al actualizar factura: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def reemplazar_detalles_factura(num_factura, detalles):
    """
    Reemplaza todas las líneas de una factura.
    detalles: lista de dicts con keys: cantidad, precio_ud, cod_servicio
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        cursor.execute("DELETE FROM Detalle_linea WHERE Num_Factura = ?", (num_factura,))
        for i, det in enumerate(detalles, 1):
            cursor.execute("""
                INSERT INTO Detalle_linea (Num_Factura, Num_Linea, NumServicios, precioPorServicio, cod_servicio)
                VALUES (?, ?, ?, ?, ?)
            """, (num_factura, i, det["cantidad"], det["precio_ud"], det["cod_servicio"]))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al reemplazar detalles: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
