from fastapi import APIRouter, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.auth_db import authenticate_user, create_access_token, create_user, _users_collection
from app.schemas import SignInRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signin")


@router.post("/signup", response_model=UserOut)
def signup(payload: UserCreate) -> UserOut:
    try:
        return create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(exc)}") from exc


@router.post("/signin", response_model=TokenResponse)
def signin(payload: SignInRequest) -> TokenResponse:
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(access_token=access_token)


@router.get("/users", response_model=list[UserOut])
def list_users():
    col = _users_collection()
    users = col.stream()
    result = []
    for doc in users:
        data = doc.to_dict()
        result.append(UserOut(
            id=doc.id,
            email=data["email"],
            name=data.get("name", ""),
            created_at=data["created_at"].isoformat() if hasattr(data["created_at"], "isoformat") else str(data["created_at"]),
        ))
    return result