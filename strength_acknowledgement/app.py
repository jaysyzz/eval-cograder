import os
from dotenv import load_dotenv

load_dotenv()  # It will automatically find .env in the same folder now!
api_key = os.getenv("OPENAI_API_KEY")
print("Loaded successfully!" if api_key else "Key not found.")
