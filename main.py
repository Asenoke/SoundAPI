from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.db.db import create_db
from api.auth.routers import  router as auth_router
from api.user.routers import router as user_router
from api.performer.routers import router as performer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db()
    yield

app = FastAPI(lifespan=lifespan, title="Sound API", description="API для музыкального сервиса 'Sound' ")


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(performer_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    uvicorn.run("main:app", port=8000)

if __name__ == "__main__":
    main()
