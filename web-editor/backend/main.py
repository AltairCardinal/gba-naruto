from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import dialogues, build, maps, units, skills, story_beats, audio, characters, battle_configs, users
import database

app = FastAPI(title="Naruto GBA Editor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dialogues.router)
app.include_router(build.router)
app.include_router(maps.router)
app.include_router(units.router)
app.include_router(skills.router)
app.include_router(story_beats.router)
app.include_router(audio.router)
app.include_router(characters.router)
app.include_router(battle_configs.router)
app.include_router(users.router)

@app.on_event("startup")
async def startup():
    database.init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)