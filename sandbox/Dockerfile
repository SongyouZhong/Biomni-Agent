FROM mambaorg/micromamba:1.5.6

# Install necessary build tools for pip packages with C extensions (macs2, pybedtools, etc.)
USER root
RUN apt-get update && apt-get install -y build-essential zlib1g-dev libbz2-dev liblzma-dev && apt-get clean
USER $MAMBA_USER

# Copy environment file
COPY --chown=$MAMBA_USER:$MAMBA_USER runtime_env.yml /tmp/env.yaml

# Create environment from yaml
RUN micromamba env create -y -f /tmp/env.yaml && \
    micromamba clean --all --yes

# Install FastAPI and Uvicorn for the sandbox server
RUN micromamba run -n biomni_runtime pip install fastapi uvicorn pydantic requests

WORKDIR /app
COPY sandbox/server.py /app/server.py

# Ensure /data exists and set up working directory
USER root
RUN mkdir -p /data && chown $MAMBA_USER:$MAMBA_USER /data
USER $MAMBA_USER

WORKDIR /data

# Expose execution port
EXPOSE 8081

# Run the execution server
CMD ["micromamba", "run", "-n", "biomni_runtime", "python", "/app/server.py"]
