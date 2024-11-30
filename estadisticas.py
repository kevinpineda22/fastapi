import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi.responses import FileResponse
from fastapi import HTTPException, FastAPI

# Crear instancia de FastAPI
app = FastAPI()

def generar_estadisticas(productos_lista):
    # Crear un DataFrame a partir de la lista de productos
    df = pd.DataFrame(productos_lista)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No se encontraron productos en la base de datos")
    
    # Verificar que las columnas necesarias existan
    columnas_requeridas = {"name", "precio"}
    if not columnas_requeridas.issubset(df.columns):
        raise HTTPException(status_code=500, detail="Faltan columnas necesarias en los datos (name, precio)")
    
    # Estadísticas básicas
    venta_max = df["precio"].max()
    venta_min = df["precio"].min()
    venta_max_datos = df[df["precio"] == venta_max].to_dict(orient="records")
    venta_min_datos = df[df["precio"] == venta_min].to_dict(orient="records")
    
    # Graficar precios
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="name", y="precio", palette="viridis")
    plt.title("Precio de productos")
    plt.xlabel("Producto")
    plt.ylabel("Precio")
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Guardar el gráfico como imagen
    grafico_path = "productos_precio.png"
    plt.savefig(grafico_path)
    plt.close()

    # Retornar estadísticas y gráfico
    return {
        "venta_max": venta_max,
        "venta_min": venta_min,
        "venta_max_datos": venta_max_datos,
        "venta_min_datos": venta_min_datos,
        "grafico_path": grafico_path
    }

# Endpoint en FastAPI para usar esta función
@app.get("/productos/estadisticas")
async def estadisticas_productos():
    # Recuperar datos de Firestore
    productos_ref = db.collection("productos")
    productos = productos_ref.stream()
    
    productos_lista = [doc.to_dict() for doc in productos]
    
    # Generar estadísticas
    resultado = generar_estadisticas(productos_lista)

    # Devolver estadísticas y el gráfico como un archivo PNG
    return {
        "venta_max": resultado["venta_max"],
        "venta_min": resultado["venta_min"],
        "venta_max_datos": resultado["venta_max_datos"],
        "venta_min_datos": resultado["venta_min_datos"],
        "grafico_url": f"/productos/estadisticas/grafico"
    }

#Endpoint para servir el gráfico generado
@app.get("/productos/estadisticas/grafico")
async def obtener_grafico():
    grafico_path = "productos_precio.png"
    return FileResponse(grafico_path, media_type="image/png", filename="productos_precio.png")
