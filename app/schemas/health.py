from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str = "0.2.0"
    database: str = "unknown"