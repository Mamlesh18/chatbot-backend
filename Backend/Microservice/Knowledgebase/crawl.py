# Step 1: Extract full links synchronously

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from crawl4ai import WebCrawler
from prometheus_flask_exporter import PrometheusMetrics
import faiss
import os
import numpy as np
from sentence_transformers import SentenceTransformer

app = Flask(__name__)
CORS(app)


index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')

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

    # Write the content to a .txt file
    txt_file_path = os.path.join(os.getcwd(), 'scraped_data.txt')
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(paragraphs)

    return jsonify({"message": "FAISS index created", "paragraphs": paragraph_list, "file_path": "/download-scraped-data"})


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5001)
