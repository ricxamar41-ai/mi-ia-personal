# src/app.py
from fastapi import FastAPI, File, UploadFile
import whisper
import openai
import subprocess
import io
import os
from dotenv import load_dotenv

# ------------------------------------------------------------------
# 1️⃣ Cargar variables de entorno (OPENAI_API_KEY)
# ------------------------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------------------------------------------
# 2️⃣ Inicializar el modelo Whisper (versión “small” – CPU friendly)
# ------------------------------------------------------------------
whisper_model = whisper.load_model("small")  # cambia por "large" si tienes GPU

# ------------------------------------------------------------------
# 3️⃣ Crear la aplicación FastAPI
# ------------------------------------------------------------------
app = FastAPI(title="Alexan")

# ------------------------------------------------------------------
# 4️⃣ Función de transcripción de audio → texto
# ------------------------------------------------------------------
def transcribe(audio_bytes: bytes) -> str:
    """Convierte un audio (WAV/MP3) a texto usando Whisper."""
    wav = io.BytesIO(audio_bytes)
    result = whisper_model.transcribe(wav)
    return result["text"]

# ------------------------------------------------------------------
# 5️⃣ Llamada a la API OpenAI (gpt‑4o‑mini) con el prompt y opcionalmente código
# ------------------------------------------------------------------
def ask_openai(prompt: str, code: str | None = None) -> str:
    """Envía el prompt (y opcionalmente código) a GPT‑4o‑mini y devuelve la respuesta."""
    messages = [
        {"role": "system",
         "content": "Eres un experto en programación, detecta errores y sugiere correcciones."},
        {"role": "user", "content": prompt}
    ]
    if code:
        messages.append({"role": "assistant", "content": code})
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )
    return response.choices[0].message.content

# ------------------------------------------------------------------
# 6️⃣ Ejecución de código en un sandbox muy sencillo (timeout 5s)
# ------------------------------------------------------------------
def sandbox_exec(code: str) -> str:
    """Ejecuta código Python en /tmp con un límite de 5 segundos y devuelve la salida."""
    script_path = "/tmp/tmp_code.py"
    with open(script_path, "w") as f:
        f.write(code)

    try:
        out = subprocess.check_output(
            ["timeout", "5", "python3", script_path],
            stderr=subprocess.STDOUT,
            text=True
        )
    except subprocess.CalledProcessError as e:
        out = f"Error:\n{e.output}"
    return out

# ------------------------------------------------------------------
# 7️⃣ Endpoint principal: recibe audio, transcribe, llama a GPT y devuelve JSON
# ------------------------------------------------------------------
@app.post("/voice")
async def voice_endpoint(file: UploadFile = File(...)):
    # Recibe el archivo y lo lee en bytes
    audio_bytes = await file.read()
    # Transcribe con Whisper
    txt = transcribe(audio_bytes)

    # Construye el prompt
    prompt = f"Revisa lo que dice: \"{txt}\". Si contiene código, corrígelo y muestra la salida."
    gpt_output = ask_openai(prompt)

    # Busca bloques de código entre ```` (backticks triples)
    code_blocks = []
    parts = gpt_output.split("```")
    for i in range(1, len(parts), 2):
        code_blocks.append(parts[i].strip())

    # Ejecuta cada bloque y almacena el resultado
    results = []
    for code in code_blocks:
        results.append({
            "original": code,
            "output": sandbox_exec(code)
        })

    return {
        "transcript": txt,
        "response": gpt_output,
        "exercises": results
    }
