from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
import json
import time
import numpy as np
import faiss
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import google.generativeai as genai
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np
import redis

app = FastAPI()

class SearchRequest(BaseModel):
    email: str
    query: Optional[str] = ""

class APIKeyRequest(BaseModel):
    email: str

index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Create the client
client = MongoClient(uri, server_api=ServerApi('1'))

# Connect to the database and collection
db = client['auth']
collection = db['authenticator']
dbpay = client['Payment']
collectionpay = dbpay['accepted']
dbpaid = client['Store']
collectionpaid = dbpaid['details']
dbrest = client['Restaurant']
collectionrest = dbrest['payment-details']


class GeminiAI:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)

    def generate_response(self, prompt):
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error occurred: {e}"
        
@app.post("/searchgeminipaid")
async def geminipaid(request: SearchRequest):
    email = request.email
    query = request.query

    
    if not query:
        raise HTTPException(status_code=400, detail="Query not provided")

    # Fetch user record
    user_data = redis_client.get(email)
    user_record = json.loads(user_data)
    # else:
    #     user_record = collectionpaid.find_one({"email": email})
    #     if not user_record:
    #         raise HTTPException(status_code=400, detail="User not found")

    #     # Update lastUsed in MongoDB
    #     current_time_nanoseconds = int(time.time() * 1e9)
    #     collectionpaid.update_one(
    #         {"email": email},
    #         {"$set": {"lastUsed": current_time_nanoseconds}}
    #     )

    #     # Cache in Redis
    #     redis_client.set(email, json.dumps(user_record))

    embeddings_list = user_record.get('embeddings')
    paragraphs = user_record.get('paragraphs')

    if not embeddings_list:
        raise HTTPException(status_code=400, detail="Embeddings not found for this user")

    # Convert embeddings to numpy array
    embeddings = np.array(embeddings_list)

    # Build FAISS index
    dimension = embeddings.shape[1]
    faiss_index = faiss.IndexFlatL2(dimension)
    faiss_index.add(embeddings)
    print(faiss_index)

    # Encode query and search
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)

    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

    # Generate Gemini AI response
    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)

    return {"answer": response}


@app.post("/getapikey")
async def get_apikey(request: APIKeyRequest):
    email = request.email

    user = collection.find_one({"email": email})
    if user and "key" in user:
        return {"key": user["key"]}

    raise HTTPException(status_code=404, detail="API key not found for the user")
