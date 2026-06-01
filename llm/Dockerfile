FROM ollama/ollama:latest

# curl para healthcheck
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV LD_LIBRARY_PATH=/usr/lib/ollama/cuda_v13:/usr/lib/ollama:$LD_LIBRARY_PATH
ENV OLLAMA_LLM_LIBRARY=cuda_v13
ENV OLLAMA_MODEL=llama3

EXPOSE 11434

VOLUME /root/.ollama

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD curl -fsS http://localhost:11434/api/tags >/dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
