import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.auth.passwords import hash_password, verify_password
from app.auth.sessions import create_session, delete_session
from app.db.mongo import users_collection

router = APIRouter(prefix="/auth", tags=["auth"])


class SignUpBody(BaseModel):
    name: str
    email: str
    password: str


class SignInBody(BaseModel):
    email: str
    password: str


def _clean_email(email: str) -> str:
    return email.strip().lower()


def _public_user(user: dict) -> dict:
    """Fields the browser is allowed to see. Hash and salt stay in Mongo."""
    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
    }


@router.post("/signup")
async def signup(body: SignUpBody):
    name = body.name.strip()
    email = _clean_email(body.email)
    password = body.password

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    salt, password_hash = hash_password(password)
    user = {
        "user_id": f"USER-{secrets.token_hex(3).upper()}",
        "name": name,
        "email": email,
        "salt": salt,
        "password_hash": password_hash,
    }

    try:
        await users_collection.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    token = await create_session(user["user_id"])
    return {"token": token, "user": _public_user(user)}


@router.post("/signin")
async def signin(body: SignInBody):
    email = _clean_email(body.email)
    user = await users_collection.find_one({"email": email})

    password_ok = user is not None and verify_password(
        body.password,
        user["salt"],
        user["password_hash"],
    )
    if not password_ok:
        raise HTTPException(status_code=401, detail="Email or password is wrong.")

    token = await create_session(user["user_id"])
    return {"token": token, "user": _public_user(user)}


@router.post("/signout")
async def signout(authorization: str = Header()):
    """
    Browser sends:  Authorization: Bearer <token>
    Header() reads that header. The token is the part after "Bearer ".
    """
    token = authorization.removeprefix("Bearer ").strip()
    await delete_session(token)
    return {"ok": True}