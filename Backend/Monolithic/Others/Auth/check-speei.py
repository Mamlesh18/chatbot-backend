from flask import Flask, jsonify, request
import openai
import os
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# Azure OpenAI Configuration (from environment variables or default values)
openai.api_type = "azure"
openai.api_key = os.getenv("AZURE_OPENAI_API_KEY", "004b5ef37cb7432d874e91be31f75195")
openai.api_base = os.getenv("ENDPOINT_URL", "https://mamlesh-oai.openai.azure.com/")
openai.api_version = "2024-05-01-preview"
deployment_id = os.getenv("DEPLOYMENT_NAME", "gpt-35-turbo")


@app.route('/search', methods=['POST'])
def search_faiss_db():
    data = request.get_json()
    query = data.get('query', '')

    # Define the chat prompt similar to demo.py
    chat_prompt = [
        {
            "role": "system",
            "content": "You are an AI assistant that answers questions based on the provided context."
        },
        {
            "role": "user",
            "content": f"Answer the following question based on this context: {query}"
        }
    ]

    try:
        # Call OpenAI's chat completion endpoint
        chat_completion = openai.ChatCompletion.create(
            deployment_id=deployment_id,
            model="gpt-3.5-turbo",
            messages=chat_prompt,
            max_tokens=1500,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None
        )
        # Get the generated response from OpenAI
        processed_answer = chat_completion.choices[0].message.content
    except Exception as e:
        processed_answer = f"Error occurred: {e}"

    return jsonify({"answer": processed_answer})


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, port=5000)
