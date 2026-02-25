import os
from google import genai

GEMINI_API_KEY = "AIzaSyCW9Ub5MRtDrvCWhO4yUT01lo-afOPdr00" 
client = genai.Client(api_key=GEMINI_API_KEY)

print("Listing all accessible Gemini models...")
count = 0
for m in client.models.list():
    print(f"- {m.name}")
    count += 1
        
print(f"Total models: {count}")
