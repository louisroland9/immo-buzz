from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, status
from sqlalchemy import event
from sqlmodel import Field, Session, SQLModel, create_engine, select

# 1. Configuration de l'Engine SQLite Sécurisé (Anti-lock & WAL)
DATABASE_URL = "sqlite:///data/app.db"
connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# 2. Cycle de vie de la Session
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# 3. Modèles SQLModel (Pattern d'héritage recommandé)
class ItemBase(SQLModel):
    title: str = Field(index=True)
    description: str | None = Field(default=None)


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: int


class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


# Initialisation des tables au démarrage
def init_db():
    SQLModel.metadata.create_all(engine)


app = FastAPI(title="Harnais API Segura", on_startup=[init_db])


@app.post("/items/", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(item_in: ItemCreate, db: SessionDep) -> Item:
    db_item = Item.model_validate(item_in)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/items/", response_model=list[ItemRead])
def read_items(db: SessionDep) -> list[Item]:
    return list(db.exec(select(Item)).all())
