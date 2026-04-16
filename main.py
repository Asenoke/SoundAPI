from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware




@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db()
    yield

app = FastAPI(lifespan=lifespan, title="Sound API", description="API для музыкального сервиса 'Sound' ")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    uvicorn.run("main:app", port=8000)

if __name__ == "__main__":
    main()
