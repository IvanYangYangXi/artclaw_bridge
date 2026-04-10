"""
ArtClaw Tool Manager - FastAPI Backend
======================================

统一工具管理器的后端服务，提供 REST API 供前端调用。
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from .api import skills, workflows, tools, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("🚀 ArtClaw Tool Manager Server starting...")
    yield
    # 关闭时
    print("👋 ArtClaw Tool Manager Server shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="ArtClaw Tool Manager API",
    description="统一工具管理器后端 API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])

# 静态文件（前端构建产物）
try:
    app.mount("/", StaticFiles(directory="src/web/dist", html=True), name="static")
except RuntimeError:
    # 开发环境前端未构建时跳过
    pass


@app.get("/api/v1")
async def root():
    """API 根路径"""
    return {
        "name": "ArtClaw Tool Manager API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "skills": "/api/v1/skills",
            "workflows": "/api/v1/workflows",
            "tools": "/api/v1/tools"
        }
    }


def main():
    """启动服务器"""
    uvicorn.run(
        "src.server.main:app",
        host="0.0.0.0",
        port=9876,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
