import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import ngrok
import uvicorn
import requests

load_dotenv()
app = FastAPI()

API_KEY = os.getenv("API_KEY")
NGROK_TOKEN = os.getenv("NGROK_TOKEN")

SYSTEM_PROMPT = """優秀なAIアシスタントです。
以下のルールを守ってください：
- 常に丁寧で知的な口調で話す
- 返答は簡潔にまとめる
- 日本語で返答する"""

class TextPayload(BaseModel):
    text: str

def ask_jarvis(text: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "gemma3:12b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "stream": False
        }
    )
    return response.json()["message"]["content"]

@app.post("/transcribe")
async def transcribe(
    payload: TextPayload,
    x_api_key: str = Header(...)
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="認証エラー")
    print(f"受信: {payload.text}")
    reply = ask_jarvis(payload.text)
    print(f"返答: {reply}")
    return {"text": reply}

if __name__ == "__main__":
    listener = ngrok.forward(8000, authtoken=NGROK_TOKEN)
    print(f"外部URL: {listener.url()}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
