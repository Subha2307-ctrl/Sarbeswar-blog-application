from fastapi import FastAPI, Depends, HTTPException,File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import Table
from sqlalchemy.orm import relationship
from typing import List
from typing import Optional
from sqlalchemy import UniqueConstraint
from sqlalchemy import or_
from datetime import date
from fastapi.staticfiles import StaticFiles
import uuid
import shutil
import os
# ======================
# DATABASE SETUP
# ======================

DATABASE_URL = "sqlite:///./blog.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
#============================
# Many to many tables
#========================
blog_tags = Table(
    "blog_tags",
    Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id")),
    Column("tag_id", Integer, ForeignKey("tags.id"))
)

# ======================
# MODELS (DB)
# ======================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)

class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String, nullable=True) 
    views = Column(Integer, default=0)
    category = relationship("Category", back_populates="blogs")

    tags = relationship(
        "Tag",
        secondary=blog_tags,
        back_populates="blogs"
    )

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)

    blogs = relationship(
        "Blog",
        secondary=blog_tags,
        back_populates="tags"
    )
class Category(Base):  
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)

    blogs = relationship("Blog", back_populates="category")   

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))
    blog_id = Column(Integer, ForeignKey("blogs.id"))

    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)

    replies = relationship(
        "Comment",
        backref="parent",
        remote_side=[id]
    )
class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    blog_id = Column(Integer, ForeignKey("blogs.id")) 
              
# ======================
# SCHEMAS (INPUT)
# ======================

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
class UserUpdate(BaseModel):
    name: str
    email: str
    password: str    

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    class Config:
          from_attributes = True
class TagCreate(BaseModel):
    name: str        
class TagResponse(BaseModel):
    id: int
    name: str    
    class Config:
        orm_mode = True
class CategoryCreate(BaseModel):
    name: str        
class CategoryResponse(BaseModel):   
    id: int
    name: str

    class Config:
        orm_mode = True
     
class BlogCreate(BaseModel):
    title: str
    content: str
    category_id: int 
    tags: List[int] 

class BlogResponse(BaseModel):
    id: int
    title: str
    content: str
    user_id: int
    category: CategoryResponse
    image_url: Optional[str]
    tags: List[TagResponse]

    class Config:
        orm_mode = True   

class LoginSchema(BaseModel):
    email: str
    password: str 
class CommentCreate(BaseModel):
    content: str
    parent_id: int | None = None

class CommentResponse(BaseModel):
    id: int
    content: str
    user_id: int
    blog_id: int
    parent_id: int | None

    class Config:
        orm_mode = True

class AnalyticsResponse(BaseModel):
    total_users: int
    total_posts: int
    most_popular_posts: list        
   
#-----------------------
#Password Hashing
#-----------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)
#-------------------------
#JWT token setup
#-----------------------
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ======================
# CREATE TABLES
# ======================
SECRET_KEY = "mysecretkey123"
ALGORITHM = "HS256"
Base.metadata.create_all(bind=engine)

# ======================
# FASTAPI APP
# ======================

app = FastAPI()
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# DATABASE DEPENDENCY
# ======================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#======================
# Get current user
#========================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.email == email).first()

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
       
# ======================
# USER APIs
# ======================

@app.post("/user")
def create_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    new_user = User(
        name=user.name,
        email=user.email,
        password= hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
#============================
# get by all user
#==================================
@app.get("/user/{id}", response_model=UserResponse)
def get_user_by_id(
    id: int,
    db: Session = Depends(get_db), 
):
    user = db.query(User).filter(User.id == id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
#==========================
#Update User
#=========================
@app.put("/user/{id}", response_model=UserResponse)
def update_user_by_id(
    id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    db_user = db.query(User).filter(User.id == id).first()

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
#=======================
# Delete User
#========================
@app.delete("/user/{id}")
def delete_user_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}
#---------------------------
#Login API
#========================
@app.post("/login")
def login(user: LoginSchema, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Password incorrect")

    access_token = create_access_token(data={"sub": db_user.email})

    return {"access_token": access_token, "token_type": "bearer"}

# ======================
# BLOG APIs
# ======================

# Create Blog
@app.post("/blog", response_model=BlogResponse)
def create_blog(
    title: str = Form(...),
    content: str = Form(...),
    category_id: int = Form(...),
    tags: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
    except:
        raise HTTPException(status_code=400, detail="Tags must be comma separated numbers like 1,2,3")

    tag_objs = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()

    image_url = None

    if image:
        if image.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Only JPG/PNG allowed")

        filename = f"{uuid.uuid4()}_{image.filename}"
        file_path = f"uploads/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        image_url = f"/uploads/{filename}"

    new_blog = Blog(
        title=title,
        content=content,
        user_id=current_user.id,
        category_id=category_id,
        image_url=image_url
    )

    new_blog.tags = tag_objs

    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)

    return new_blog
#====================
# Get All Blogs
#===================
@app.get("/blog",response_model=List[BlogResponse])
def get_all_blogs(
    search: str = None,
    category: int = None,
    author: int = None,
    start_date: date = None,
    end_date: date = None,
    page: int = 1,
    limit: int = 10,
    sort: str = "latest",
    db: Session = Depends(get_db)
):
    query = db.query(Blog)

    if search:
        query = query.filter(
            or_(
                Blog.title.ilike(f"%{search}%"),
                Blog.content.ilike(f"%{search}%")
            )
        )

    if category:
        query = query.filter(Blog.category_id == category)

    if author:
        query = query.filter(Blog.user_id == author)
    if start_date and end_date:
        query = query.filter(Blog.created_at.between(start_date, end_date))

    if sort == "latest":
        query = query.order_by(Blog.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Blog.created_at.asc())

    skip = (page - 1) * limit
    query = query.offset(skip).limit(limit)
    
    return query.all()
#===================
# Get Single Blog
#========================
@app.get("/blog/{id}" ,response_model=BlogResponse)
def get_blog(id: int, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.id == id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog
#-----------------
# Update blog
#---------------
@app.put("/blog/{id}",response_model=BlogResponse)
def update_blog(
    id: int,
    blog: BlogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing_blog = db.query(Blog).filter(Blog.id == id).first()

    if not existing_blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    if existing_blog.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # check category
    category = db.query(Category).filter(Category.id == blog.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    tags = db.query(Tag).filter(Tag.id.in_(blog.tags)).all()

    existing_blog.title = blog.title
    existing_blog.content = blog.content
    existing_blog.category_id = blog.category_id
    existing_blog.tags = tags

    db.commit()
    db.refresh(existing_blog)

    return existing_blog
#=========================
# View blog Api
#========================
@app.post("/blog/{id}/view")
def increase_view(id: int, db: Session = Depends(get_db)):

    blog = db.query(Blog).filter(Blog.id == id).first()

    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    blog.views += 1

    db.commit()

    db.refresh(blog)

    return {
        "message": "view added",
        "total_views": blog.views
    }

#=======================
# Delete Blog
#====================
@app.delete("/blog/{id}")
def delete_blog(id: int, db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)     
    ):
        blog = db.query(Blog).filter(Blog.id == id).first()
        if not blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        if blog.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db.delete(blog)
        db .commit()
        return {"message": "Blog deleted successfully"}

#========================
# Analytics Api
#====================
@app.get("/analytics/dashboard")
def analytics_dashboard(db: Session = Depends(get_db)):

    total_users = db.query(User).count()
    total_posts = db.query(Blog).count()

    top_posts = (
        db.query(Blog)
        .order_by(Blog.views.desc())
        .limit(5)
        .all()
    )

    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "most_popular_posts": [
            {
                "id": post.id,
                "title": post.title,
                "views": post.views
            }
            for post in top_posts
        ]
    }
#===================
# TAG api
#===============
@app.post("/tag", response_model=TagResponse)
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    existing_tag = db.query(Tag).filter(Tag.name == tag.name).first()

    if existing_tag:
        raise HTTPException(status_code=400, detail="Tag already exists")

    new_tag = Tag(name=tag.name) 

    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)

    return new_tag
#=============================
# get by all tag api
#==========================
@app.get("/tag")
def get_all_tags(db: Session = Depends(get_db)):
    return db.query(Tag).all()

#==============================
# Create Category APIs
#==========================
@app.post("/category", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    existing_category = db.query(Category).filter(
        Category.name == category.name
    ).first()

    if existing_category:
        raise HTTPException(
            status_code=400,
            detail="Category already exists"
        )
    new_category = Category(name=category.name)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category
#=====================
# get category
#======================
@app.get("/category")
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()

#========================
#Create comment api
#==========================
@app.post("/post/{post_id}/comments", response_model=CommentResponse)
def add_comment(
    post_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    blog = db.query(Blog).filter(Blog.id == post_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    new_comment = Comment(
        content=comment.content,
        user_id=current_user.id,
        blog_id=post_id,
        parent_id=comment.parent_id
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return new_comment
#============================
#get by id comment
#==========================
@app.get("/post/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.blog_id == post_id).all()
    return comments

#==========================
#Delete comment by id
#=============================
@app.delete("/comment/{id}")
def delete_comment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(Comment.id == id).first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(comment)
    db.commit()

    return {"message": "Comment deleted successfully"}

#=======================
#Like api
#=====================
@app.post("/post/{post_id}/like")
def like_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    blog = db.query(Blog).filter(Blog.id == post_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    existing_like = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.blog_id == post_id
    ).first()

    if existing_like:
        raise HTTPException(status_code=400, detail="Already liked")

    new_like = Like(user_id=current_user.id, blog_id=post_id)
    db.add(new_like)
    db.commit()

    return {"message": "Post liked"}
#======================
#unlike api
#===================
@app.delete("/post/{post_id}/like")
def unlike_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    like = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.blog_id == post_id
    ).first()

    if not like:
        raise HTTPException(status_code=404, detail="Like not found")

    db.delete(like)
    db.commit()

    return {"message": "Post unliked"}

#========================
#get like count
#======================
@app.get("/post/{post_id}/likes")
def get_likes(post_id: int, db: Session = Depends(get_db)):
    count = db.query(Like).filter(Like.blog_id == post_id).count()
    return {"total_likes": count}