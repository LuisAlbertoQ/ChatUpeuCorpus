#!/bin/sh

export LD_LIBRARY_PATH=/usr/lib/ollama/cuda_v13:/usr/lib/ollama:$LD_LIBRARY_PATH
export OLLAMA_LLM_LIBRARY=cuda_v13

exec ollama serve