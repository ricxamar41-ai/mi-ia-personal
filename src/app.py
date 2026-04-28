# src/app.py
from fastapi import FastAPI, File, UploadFile
import whisper
import openai
import subprocess
import io
import os
from dotenv import load_dotenv

# 1️⃣ Cargar variables de entorno
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# 2️⃣ Modelo Whisper (CPU amigable)
whisper_model = whisper.load_model("small")   # cambia a "large" si tu GPU lo permite

# 3️⃣ Instancia FastAPI
app = FastAPI(title="Alexan")

# 4️⃣ Transcribe audio → texto
def transcribe(audio_bytes: bytes) -> str:
    wav = io.BytesIO(audio_bytes)
    result = whisper_model.transcribe(wav)
    return result["text"]

# 5️⃣ Llamada a la API de OpenAI (gpt‑4o‑mini)
def ask_openai(prompt: str, code: str | None = None) -> str:
    messages = [
        {"role":"system",
         "content":"Eres un experto en programación, detecta errores y sugiere correcciones."},
        {"role":"user","content":prompt}
    ]
    if code:
        messages.append({"role":"assistant","content":code})
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )
    return resp.choices[0].message.content

# 6️⃣ Sandbox simple: ejecuta código Python con timeout
def sandbox_exec(code: str) -> str:
    script_path = "/tmp/tmp_code.py"
    with open(script_path, "w") as f:
        f.write(code)
    try:
        out = subprocess.check_output(
            ["timeout","5","python3", script_path],
            stderr=subprocess.STDOUT,
            text=True
        )
    except subprocess.CalledProcessError as e:
        out = f"Error:\n{e.output}"
    return out

# 7️⃣ Endpoint principal
@app.post("/voice")
async def voice_endpoint(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    text = transcribe(audio_bytes)

    prompt = f"Revisa lo que dice: \"{text}\". Si contiene código, corrígelo y muestra la salida."
    gpt_out = ask_openai(prompt)

    # Extraer bloques de código entre triple backticks
    code_blocks = []
    parts = gpt_out.split("```")
    for i in range(1, len(parts), 2):
        code_blocks.append(parts[i].strip())

    results = []
    for code in code_blocks:
        results.append({
            "original": code,
            "output": sandbox_exec(code)
        })

    return {
        "transcript": text,
        "response": gpt_out,
        "exercises": results
    }
