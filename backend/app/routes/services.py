from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service, ServiceCatalog
from app.schemas import (
    ServiceCatalogCreate,
    ServiceCatalogUpdate,
    ServiceCreate,
    ServiceUpdate,
)


router = APIRouter()


def clean_name(value: str):
    return " ".join(value.strip().split())


def find_catalog_item_by_name(
    db: Session,
    shop_slug: str,
    name: str,
):
    return (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.shop_slug == shop_slug,
            func.lower(ServiceCatalog.name)
            == clean_name(name).lower(),
        )
        .first()
    )


def seed_catalog_from_existing_services(
    db: Session,
    shop_slug: str,
):
    """
    Add any existing staff-assigned service names to the shop's
    master service catalog.

    This lets existing ChairTime shops adopt the catalog without
    re-entering services manually.
    """

    existing_services = (
        db.query(Service)
        .filter(
            Service.shop_slug == shop_slug,
        )
        .all()
    )

    added = False

    for service in existing_services:
        service_name = clean_name(service.name)

        if not service_name:
            continue

        existing_catalog_item = find_catalog_item_by_name(
            db=db,
            shop_slug=shop_slug,
            name=service_name,
        )

        if existing_catalog_item:
            continue

        catalog_item = ServiceCatalog(
            shop_slug=shop_slug,
            name=service_name,
        )

        db.add(catalog_item)
        added = True

    if added:
        db.commit()


#
# MASTER SHOP SERVICE CATALOG
#


@router.get("/service-catalog")
def list_service_catalog(
    shop_slug: str,
    db: Session = Depends(get_db),
):
    seed_catalog_from_existing_services(
        db=db,
        shop_slug=shop_slug,
    )

    return (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.shop_slug == shop_slug,
        )
        .order_by(ServiceCatalog.name)
        .all()
    )


@router.post("/service-catalog")
def create_service_catalog_item(
    payload: ServiceCatalogCreate,
    db: Session = Depends(get_db),
):
    name = clean_name(payload.name)

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Service name is required",
        )

    existing = find_catalog_item_by_name(
        db=db,
        shop_slug=payload.shop_slug,
        name=name,
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="That service already exists",
        )

    catalog_item = ServiceCatalog(
        shop_slug=payload.shop_slug,
        name=name,
    )

    db.add(catalog_item)
    db.commit()
    db.refresh(catalog_item)

    return catalog_item


@router.patch("/service-catalog/{catalog_id}")
def update_service_catalog_item(
    catalog_id: str,
    payload: ServiceCatalogUpdate,
    db: Session = Depends(get_db),
):
    catalog_item = (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.id == catalog_id,
        )
        .first()
    )

    if not catalog_item:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    new_name = clean_name(payload.name)

    if not new_name:
        raise HTTPException(
            status_code=400,
            detail="Service name is required",
        )

    duplicate = (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.shop_slug
            == catalog_item.shop_slug,
            func.lower(ServiceCatalog.name)
            == new_name.lower(),
            ServiceCatalog.id != catalog_item.id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="That service already exists",
        )

    old_name = catalog_item.name

    #
    # Rename the master catalog entry.
    #
    catalog_item.name = new_name

    #
    # Also rename every staff assignment using this service.
    #
    assigned_services = (
        db.query(Service)
        .filter(
            Service.shop_slug
            == catalog_item.shop_slug,
            func.lower(Service.name)
            == old_name.lower(),
        )
        .all()
    )

    for service in assigned_services:
        service.name = new_name

    db.commit()
    db.refresh(catalog_item)

    return catalog_item


@router.delete("/service-catalog/{catalog_id}")
def delete_service_catalog_item(
    catalog_id: str,
    db: Session = Depends(get_db),
):
    catalog_item = (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.id == catalog_id,
        )
        .first()
    )

    if not catalog_item:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    #
    # Do not allow the shop to delete a master service while staff
    # members are still assigned to provide it.
    #
    assigned_service = (
        db.query(Service)
        .filter(
            Service.shop_slug
            == catalog_item.shop_slug,
            func.lower(Service.name)
            == catalog_item.name.lower(),
        )
        .first()
    )

    if assigned_service:
        raise HTTPException(
            status_code=409,
            detail=(
                "This service is still assigned to one or more "
                "staff members. Remove those assignments first."
            ),
        )

    db.delete(catalog_item)
    db.commit()

    return {
        "message": "Service deleted",
    }


#
# STAFF-SPECIFIC SERVICE ASSIGNMENTS
#


@router.post("/services")
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
):
    service_name = clean_name(payload.name)

    if not service_name:
        raise HTTPException(
            status_code=400,
            detail="Service name is required",
        )

    #
    # Prevent the same staff member from being assigned the same
    # service more than once.
    #
    if payload.barber_id and payload.shop_slug:
        existing_assignment = (
            db.query(Service)
            .filter(
                Service.shop_slug
                == payload.shop_slug,
                Service.barber_id
                == payload.barber_id,
                func.lower(Service.name)
                == service_name.lower(),
            )
            .first()
        )

        if existing_assignment:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This service is already assigned "
                    "to this staff member"
                ),
            )

    #
    # Make sure the service also exists in the master catalog.
    #
    if payload.shop_slug:
        catalog_item = find_catalog_item_by_name(
            db=db,
            shop_slug=payload.shop_slug,
            name=service_name,
        )

        if not catalog_item:
            catalog_item = ServiceCatalog(
                shop_slug=payload.shop_slug,
                name=service_name,
            )
            db.add(catalog_item)

    service_data = payload.model_dump()
    service_data["name"] = service_name

    service = Service(**service_data)

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


@router.get("/services")
def list_services(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Service)

    if shop_slug:
        query = query.filter(
            Service.shop_slug == shop_slug
        )

    return query.all()


@router.delete("/services")
def delete_all_services(
    db: Session = Depends(get_db),
):
    db.query(Service).delete()
    db.commit()

    return {
        "message": "All services deleted",
    }


@router.delete("/services/{service_id}")
def delete_service(
    service_id: str,
    db: Session = Depends(get_db),
):
    service = (
        db.query(Service)
        .filter(
            Service.id == service_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    db.delete(service)
    db.commit()

    return {
        "message": "Service assignment removed",
    }


@router.patch("/services/{service_id}")
def update_service(
    service_id: str,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
):
    service = (
        db.query(Service)
        .filter(
            Service.id == service_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    if "name" in updates:
        new_name = clean_name(
            updates["name"]
        )

        if not new_name:
            raise HTTPException(
                status_code=400,
                detail="Service name is required",
            )

        updates["name"] = new_name

        shop_slug = (
            updates.get("shop_slug")
            or service.shop_slug
        )

        if shop_slug:
            catalog_item = find_catalog_item_by_name(
                db=db,
                shop_slug=shop_slug,
                name=new_name,
            )

            if not catalog_item:
                catalog_item = ServiceCatalog(
                    shop_slug=shop_slug,
                    name=new_name,
                )
                db.add(catalog_item)

    for key, value in updates.items():
        setattr(
            service,
            key,
            value,
        )

    db.commit()
    db.refresh(service)

    return service
