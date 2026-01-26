from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from app.database import get_db
from app.models.database_models import User, UserRole
from app.schemas.schemas import UserCreate, UserLogin, UserResponse, TokenResponse, MicrosoftAuthRequest
from app.services.auth import hash_password, verify_password, create_access_token, decode_access_token
from app.services import microsoft_graph

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(
    token: str,
    db: AsyncSession
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if this is the first user - make them admin
    user_count_result = await db.execute(select(User))
    existing_users = user_count_result.scalars().all()
    is_first_user = len(existing_users) == 0
    
    hashed_password = hash_password(user_data.password)
    
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole.ADMIN if is_first_user else UserRole.USER
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    access_token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email, "role": new_user.role.value}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/microsoft/url")
async def get_microsoft_auth_url(redirect_uri: str):
    auth_url = microsoft_graph.get_auth_url(redirect_uri)
    return {"auth_url": auth_url}


@router.post("/microsoft/callback", response_model=TokenResponse)
async def microsoft_callback(
    auth_request: MicrosoftAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    token_result = await microsoft_graph.exchange_code_for_token(
        auth_request.code,
        auth_request.redirect_uri
    )
    
    if "error" in token_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=token_result.get("error_description", "Failed to authenticate with Microsoft")
        )
    
    access_token = token_result.get("access_token")
    refresh_token = token_result.get("refresh_token")
    
    user_profile = await microsoft_graph.get_user_profile(access_token)
    microsoft_id = user_profile.get("id")
    email = user_profile.get("mail") or user_profile.get("userPrincipalName")
    display_name = user_profile.get("displayName", email)
    
    result = await db.execute(select(User).where(User.microsoft_id == microsoft_id))
    user = result.scalar_one_or_none()
    
    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            user.microsoft_id = microsoft_id
            user.microsoft_access_token = access_token
            user.microsoft_refresh_token = refresh_token
        else:
            user = User(
                email=email,
                full_name=display_name,
                microsoft_id=microsoft_id,
                microsoft_access_token=access_token,
                microsoft_refresh_token=refresh_token,
                role=UserRole.USER
            )
            db.add(user)
    else:
        user.microsoft_access_token = access_token
        user.microsoft_refresh_token = refresh_token
    
    await db.commit()
    await db.refresh(user)
    
    app_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    
    return TokenResponse(
        access_token=app_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    authorization: str = None,
    db: AsyncSession = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    user = await get_current_user(token, db)
    return UserResponse.model_validate(user)


@router.get("/setup/status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check if there are any admin users in the system"""
    result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
    admins = result.scalars().all()
    return {
        "has_admin": len(admins) > 0,
        "admin_count": len(admins)
    }


@router.post("/setup/promote-to-admin", response_model=TokenResponse)
async def promote_to_admin(
    authorization: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Promote the current user to admin if there are no admins in the system"""
    admin_check = await db.execute(select(User).where(User.role == UserRole.ADMIN))
    existing_admins = admin_check.scalars().all()
    
    if len(existing_admins) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users already exist. Contact an existing admin to be promoted."
        )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    user = await get_current_user(token, db)
    
    user.role = UserRole.ADMIN
    await db.commit()
    await db.refresh(user)
    
    new_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    
    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/setup/promote-by-email")
async def promote_user_by_email(
    email: str,
    secret_key: str,
    db: AsyncSession = Depends(get_db)
):
    """Promote a specific user to admin by email (requires secret key for security)"""
    import os
    expected_key = os.getenv("ADMIN_SETUP_KEY", "scheduling-app-admin-setup-2024")
    
    if secret_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key"
        )
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found"
        )
    
    user.role = UserRole.ADMIN
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": f"User {email} has been promoted to admin",
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value
    }
