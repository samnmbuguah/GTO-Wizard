from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, worker

# models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Private GTO Wizard API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Private GTO Wizard API"}

@app.get("/solutions", response_model=List[schemas.Solution])
def list_solutions(db: Session = Depends(database.get_db)):
    return db.query(models.Solution).all()

@app.get("/solutions/{solution_id}/strategy", response_model=List[schemas.StrategyNode])
def get_strategy(solution_id: int, path: str = "root", hand: str = None, db: Session = Depends(database.get_db)):
    query = db.query(models.StrategyNode).filter(models.StrategyNode.solution_id == solution_id, models.StrategyNode.path == path)
    if hand:
        query = query.filter(models.StrategyNode.hand == hand)
    return query.all()

@app.post("/ingest")
async def start_ingestion(request: schemas.IngestionRequest, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    background_tasks.add_task(worker.process_ingestion, db, request.file_path, request.name, request.format)
    return {"message": "Ingestion started in background"}
