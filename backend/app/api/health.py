"""健康检查接口"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
  """健康检查响应"""
  status: str
  version: str


@router.get("/health", response_model=HealthResponse)
async def health():
  """健康检查"""
  return HealthResponse(
      status="ok",
      version="0.1.0"
  )