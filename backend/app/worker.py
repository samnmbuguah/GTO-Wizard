from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from .ingestion.pio_parser import ingest_pio_csv

async def process_ingestion(db: Session, file_path: str, name: str, format: str):
    """
    Background worker for processing large solver files.
    """
    if format == "pio_csv":
        solution_id, count = ingest_pio_csv(db, file_path, name)
        return {"solution_id": solution_id, "nodes_imported": count}
    # Add other formats
    return {"error": "Unsupported format"}
