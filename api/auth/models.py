from pydantic import BaseModel, Field, EmailStr, field_validator


class UserRegister(BaseModel):
    firstname: str = Field(..., title="First Name")
    lastname: str = Field(..., title="Last Name")
    email: EmailStr = Field(..., title="Email")
    password: str = Field(..., title="Password", min_length=8)

    @field_validator("password")
    def password_validator(cls, value: str):
        special_chars = ["/", "!", "@", "#", "$", "%", "^", "&", "*", "+", "-", "?"]
        for char in special_chars:
            if char not in value:
                raise ValueError("В пароле должны быть специальные символы: /!@#$%^&*+-?")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., title="Email")
    password: str = Field(..., title="Password")


class UserEdit(UserRegister):
    firstname: str = Field(title="First Name")
    lastname: str = Field(title="Last Name")
    email: EmailStr = Field(title="Email")
    password: str = Field(title="Password")


