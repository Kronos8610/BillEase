import sqlite3
from tabulate import tabulate  # Si no tienes esta librería, instálala con: pip install tabulate

def listar_autonomos():
    """
    Consulta y muestra todos los autónomos registrados en la base de datos.
    """
    conn = None
    try:
        conn = sqlite3.connect("BillEase.db")
        cursor = conn.cursor()
        
        # Primero, obtener los nombres de columna de la tabla Autonomo
        cursor.execute("PRAGMA table_info(Autonomo)")
        columnas = [info[1] for info in cursor.fetchall()]
        
        # Luego, obtener todos los registros
        cursor.execute("SELECT * FROM Autonomo")
        autonomos = cursor.fetchall()
        
        if not autonomos:
            print("\n--- NO HAY AUTÓNOMOS REGISTRADOS EN LA BASE DE DATOS ---\n")
            return
        
        print(f"\n--- AUTÓNOMOS REGISTRADOS ({len(autonomos)}) ---\n")
        
        # Formatear para no mostrar la contraseña completa
        formatted_autonomos = []
        for autonomo in autonomos:
            # Convertir a lista para poder modificar
            autonomo_list = list(autonomo)
            # Reemplazar la contraseña por "********"
            if len(autonomo_list) >= 8:  # Asumiendo que la contraseña está en la posición 7 (índice 7)
                autonomo_list[7] = "********"
            formatted_autonomos.append(autonomo_list)
        
        # Mostrar la tabla formateada
        print(tabulate(formatted_autonomos, headers=columnas, tablefmt="pretty"))
        
    except Exception as e:
        print(f"Error al listar autónomos: {e}")
    finally:
        if conn:
            conn.close()

# Si no tienes tabulate, aquí hay una versión alternativa que no requiere librerías externas
def listar_autonomos_simple():
    """
    Versión alternativa sin depender de la librería tabulate.
    """
    conn = None
    try:
        conn = sqlite3.connect("BillEase.db")
        cursor = conn.cursor()
        
        # Obtener nombres de columnas
        cursor.execute("PRAGMA table_info(Autonomo)")
        columnas = [info[1] for info in cursor.fetchall()]
        
        # Obtener todos los registros
        cursor.execute("SELECT * FROM Autonomo")
        autonomos = cursor.fetchall()
        
        if not autonomos:
            print("\n--- NO HAY AUTÓNOMOS REGISTRADOS EN LA BASE DE DATOS ---\n")
            return
        
        print(f"\n--- AUTÓNOMOS REGISTRADOS ({len(autonomos)}) ---\n")
        
        # Imprimir encabezados
        header = " | ".join([f"{col:<15}" for col in columnas])
        print(header)
        print("-" * len(header))
        
        # Imprimir datos
        for autonomo in autonomos:
            autonomo_list = list(autonomo)
            # Ocultar contraseña
            if len(autonomo_list) >= 8:
                autonomo_list[7] = "********"
            
            # Formatear cada campo a 15 caracteres de ancho
            row_data = []
            for item in autonomo_list:
                if item is None:
                    item = ""
                item_str = str(item)
                if len(item_str) > 15:
                    item_str = item_str[:12] + "..."
                row_data.append(f"{item_str:<15}")
                
            print(" | ".join(row_data))
        
    except Exception as e:
        print(f"Error al listar autónomos: {e}")
    finally:
        if conn:
            conn.close()

# Función para verificar y crear un autónomo de prueba si no existe ninguno
def asegurar_autonomo_existe():
    """
    Verifica si existe algún autónomo y crea uno de prueba si no existe.
    """
    conn = sqlite3.connect("BillEase.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM Autonomo")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("No hay autónomos registrados. Creando uno de prueba...")
            # Hash de la contraseña (en un caso real deberías usar hashlib)
            password = "password123"
            
            cursor.execute("""
                INSERT INTO Autonomo (
                    DNI, nombre, apellido, direccion, codigo_postal, telefono, email, contrasena
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ('12345678A', 'Juan', 'Pérez', 'Calle Principal 123', '28001', 
                  '600123456', 'juan.perez@example.com', password))
            conn.commit()
            print("Autónomo de prueba creado correctamente.")
            return True
        return count > 0
    except Exception as e:
        print(f"Error al verificar o crear autónomo: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Primero asegurarnos de que existe al menos un autónomo
    if asegurar_autonomo_existe():
        # Intentar usar tabulate si está instalado
        try:
            listar_autonomos()
        except ImportError:
            print("La librería 'tabulate' no está instalada. Usando formato simple.")
            listar_autonomos_simple()
    else:
        print("No se pudo asegurar la existencia de un autónomo en la base de datos.")