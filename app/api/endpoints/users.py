from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.models.auth import UserResponse, UserUpdate, UserRole
from app.services.user_service import user_service
from app.middleware.auth_middleware import (
    AuthContext, require_admin, check_rate_limit
)

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="スキップするレコード数"),
    limit: int = Query(100, ge=1, le=1000, description="取得するレコード数"),
    role: Optional[UserRole] = Query(None, description="ロールでフィルタ"),
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザー一覧を取得（管理者専用）"""
    try:
        users = await user_service.list_users(skip=skip, limit=limit, role=role)
        return users
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """特定ユーザーの情報を取得（管理者専用）"""
    try:
        user = await user_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
            rate_limit_requests=user.rate_limit_requests
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザー情報を更新（管理者専用）"""
    try:
        updated_user = await user_service.update_user(user_id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes made"
            )
        
        return UserResponse(
            id=str(updated_user.id),
            username=updated_user.username,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login,
            rate_limit_requests=updated_user.rate_limit_requests
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーを削除（無効化）（管理者専用）"""
    
    # 自分自身は削除できない
    if auth_context.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    try:
        success = await user_service.delete_user(user_id)
        
        if success:
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.get("/stats/overview")
async def get_user_stats(
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザー統計情報を取得（管理者専用）"""
    try:
        total_users = await user_service.get_user_count()
        admin_count = await user_service.get_user_count(UserRole.ADMIN)
        user_count = await user_service.get_user_count(UserRole.USER)
        readonly_count = await user_service.get_user_count(UserRole.READONLY)
        
        return {
            "total_users": total_users,
            "users_by_role": {
                "admin": admin_count,
                "user": user_count,
                "readonly": readonly_count
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user stats: {str(e)}"
        )


@router.post("/{user_id}/verify")
async def verify_user(
    user_id: str,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーを認証済みにする（管理者専用）"""
    try:
        user_update = UserUpdate(is_verified=True)
        updated_user = await user_service.update_user(user_id, user_update)
        
        if updated_user:
            return {"message": "User verified successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify user: {str(e)}"
        )


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーを有効化する（管理者専用）"""
    try:
        user_update = UserUpdate(is_active=True)
        updated_user = await user_service.update_user(user_id, user_update)
        
        if updated_user:
            return {"message": "User activated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    auth_context: AuthContext = Depends(require_admin),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーを無効化する（管理者専用）"""
    
    # 自分自身は無効化できない
    if auth_context.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    try:
        user_update = UserUpdate(is_active=False)
        updated_user = await user_service.update_user(user_id, user_update)
        
        if updated_user:
            return {"message": "User deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}"
        )