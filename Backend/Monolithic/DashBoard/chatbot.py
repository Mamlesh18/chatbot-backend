from flask import Flask, request, jsonify
from crawl4ai import WebCrawler
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np
from openai import AzureOpenAI
import os
from flask_cors import CORS  # Import CORS

app = Flask(__name__)
CORS(app)

# Azure OpenAI Configuration
endpoint = os.getenv("ENDPOINT_URL", "https://mamlesh-oai.openai.azure.com/")
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-35-turbo")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY", "004b5ef37cb7432d874e91be31f75195")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version="2024-05-01-preview",
)

# Initialize global variables for FAISS index and content
index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')

# Step 1: Extract full links synchronously
@app.route('/extractlinks', methods=['POST'])
def extract_full_links():
    data = request.json
    base_url = data.get('base_url')

    crawler = WebCrawler()
    crawler.warmup()
    
    result = crawler.run(url=base_url)
    internal_links = result.links.get('internal', [])
    full_links = [base_url + link['href'] if link['href'].startswith('/') else link['href'] for link in internal_links]
    
    return jsonify({"links": full_links})

# Step 2: Process the selected links and store content as a single string
@app.route('/process-links', methods=['POST'])
def process_links():
    global index, paragraphs  # Make the content global for FAISS indexing

    data = request.get_json()
    selected_links = data.get('selected_links', [])
    
    crawler = WebCrawler()
    crawler.warmup()

    content = []
    for link in selected_links:
        result = crawler.run(url=link)
        content.append(result.markdown)
    
    paragraphs = "\n\n".join(content)  # Store content as a single string

    

    if not paragraphs:
        return jsonify({"message": "No content to index"})

    # Split paragraphs into list for indexing
    paragraph_list = paragraphs.split("\n\n")
    embeddings = model.encode(paragraph_list)
    dimension = embeddings.shape[1]

    # Initialize FAISS index
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings))

    return jsonify({"message": "FAISS index created", "paragraphs": paragraph_list})
    


# Step 4: Search FAISS database and retrieve the most relevant answer
@app.route('/search', methods=['POST'])
def search_faiss_db():
    global index, paragraphs

    if not index:
        return jsonify({"message": "FAISS index not created"})

    data = request.get_json()
    query = data.get('query', '')

    # Encode the query and search the FAISS index
    query_embedding = model.encode([query])
    _, indices = index.search(query_embedding, k=5)

    paragraph_list = paragraphs.split("\n\n")
    closest_match = [paragraph_list[idx] for idx in indices[0]]

    # Use OpenAI to refine the response based on the closest match
    chat_prompt = [
        {
            "role": "system",
            "content": "You are an AI assistant that answers questions based on the provided context."
        },
        {
            "role": "user",
            "content": f"""Here are 5 most relevant paragraphs:\n\n{closest_match}\n\n
                           Answer the following question based on this context: {query}"""
        }
    ]
    
    try:
        completion = client.chat.completions.create(
            model=deployment,
            messages=chat_prompt,
            max_tokens=1500,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False
        )
        processed_answer = completion.choices[0].message.content
    except Exception as e:
        processed_answer = f"Error occurred: {e}"

    return jsonify({"answer": processed_answer})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
