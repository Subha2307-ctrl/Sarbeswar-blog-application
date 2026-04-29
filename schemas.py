from pydantic import BaseModel, EmailStr


# ======================
# USER SCHEMAS
# ======================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True  


# ======================
# LOGIN SCHEMA
# ======================

class LoginSchema(BaseModel):
    email: EmailStr
    password: str