from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import Base, engine
from app.routes.appointments import router as appointments_router
from app.routes.auth import router as auth_router
from app.routes.availability import router as availability_router
from app.routes.barbers import router as barbers_router
from app.routes.blocked_times import router as blocked_times_router
from app.routes.customers import router as customers_router
from app.routes.migration import router as migration_router
from app.routes.reminders import router as reminders_router
from app.routes.services import router as services_router
from app.routes.shops import router as shops_router
from app.routes.voice import router as voice_router

def run_startup_migrations():
    with engine.begin() as conn:
        dialect_name = engine.dialect.name

        if dialect_name == "postgresql":
            conn.execute(
                text(
                    """
                    ALTER TABLE blocked_times
                    ADD COLUMN IF NOT EXISTS series_id VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_blocked_times_series_id
                    ON blocked_times (series_id)
                    """
                )
            )

        elif dialect_name == "sqlite":
            existing_columns = conn.execute(
                text("PRAGMA table_info(blocked_times)")
            ).fetchall()

            column_names = {
                row[1]
                for row in existing_columns
            }

            if "series_id" not in column_names:
                conn.execute(
                    text(
                        """
                        ALTER TABLE blocked_times
                        ADD COLUMN series_id VARCHAR
                        """
                    )
                )

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_blocked_times_series_id
                    ON blocked_times (series_id)
                    """
                )
            )


Base.metadata.create_all(bind=engine)
run_startup_migrations()

app = FastAPI(title="ChairTime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"],
)
app.include_router(barbers_router, prefix="/api")
app.include_router(services_router, prefix="/api")
app.include_router(shops_router, prefix="/api")
app.include_router(availability_router, prefix="/api")
app.include_router(blocked_times_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(customers_router, prefix="/api")
app.include_router(reminders_router, prefix="/api")
app.include_router(migration_router, prefix="/api")
app.include_router(voice_router, prefix="/api")

@app.get("/")
def healthcheck():
    return {"status": "ChairTime backend is running"}
