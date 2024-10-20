from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
import qrcode
import os
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from PIL import Image


DATABASE_URL = "sqlite:///./queue.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class QueuePoint(Base):
    __tablename__ = "queue_points"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    max_simultaneous = Column(Integer)
    avg_time = Column(Integer)
    people = relationship("PersonInQueue", back_populates="queue_point")


class PersonInQueue(Base):
    __tablename__ = "people_in_queue"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    queue_point_id = Column(Integer, ForeignKey('queue_points.id'))
    is_changed = Column(Boolean, default=False)
    queue_point = relationship("QueuePoint", back_populates="people")
    created_at = Column(DateTime, server_default=func.now())


Base.metadata.create_all(bind=engine)

app = FastAPI()
# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class QueuePointCreate(BaseModel):
    name: str
    max_simultaneous: int
    avg_time: int


class PersonInQueueCreate(BaseModel):
    name: str


class QueuePointResponse(BaseModel):
    id: int
    name: str


    class Config:
        from_attributes = True


class PersonInQueueResponse(BaseModel):
    id: int
    name: str
    queue_point_id: int


    class Config:
        from_attributes = True


class PositionInQueue(BaseModel):
    position_in_queue: int
    estimated_time: int

class QueuePointResponse(BaseModel):
    id: int
    name: str
    max_simultaneous: int
    avg_time: int

    class Config:
        from_attributes = True

class QueuePointDetailResponse(BaseModel):
    queue_point_id: int
    qr_code_url: str
    count_persons: int
    max_simultaneous: int
    avg_time: int

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/queues", response_model=List[QueuePointResponse])
def get_queues(db: Session = Depends(get_db)):
    queues = db.query(QueuePoint).all()
    return queues

@app.get("/queue/{queue_point_id}", response_model=QueuePointDetailResponse)
def get_queue(queue_point_id: int, db: Session = Depends(get_db)):
    db_queue_point = db.query(QueuePoint).filter(QueuePoint.id == queue_point_id).first()
    img_path = f"static/{db_queue_point.id}_qr_code.png"

    if not db_queue_point:
        raise HTTPException(status_code=404, detail="Точка очереди не найдена")

    if not os.path.exists(img_path):
        # Генерация QR-кода
        qr_data = f"http://{{sensitive data}}/add-in-queue?queue_point_id={db_queue_point.id}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Сохранение QR-кода
        img.save(img_path)

    qr_code_url = f"http://{{sensitive data}}:8000/static/{db_queue_point.id}_qr_code.png"  # Обновленный URL для доступа к QR-коду
    count_persons = db.query(PersonInQueue).filter(
        PersonInQueue.queue_point_id == queue_point_id,
    ).count()
    return QueuePointDetailResponse(
        queue_point_id=db_queue_point.id,
        qr_code_url=qr_code_url,
        count_persons=count_persons,
        max_simultaneous=db_queue_point.max_simultaneous,
        avg_time=db_queue_point.avg_time
    )


@app.post("/queue-point/", response_model=QueuePointResponse)
def create_queue_point(queue_point: QueuePointCreate, db: Session = Depends(get_db)):
    try:
        db_queue_point = QueuePoint(
            name=queue_point.name,
            max_simultaneous=queue_point.max_simultaneous,  # Сохранение нового поля
            avg_time=queue_point.avg_time  # Сохранение нового поля
        )
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

    db_person_in_queue = db.query(PersonInQueue).filter(PersonInQueue.name == person.name).first()
    if db_person_in_queue:
        raise HTTPException(status_code=400, detail="Вы уже стоите в очереди")

    try:
        db_person = PersonInQueue(name=person.name, queue_point_id=queue_point_id)
        db.add(db_person)
        db.commit()
        db.refresh(db_person)
        print(db_person.id)
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


@app.get("/queue/{person_in_queue_id}/current-position", response_model=PositionInQueue)
def get_current_queue(person_in_queue_id: int, db: SessionLocal = Depends(get_db)):
    current_person = db.query(PersonInQueue).filter(PersonInQueue.id == person_in_queue_id).first()
    if not current_person:
        raise HTTPException(status_code=404, detail="Человек не найден в очереди")

    db_queue_point = current_person.queue_point

    persons_in_queue = db.query(PersonInQueue).filter(
        PersonInQueue.queue_point_id == current_person.queue_point_id
    ).order_by(
        PersonInQueue.created_at
    ).all()
    list_persons_id =[]
    for i in persons_in_queue:
        list_persons_id.append(i.id)
    # [1, 2, 3].index(2) -> 1
    position_in_queue = list_persons_id.index(person_in_queue_id) + 1

    # people_before / max_simultaneous * avg_time; 10 / 3 * 10 = 30;

    people_before = position_in_queue - 1
    estimated_time = people_before // db_queue_point.max_simultaneous * db_queue_point.avg_time

    return PositionInQueue(
        position_in_queue=position_in_queue,
        estimated_time=estimated_time
    )


@app.put("/queue/{queue_point_id}/pass/{person_id}", response_model=PersonInQueueResponse)
def pass_person(queue_point_id: int, person_id: int, db: SessionLocal = Depends(get_db)):
    db_person = db.query(PersonInQueue).filter(
        PersonInQueue.queue_point_id == queue_point_id,
        PersonInQueue.id == person_id
    ).first()

    if not db_person:
        raise HTTPException(status_code=404, detail="Человек не найден в очереди")


    db_next_person = db.query(PersonInQueue).filter(
        PersonInQueue.queue_point_id == queue_point_id,
        PersonInQueue.created_at > db_person.created_at
    ).order_by(PersonInQueue.created_at).first()

    if not db_next_person:
        raise HTTPException(status_code=404, detail="Невозможно передвинуть человека, он уже последний в очереди")

    try:
        temp_time = db_person.created_at
        db_person.created_at = db_next_person.created_at
        db_next_person.created_at = temp_time

        db_person.is_changed = True

        db.commit()
        db.refresh(db_person)

        return db_person
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при передвижении человека в очереди")
