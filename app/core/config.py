from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    SECRET_KEY: str
    GEMINI_API_KEY: str

    # En True devuelve una recomendacion de demostracion sin consumir Gemini.
    DEMO_MODE: bool = False

    # Modelo principal de Gemini.
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Respaldos en orden; se usan si el principal responde 429 o 503.
    GEMINI_MODELOS_RESPALDO: list[str] = [
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    ]

    # Vigencia del token JWT (en horas).
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Tope de tokens de salida: el prompt pide dos textos largos y alertas.
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096

    # Reintentos ante fallos transitorios de la API (429/503).
    GEMINI_MAX_RETRIES: int = 3

    # Espera maxima por una respuesta de Gemini (segundos).
    GEMINI_TIMEOUT_S: float = 60.0

    # Tope para toda la cadena de reintentos; la app espera hasta 300 s.
    GEMINI_TOTAL_TIMEOUT_S: float = 240.0

    # Orígenes permitidos por CORS. En produccion debe ser una lista explicita
    # de dominios; "*" se permite solo mientras se desarrolla.
    CORS_ORIGINS: list[str] = ["*"]

    @property
    def gemini_generate_url(self) -> str:
        return self.gemini_url_para(self.GEMINI_MODEL)

    def gemini_url_para(self, modelo: str) -> str:
        """URL de generacion para un modelo concreto (uno de la cadena)."""
        return f"{self.GEMINI_API_BASE}/{modelo}:generateContent"

    @property
    def gemini_modelos(self) -> list[str]:
        """Modelo principal seguido de los de respaldo, sin duplicados."""
        vistos: set[str] = set()
        cadena: list[str] = []
        for modelo in [self.GEMINI_MODEL, *self.GEMINI_MODELOS_RESPALDO]:
            limpio = (modelo or "").strip()
            if limpio and limpio not in vistos:
                vistos.add(limpio)
                cadena.append(limpio)
        return cadena


settings = Settings()
