# Local bge-m3 embeddings for the knowledge base.
#
# The weights are not baked into the image: they come from the Hugging Face
# cache volume that the hindsight service already populated, mounted at
# /models. The torch wheel is the CPU-only one, which keeps the image around
# 1 GB instead of pulling the CUDA stack.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=2 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pytorch-wheels/cpu torch \
    && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
        fastapi "uvicorn[standard]" sentence-transformers

WORKDIR /app
COPY server.py /app/server.py

EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
