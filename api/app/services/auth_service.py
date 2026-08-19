from __future__ import annotations

import secrets
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class UserAlreadyExists(AuthError):
    pass


class UserDisabled(AuthError):
    pass


class AuthService:
    def __init__(
        self,
        db: Session,
        *,
        jwt_secret_key: str,
        jwt_algorithm: str,
        access_token_minutes: int,
        jwt_issuer: str,
        jwt_audience: str,
    ) -> None:

        self.db = db

        self.jwt_secret_key = (
            jwt_secret_key
        )

        self.jwt_algorithm = (
            jwt_algorithm
        )

        self.access_token_minutes = (
            access_token_minutes
        )

        self.jwt_issuer = (
            jwt_issuer
        )

        self.jwt_audience = (
            jwt_audience
        )

        self.password_hash = (
            PasswordHash.recommended()
        )

    # ======================================================
    # PASSWORD
    # ======================================================

    def hash_password(
        self,
        password: str,
    ) -> str:

        return self.password_hash.hash(
            password
        )

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:

        return self.password_hash.verify(
            password,
            password_hash,
        )

    # ======================================================
    # USER
    # ======================================================

    def create_user(
        self,
        *,
        email: str,
        password: str,
        role: str = "user",
    ) -> User:

        user = User(
            email=(
                email.strip().lower()
            ),

            password_hash=(
                self.hash_password(
                    password
                )
            ),

            role=role,

            is_active=True,
        )

        self.db.add(
            user
        )

        try:
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            raise UserAlreadyExists(
                f"User '{email}' "
                "already exists"
            ) from exc

        self.db.refresh(
            user
        )

        return user

    def get_user_by_email(
        self,
        email: str,
    ) -> User | None:

        statement = (
            select(User)
            .where(
                User.email
                == email.strip().lower()
            )
        )

        return (
            self.db
            .execute(statement)
            .scalar_one_or_none()
        )

    # ======================================================
    # AUTHENTICATION
    # ======================================================

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:

        user = self.get_user_by_email(
            email
        )

        if user is None:
            raise InvalidCredentials(
                "Invalid email or password"
            )

        if not user.is_active:
            raise UserDisabled(
                "User account is disabled"
            )

        if not self.verify_password(
            password,
            user.password_hash,
        ):
            raise InvalidCredentials(
                "Invalid email or password"
            )

        return user

    # ======================================================
    # JWT
    # ======================================================

    def create_access_token(
        self,
        user: User,
    ) -> tuple[str, int]:

        now = datetime.now(
            timezone.utc
        )

        expires = (
            now
            + timedelta(
                minutes=(
                    self.access_token_minutes
                )
            )
        )

        payload = {
            "sub": str(
                user.id
            ),

            "email": (
                user.email
            ),

            "role": (
                user.role
            ),

            "type": "access",

            "iss": (
                self.jwt_issuer
            ),

            "aud": (
                self.jwt_audience
            ),

            "jti": (
                secrets.token_urlsafe(
                    24
                )
            ),

            "iat": int(
                now.timestamp()
            ),

            "exp": int(
                expires.timestamp()
            ),
        }

        token = jwt.encode(
            payload,
            self.jwt_secret_key,
            algorithm=(
                self.jwt_algorithm
            ),
        )

        return (
            token,
            self.access_token_minutes * 60,
        )
