from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator


class UserRegister(BaseModel):
    firstname: str = Field(..., title="First Name")
    lastname: str = Field(..., title="Last Name")
    email: EmailStr = Field(..., title="Email")
    phone_number: str = Field(..., title="Phone Number")
    password: str = Field(..., title="Password", min_length=8)
    age: int = Field(..., title="Age", ge=1)

    @field_validator("password")
    def password_validator(cls, value: Optional[str]):
        if value is None:
            return value

        special_chars = ["/", "!", "@", "#", "$", "%", "^", "&", "*", "+", "-", "?"]

        if not any(char in value for char in special_chars):
            raise ValueError("Пароль должен содержать хотя бы один специальный символ: /!@#$%^&*+-?")

        if not any(c.isupper() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")

        if not any(c.islower() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну строчную букву")

        if not any(c.isdigit() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        return value

    @field_validator('phone_number')
    def validate_phone(cls, v: Optional[str]):
        if v is None:
            return v

        # Очищаем от пробелов и тире
        v = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        if not v.isdigit():
            raise ValueError('Номер телефона должен содержать только цифры')

        if len(v) < 10 or len(v) > 12:
            raise ValueError('Номер телефона должен содержать 10-12 цифр')

        return v


class UserLogin(BaseModel):
    email: EmailStr = Field(..., title="Email")
    password: str = Field(..., title="Password")


class UserEdit(BaseModel):
    firstname: Optional[str] = Field(None, title="First Name", min_length=1, max_length=100)
    lastname: Optional[str] = Field(None, title="Last Name", min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, title="Phone Number")
    email: Optional[EmailStr] = Field(None, title="Email")
    password: Optional[str] = Field(None, title="Password", min_length=8)
    age: Optional[int] = Field(None, title="Age", ge=1, le=150)

    @field_validator("password")
    def password_validator(cls, value: Optional[str]):
        if value is None:
            return value

        special_chars = ["/", "!", "@", "#", "$", "%", "^", "&", "*", "+", "-", "?"]

        if not any(char in value for char in special_chars):
            raise ValueError("Пароль должен содержать хотя бы один специальный символ: /!@#$%^&*+-?")

        if not any(c.isupper() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")

        if not any(c.islower() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну строчную букву")

        if not any(c.isdigit() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        return value

    @field_validator('phone_number')
    def validate_phone(cls, v: Optional[str]):
        if v is None:
            return v

        # Очищаем от пробелов и тире
        v = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        if not v.isdigit():
            raise ValueError('Номер телефона должен содержать только цифры')

        if len(v) < 10 or len(v) > 12:
            raise ValueError('Номер телефона должен содержать 10-12 цифр')

        return v

