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
    def password_validator(cls, value: str):
        special_chars = ["/", "!", "@", "#", "$", "%", "^", "&", "*", "+", "-", "?"]

        # Проверяем, есть ли хотя бы один спецсимвол
        if not any(char in value for char in special_chars):
            raise ValueError("Пароль должен содержать хотя бы один специальный символ: /!@#$%^&*+-?")

        # Дополнительные проверки (опционально)
        if not any(c.isupper() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")

        if not any(c.islower() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну строчную букву")

        if not any(c.isdigit() for c in value):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")

        return value

    @field_validator('phone_number')
    def validate_phone(cls, v: str):
        if not v.isdigit():
            raise ValueError('Номер телефона должен содержать только цифры')


class UserLogin(BaseModel):
    email: EmailStr = Field(..., title="Email")
    password: str = Field(..., title="Password")


class UserEdit(UserRegister):
    firstname: Optional[str] = Field(title="First Name")
    lastname: Optional[str] = Field(title="Last Name")
    phone_number: Optional[str] = Field(title="Phone Number")
    email: Optional[EmailStr] = Field(title="Email")
    password: Optional[str] = Field(title="Password")


