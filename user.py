from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas  

from deps import get_db
from auth import get_current_user, hash_password

router = APIRouter(prefix="/user", tags=["User"])


# ======================
# CREATE USER
# ======================
@router.post("/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ======================
# GET USER BY ID
# ======================
@router.get("/{id}", response_model=schemas.UserResponse)
def get_user(id: int, db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.id == id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


# ======================
# UPDATE USER
# ======================
@router.put("/{id}", response_model=schemas.UserResponse)
def update_user(
    id: int,
    user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    db_user = db.query(models.User).filter(models.User.id == id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db_user.name = user.name
    db_user.email = user.email
    db_user.password = hash_password(user.password)

    db.commit()
    db.refresh(db_user)

    return db_user


# ======================
# DELETE USER
# ======================
@router.delete("/{id}")
def delete_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    user = db.query(models.User).filter(models.User.id == id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}