# Imagen base de Python con sistema operativo mínimo
FROM python:3.11-slim

# Instala dependencias del sistema necesarias para pyodbc y drivers
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    libpq-dev \
    libssl-dev \
    libsasl2-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de tu proyecto al contenedor
COPY . .

# Instala dependencias Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expone el puerto que usará Uvicorn
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
