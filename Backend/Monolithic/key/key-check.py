
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi




uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"

client = MongoClient(uri, server_api=ServerApi('1'))

db = client['auth']
collection = db['authenticator']

def validate_key(user_key):
    """
    Validates if the provided key exists in the MongoDB collection.

    Args:
        user_key (str): The key provided by the user.

    Returns:
        bool: True if the key exists in the collection, False otherwise.
    """
    try:
        # Replace 'key' with the name of the field in your MongoDB collection
        document = collection.find_one({"key": user_key})
        if document:
            return True
        return False
    except Exception as e:
        print(f"Error occurred during key validation: {e}")
        return False

api = ""
print(validate_key(api))