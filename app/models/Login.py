from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    user_id: str
    avatar: str
    email: str
    name: str
    role: str

class LoginResponse(BaseModel):
    accessToken: str
    user: UserResponse

class User(BaseModel):
    user_id: str
    email: str
    name: str
    avatar: str
    role: str
    password: str