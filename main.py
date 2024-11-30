from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import firebase_admin
from firebase_admin import credentials, firestore

# Inicialización de Firebase
try:
    cred = credentials.Certificate("C:\\Users\\USER\\Downloads\\fatapi.json")  # Cambia esta ruta si es necesario
    firebase_admin.initialize_app(cred)
    db = firestore.client()  # Inicializa la conexión con Firestore
except Exception as e:
    print(f"Error al inicializar Firebase: {e}")
    db = None  # Esto asegura que si falla, no haya un objeto db inválido

# Crear instancia de la aplicación FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Cambia este origen al del frontend si está en otro puerto
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos los encabezados
)

# Definimos el modelo de datos para el Producto
class Producto(BaseModel):
    Referencia: str
    Unidad: int
    available: int
    name: str
    precio: int
    

# Endpoint para agregar un nuevo producto
@app.post("/productos/", response_model=Producto)
async def agregar_producto(producto: Producto):
    try:
        # Verificar si ya existe un producto con la misma referencia
        productos_ref = db.collection("productos")
        query = productos_ref.where("Referencia", "==", producto.Referencia)
        existing_product = query.stream()

        # Si el producto ya existe, lanzamos una excepción
        if any(existing_product):
            raise HTTPException(status_code=400, detail="Producto con esa referencia ya existe.")
        
        # Agregar el nuevo producto a la base de datos
        producto_dict = producto.dict()  # Convertir el modelo a un diccionario
        db.collection("productos").add(producto_dict)
        
        return producto  # Retornar el producto agregado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar el producto: {str(e)}")


# Endpoint para buscar productos por referencia
@app.get("/productos/", response_model=List[Producto])
async def get_productos(referencia: Optional[str] = Query(None, alias="referencia")):
    if db is None:
        raise HTTPException(status_code=500, detail="Firebase no está inicializado")

    if referencia:  # Si se pasa una referencia
        productos_ref = db.collection("productos")
        query = productos_ref.where("Referencia", "==", referencia)
        productos = query.stream()

        productos_lista = []
        for doc in productos:
            producto = doc.to_dict()
            producto["Referencia"] = producto.get("Referencia", doc.id)  # Agregar la referencia si no está
            productos_lista.append(producto)

        return productos_lista if productos_lista else []
    else:
        return []
    
    
    # Endpoint para editar un producto por referencia
@app.put("/productos/", response_model=Producto)
async def editar_producto(referencia: str, producto: Producto):
    if db is None:
        raise HTTPException(status_code=500, detail="Firebase no está inicializado")
    
    try:
        # Buscar el producto en la base de datos usando la referencia
        productos_ref = db.collection("productos")
        query = productos_ref.where("Referencia", "==", referencia)
        productos = query.stream()

        productos_lista = [doc for doc in productos]
        
        if not productos_lista:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")  # Si no hay productos, lanzar error

        # Asumiendo que solo hay un producto con la referencia (ya que la referencia debería ser única)
        producto_doc = productos_lista[0]  # Tomar el primer producto que coincida con la referencia
        producto_ref = productos_ref.document(producto_doc.id)
        
        # Actualizar el producto en la base de datos
        producto_dict = producto.dict(exclude_unset=True)  # Excluir los campos no establecidos
        producto_ref.update(producto_dict)
        
        # Retornar el producto actualizado
        return producto

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al editar el producto: {str(e)}")

# Endpoint para eliminar un producto por referencia
@app.delete("/productos/", response_model=Producto)
async def eliminar_producto(referencia: str = Query(..., alias="referencia")):
    if db is None:
        raise HTTPException(status_code=500, detail="Firebase no está inicializado")
    
    try:
        # Buscar el producto en la base de datos usando la referencia
        productos_ref = db.collection("productos")
        query = productos_ref.where("Referencia", "==", referencia)
        productos = query.stream()

        # Verificar si se encontró el producto
        producto_doc = None
        for doc in productos:
            producto_doc = doc
            break  # Solo necesitamos el primer documento que coincida

        if not producto_doc:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")

        # Eliminar el producto de la base de datos
        producto_ref = db.collection("productos").document(producto_doc.id)
        producto_ref.delete()

        # Retornar el producto eliminado
        return producto_doc.to_dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar el producto: {str(e)}")


# Función para generar estadísticas
def generar_estadisticas(productos_lista):
    # Crear un DataFrame a partir de la lista de productos
    df = pd.DataFrame(productos_lista)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No se encontraron productos en la base de datos")
    
    # Verificar que las columnas necesarias existan
    columnas_requeridas = {"name", "precio", "Unidad", "available"}
    if not columnas_requeridas.issubset(df.columns):
        raise HTTPException(status_code=500, detail="Faltan columnas necesarias en los datos (name, precio, Unidad, available)")
    
    # Estadísticas básicas
    venta_max = df["precio"].max()
    venta_min = df["precio"].min()
    venta_max_datos = df[df["precio"] == venta_max].to_dict(orient="records")
    venta_min_datos = df[df["precio"] == venta_min].to_dict(orient="records")
    
 # Filtrar los productos más caros (por ejemplo, los 5 más caros)
    df_top = df.nlargest(5, "precio")  # Selecciona los 5 productos más caros
    
    # Graficar precios de los productos más caros
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df_top, x="name", y="precio", palette="coolwarm")
    plt.title("productos más caros", fontsize=16)
    plt.xlabel("Producto", fontsize=12)
    plt.ylabel("Precio", fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()
    grafico_precio_path = "productos_precio.png"
    plt.savefig(grafico_precio_path)
    plt.close()

    # Graficar productos con más unidades disponibles (gráfico de dona)
    productos_mas_unidades = df[df["Unidad"] > 0].sort_values(by="Unidad", ascending=False).head(4)
    unidades = productos_mas_unidades["Unidad"]
    nombres = productos_mas_unidades["name"]

    # Gráfico de dona
    plt.figure(figsize=(10, 6))
    plt.pie(unidades, labels=nombres, autopct='%1.1f%%', startangle=90, colors=sns.color_palette("Blues_d", len(unidades)))
    plt.title("Productos con más unidades disponibles", fontsize=16)
    plt.gca().set_aspect('equal')  # Asegura que el gráfico sea circular
    plt.tight_layout()
    grafico_unidades_path = "productos_mas_unidades_dona.png"
    plt.savefig(grafico_unidades_path)
    plt.close()

    # Graficar productos no disponibles (scatter plot)
    productos_no_disponibles = df[df["available"] == 0]
    plt.figure(figsize=(10, 6))
    sns.barplot(data=productos_no_disponibles, x="name", y="precio", palette="coolwarm")
    plt.title("Productos no disponibles", fontsize=14)
    plt.xlabel("Producto", fontsize=10)
    plt.ylabel("Precio", fontsize=10)
    plt.xticks(rotation=45)
    plt.tight_layout()
    grafico_no_disponibles_path = "productos_no_disponibles.png"
    plt.savefig(grafico_no_disponibles_path)
    plt.close()

    # Retornar estadísticas y gráficos generados
    return {
        "venta_max": venta_max,
        "venta_min": venta_min,
        "venta_max_datos": venta_max_datos,
        "venta_min_datos": venta_min_datos,
        "grafico_precio_url": "/productos/estadisticas/grafico_precio",
        "grafico_unidades_url": "/productos/estadisticas/grafico_unidades",
        "grafico_no_disponibles_url": "/productos/estadisticas/grafico_no_disponibles"
    }

# Endpoint para generar estadísticas
@app.get("/productos/estadisticas")
async def estadisticas_productos():
    # Recuperar datos de Firestore
    productos_ref = db.collection("productos")
    productos = productos_ref.stream()
    
    productos_lista = [doc.to_dict() for doc in productos]
    
    # Generar estadísticas
    resultado = generar_estadisticas(productos_lista)

    # Devolver estadísticas y los gráficos como URLs
    return {
        "venta_max": resultado["venta_max"],
        "venta_min": resultado["venta_min"],
        "venta_max_datos": resultado["venta_max_datos"],
        "venta_min_datos": resultado["venta_min_datos"],
        "grafico_precio_url": resultado["grafico_precio_url"],
        "grafico_unidades_url": resultado["grafico_unidades_url"],
        "grafico_no_disponibles_url": resultado["grafico_no_disponibles_url"]
    }

# Endpoint para servir los gráficos generados
@app.get("/productos/estadisticas/grafico_precio")
async def obtener_grafico_precio():
    grafico_precio_path = "productos_precio.png"
    return FileResponse(grafico_precio_path, media_type="image/png", filename="productos_precio.png")

@app.get("/productos/estadisticas/grafico_unidades")
async def obtener_grafico_unidades():
    grafico_unidades_path = "productos_mas_unidades_dona.png"
    return FileResponse(grafico_unidades_path, media_type="image/png", filename="productos_mas_unidades_dona.png")

@app.get("/productos/estadisticas/grafico_no_disponibles")
async def obtener_grafico_no_disponibles():
    grafico_no_disponibles_path = "productos_no_disponibles.png"
    return FileResponse(grafico_no_disponibles_path, media_type="image/png", filename="productos_no_disponibles.png")