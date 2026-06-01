#!/bin/sh
set -eu

export LD_LIBRARY_PATH=/usr/lib/ollama/cuda_v13:/usr/lib/ollama:${LD_LIBRARY_PATH:-}
export OLLAMA_LLM_LIBRARY=cuda_v13

MODEL="${OLLAMA_MODEL:-llama3}"

echo "[llm] arrancando Ollama serve…"
ollama serve &
SERVER_PID=$!

# Esperar a que el daemon responda
echo "[llm] esperando a que Ollama responda…"
for i in $(seq 1 30); do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Pre-pull del modelo si todavía no está en caché.
# Evita el "cold start" >60 s en la primera consulta del usuario (T04).
if ! ollama list | awk 'NR>1 {print $1}' | grep -q "^${MODEL}\(:.*\)\?$"; then
  echo "[llm] descargando modelo ${MODEL}…"
  ollama pull "${MODEL}" || echo "[llm] WARN: no se pudo pre-descargar ${MODEL}"
else
  echo "[llm] modelo ${MODEL} ya disponible."
fi

# Warm-up: carga el modelo en RAM/GPU con una inferencia trivial.
# Sin esto, la primera consulta del usuario paga 20-40 s de "carga" y
# cae en el timeout de 15 s (T04 → M06).  Con esto, las consultas reales
# empiezan con el modelo ya caliente y responden en 5-10 s.
echo "[llm] calentando modelo ${MODEL}…"
if curl -sf -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${MODEL}\",\"prompt\":\"ok\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
    > /dev/null 2>&1; then
  echo "[llm] modelo caliente y listo."
else
  echo "[llm] WARN: warm-up falló (continúa de todos modos)."
fi

echo "[llm] listo."
wait "$SERVER_PID"
