from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import Base, engine
from app.routes.appointments import router as appointments_router
from app.routes.auth import router as auth_router
from app.routes.availability import router as availability_router
from app.routes.barbers import router as barbers_router
from app.routes.billing import router as billing_router
from app.routes.blocked_times import router as blocked_times_router
from app.routes.customers import router as customers_router
from app.routes.migration import router as migration_router
from app.routes.reminders import router as reminders_router
from app.routes.services import router as services_router
from app.routes.shop_availability import (
    router as shop_availability_router,
)
from app.routes.shop_blocked_times import (
    router as shop_blocked_times_router,
)
from app.routes.shops import router as shops_router
from app.routes.voice import router as voice_router


def add_sqlite_column_if_missing(
    conn,
    table_name,
    column_name,
    column_definition,
):
    existing_columns = conn.execute(
        text(f"PRAGMA table_info({table_name})")
    ).fetchall()

    column_names = {
        row[1]
        for row in existing_columns
    }

    if column_name not in column_names:
        conn.execute(
            text(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN {column_name} {column_definition}
                """
            )
        )


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

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS subscription_status VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS ai_voice_enabled BOOLEAN
                    NOT NULL DEFAULT FALSE
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS highlevel_location_id VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS highlevel_phone_number VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    ALTER TABLE shops
                    ADD COLUMN IF NOT EXISTS stripe_connect_account_id VARCHAR
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_customer_id
                    ON shops (stripe_customer_id)
                    WHERE stripe_customer_id IS NOT NULL
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_subscription_id
                    ON shops (stripe_subscription_id)
                    WHERE stripe_subscription_id IS NOT NULL
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_connect_account_id
                    ON shops (stripe_connect_account_id)
                    WHERE stripe_connect_account_id IS NOT NULL
                    """
                )
            )

        elif dialect_name == "sqlite":
            add_sqlite_column_if_missing(
                conn,
                "blocked_times",
                "series_id",
                "VARCHAR",
            )

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_blocked_times_series_id
                    ON blocked_times (series_id)
                    """
                )
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "stripe_customer_id",
                "VARCHAR",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "stripe_subscription_id",
                "VARCHAR",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "subscription_status",
                "VARCHAR",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "trial_ends_at",
                "DATETIME",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "ai_voice_enabled",
                "BOOLEAN NOT NULL DEFAULT 0",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "highlevel_location_id",
                "VARCHAR",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "highlevel_phone_number",
                "VARCHAR",
            )

            add_sqlite_column_if_missing(
                conn,
                "shops",
                "stripe_connect_account_id",
                "VARCHAR",
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_customer_id
                    ON shops (stripe_customer_id)
                    WHERE stripe_customer_id IS NOT NULL
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_subscription_id
                    ON shops (stripe_subscription_id)
                    WHERE stripe_subscription_id IS NOT NULL
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_shops_stripe_connect_account_id
                    ON shops (stripe_connect_account_id)
                    WHERE stripe_connect_account_id IS NOT NULL
                    """
                )
            )


Base.metadata.create_all(
    bind=engine
)

run_startup_migrations()


app = FastAPI(
    title="ChairTime API"
)

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

app.include_router(
    billing_router,
    prefix="/api/billing",
    tags=["Billing"],
)

app.include_router(
    barbers_router,
    prefix="/api",
)

app.include_router(
    services_router,
    prefix="/api",
)

app.include_router(
    shops_router,
    prefix="/api",
)

app.include_router(
    availability_router,
    prefix="/api",
)

app.include_router(
    shop_availability_router,
    prefix="/api",
)

app.include_router(
    blocked_times_router,
    prefix="/api",
)

app.include_router(
    shop_blocked_times_router,
    prefix="/api",
)

app.include_router(
    appointments_router,
    prefix="/api",
)

app.include_router(
    customers_router,
    prefix="/api",
)

app.include_router(
    reminders_router,
    prefix="/api",
)

app.include_router(
    migration_router,
    prefix="/api",
)

app.include_router(
    voice_router,
    prefix="/api",
)


@app.get("/")
def healthcheck():
    return {
        "status": "ChairTime backend is running"
    }
