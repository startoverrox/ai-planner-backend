from fastapi import FastAPI
from app.core.db import init_db

app = FastAPI()


init_db()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
