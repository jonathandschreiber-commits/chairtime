from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import router

Base.metadata.create_all(bind=engine)

with engine.connect() as connection:
    try:
        connection.exec_driver_sql(
            "ALTER TABLE appointments ADD COLUMN notes VARCHAR"
        )
        connection.commit()
    except Exception:
        connection.rollback()

    try:
        connection.exec_driver_sql(
            "ALTER TABLE appointments ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        connection.commit()
    except Exception:
        connection.rollback()

app = FastAPI(title="ChairTime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def healthcheck():
    return {"status": "ChairTime backend is running"}