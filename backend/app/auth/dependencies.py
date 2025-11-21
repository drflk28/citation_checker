# backend/app/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from ..models.user_models import User

# Простая заглушка для аутентификации
security = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Упрощенная аутентификация для демонстрации
    """
    try:
        # В демо-режиме используем токен как user_id
        user_id = credentials.credentials

        return User(
            id=user_id,
            email=f"user_{user_id}@example.com",
            name=f"User {user_id}"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


# Альтернативная версия для тестирования без аутентификации
async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    if credentials:
        return await get_current_user(credentials)
    return None