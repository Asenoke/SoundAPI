from datetime import datetime
import enum
from typing import Optional

from sqlalchemy import BigInteger, String, Enum, DateTime, ForeignKey, Numeric, Boolean, Integer, Table, Column, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship, declarative_base

Base = declarative_base()


class Subscription(enum.Enum):
    BASE = 'BASE'
    PREMIUM = 'PREMIUM'


class Role(enum.Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'


# Таблица users
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firstname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lastname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subscription: Mapped[Subscription] = mapped_column(Enum(Subscription), nullable=False, default=Subscription.BASE)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    playlists: Mapped[list["Playlist"]] = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")


# Таблица исполнителей
class Performer(Base):
    __tablename__ = "performers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    style_music: Mapped[str] = mapped_column(String(200), nullable=False)
    photo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    songs: Mapped[list["Song"]] = relationship("Song", back_populates="performer", cascade="all, delete-orphan")


# Таблица песен
class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    performer_id: Mapped[int] = mapped_column(ForeignKey('performers.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    style_music: Mapped[str] = mapped_column(String(200), nullable=False)
    cover: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    auditions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    performer: Mapped[Performer] = relationship("Performer", back_populates="songs")
    playlist_tracks: Mapped[list["PlaylistTrack"]] = relationship("PlaylistTrack", back_populates="song", cascade="all, delete-orphan")


# Таблица плейлистов
class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    user: Mapped[User] = relationship("User", back_populates="playlists")
    tracks: Mapped[list["PlaylistTrack"]] = relationship("PlaylistTrack", back_populates="playlist", cascade="all, delete-orphan")


# Таблица связи плейлистов и песен
class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey('playlists.id'), nullable=False, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey('songs.id'), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # связи
    playlist: Mapped[Playlist] = relationship("Playlist", back_populates="tracks")
    song: Mapped[Song] = relationship("Song", back_populates="playlist_tracks")


# Таблица для refresh токенов
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


# Таблица для всех покупок
class Buy(Base):
    __tablename__ = "buys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    data: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # связи
    user: Mapped["User"] = relationship("User", back_populates="buys")



class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    card_number: Mapped[str] = mapped_column(String(19), nullable=False)
    cvv: Mapped[str] = mapped_column(String(3), nullable=False)
    holders_name: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # связи
    user: Mapped["User"] = relationship("User", back_populates="payments")
    buy: Mapped["Buy"] = relationship("Buy", back_populates="payment")