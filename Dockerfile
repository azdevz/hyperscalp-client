# ==============================================================================
# STAGE 1: Builder (Compiles Python source files into native C shared libraries)
# ==============================================================================
FROM python:3.11-slim AS builder

# Install C/C++ compiler and build-essential packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python dependencies definitions
COPY requirements.txt .

# Install Cython and all other runtime dependencies
RUN pip install --no-cache-dir Cython && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source folders and files
COPY hl_bot/ hl_bot/
COPY meme_bot/ meme_bot/
COPY api/ api/
COPY db.py config.py alerts.py main.py setup.py launcher.py ./

# Run Cython in-place compilation
RUN python setup.py build_ext --inplace

# IP protection sweep: Delete all raw python source files (.py) and generated C source files (.c),
# EXCEPT for the launcher.py entrypoint and empty package package indicators (__init__.py)
RUN find . -type f -name "*.py" ! -name "launcher.py" ! -name "__init__.py" -delete && \
    find . -type f -name "*.c" -delete && \
    rm -rf build setup.py

# ==============================================================================
# STAGE 2: Final Production Runner (Secure, lightweight execution environment)
# ==============================================================================
FROM python:3.11-slim AS runner

# Set secure production environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy python package dependencies directly from the builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy compiled native shared object binaries (.so) and the non-sensitive launcher bootstrap
COPY --from=builder /app /app

# Expose API port for the Client Dashboard to communicate with
EXPOSE 8080

# Execute using our thin uncompiled entrypoint bootstrap
CMD ["python", "launcher.py"]
