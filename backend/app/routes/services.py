from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service, ServiceCatalog
from app.schemas import (
    ServiceCatalogCreate,
    ServiceCatalogUpdate,
    ServiceCreate,
    ServiceUpdate,
)


router = APIRouter()


def clean_name(value: str):
    return " ".join(value.strip().split())


def normalized_name(value: str):
    return clean_name(value).lower()


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
            == normalized_name(name),
        )
        .first()
    )


def seed_catalog_from_existing_services(
    db: Session,
    shop_slug: str,
):
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

        db.add(
            ServiceCatalog(
                shop_slug=shop_slug,
                name=service_name,
            )
        )

        added = True

    if added:
        db.commit()


def remove_duplicate_catalog_items(
    db: Session,
    shop_slug: str,
):
    """
    Keep one catalog entry for each service name, ignoring
    capitalization and extra spaces.

    Catalog IDs are not used by appointments or staff assignments,
    so duplicate catalog rows can safely be removed.
    """

    catalog_items = (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.shop_slug == shop_slug,
        )
        .order_by(ServiceCatalog.name, ServiceCatalog.id)
        .all()
    )

    seen = {}
    duplicates = []

    for item in catalog_items:
        key = normalized_name(item.name)

        if key in seen:
            duplicates.append(item)
        else:
            seen[key] = item

    if duplicates:
        for item in duplicates:
            db.delete(item)

        db.commit()


def get_assignment_details(
    db: Session,
    shop_slug: str,
    service_name: str,
):
    assignments = (
        db.query(Service)
        .filter(
            Service.shop_slug == shop_slug,
            func.lower(Service.name)
            == normalized_name(service_name),
        )
        .all()
    )

    barber_ids = {
        service.barber_id
        for service in assignments
        if service.barber_id
    }

    if not barber_ids:
        return []

    barbers = (
        db.query(Barber)
        .filter(
            Barber.shop_slug == shop_slug,
            Barber.id.in_(barber_ids),
        )
        .order_by(Barber.name)
        .all()
    )

    return [
        barber.name
        for barber in barbers
    ]


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

    remove_duplicate_catalog_items(
        db=db,
        shop_slug=shop_slug,
    )

    catalog_items = (
        db.query(ServiceCatalog)
        .filter(
            ServiceCatalog.shop_slug == shop_slug,
        )
        .order_by(ServiceCatalog.name)
        .all()
    )

    results = []

    for item in catalog_items:
        assigned_staff = get_assignment_details(
            db=db,
            shop_slug=shop_slug,
            service_name=item.name,
        )

        results.append(
            {
                "id": item.id,
                "shop_slug": item.shop_slug,
                "name": item.name,
                "assignment_count": len(assigned_staff),
                "assigned_staff": assigned_staff,
            }
        )

    return results


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
            == normalized_name(new_name),
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

    catalog_item.name = new_name

    assigned_services = (
        db.query(Service)
        .filter(
            Service.shop_slug
            == catalog_item.shop_slug,
            func.lower(Service.name)
            == normalized_name(old_name),
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

    assigned_staff = get_assignment_details(
        db=db,
        shop_slug=catalog_item.shop_slug,
        service_name=catalog_item.name,
    )

    if assigned_staff:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This service is still assigned to staff."
                ),
                "assigned_staff": assigned_staff,
            },
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

    if payload.barber_id and payload.shop_slug:
        existing_assignment = (
            db.query(Service)
            .filter(
                Service.shop_slug
                == payload.shop_slug,
                Service.barber_id
                == payload.barber_id,
                func.lower(Service.name)
                == normalized_name(service_name),
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

    if payload.shop_slug:
        catalog_item = find_catalog_item_by_name(
            db=db,
            shop_slug=payload.shop_slug,
            name=service_name,
        )

        if not catalog_item:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This service is not in the shop service list. "
                    "Add it from Staff & Services first."
                ),
            )

        #
        # Always use the catalog spelling.
        #
        service_name = catalog_item.name

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
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This service is not in the shop service list."
                    ),
                )

            new_name = catalog_item.name

        updates["name"] = new_name

    for key, value in updates.items():
        setattr(
            service,
            key,
            value,
        )

    db.commit()
    db.refresh(service)

    return service
