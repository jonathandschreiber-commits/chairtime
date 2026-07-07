from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes.appointments import router as appointments_router
from app.routes.availability import router as availability_router
from app.routes.barbers import router as barbers_router
from app.routes.blocked_times import router as blocked_times_router
from app.routes.customers import router as customers_router
from app.routes.reminders import router as reminders_router
from app.routes.services import router as services_router
from app.routes.shops import router as shops_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChairTime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(barbers_router, prefix="/api")
app.include_router(services_router, prefix="/api")
app.include_router(shops_router, prefix="/api")
app.include_router(availability_router, prefix="/api")
app.include_router(blocked_times_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(customers_router, prefix="/api")
app.include_router(reminders_router, prefix="/api")


@app.get("/")
def healthcheck():
    return {"status": "ChairTime backend is running"}