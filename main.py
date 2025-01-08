from fastapi import FastAPI, HTTPException
from bs4 import BeautifulSoup
import requests
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz, process
import re


app = FastAPI()

# Configuración de CORS para permitir solicitudes solo desde el frontend de React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Reemplaza con la URL de tu frontend de React
    allow_credentials=True,
    allow_methods=["*"],  # Permite cualquier método (GET, POST, etc.) 
    allow_headers=["*"],  # Permite cualquier encabezado
)

# Inicialización de Firebase
try:
    cred = credentials.Certificate("C:\\Users\\USER\\Downloads\\fatapi.json")  # Cambia esta ruta si es necesario
    firebase_admin.initialize_app(cred)
    db = firestore.client()  # Inicializa la conexión con Firestore
except Exception as e:
    print(f"Error al inicializar Firebase: {e}")
    db = None  # Esto asegura que si falla, no haya un objeto db inválido

# Modelo de datos para recibir el query
class QueryRequest(BaseModel):
    query: str

# Normalizar texto para comparación
def normalize_text(text):
    """Convierte texto a minúsculas, elimina puntuación y espacios extra."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)  # Eliminar signos de puntuación
    text = re.sub(r"\s+", " ", text).strip()  # Espacios extra
    return text

# Función para buscar la mejor coincidencia
def find_best_match(user_question, faq_data):
    """Encuentra la respuesta más relevante basada en similitud."""
    user_question = normalize_text(user_question)
    questions = [normalize_text(item["question"]) for item in faq_data]
    
    # Buscar mejor coincidencia
    match = process.extractOne(user_question, questions, scorer=fuzz.token_set_ratio)
    if match and match[1] > 80:  # Similitud mayor al 80%
        index = questions.index(match[0])
        return faq_data[index]["answer"]
    return "Lo siento, no encontré una respuesta a tu pregunta."

@app.get("/scrape")
async def scrape_url(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="URL no válida o inaccesible.")
        
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.title.string if soup.title else "Sin título"
        
        # Ejemplo de extracción específica
        headings = [h.get_text() for h in soup.find_all("h1")]

        # Guardar en Firestore
        doc_ref = db.collection("scraped_data").add({
            "url": url,
            "title": title,
            "headings": headings,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        
        return {"url": url, "title": title, "headings": headings}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en scraping: {str(e)}")

# Endpoint para agregar preguntas y respuestas (sin cambios)
@app.get("/add_faq_data")
async def add_faq_data():
    
    if db is None:
        return {"error": "Firebase no está inicializado correctamente."}
    
    try:
        # Crear un conjunto de preguntas y respuestas de ejemplo
        faq_data = [
            {"question":"Cuando comienza el semestre", "answer":{"22 de Octubre 2024 : (Estudiantes nuevos)","10 de Febrero 2025: (Induccion Estudiantes nuevos)","21 de Diciembre 2024: (Limite de pago sin recargo estudiantes antiguos. Todas las escuelas)","10 de Diciembre 2024:(Limite de matricula estudiantes antiguos. Todas las escuelas)"}},
            {"question":"Que servicios manejan", "answer":["Aliados","Bienestar Estudiantil","Centro Cultural","Colegios","Educacion Digital","Emprendimientos","Proyectos"]},
           {"question": "Como inicio sesion", "answer":"Para iniciar sesion ingresas a este link www.cesde.com "},
           {"question": "Que descuentos manejan", "answer":["Si eres afiliado a comfama Aplicas a lo siguiente:","Tarifa A: 35%","Tarifa B: 30%"]},
            {"question": "¿Cuales son los medios de pago?", "answer":["Presencial", "pago en linea (todas las tarjetas de crédito o debito)", "pago con casantías", "banco davivienda (liquidación impresa)", "banco caja social (liquidación impresa)", "financiación",  ]},
              {"question": "Cuantas sedes tiene el cesde", "answer": "contamos con 6 sedes a nivel de Antioquia"},
              {
    "question": "¿Dónde están ubicados?",
    "answer": [
        "Medellín",
        "Bello",
        "Rionegro",
        "La Pintada",
        "Apartadó",
        "Bogotá",
       
    ]
}
        
        ]
        
        # Añadir cada pregunta y respuesta a la colección 'faq'
        for item in faq_data:
            db.collection("faq").add({
                "question": item["question"],
                "answer": item["answer"],
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        
        return {"message": "Datos de preguntas y respuestas añadidos correctamente."}
    
    except Exception as e:
        return {"error": f"Error al agregar los datos de preguntas y respuestas: {str(e)}"}

# Nuevo endpoint para realizar consultas basadas en similitud
@app.post("/ask_faq")
async def ask_faq(query: QueryRequest):
    if db is None:
        return {"error": "Firebase no está inicializado correctamente."}
    
    try:
        user_question = query.query
        user_question_normalized = normalize_text(user_question)
        
        # Recuperar todas las preguntas y respuestas de Firestore
        docs = db.collection("faq").stream()
        faq_data = [{"question": doc.to_dict()["question"], 
                     "answer": doc.to_dict()["answer"]} for doc in docs]
        
        # Buscar la mejor coincidencia
        response = find_best_match(user_question_normalized, faq_data)
        return {"answer": response}
    
    except Exception as e:
        return {"error": f"Error al procesar la pregunta: {str(e)}"}

@app.get("/get_faq_data")
async def get_faq_data():
    if db is None:
        return {"error": "Firebase no está inicializado correctamente."}
    
    try:
        # Obtener todos los documentos de la colección 'faq'
        docs = db.collection("faq").stream()
        
        faq_list = []
        for doc in docs:
            faq_list.append(doc.to_dict())
        
        return {"faq": faq_list}
    
    except Exception as e:
        return {"error": f"Error al obtener los datos de preguntas y respuestas: {str(e)}"}
    
    # Endpoint para consultar las preguntas y respuestas en Firestore
@app.post("/chatbot/")
async def chatbot(query_request: QueryRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Firebase no está inicializado correctamente.")
    
    try:
        query = query_request.query  # Obtener el 'query' del modelo recibido
        normalized_query = normalize_text(query)

        # Obtener todas las preguntas y respuestas de la colección 'faq'
        docs = db.collection("faq").stream()
        faq_data = [{"question": doc.to_dict().get("question"), "answer": doc.to_dict().get("answer")} for doc in docs]

        # Normalizar preguntas de la base de datos
        questions_normalized = [normalize_text(item["question"]) for item in faq_data]

        # Usar Rapidfuzz para encontrar la mejor coincidencia
        best_match = process.extractOne(normalized_query, questions_normalized)

        # Configura un umbral de similitud
        threshold = 70  # Ajusta este valor según la precisión deseada
        if best_match and best_match[1] > threshold:
            # Obtener la respuesta correspondiente a la mejor coincidencia
            index = questions_normalized.index(best_match[0])
            return {"query": query, "answer": faq_data[index]["answer"]}

        # Si no hay coincidencias suficientemente cercanas
        return {"query": query, "answer": "Lo siento, no tengo información sobre eso."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la consulta: {str(e)}")