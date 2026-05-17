from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.db.db import create_db
from api.auth.routers import  router as auth_router
from api.user.routers import router as user_router
from api.performer.routers import router as performer_router
from api.song.routers import router as song_router
from api.playlist.routers import router as playlist_router
from api.likes.routers import router as likes_router
from api.search.routers import router as search_router
from api.history.routers import router as history_router
from api.recommendations.routers import router as recommendations_router
from api.subscription.routers import router as subscription_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db()
    yield

app = FastAPI(lifespan=lifespan, title="Sound API", description="API для музыкального сервиса 'Sound' ")


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(performer_router)
app.include_router(song_router)
app.include_router(playlist_router)
app.include_router(likes_router)
app.include_router(search_router)
app.include_router(history_router)
app.include_router(recommendations_router)
app.include_router(subscription_router)

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
