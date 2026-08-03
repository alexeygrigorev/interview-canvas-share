"""Current-user routes."""

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/v1", tags=["Me"])


@router.get("/me", response_model=User, operation_id="getCurrentUser")
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
