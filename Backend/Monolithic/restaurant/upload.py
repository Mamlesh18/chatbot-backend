@app.route('/uploadpaid', methods=['POST'])
def upload_file_paid():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    email = request.form.get('email')  # Extract email from form data
    print(email)
    print(file.filename)
    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})
    if file.filename == '' or not email:
        return jsonify({'error': 'No file selected or email missing'}), 400

    if file and allowed_file(file.filename):
        try:
            # Read the file content in memory (without saving it to disk)
            file_content = file.read().decode('utf-8', errors='ignore')

            # Debugging log to check the file content
            print(f"File content: {file_content}")

            # Split the content into paragraphs
            paragraphs = file_content.split("\n\n")

            # Create embeddings for each paragraph and initialize FAISS index
            embeddings = model.encode(paragraphs)
            dimension = embeddings.shape[1]  # Get the dimension of the embeddings
            faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
            faiss_index.add(np.array(embeddings))  # Add embeddings to FAISS index

            embeddings_list = embeddings.tolist()
            print("here it is -------->", embeddings_list)

            # Check if the email already exists in the MongoDB collection
            existing_record = collectionpaid.find_one({'email': email})

            if existing_record:
                # If email exists, update the file content and embeddings
                collectionpaid.update_one(
                    {'email': email},
                    {'$set': {
                        'file_content': file_content,
                        'embeddings': embeddings_list,
                        'paragraphs' : paragraphs
                    }}
                )
                return jsonify({'message': 'File updated and re-indexed successfully'}), 200
            else:
                # If email does not exist, insert a new record
                record = {
                    'email': email,
                    'file_content': file_content,
                    'embeddings': embeddings_list,
                    'paragraphs' : paragraphs


                }
                collectionpaid.insert_one(record)
                return jsonify({'message': 'File uploaded and indexed successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400





@app.route('/searchgeminipaid', methods=['POST'])
def geminipaid():
    data = request.json  # Use request.json to handle JSON payload
    email = data.get('email')    
    query = data.get('query', '')
    print(email)
    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Fetch the user's record from MongoDB to get the embeddings and paragraphs
    user_record = collectionpaid.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400
    print("1")
    embeddings_list = user_record.get('embeddings')
    print("2")

    paragraphs = user_record.get('paragraphs')
    print("3")

    if not embeddings_list:
        return jsonify({"error": "Embeddings not found for this user"}), 400
    print("4")

    # Convert the embeddings list back to a numpy array
    embeddings = np.array(embeddings_list)
    print("5")

    # Rebuild the FAISS index
    dimension = embeddings.shape[1]  # Get the dimension of the embeddings
    faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
    faiss_index.add(embeddings)  # Add embeddings to FAISS index
    print("6")

    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)  # Get top 5 relevant paragraphs
    print("7")

    # Extract the relevant paragraphs from the indices
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)
    print("8")

    # Generate the prompt for Gemini
    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )
    print("10")

    # Create a Gemini AI client and get the response
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)

    return jsonify({"answer": response})
