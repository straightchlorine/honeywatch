from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = create_engine("sqlite://")
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)


def init_db(database_url: str) -> None:
    global engine, SessionLocal
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
