from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- 1. Configuración del Servidor ---
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # --- 2. Base de Datos (PostgreSQL) ---
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str

    database_url: str

    # --- 3. Mensajería (Kafka) ---
    kafka_broker_url: str

    # --- 4. Almacenamiento (MinIO) ---
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str

    # --- 5. Telemetría (InfluxDB) ---
    influxdb_user: str
    influxdb_password: str
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str

    #--- 7. grafana ---
    gf_admin_user: str
    gf_admin_password: str

    # --- 6. Seguridad (JWT) ---
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    class Config:
        # Le indicamos que busque las variables en el archivo .env de la raíz
        env_file = ".env"
        # Aseguramos que lea bien caracteres especiales
        env_file_encoding = "utf-8"

        extra = "ignore"  # Ignora variables no definidas en esta clase

settings = Settings()