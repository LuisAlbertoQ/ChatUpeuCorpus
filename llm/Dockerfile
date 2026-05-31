FROM ollama/ollama:latest

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV LD_LIBRARY_PATH=/usr/lib/ollama/cuda_v13:/usr/lib/ollama:$LD_LIBRARY_PATH
ENV OLLAMA_LLM_LIBRARY=cuda_v13

EXPOSE 11434

VOLUME /root/.ollama

ENTRYPOINT ["/entrypoint.sh"]