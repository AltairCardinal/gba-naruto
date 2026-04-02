from fastapi import FastAPI
from routers import dialogues
import database

app = FastAPI(title="Naruto GBA Editor API")

app.include_router(dialogues.router)

@app.on_event("startup")
async def startup():
    database.init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)