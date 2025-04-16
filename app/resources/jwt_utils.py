import datetime
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.resources.constants import (
    AUTHORIZATION_PREFIX,
    JWT_SECRET,
    JWT_DURATION,
    AUTHORIZATION_ALGORITHM,
    JWT_USER_ID,
)


class JwtException(Exception):
    pass


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def generate_jwt_token(user_id, name, email, role):
    jwt_object = {
        JWT_USER_ID: str(user_id),
        "name": str(name),
        "email": str(email),
        "role": str(role),
        "exp": datetime.datetime.utcnow() + JWT_DURATION,
    }
    return AUTHORIZATION_PREFIX + jwt.encode(
        jwt_object, JWT_SECRET, algorithm=AUTHORIZATION_ALGORITHM
    )


async def validate_jwt_authorization(request: Request) -> dict:
    token: Optional[str] = request.headers.get("Authorization")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token = token.replace(AUTHORIZATION_PREFIX, "").strip()
        payload = jwt.decode(token, JWT_SECRET, algorithms=[AUTHORIZATION_ALGORITHM])
        user_id: str = payload.get(JWT_USER_ID)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"user_id": user_id}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
