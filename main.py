from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from typing import List
import qrcode
import io
from fastapi.responses import StreamingResponse

DATABASE_URL = "postgresql://{{sensitive data}}:{{sensitive data}}@localhost/dbname"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class QueuePoint(Base):
    __tablename__ = "queue_points"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String, index=True)
    created_at = Column(DateTime, default=datetime)
    people = relationship("PersonInQueue", back_populates="queue_point")


class PersonInQueue(Base):
    __tablename__ = "people_in_queue"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    queue_point_id = Column(Integer, ForeignKey('queue_points.id'))
    created_at = Column(DateTime, default=datetime)
    queue_point = relationship("QueuePoint", back_populates="people")


Base.metadata.create_all(bind=engine)

app = FastAPI()


class QueuePointCreate(BaseModel):
    name: str
    address: str


class PersonInQueueCreate(BaseModel):
    name: str


class QueuePointResponse(BaseModel):
    id: int
    name: str
    address: str
    created_at: datetime

    class Config:
        from_attributes = True


class PersonInQueueResponse(BaseModel):
    id: int
    name: str
    queue_point_id: int
    created_at: datetime

    class Config:
        from_attributes = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/queue-point/", response_model=QueuePointResponse)
def create_queue_point(queue_point: QueuePointCreate, db: SessionLocal = Depends(get_db)):
    try:
        db_queue_point = QueuePoint(name=queue_point.name, address=queue_point.address)
        db.add(db_queue_point)
        db.commit()
        db.refresh(db_queue_point)
        return db_queue_point
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при создании точки очереди")


@app.post("/queue/{queue_point_id}/", response_model=PersonInQueueResponse)
def join_queue(queue_point_id: int, person: PersonInQueueCreate, db: SessionLocal = Depends(get_db)):
    db_queue_point = db.query(QueuePoint).filter(QueuePoint.id == queue_point_id).first()

    if not db_queue_point:
        raise HTTPException(status_code=404, detail="Точка очереди не найдена")

    try:
        db_person = PersonInQueue(name=person.name, queue_point_id=queue_point_id)
        db.add(db_person)
        db.commit()
        db.refresh(db_person)
        return db_person
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при добавлении человека в очередь")


@app.delete("/queue/{queue_point_id}/")
def leave_queue(queue_point_id: int, person_id: int, db: SessionLocal = Depends(get_db)):
    db_person = db.query(PersonInQueue).filter(
        PersonInQueue.queue_point_id == queue_point_id,
        PersonInQueue.id == person_id
    ).first()

    if db_person:
        try:
            db.delete(db_person)
            db.commit()
            return {"message": "Удалён из очереди", "person": db_person}
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(status_code=500, detail="Ошибка при удалении человека из очереди")

    raise HTTPException(status_code=404, detail="Человек не найден в очереди")


@app.get("/queue/{queue_point_id}/current/", response_model=List[PersonInQueueResponse])
def get_current_queue(queue_point_id: int, db: SessionLocal = Depends(get_db)):
    db_queue_point = db.query(QueuePoint).filter(QueuePoint.id == queue_point_id).first()

    if not db_queue_point:
        raise HTTPException(status_code=404, detail="Точка очереди не найдена")

    current_queue = db.query(PersonInQueue).filter(PersonInQueue.queue_point_id == queue_point_id).order_by(
        PersonInQueue.created_at).all()
    return current_queue


@app.get("/queue/{queue_point_id}/qrcode/")
def generate_qr(queue_point_id: int, db: SessionLocal = Depends(get_db)):
    db_queue_point = db.query(QueuePoint).filter(QueuePoint.id == queue_point_id).first()

    if not db_queue_point:
        raise HTTPException(status_code=404, detail="Точка очереди не найдена")

    qr = qrcode.make(f"Queue Point ID: {queue_point_id}, Name: {db_queue_point.name}")
    buf = io.BytesIO()
    qr.save(buf)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
