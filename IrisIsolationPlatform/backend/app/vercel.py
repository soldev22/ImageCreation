from fastapi import FastAPI

from app.api.isolation import router

app = FastAPI(title="Iris Isolation API", version="0.1.0")
app.include_router(router)