from datetime import datetime
import enum

from sqlalchemy import BigInteger, String, Enum, DateTime, ForeignKey, Numeric, Boolean, Integer
from sqlalchemy.orm import mapped_column, Mapped, relationship, declarative_base

# базовый класс для таблиц в бд
Base = declarative_base()

# класс для хранения вариаций подписок
class Subscription(enum.Enum):
    BASE = 'BASE'
    PREMIUM = 'PREMIUM'

# Класс для хранения ролей пользователя
class Role(enum.Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'


# Таблица users в бд
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firstname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lastname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False, index=False, default=1)
    password: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)
    subscription: Mapped[Subscription] = mapped_column(Enum(Subscription), nullable=False, default=Subscription.BASE)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.USER)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user", uselist=False)
    buys: Mapped[list["Buy"]] = relationship("Buy", back_populates="user")

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# Данные карт пользователей для проведения оплаты подписки в бд
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True, nullable=False, index=True)
    card_number: Mapped[str] = mapped_column(String(19), nullable=True, unique=True, index=True)
    cvv: Mapped[str] = mapped_column(String(3), nullable=True, unique=True, index=True)
    holders_name: Mapped[str] = mapped_column(String(), nullable=True, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=False)

    # Связь
    user: Mapped[User] = relationship("User", back_populates="payments")


# таблица с покупками в бд (оплата подписки)
class Buy(Base):
    __tablename__ = "buys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric, nullable=False, index=True)
    data: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, index=False)

    # Связь
    user: Mapped[User] = relationship("User", back_populates="buys")


# Таблица с исполнителями в бд
class Performer(Base):
    __tablename__ = "performers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    style_music: Mapped[str] = mapped_column(String(), nullable=False, index=True)
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)

    # Связь
    songs: Mapped[list["Song"]] = relationship("Song", back_populates="performer")


# таблица с треками в бд
class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    performers_id: Mapped[int] = mapped_column(ForeignKey('performers.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    style_music: Mapped[str] = mapped_column(String(), nullable=False, index=True)
    cover: Mapped[str] = mapped_column(String(255), nullable=True, index=False)
    auditions: Mapped[int] = mapped_column(BigInteger, nullable=False, index=False, default=0)

    # Связь
    performer: Mapped[Performer] = relationship("Performer", back_populates="songs")

# Таблица для хранения refresh токенов
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")



