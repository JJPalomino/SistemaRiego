from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `class Config` esta deprecado en pydantic-settings v2.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    SECRET_KEY: str
    GEMINI_API_KEY: str

    # Cuando es True el advisor de IA devuelve una respuesta de demostracion
    # sin consumir cuota de Gemini (util para desarrollo y para pruebas de
    # integracion que no deben depender de un servicio de terceros).
    DEMO_MODE: bool = False

    # Modelo de Gemini a utilizar.
    # NOTA: Verifica siempre los modelos vigentes con:
    #   GET https://generativelanguage.googleapis.com/v1beta/models
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Vigencia del token JWT (en horas).
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Tope de tokens de salida para la generacion. El prompt solicita 2 textos
    # largos mas un arreglo de alertas: con 1024 la respuesta llegaba truncada y
    # `json.loads` fallaba con "Unterminated string".
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096

    # Numero de reintentos ante fallos transitorios de la API (429/503).
    GEMINI_MAX_RETRIES: int = 3

    # Tiempo maximo de espera por respuesta de Gemini (segundos). Los modelos
    # con razonamiento pueden tardar mas de un minuto incluso en respuestas
    # cortas, por lo que 60 s provocaba 502 intermitentes.
    GEMINI_TIMEOUT_S: float = 180.0

    # Orígenes permitidos por CORS. En produccion debe ser una lista explicita
    # de dominios; "*" se permite solo mientras se desarrolla.
    CORS_ORIGINS: list[str] = ["*"]

    @property
    def gemini_generate_url(self) -> str:
        return f"{self.GEMINI_API_BASE}/{self.GEMINI_MODEL}:generateContent"


settings = Settings()
