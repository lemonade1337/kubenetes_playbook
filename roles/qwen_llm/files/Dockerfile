FROM ollama/ollama:latest

# Pre-download Qwen 2.5 3B model into image layer
RUN ollama serve & \
    SERVER_PID=$! && \
    until ollama list >/dev/null 2>&1; do sleep 1; done && \
    echo "[Build] Pre-baking Qwen 2.5 3B model into image layer..." && \
    ollama pull qwen2.5:3b && \
    kill $SERVER_PID && \
    wait $SERVER_PID 2>/dev/null || true

EXPOSE 11434

ENV OLLAMA_KEEP_ALIVE=24h
ENV OLLAMA_NUM_PARALLEL=1

ENTRYPOINT ["ollama", "serve"]
