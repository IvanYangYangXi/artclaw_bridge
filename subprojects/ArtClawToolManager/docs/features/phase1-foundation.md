# Phase 1: 基础框架 + 对话面板 - 详细开发文档

> 版本: 1.0
> 日期: 2026-04-10
> 工期: 3周

---

## 目录

1. [概述](#1-概述)
2. [开发任务分解](#2-开发任务分解)
3. [API 接口详细定义](#3-api-接口详细定义)
4. [数据库/存储设计](#4-数据库存储设计)
5. [错误处理方案](#5-错误处理方案)
6. [测试计划](#6-测试计划)
7. [代码示例](#7-代码示例)
8. [附录](#8-附录)

---

## 1. 概述

### 1.1 目标

搭建 ArtClaw Tool Manager 的可运行基础框架，实现核心对话面板功能。

### 1.2 交付物清单

| 序号 | 交付物 | 类型 | 说明 |
|------|--------|------|------|
| 1 | FastAPI 后端服务 | 代码 | 完整的 REST API + WebSocket 服务 |
| 2 | React 前端应用 | 代码 | 完整的 Web 界面 |
| 3 | 对话面板组件 | 代码 | 核心功能组件 |
| 4 | Skills 管理界面 | 代码 | 基础列表展示 |
| 5 | API 文档 | 文档 | 自动生成 Swagger/OpenAPI |
| 6 | 单元测试 | 代码 | 核心模块测试覆盖 |

### 1.3 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端 | FastAPI | ^0.115.0 |
| 后端 | Python | 3.11+ |
| 后端 | WebSocket | 原生 |
| 后端 | SQLite | 3.40+ |
| 前端 | React | ^18.2.0 |
| 前端 | TypeScript | ^5.0.0 |
| 前端 | Tailwind CSS | ^3.4.0 |
| 前端 | Zustand | ^4.5.0 |
| 前端 | Axios | ^1.6.0 |

---

## 2. 开发任务分解

### Week 1: 后端基础（FastAPI 项目、数据模型、Skills API）

#### Day 1: 项目初始化与基础架构

**任务**: 搭建 FastAPI 项目骨架

**详细任务**:
1. 创建项目目录结构
2. 配置 Python 虚拟环境
3. 安装依赖: fastapi, uvicorn, sqlalchemy, pydantic, websockets
4. 配置代码质量工具: black, ruff, mypy
5. 创建基础配置文件 (pyproject.toml, .env.example)
6. 配置日志系统

**交付物**:
- 可运行的 FastAPI 基础服务
- 项目目录结构
- 配置文件模板

**验收标准**:
- [ ] `uvicorn main:app --reload` 可正常启动
- [ ] 访问 `/health` 返回 `{"status": "ok"}`
- [ ] 代码格式化工具配置完成

**代码示例**:
```python
# src/server/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api import skills, sessions, chat, system
from core.config import settings
from core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    await init_db()
    yield
    # 关闭时清理

app = FastAPI(
    title="ArtClaw Tool Manager API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

---

#### Day 2: 数据模型与数据库设计

**任务**: 实现核心数据模型

**详细任务**:
1. 设计 SQLAlchemy 模型
2. 实现 Pydantic Schema
3. 配置数据库连接
4. 实现数据库迁移脚本

**交付物**:
- 完整的数据模型定义
- 数据库迁移脚本
- Schema 验证类

**验收标准**:
- [ ] 所有模型可正常创建表
- [ ] Pydantic Schema 验证通过
- [ ] 迁移脚本可正常运行

**代码示例**:
```python
# src/server/models/base.py
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# src/server/models/skill.py
from sqlalchemy import Column, String, Integer, Boolean, JSON, Enum
from .base import Base, TimestampMixin
import enum

class SkillSource(str, enum.Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"

class SkillStatus(str, enum.Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DISABLED = "disabled"

class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    
    id = Column(String, primary_key=True)  # format: {source}/{name}
    name = Column(String, nullable=False)
    description = Column(String)
    version = Column(String, default="1.0.0")
    source = Column(Enum(SkillSource), nullable=False)
    target_dccs = Column(JSON, default=list)  # ["ue57", "comfyui"]
    status = Column(Enum(SkillStatus), default=SkillStatus.NOT_INSTALLED)
    
    # Runtime status
    is_enabled = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)
    is_favorited = Column(Boolean, default=False)
    
    # Stats
    use_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    
    # Data
    skill_path = Column(String)
    priority = Column(Integer, default=0)
    dependencies = Column(JSON, default=list)

# src/server/schemas/skill.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class SkillSource(str, Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"

class SkillStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DISABLED = "disabled"

class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    target_dccs: List[str] = Field(default_factory=list)

class SkillCreate(SkillBase):
    source: SkillSource
    skill_path: Optional[str] = None

class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_enabled: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_favorited: Optional[bool] = None

class SkillResponse(SkillBase):
    id: str
    source: SkillSource
    status: SkillStatus
    is_enabled: bool
    is_pinned: bool
    is_favorited: bool
    use_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SkillListResponse(BaseModel):
    items: List[SkillResponse]
    total: int
    page: int
    page_size: int
```

---

#### Day 3: Skills API 基础实现

**任务**: 实现 Skills CRUD API

**详细任务**:
1. 实现 Skills 列表查询 API
2. 实现 Skills 详情查询 API
3. 实现 Skills 安装/卸载 API
4. 实现批量操作 API

**交付物**:
- 完整的 Skills REST API
- API 文档 (Swagger)

**验收标准**:
- [ ] GET /api/v1/skills 返回技能列表
- [ ] GET /api/v1/skills/{id} 返回技能详情
- [ ] POST /api/v1/skills/{id}/install 安装技能
- [ ] POST /api/v1/skills/batch 批量操作

**代码示例**:
```python
# src/server/api/skills.py
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from schemas.skill import (
    SkillResponse, SkillListResponse, SkillUpdate,
    SkillStatus, SkillSource
)
from services.skill_service import SkillService
from models.skill import Skill

router = APIRouter()

@router.get("", response_model=SkillListResponse)
async def list_skills(
    source: Optional[SkillSource] = None,
    status: Optional[SkillStatus] = None,
    search: Optional[str] = None,
    pinned: Optional[bool] = None,
    favorited: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取技能列表，支持筛选和分页"""
    service = SkillService(db)
    
    filters = {
        "source": source,
        "status": status,
        "search": search,
        "pinned": pinned,
        "favorited": favorited
    }
    
    items, total = await service.list_skills(
        filters=filters,
        page=page,
        page_size=page_size
    )
    
    return SkillListResponse(
        items=[SkillResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str, db: Session = Depends(get_db)):
    """获取技能详情"""
    service = SkillService(db)
    skill = await service.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return SkillResponse.model_validate(skill)

@router.post("/{skill_id}/install")
async def install_skill(skill_id: str, db: Session = Depends(get_db)):
    """安装技能"""
    service = SkillService(db)
    
    try:
        result = await service.install_skill(skill_id)
        return {"success": True, "message": "Skill installed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{skill_id}/uninstall")
async def uninstall_skill(skill_id: str, db: Session = Depends(get_db)):
    """卸载技能"""
    service = SkillService(db)
    
    try:
        await service.uninstall_skill(skill_id)
        return {"success": True, "message": "Skill uninstalled successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    update_data: SkillUpdate,
    db: Session = Depends(get_db)
):
    """更新技能（启用/禁用/钉选/收藏）"""
    service = SkillService(db)
    
    skill = await service.update_skill(skill_id, update_data)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return SkillResponse.model_validate(skill)

@router.post("/batch")
async def batch_operation(
    operation: str = Body(..., description="install|uninstall|enable|disable|pin|unpin|favorite|unfavorite"),
    skill_ids: List[str] = Body(...),
    db: Session = Depends(get_db)
):
    """批量操作技能"""
    service = SkillService(db)
    
    valid_operations = ["install", "uninstall", "enable", "disable", 
                       "pin", "unpin", "favorite", "unfavorite"]
    
    if operation not in valid_operations:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid operation. Must be one of: {valid_operations}"
        )
    
    results = await service.batch_operation(operation, skill_ids)
    
    return {
        "success": True,
        "operation": operation,
        "total": len(skill_ids),
        "succeeded": results["succeeded"],
        "failed": results["failed"],
        "errors": results.get("errors", [])
    }
```

---

#### Day 4: 会话管理 API

**任务**: 实现对话会话管理 API

**详细任务**:
1. 设计 Session 数据模型
2. 实现 Session CRUD API
3. 实现 Session 历史查询

**交付物**:
- Session 管理 API
- 消息存储模型

**验收标准**:
- [ ] 可创建/获取/更新/删除会话
- [ ] 支持会话列表分页
- [ ] 支持按时间筛选

**代码示例**:
```python
# src/server/models/session.py
from sqlalchemy import Column, String, DateTime, Integer, Text, Enum, JSON
from .base import Base, TimestampMixin
import enum

class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True)  # UUID
    title = Column(String, default="New Chat")
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    
    # Context
    dcc_software = Column(String, default="none")  # ue57, maya2024, comfyui
    agent_platform = Column(String, default="openclaw")
    agent_id = Column(String)
    
    # Stats
    message_count = Column(Integer, default=0)
    context_usage = Column(Integer, default=0)  # token count
    
    # Settings
    pinned_skills = Column(JSON, default=list)  # [skill_id, ...]

class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # user, assistant, system, tool
    content = Column(Text)
    
    # For tool calls
    tool_calls = Column(JSON)
    tool_results = Column(JSON)
    
    # Metadata
    tokens_used = Column(Integer)
    latency_ms = Column(Integer)

# src/server/api/sessions.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from schemas.session import (
    SessionCreate, SessionResponse, SessionUpdate,
    MessageCreate, MessageResponse, SessionListResponse
)
from services.session_service import SessionService

router = APIRouter()

@router.get("", response_model=SessionListResponse)
async def list_sessions(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取会话列表"""
    service = SessionService(db)
    
    items, total = await service.list_sessions(
        status=status,
        search=search,
        page=page,
        page_size=page_size
    )
    
    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )

@router.post("", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db)
):
    """创建新会话"""
    service = SessionService(db)
    session = await service.create_session(data)
    return SessionResponse.model_validate(session)

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """获取会话详情"""
    service = SessionService(db)
    session = await service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse.model_validate(session)

@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    db: Session = Depends(get_db)
):
    """更新会话"""
    service = SessionService(db)
    session = await service.update_session(session_id, data)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse.model_validate(session)

@router.delete("/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """删除会话"""
    service = SessionService(db)
    success = await service.delete_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True}

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    before_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取会话消息历史"""
    service = SessionService(db)
    messages = await service.get_messages(session_id, before_id, limit)
    return [MessageResponse.model_validate(m) for m in messages]

@router.post("/{session_id}/messages", response_model=MessageResponse)
async def create_message(
    session_id: str,
    data: MessageCreate,
    db: Session = Depends(get_db)
):
    """创建消息（用于存储用户消息）"""
    service = SessionService(db)
    message = await service.create_message(session_id, data)
    return MessageResponse.model_validate(message)
```

---

#### Day 5: 系统集成与配置管理

**任务**: 实现系统配置和集成

**详细任务**:
1. 实现配置管理服务
2. 集成 OpenClaw Gateway 客户端
3. 实现 DCC 连接管理
4. 实现系统状态 API

**交付物**:
- 配置管理系统
- Gateway 客户端
- 系统状态 API

**验收标准**:
- [ ] 配置可持久化到文件
- [ ] 可检测 Gateway 连接状态
- [ ] 可检测 DCC 连接状态

**代码示例**:
```python
# src/server/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App
    APP_NAME: str = "ArtClaw Tool Manager"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./artclaw.db"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # OpenClaw Gateway
    GATEWAY_URL: str = "ws://localhost:9876"
    GATEWAY_API_URL: str = "http://localhost:9876"
    
    # Data paths
    DATA_DIR: str = "~/.artclaw"
    SKILLS_DIR: str = "~/.openclaw/skills"
    
    class Config:
        env_file = ".env"

settings = Settings()

# src/server/services/gateway_client.py
import asyncio
import json
from typing import Optional, Callable, Dict, Any
import websockets

class GatewayClient:
    """OpenClaw Gateway WebSocket 客户端"""
    
    def __init__(self, url: str = "ws://localhost:9876"):
        self.url = url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.message_handlers: List[Callable] = []
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """连接到 Gateway"""
        try:
            self.ws = await websockets.connect(self.url)
            self.connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            return True
        except Exception as e:
            print(f"Failed to connect to Gateway: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
        if self.ws:
            await self.ws.close()
    
    async def _receive_loop(self):
        """接收消息循环"""
        try:
            while self.connected:
                message = await self.ws.recv()
                data = json.loads(message)
                for handler in self.message_handlers:
                    try:
                        await handler(data)
                    except Exception as e:
                        print(f"Message handler error: {e}")
        except websockets.exceptions.ConnectionClosed:
            self.connected = False
    
    async def send(self, data: Dict[str, Any]):
        """发送消息"""
        if self.ws and self.connected:
            await self.ws.send(json.dumps(data))
    
    def on_message(self, handler: Callable):
        """注册消息处理器"""
        self.message_handlers.append(handler)
    
    async def send_chat_message(
        self, 
        session_id: str, 
        content: str,
        agent_id: Optional[str] = None,
        attachments: Optional[List[Dict]] = None
    ):
        """发送聊天消息"""
        message = {
            "type": "chat",
            "session_id": session_id,
            "content": content,
            "agent_id": agent_id,
            "attachments": attachments or []
        }
        await self.send(message)

# src/server/api/system.py
from fastapi import APIRouter
from core.config import settings
from services.gateway_client import GatewayClient
from services.dcc_manager import DCCManager

router = APIRouter()
gateway_client = GatewayClient(settings.GATEWAY_URL)
dcc_manager = DCCManager()

@router.get("/status")
async def get_system_status():
    """获取系统状态"""
    gateway_status = "connected" if gateway_client.connected else "disconnected"
    
    return {
        "status": "ok",
        "version": "1.0.0",
        "gateway": {
            "status": gateway_status,
            "url": settings.GATEWAY_URL
        },
        "dccs": await dcc_manager.get_all_status()
    }

@router.post("/gateway/connect")
async def connect_gateway():
    """连接到 Gateway"""
    success = await gateway_client.connect()
    return {"success": success, "status": "connected" if success else "disconnected"}

@router.post("/gateway/disconnect")
async def disconnect_gateway():
    """断开 Gateway"""
    await gateway_client.disconnect()
    return {"success": True, "status": "disconnected"}

@router.get("/config")
async def get_config():
    """获取系统配置"""
    return {
        "app_name": settings.APP_NAME,
        "gateway_url": settings.GATEWAY_URL,
        "data_dir": settings.DATA_DIR
    }
```

---

#### Day 6-7: Week 1 测试与修复

**任务**: 完成 Week 1 测试

**详细任务**:
1. 编写单元测试
2. 集成测试
3. API 文档验证
4. Bug 修复

**交付物**:
- 单元测试报告
- API 文档
- 修复后的代码

**验收标准**:
- [ ] 核心模块测试覆盖率 > 80%
- [ ] 所有 API 可正常调用
- [ ] 文档完整准确

---

### Week 2: 对话面板核心（WebSocket、会话管理、上下文管理）

#### Day 8: WebSocket 基础架构

**任务**: 实现 WebSocket 服务

**详细任务**:
1. 创建 WebSocket 连接管理器
2. 实现消息路由
3. 实现心跳检测

**交付物**:
- WebSocket 服务
- 连接管理器

**验收标准**:
- [ ] 客户端可建立 WebSocket 连接
- [ ] 支持多客户端同时连接
- [ ] 心跳检测正常

**代码示例**:
```python
# src/server/websocket/manager.py
from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # session_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> session_ids
        self.user_sessions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """建立连接"""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
    
    async def send_to_session(self, session_id: str, message: dict):
        """发送消息到会话的所有连接"""
        if session_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.active_connections[session_id].discard(conn)
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for session_id in self.active_connections:
            await self.send_to_session(session_id, message)

manager = ConnectionManager()

# src/server/websocket/chat_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import json

from .manager import manager
from services.gateway_client import gateway_client
from services.session_service import SessionService
from core.database import SessionLocal

router = APIRouter()

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """聊天 WebSocket 端点"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "chat":
                # 处理聊天消息
                await handle_chat_message(session_id, message, websocket)
            elif msg_type == "ping":
                # 心跳响应
                await websocket.send_json({"type": "pong"})
            elif msg_type == "typing":
                # 转发打字状态
                await manager.send_to_session(session_id, {
                    "type": "typing",
                    "is_typing": message.get("is_typing", False)
                })
            elif msg_type == "cancel":
                # 取消生成
                await handle_cancel_generation(session_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

async def handle_chat_message(session_id: str, message: dict, websocket: WebSocket):
    """处理聊天消息"""
    content = message.get("content", "")
    agent_id = message.get("agent_id")
    
    # 保存用户消息到数据库
    db = SessionLocal()
    try:
        session_service = SessionService(db)
        await session_service.create_message(
            session_id=session_id,
            role="user",
            content=content
        )
    finally:
        db.close()
    
    # 转发到 Gateway
    await gateway_client.send_chat_message(
        session_id=session_id,
        content=content,
        agent_id=agent_id
    )
    
    # 通知客户端消息已接收
    await websocket.send_json({
        "type": "message_received",
        "session_id": session_id
    })

# 注册 Gateway 消息处理器
async def on_gateway_message(data: dict):
    """处理来自 Gateway 的消息"""
    session_id = data.get("session_id")
    if session_id:
        await manager.send_to_session(session_id, data)

gateway_client.on_message(on_gateway_message)
```

---

#### Day 9-10: 聊天消息处理

**任务**: 实现聊天消息处理逻辑

**详细任务**:
1. 实现消息流处理
2. 实现工具调用处理
3. 实现附件上传处理

**交付物**:
- 消息处理服务
- 工具调用处理器
- 文件上传 API

**验收标准**:
- [ ] 支持流式消息接收
- [ ] 工具调用可正确显示
- [ ] 支持图片/文件上传

**代码示例**:
```python
# src/server/services/chat_service.py
from typing import AsyncIterator, Dict, Any, Optional
import json

class ChatService:
    """聊天服务"""
    
    def __init__(self, db_session, gateway_client):
        self.db = db_session
        self.gateway = gateway_client
    
    async def send_message(
        self,
        session_id: str,
        content: str,
        attachments: Optional[list] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """发送消息并流式接收响应"""
        
        # 保存用户消息
        await self._save_message(session_id, "user", content, attachments)
        
        # 发送给 Gateway
        await self.gateway.send_chat_message(
            session_id=session_id,
            content=content,
            attachments=attachments
        )
        
        # 流式接收响应
        async for chunk in self._stream_response(session_id):
            yield chunk
    
    async def _stream_response(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """流式接收 AI 响应"""
        # 实际实现依赖于 Gateway 的流式协议
        # 这里使用事件监听模式
        pass
    
    async def handle_tool_call(
        self,
        session_id: str,
        tool_call: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理工具调用"""
        tool_name = tool_call.get("name")
        parameters = tool_call.get("parameters", {})
        
        # 根据工具名称路由到对应处理器
        if tool_name.startswith("run_python"):
            return await self._handle_dcc_tool(tool_name, parameters)
        elif tool_name.startswith("skill_"):
            return await self._handle_skill_tool(tool_name, parameters)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _handle_dcc_tool(self, tool_name: str, parameters: dict) -> dict:
        """处理 DCC 工具调用"""
        # 转发到对应的 DCC Adapter
        dcc = parameters.get("dcc", "comfyui")
        # ... 实现 DCC 调用
        return {"status": "success", "result": None}
    
    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: Optional[list] = None
    ):
        """保存消息到数据库"""
        from models.session import ChatMessage
        import uuid
        
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=attachments
        )
        self.db.add(message)
        self.db.commit()

# src/server/api/chat.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
import uuid
import shutil
import os

from core.config import settings
from core.database import get_db
from services.chat_service import ChatService
from services.gateway_client import gateway_client

router = APIRouter()
UPLOAD_DIR = os.path.expanduser("~/.artclaw/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """上传文件/图片"""
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "url": f"/api/v1/chat/files/{file_id}{file_ext}",
        "type": file.content_type
    }

@router.post("/sessions/{session_id}/send")
async def send_chat_message(
    session_id: str,
    content: str,
    agent_id: Optional[str] = None,
    attachments: Optional[List[str]] = None
):
    """发送聊天消息（HTTP 方式，非流式）"""
    # 实际生产环境使用 WebSocket 流式传输
    # 这里提供 HTTP 备用方案
    pass
```

---

#### Day 11-12: 上下文管理

**任务**: 实现上下文管理功能

**详细任务**:
1. 实现 Skill 钉选功能
2. 实现上下文用量计算
3. 实现上下文压缩提示

**交付物**:
- 上下文管理服务
- Skill 钉选 API

**验收标准**:
- [ ] 可钉选/取消钉选 Skill
- [ ] 上下文用量可正确计算
- [ ] 超限时给出提示

**代码示例**:
```python
# src/server/services/context_service.py
from typing import List, Dict, Any
import json

class ContextService:
    """上下文管理服务"""
    
    # Token 估算常量
    TOKENS_PER_MESSAGE = 4
    TOKENS_PER_CHARACTER = 0.5
    MAX_CONTEXT_TOKENS = 128000  # Claude-4 context limit
    WARNING_THRESHOLD = 0.8
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_pinned_skills(self, session_id: str) -> List[Dict]:
        """获取会话钉选的 Skills"""
        from models.session import ChatSession
        
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session or not session.pinned_skills:
            return []
        
        # 获取 Skill 详情
        from models.skill import Skill
        skills = []
        for skill_id in session.pinned_skills:
            skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
            if skill:
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description
                })
        
        return skills
    
    async def pin_skill(self, session_id: str, skill_id: str):
        """钉选 Skill"""
        from models.session import ChatSession
        
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session:
            return False
        
        pinned = session.pinned_skills or []
        if skill_id not in pinned:
            pinned.append(skill_id)
            session.pinned_skills = pinned
            self.db.commit()
        
        return True
    
    async def unpin_skill(self, session_id: str, skill_id: str):
        """取消钉选 Skill"""
        from models.session import ChatSession
        
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session or not session.pinned_skills:
            return False
        
        pinned = session.pinned_skills
        if skill_id in pinned:
            pinned.remove(skill_id)
            session.pinned_skills = pinned
            self.db.commit()
        
        return True
    
    async def calculate_context_usage(
        self,
        session_id: str,
        include_pinned_skills: bool = True
    ) -> Dict[str, Any]:
        """计算上下文用量"""
        from models.session import ChatSession, ChatMessage
        
        # 获取消息
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).all()
        
        # 计算消息 tokens
        message_tokens = 0
        for msg in messages:
            message_tokens += self.TOKENS_PER_MESSAGE
            message_tokens += len(msg.content or "") * self.TOKENS_PER_CHARACTER
        
        # 计算钉选 Skills tokens
        skill_tokens = 0
        if include_pinned_skills:
            skills = await self.get_pinned_skills(session_id)
            for skill in skills:
                skill_tokens += len(skill.get("description", "")) * self.TOKENS_PER_CHARACTER
                skill_tokens += 100  # Skill 元数据估算
        
        total_tokens = message_tokens + skill_tokens
        usage_percent = (total_tokens / self.MAX_CONTEXT_TOKENS) * 100
        
        return {
            "total_tokens": int(total_tokens),
            "message_tokens": int(message_tokens),
            "skill_tokens": int(skill_tokens),
            "max_tokens": self.MAX_CONTEXT_TOKENS,
            "usage_percent": round(usage_percent, 1),
            "is_warning": usage_percent >= (self.WARNING_THRESHOLD * 100),
            "is_critical": usage_percent >= 95
        }
    
    async def get_context_summary(self, session_id: str) -> str:
        """生成上下文摘要（用于压缩）"""
        # 这里可以集成 AI 生成摘要
        # 简化版本：返回最近几条消息的摘要
        from models.session import ChatMessage
        
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        
        summary_parts = []
        for msg in reversed(messages):
            prefix = "User" if msg.role == "user" else "AI"
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            summary_parts.append(f"{prefix}: {content}")
        
        return "\n".join(summary_parts)

# API 端点
@router.get("/sessions/{session_id}/context")
async def get_context_info(session_id: str, db: Session = Depends(get_db)):
    """获取上下文信息"""
    service = ContextService(db)
    
    usage = await service.calculate_context_usage(session_id)
    pinned_skills = await service.get_pinned_skills(session_id)
    
    return {
        "usage": usage,
        "pinned_skills": pinned_skills
    }

@router.post("/sessions/{session_id}/pin-skill")
async def pin_skill_to_session(
    session_id: str,
    skill_id: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """钉选 Skill 到会话"""
    service = ContextService(db)
    success = await service.pin_skill(session_id, skill_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True}

@router.post("/sessions/{session_id}/unpin-skill")
async def unpin_skill_from_session(
    session_id: str,
    skill_id: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """取消钉选 Skill"""
    service = ContextService(db)
    success = await service.unpin_skill(session_id, skill_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True}
```

---

#### Day 13-14: Week 2 测试与修复

**任务**: 完成 Week 2 测试

**详细任务**:
1. WebSocket 压力测试
2. 消息流测试
3. 上下文管理测试
4. Bug 修复

**交付物**:
- WebSocket 测试报告
- 性能测试数据
- 修复后的代码

**验收标准**:
- [ ] WebSocket 支持 100+ 并发连接
- [ ] 消息延迟 < 100ms
- [ ] 上下文计算准确

---

### Week 3: 前端基础（React 项目、对话面板 UI、Skills 列表）

#### Day 15: React 项目初始化

**任务**: 搭建 React 项目

**详细任务**:
1. 使用 Vite 创建项目
2. 配置 TypeScript
3. 配置 Tailwind CSS
4. 安装依赖: react-router-dom, zustand, axios
5. 配置 ESLint + Prettier
6. 创建项目目录结构

**交付物**:
- 可运行的 React 项目
- 项目配置

**验收标准**:
- [ ] `npm run dev` 可正常启动
- [ ] TypeScript 编译无错误
- [ ] Tailwind CSS 样式生效

**代码示例**:
```typescript
// src/web/package.json
{
  "name": "artclaw-tool-manager-web",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "format": "prettier --write \"src/**/*.{ts,tsx}\""
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.56.0",
    "postcss": "^8.4.0",
    "prettier": "^3.2.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}

// src/web/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)

// src/web/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ChatPage from './pages/Chat'
import SkillsPage from './pages/Skills'
import WorkflowsPage from './pages/Workflows'
import ToolsPage from './pages/Tools'
import SettingsPage from './pages/Settings'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
```

---

#### Day 16-17: 对话面板 UI 组件

**任务**: 实现对话面板核心组件

**详细任务**:
1. 实现 StatusBar 组件
2. 实现 MessageList 组件
3. 实现 ChatInput 组件
4. 实现 Toolbar 组件

**交付物**:
- 完整的对话面板组件
- 组件样式

**验收标准**:
- [ ] 所有组件可正常渲染
- [ ] 样式符合 UI 设计规范
- [ ] 支持响应式布局

**代码示例**:
```typescript
// src/web/src/components/Chat/StatusBar.tsx
import { useState } from 'react'
import { useChatStore } from '../../stores/chatStore'

interface StatusBarProps {
  sessionId: string
}

export function StatusBar({ sessionId }: StatusBarProps) {
  const { connectionStatus, contextUsage, currentDCC, currentAgent } = useChatStore()
  const [expanded, setExpanded] = useState(false)
  
  const statusColors = {
    connected: 'bg-green-500',
    disconnected: 'bg-gray-500',
    connecting: 'bg-orange-500'
  }
  
  const usageColor = contextUsage > 80 ? 'text-red-400' : 
                     contextUsage > 60 ? 'text-orange-400' : 'text-green-400'
  
  return (
    <div className="bg-[#2D2D2D] border-b border-[#555555] p-2">
      {/* Row 1 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <button 
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 text-sm"
          >
            <span className={`w-2 h-2 rounded-full ${statusColors[connectionStatus]}`} />
            <span className="text-gray-300">
              {connectionStatus === 'connected' ? '已连接' : '已断开'}
            </span>
          </button>
          
          {/* DCC Selector */}
          <div className="flex items-center gap-1 text-sm">
            <span className="text-gray-500">|</span>
            <span className="text-blue-400">{currentDCC || 'None'}</span>
          </div>
          
          {/* Agent Selector */}
          <div className="flex items-center gap-1 text-sm">
            <span className="text-gray-500">|</span>
            <span className="text-purple-400">{currentAgent || 'Claude-4'}</span>
          </div>
        </div>
        
        {/* Context Usage */}
        <div className="flex items-center gap-2">
          <span className={`text-sm ${usageColor}`}>
            上下文: {contextUsage}%
          </span>
          <button className="text-gray-400 hover:text-white">
            ⚙️
          </button>
        </div>
      </div>
      
      {/* Row 2 - Expanded */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-[#555555] text-xs text-gray-400">
          <div className="flex items-center gap-4">
            <span>OpenClaw · {connectionStatus === 'connected' ? '已连接' : '已断开'}</span>
            <span>MCP就绪</span>
            <span>ws://localhost:9876</span>
          </div>
          <div className="mt-2 flex gap-2">
            <button className="px-2 py-1 bg-[#3C3C3C] rounded hover:bg-[#4A4A4A]">
              连接
            </button>
            <button className="px-2 py-1 bg-[#3C3C3C] rounded hover:bg-[#4A4A4A]">
              断开
            </button>
            <button className="px-2 py-1 bg-[#3C3C3C] rounded hover:bg-[#4A4A4A]">
              诊断
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// src/web/src/components/Chat/MessageList.tsx
import { useEffect, useRef } from 'react'
import { useChatStore } from '../../stores/chatStore'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: string
  toolCalls?: any[]
  attachments?: any[]
}

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
}

export function MessageList({ messages, isTyping }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])
  
  const getMessageStyle = (role: string) => {
    switch (role) {
      case 'user':
        return 'bg-[#2A3530] border-l-3 border-green-500 ml-auto'
      case 'assistant':
        return 'bg-[#282C38] border-l-3 border-blue-500'
      case 'tool':
        return 'bg-[#262218] border-l-3 border-yellow-500'
      default:
        return 'bg-[#2A2A2A]'
    }
  }
  
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`max-w-[90%] rounded-lg p-3 ${getMessageStyle(message.role)}`}
        >
          {/* Header */}
          <div className="flex items-center gap-2 mb-1 text-xs text-gray-400">
            <span>
              {message.role === 'user' ? '👤' : 
               message.role === 'assistant' ? '🤖' : '🔧'}
            </span>
            <span>{message.role === 'user' ? '用户' : 
                   message.role === 'assistant' ? 'AI' : '工具'}</span>
            <span className="text-gray-600">{message.timestamp}</span>
          </div>
          
          {/* Content */}
          <div className="text-sm text-gray-200 whitespace-pre-wrap">
            {message.content}
          </div>
          
          {/* Tool Calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-2 space-y-2">
              {message.toolCalls.map((tool, idx) => (
                <ToolCallCard key={idx} tool={tool} />
              ))}
            </div>
          )}
          
          {/* Attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 flex gap-2">
              {message.attachments.map((att, idx) => (
                <AttachmentPreview key={idx} attachment={att} />
              ))}
            </div>
          )}
        </div>
      ))}
      
      {/* Typing Indicator */}
      {isTyping && (
        <div className="bg-[#2A283A] rounded-lg p-3 max-w-[90%]">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span>💭</span>
            <span>思考中...</span>
          </div>
          <div className="mt-1 text-sm text-gray-500">
            正在处理...
          </div>
        </div>
      )}
      
      <div ref={bottomRef} />
    </div>
  )
}

function ToolCallCard({ tool }: { tool: any }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="bg-[#1E1E1E] rounded border border-[#444]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-2 text-xs"
      >
        <span className="text-yellow-400">🔧 {tool.name}</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      
      {expanded && (
        <div className="p-2 border-t border-[#444] text-xs">
          <pre className="text-gray-400 overflow-x-auto">
            {JSON.stringify(tool.parameters, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

// src/web/src/components/Chat/ChatInput.tsx
import { useState, useRef, KeyboardEvent } from 'react'
import { useChatStore } from '../../stores/chatStore'

interface ChatInputProps {
  onSend: (content: string, attachments?: File[]) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [content, setContent] = useState('')
  const [attachments, setAttachments] = useState<File[]>([])
  const [showCommands, setShowCommands] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  const commands = [
    { cmd: '/connect', desc: '连接 OpenClaw Gateway' },
    { cmd: '/disconnect', desc: '断开 Gateway 连接' },
    { cmd: '/clear', desc: '清空聊天记录' },
    { cmd: '/new', desc: '开始新对话' },
  ]
  
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  
  const handleSend = () => {
    if (!content.trim() || disabled) return
    
    onSend(content.trim(), attachments)
    setContent('')
    setAttachments([])
  }
  
  const handleInputChange = (value: string) => {
    setContent(value)
    setShowCommands(value.startsWith('/') && value.length < 20)
  }
  
  return (
    <div className="border-t border-[#555555] bg-[#2D2D2D]">
      {/* Quick Input */}
      <div className="px-3 py-2 flex gap-2 overflow-x-auto">
        {['常用提示', '创建 Skill', '文生图', '批量导出'].map((tip) => (
          <button
            key={tip}
            onClick={() => setContent(tip)}
            className="px-3 py-1 text-xs bg-[#3C3C3C] rounded-full text-gray-300 
                       hover:bg-[#4A4A4A] whitespace-nowrap"
          >
            {tip}
          </button>
        ))}
      </div>
      
      {/* Attachment Preview */}
      {attachments.length > 0 && (
        <div className="px-3 py-2 flex gap-2">
          {attachments.map((file, idx) => (
            <div key={idx} className="flex items-center gap-1 text-xs bg-[#3C3C3C] px-2 py-1 rounded">
              <span>📎 {file.name}</span>
              <button 
                onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                className="text-gray-500 hover:text-red-400"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      
      {/* Input Area */}
      <div className="p-3">
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Shift+Enter 换行, Enter 发送)"
            disabled={disabled}
            className="w-full bg-[#3C3C3C] text-gray-200 rounded p-3 pr-20 resize-none
                       placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                       min-h-[60px] max-h-[120px]"
            rows={2}
          />
          
          {/* Command Suggestions */}
          {showCommands && (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-[#3C3C3C] rounded 
                            border border-[#555555] shadow-lg max-h-40 overflow-y-auto">
              {commands.filter(c => c.cmd.startsWith(content)).map((cmd) => (
                <button
                  key={cmd.cmd}
                  onClick={() => {
                    setContent(cmd.cmd + ' ')
                    setShowCommands(false)
                    textareaRef.current?.focus()
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-[#4A4A4A]"
                >
                  <span className="text-blue-400">{cmd.cmd}</span>
                  <span className="text-gray-500 ml-2">{cmd.desc}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        
        {/* Toolbar */}
        <div className="flex items-center justify-between mt-2">
          <div className="flex gap-2">
            <button className="text-xs text-gray-400 hover:text-white px-2 py-1">
              新对话
            </button>
            <button className="text-xs text-gray-400 hover:text-white px-2 py-1">
              管理
            </button>
            <label className="text-xs text-gray-400 hover:text-white px-2 py-1 cursor-pointer">
              📎 附件
              <input
                type="file"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    setAttachments(prev => [...prev, ...Array.from(e.target.files!)])
                  }
                }}
              />
            </label>
          </div>
          
          <div className="flex gap-2">
            {disabled && (
              <button className="px-3 py-1.5 bg-red-900/50 text-red-400 rounded text-sm">
                ⏹ 停止
              </button>
            )}
            <button
              onClick={handleSend}
              disabled={!content.trim() || disabled}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm
                         hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed"
            >
              {disabled ? '等待...' : '发送 ➤'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

---

#### Day 18-19: 状态管理（Zustand）

**任务**: 实现全局状态管理

**详细任务**:
1. 创建 Chat Store
2. 创建 Skills Store
3. 创建 System Store
4. 实现 WebSocket 连接管理

**交付物**:
- Zustand Store 定义
- WebSocket Hook

**验收标准**:
- [ ] 状态可正确更新
- [ ] WebSocket 连接稳定
- [ ] 状态持久化（可选）

**代码示例**:
```typescript
// src/web/src/stores/chatStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: string
  toolCalls?: any[]
  attachments?: any[]
}

interface ChatState {
  // Connection
  connectionStatus: 'connected' | 'disconnected' | 'connecting'
  ws: WebSocket | null
  
  // Session
  currentSessionId: string | null
  messages: Message[]
  isTyping: boolean
  
  // Settings
  currentDCC: string
  currentAgent: string
  currentAgentPlatform: string
  contextUsage: number
  
  // Actions
  connect: () => void
  disconnect: () => void
  sendMessage: (content: string, attachments?: File[]) => void
  addMessage: (message: Message) => void
  setTyping: (typing: boolean) => void
  setSession: (sessionId: string) => void
  setDCC: (dcc: string) => void
  setAgent: (agent: string) => void
  setContextUsage: (usage: number) => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // Initial state
      connectionStatus: 'disconnected',
      ws: null,
      currentSessionId: null,
      messages: [],
      isTyping: false,
      currentDCC: 'none',
      currentAgent: 'claude-4',
      currentAgentPlatform: 'openclaw',
      contextUsage: 0,
      
      // Actions
      connect: () => {
        const { currentSessionId } = get()
        if (!currentSessionId) return
        
        const ws = new WebSocket(
          `ws://localhost:8000/api/v1/ws/chat/${currentSessionId}`
        )
        
        ws.onopen = () => {
          set({ connectionStatus: 'connected', ws })
        }
        
        ws.onclose = () => {
          set({ connectionStatus: 'disconnected', ws: null })
        }
        
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          
          switch (data.type) {
            case 'message':
              get().addMessage({
                id: data.id || Date.now().toString(),
                role: data.role,
                content: data.content,
                timestamp: new Date().toLocaleTimeString(),
                toolCalls: data.tool_calls,
              })
              break
            case 'typing':
              set({ isTyping: data.is_typing })
              break
            case 'context_usage':
              set({ contextUsage: data.usage_percent })
              break
          }
        }
        
        set({ connectionStatus: 'connecting' })
      },
      
      disconnect: () => {
        const { ws } = get()
        ws?.close()
        set({ connectionStatus: 'disconnected', ws: null })
      },
      
      sendMessage: (content, attachments) => {
        const { ws, currentSessionId } = get()
        if (!ws || ws.readyState !== WebSocket.OPEN) return
        
        // Add user message locally
        const userMessage: Message = {
          id: Date.now().toString(),
          role: 'user',
          content,
          timestamp: new Date().toLocaleTimeString(),
        }
        get().addMessage(userMessage)
        
        // Send to server
        ws.send(JSON.stringify({
          type: 'chat',
          content,
          session_id: currentSessionId,
          attachments: attachments?.map(f => f.name),
        }))
        
        set({ isTyping: true })
      },
      
      addMessage: (message) => {
        set((state) => ({
          messages: [...state.messages, message],
        }))
      },
      
      setTyping: (typing) => set({ isTyping: typing }),
      
      setSession: (sessionId) => {
        get().disconnect()
        set({ 
          currentSessionId: sessionId, 
          messages: [],
          contextUsage: 0 
        })
        get().connect()
      },
      
      setDCC: (dcc) => set({ currentDCC: dcc }),
      setAgent: (agent) => set({ currentAgent: agent }),
      setContextUsage: (usage) => set({ contextUsage: usage }),
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({
        currentDCC: state.currentDCC,
        currentAgent: state.currentAgent,
        currentAgentPlatform: state.currentAgentPlatform,
      }),
    }
  )
)

// src/web/src/stores/skillsStore.ts
import { create } from 'zustand'

interface Skill {
  id: string
  name: string
  description: string
  version: string
  source: 'official' | 'marketplace' | 'user'
  status: 'not_installed' | 'installed' | 'update_available' | 'disabled'
  is_enabled: boolean
  is_pinned: boolean
  is_favorited: boolean
  use_count: number
  target_dccs: string[]
}

interface SkillsState {
  skills: Skill[]
  loading: boolean
  error: string | null
  selectedSkills: Set<string>
  
  // Filters
  filterSource: string | null
  filterStatus: string | null
  searchQuery: string
  
  // Actions
  fetchSkills: () => Promise<void>
  installSkill: (id: string) => Promise<void>
  uninstallSkill: (id: string) => Promise<void>
  updateSkill: (id: string, data: Partial<Skill>) => Promise<void>
  batchOperation: (operation: string, ids: string[]) => Promise<void>
  toggleSelection: (id: string) => void
  selectAll: (ids: string[]) => void
  clearSelection: () => void
  setFilter: (key: string, value: string | null) => void
  setSearchQuery: (query: string) => void
}

export const useSkillsStore = create<SkillsState>((set, get) => ({
  skills: [],
  loading: false,
  error: null,
  selectedSkills: new Set(),
  filterSource: null,
  filterStatus: null,
  searchQuery: '',
  
  fetchSkills: async () => {
    set({ loading: true, error: null })
    try {
      const { filterSource, filterStatus, searchQuery } = get()
      const params = new URLSearchParams()
      if (filterSource) params.append('source', filterSource)
      if (filterStatus) params.append('status', filterStatus)
      if (searchQuery) params.append('search', searchQuery)
      
      const response = await fetch(`/api/v1/skills?${params}`)
      const data = await response.json()
      set({ skills: data.items, loading: false })
    } catch (err) {
      set({ error: (err as Error).message, loading: false })
    }
  },
  
  installSkill: async (id) => {
    try {
      await fetch(`/api/v1/skills/${id}/install`, { method: 'POST' })
      get().fetchSkills()
    } catch (err) {
      set({ error: (err as Error).message })
    }
  },
  
  uninstallSkill: async (id) => {
    try {
      await fetch(`/api/v1/skills/${id}/uninstall`, { method: 'POST' })
      get().fetchSkills()
    } catch (err) {
      set({ error: (err as Error).message })
    }
  },
  
  updateSkill: async (id, data) => {
    try {
      await fetch(`/api/v1/skills/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      get().fetchSkills()
    } catch (err) {
      set({ error: (err as Error).message })
    }
  },
  
  batchOperation: async (operation, ids) => {
    try {
      await fetch('/api/v1/skills/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operation, skill_ids: ids }),
      })
      get().fetchSkills()
      get().clearSelection()
    } catch (err) {
      set({ error: (err as Error).message })
    }
  },
  
  toggleSelection: (id) => {
    set((state) => {
      const newSet = new Set(state.selectedSkills)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return { selectedSkills: newSet }
    })
  },
  
  selectAll: (ids) => {
    set({ selectedSkills: new Set(ids) })
  },
  
  clearSelection: () => {
    set({ selectedSkills: new Set() })
  },
  
  setFilter: (key, value) => {
    set({ [key]: value } as Partial<SkillsState>)
    get().fetchSkills()
  },
  
  setSearchQuery: (query) => {
    set({ searchQuery: query })
    // Debounce search
    setTimeout(() => get().fetchSkills(), 300)
  },
}))
```

---

#### Day 20-21: Skills 列表页面

**任务**: 实现 Skills 管理页面

**详细任务**:
1. 实现 Skills 列表组件
2. 实现筛选和搜索
3. 实现批量操作
4. 实现 Skill 卡片

**交付物**:
- Skills 页面组件
- Skill 卡片组件
- 批量操作栏

**验收标准**:
- [ ] 列表可正常显示
- [ ] 筛选和搜索有效
- [ ] 批量操作可用

**代码示例**:
```typescript
// src/web/src/pages/Skills/index.tsx
import { useEffect, useState } from 'react'
import { useSkillsStore } from '../../stores/skillsStore'
import { SkillCard } from '../../components/Skills/SkillCard'
import { BatchActionBar } from '../../components/Skills/BatchActionBar'

const tabs = [
  { id: 'all', label: '全部' },
  { id: 'official', label: '官方' },
  { id: 'marketplace', label: '市集' },
  { id: 'user', label: '我的' },
]

export default function SkillsPage() {
  const [activeTab, setActiveTab] = useState('all')
  const {
    skills,
    loading,
    selectedSkills,
    searchQuery,
    fetchSkills,
    setFilter,
    setSearchQuery,
    toggleSelection,
    selectAll,
    clearSelection,
  } = useSkillsStore()
  
  useEffect(() => {
    fetchSkills()
  }, [fetchSkills])
  
  useEffect(() => {
    setFilter('filterSource', activeTab === 'all' ? null : activeTab)
  }, [activeTab, setFilter])
  
  const hasSelection = selectedSkills.size > 0
  
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-[#555555]">
        <h1 className="text-xl font-semibold text-gray-200 mb-4">Skills</h1>
        
        {/* Tabs */}
        <div className="flex gap-1 mb-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded text-sm ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#3C3C3C] text-gray-300 hover:bg-[#4A4A4A]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        
        {/* Search */}
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索 Skills..."
            className="flex-1 bg-[#3C3C3C] text-gray-200 px-3 py-2 rounded
                       placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button className="px-3 py-2 bg-[#3C3C3C] rounded text-gray-300 hover:bg-[#4A4A4A]">
            筛选 ▼
          </button>
        </div>
      </div>
      
      {/* Batch Action Bar */}
      {hasSelection && (
        <BatchActionBar
          selectedCount={selectedSkills.size}
          onClear={clearSelection}
          onSelectAll={() => selectAll(skills.map(s => s.id))}
        />
      )}
      
      {/* Skills List */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="text-center text-gray-500 py-8">加载中...</div>
        ) : (
          <div className="space-y-3">
            {skills.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                selected={selectedSkills.has(skill.id)}
                onSelect={() => toggleSelection(skill.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// src/web/src/components/Skills/SkillCard.tsx
import { useSkillsStore } from '../../stores/skillsStore'

interface SkillCardProps {
  skill: {
    id: string
    name: string
    description: string
    version: string
    source: string
    status: string
    is_enabled: boolean
    is_pinned: boolean
    is_favorited: boolean
    use_count: number
    target_dccs: string[]
  }
  selected: boolean
  onSelect: () => void
}

export function SkillCard({ skill, selected, onSelect }: SkillCardProps) {
  const { installSkill, uninstallSkill, updateSkill } = useSkillsStore()
  
  const statusLabels = {
    not_installed: '可安装',
    installed: '已安装',
    update_available: '有更新',
    disabled: '已禁用',
  }
  
  const statusColors = {
    not_installed: 'text-gray-400',
    installed: 'text-green-400',
    update_available: 'text-orange-400',
    disabled: 'text-red-400',
  }
  
  return (
    <div className={`bg-[#2D2D2D] rounded-lg p-4 border ${
      selected ? 'border-blue-500' : 'border-[#444]'
    }`}>
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          className="mt-1"
        />
        
        {/* Icon */}
        <div className="w-10 h-10 bg-[#3C3C3C] rounded flex items-center justify-center text-xl">
          🎯
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-gray-200 font-medium truncate">{skill.name}</h3>
            <span className={`text-xs ${statusColors[skill.status]}`}>
              {statusLabels[skill.status]}
            </span>
            {skill.is_pinned && <span className="text-xs text-blue-400">📌</span>}
            {skill.is_favorited && <span className="text-xs text-yellow-400">⭐</span>}
          </div>
          
          <p className="text-sm text-gray-400 mt-1 line-clamp-2">
            {skill.description}
          </p>
          
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span>{skill.source} · v{skill.version}</span>
            <span>使用: {skill.use_count}次</span>
            {skill.target_dccs.length > 0 && (
              <span>支持: {skill.target_dccs.join(', ')}</span>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex flex-col gap-1">
          {skill.status === 'not_installed' ? (
            <button
              onClick={() => installSkill(skill.id)}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
            >
              安装
            </button>
          ) : (
            <>
              <button className="px-3 py-1 bg-[#3C3C3C] text-gray-300 text-sm rounded hover:bg-[#4A4A4A]">
                运行
              </button>
              <button
                onClick={() => updateSkill(skill.id, { is_enabled: !skill.is_enabled })}
                className="px-3 py-1 bg-[#3C3C3C] text-gray-300 text-sm rounded hover:bg-[#4A4A4A]"
              >
                {skill.is_enabled ? '禁用' : '启用'}
              </button>
              <button
                onClick={() => uninstallSkill(skill.id)}
                className="px-3 py-1 bg-red-900/50 text-red-400 text-sm rounded hover:bg-red-900"
              >
                卸载
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// src/web/src/components/Skills/BatchActionBar.tsx
import { useSkillsStore } from '../../stores/skillsStore'

interface BatchActionBarProps {
  selectedCount: number
  onClear: () => void
  onSelectAll: () => void
}

export function BatchActionBar({ selectedCount, onClear, onSelectAll }: BatchActionBarProps) {
  const { batchOperation } = useSkillsStore()
  
  const operations = [
    { id: 'install', label: '批量安装', icon: '⬇️' },
    { id: 'uninstall', label: '批量卸载', icon: '🗑️' },
    { id: 'enable', label: '批量启用', icon: '✅' },
    { id: 'disable', label: '批量禁用', icon: '🚫' },
    { id: 'pin', label: '批量钉选', icon: '📌' },
    { id: 'favorite', label: '批量收藏', icon: '⭐' },
  ]
  
  return (
    <div className="bg-blue-900/30 border-y border-blue-700/50 px-4 py-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-blue-400 text-sm">
            已选择 {selectedCount} 项
          </span>
          <button
            onClick={onSelectAll}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            全选
          </button>
          <button
            onClick={onClear}
            className="text-xs text-gray-400 hover:text-gray-300"
          >
            清除
          </button>
        </div>
        
        <div className="flex gap-2">
          {operations.map((op) => (
            <button
              key={op.id}
              onClick={() => {
                const { selectedSkills } = useSkillsStore.getState()
                batchOperation(op.id, Array.from(selectedSkills))
              }}
              className="px-2 py-1 bg-blue-600/50 text-blue-200 text-xs rounded 
                         hover:bg-blue-600 flex items-center gap-1"
            >
              <span>{op.icon}</span>
              <span>{op.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
```

---

## 3. API 接口详细定义

### 3.1 REST API 汇总

| 方法 | 路径 | 描述 | 状态码 |
|------|------|------|--------|
| GET | `/api/v1/health` | 健康检查 | 200 |
| GET | `/api/v1/system/status` | 系统状态 | 200 |
| GET | `/api/v1/system/config` | 系统配置 | 200 |
| POST | `/api/v1/system/gateway/connect` | 连接 Gateway | 200 |
| POST | `/api/v1/system/gateway/disconnect` | 断开 Gateway | 200 |
| GET | `/api/v1/skills` | 获取 Skills 列表 | 200 |
| GET | `/api/v1/skills/{id}` | 获取 Skill 详情 | 200, 404 |
| POST | `/api/v1/skills/{id}/install` | 安装 Skill | 200, 400 |
| POST | `/api/v1/skills/{id}/uninstall` | 卸载 Skill | 200, 400 |
| PATCH | `/api/v1/skills/{id}` | 更新 Skill | 200, 404 |
| POST | `/api/v1/skills/batch` | 批量操作 | 200, 400 |
| GET | `/api/v1/sessions` | 获取会话列表 | 200 |
| POST | `/api/v1/sessions` | 创建会话 | 201 |
| GET | `/api/v1/sessions/{id}` | 获取会话详情 | 200, 404 |
| PATCH | `/api/v1/sessions/{id}` | 更新会话 | 200, 404 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 | 200, 404 |
| GET | `/api/v1/sessions/{id}/messages` | 获取消息历史 | 200 |
| GET | `/api/v1/sessions/{id}/context` | 获取上下文信息 | 200 |
| POST | `/api/v1/sessions/{id}/pin-skill` | 钉选 Skill | 200 |
| POST | `/api/v1/sessions/{id}/unpin-skill` | 取消钉选 | 200 |
| POST | `/api/v1/chat/upload` | 上传文件 | 200, 400 |

### 3.2 WebSocket API

**连接 URL**: `ws://{host}/api/v1/ws/chat/{session_id}`

**客户端发送消息**:

```typescript
// 聊天消息
{
  type: "chat",
  content: string,
  agent_id?: string,
  attachments?: string[]
}

// 心跳
{
  type: "ping"
}

// 打字状态
{
  type: "typing",
  is_typing: boolean
}

// 取消生成
{
  type: "cancel"
}
```

**服务端发送消息**:

```typescript
// 心跳响应
{
  type: "pong"
}

// 消息接收确认
{
  type: "message_received",
  session_id: string
}

// AI 消息
{
  type: "message",
  id: string,
  role: "assistant",
  content: string,
  tool_calls?: any[]
}

// 打字状态
{
  type: "typing",
  is_typing: boolean
}

// 上下文用量更新
{
  type: "context_usage",
  usage_percent: number,
  total_tokens: number
}

// 工具调用结果
{
  type: "tool_result",
  tool_call_id: string,
  result: any
}

// 错误
{
  type: "error",
  code: string,
  message: string
}
```

---

## 4. 数据库/存储设计

### 4.1 数据库 Schema

```sql
-- Skills 表
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT DEFAULT '1.0.0',
    source TEXT NOT NULL,  -- official, marketplace, user
    target_dccs JSON DEFAULT '[]',
    status TEXT DEFAULT 'not_installed',
    is_enabled BOOLEAN DEFAULT 1,
    is_pinned BOOLEAN DEFAULT 0,
    is_favorited BOOLEAN DEFAULT 0,
    use_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    skill_path TEXT,
    priority INTEGER DEFAULT 0,
    dependencies JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 会话表
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT 'New Chat',
    status TEXT DEFAULT 'active',  -- active, archived, deleted
    dcc_software TEXT DEFAULT 'none',
    agent_platform TEXT DEFAULT 'openclaw',
    agent_id TEXT,
    message_count INTEGER DEFAULT 0,
    context_usage INTEGER DEFAULT 0,
    pinned_skills JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 消息表
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user, assistant, system, tool
    content TEXT,
    tool_calls JSON,
    tool_results JSON,
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

-- 索引
CREATE INDEX idx_messages_session ON chat_messages(session_id);
CREATE INDEX idx_messages_created ON chat_messages(created_at);
CREATE INDEX idx_skills_source ON skills(source);
CREATE INDEX idx_skills_status ON skills(status);
```

### 4.2 文件存储结构

```
~/.artclaw/
├── config.json              # 用户配置
├── artclaw.db               # SQLite 数据库
├── uploads/                 # 上传文件
│   ├── {uuid}.png
│   └── {uuid}.fbx
├── skills/                  # 已安装 Skills
│   ├── official/
│   │   └── {skill-name}/
│   │       ├── v1.0.0/
│   │       └── current -> v1.0.0
│   └── marketplace/
├── workflows/               # 用户 Workflows
│   └── user/
└── tools/                   # 用户 Tools
    └── user/
```

### 4.3 配置文件格式

```json
// ~/.artclaw/config.json
{
  "version": "1.0.0",
  "settings": {
    "language": "zh-CN",
    "theme": "dark",
    "send_shortcut": "enter",
    "auto_connect": true
  },
  "gateway": {
    "url": "ws://localhost:9876",
    "api_url": "http://localhost:9876"
  },
  "dccs": {
    "ue57": {
      "enabled": true,
      "host": "localhost",
      "port": 8080
    },
    "comfyui": {
      "enabled": true,
      "host": "localhost",
      "port": 8188
    }
  },
  "agents": {
    "default_platform": "openclaw",
    "default_agent": "claude-4"
  }
}
```

---

## 5. 错误处理方案

### 5.1 错误码定义

| 错误码 | 描述 | HTTP 状态码 |
|--------|------|-------------|
| `INVALID_REQUEST` | 请求参数错误 | 400 |
| `UNAUTHORIZED` | 未授权 | 401 |
| `FORBIDDEN` | 禁止访问 | 403 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `CONFLICT` | 资源冲突 | 409 |
| `RATE_LIMITED` | 请求过于频繁 | 429 |
| `INTERNAL_ERROR` | 服务器内部错误 | 500 |
| `GATEWAY_ERROR` | Gateway 连接错误 | 502 |
| `SERVICE_UNAVAILABLE` | 服务不可用 | 503 |

### 5.2 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Skill not found",
    "details": {
      "skill_id": "official/non-existent"
    }
  }
}
```

### 5.3 前端错误处理

```typescript
// src/web/src/utils/errorHandler.ts
export class APIError extends Error {
  constructor(
    public code: string,
    message: string,
    public details?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export async function handleAPIResponse(response: Response) {
  const data = await response.json()
  
  if (!response.ok) {
    throw new APIError(
      data.error?.code || 'UNKNOWN',
      data.error?.message || 'Unknown error',
      data.error?.details
    )
  }
  
  return data
}

// 错误提示组件
export function ErrorToast({ error, onClose }: { error: APIError; onClose: () => void }) {
  const errorMessages: Record<string, string> = {
    'NOT_FOUND': '请求的资源不存在',
    'INVALID_REQUEST': '请求参数错误',
    'GATEWAY_ERROR': '无法连接到 Gateway，请检查服务状态',
    'SERVICE_UNAVAILABLE': '服务暂时不可用，请稍后重试',
  }
  
  return (
    <div className="bg-red-900/80 text-red-200 px-4 py-3 rounded-lg flex items-center gap-3">
      <span>❌</span>
      <span>{errorMessages[error.code] || error.message}</span>
      <button onClick={onClose} className="ml-auto text-red-400 hover:text-red-200">✕</button>
    </div>
  )
}
```

### 5.4 重试策略

```typescript
// 指数退避重试
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number
    baseDelay?: number
    maxDelay?: number
    retryableErrors?: string[]
  } = {}
): Promise<T> {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    maxDelay = 10000,
    retryableErrors = ['GATEWAY_ERROR', 'SERVICE_UNAVAILABLE', 'RATE_LIMITED']
  } = options
  
  let lastError: Error | null = null
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error as Error
      
      if (attempt === maxRetries) break
      
      if (error instanceof APIError && !retryableErrors.includes(error.code)) {
        throw error
      }
      
      // 指数退避
      const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay)
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }
  
  throw lastError
}
```

---

## 6. 测试计划

### 6.1 单元测试

**后端测试** (pytest):

```python
# tests/test_skills_api.py
import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

class TestSkillsAPI:
    def test_list_skills(self):
        response = client.get("/api/v1/skills")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    def test_get_skill_not_found(self):
        response = client.get("/api/v1/skills/invalid-id")
        assert response.status_code == 404
    
    def test_batch_operation_invalid(self):
        response = client.post("/api/v1/skills/batch", json={
            "operation": "invalid_op",
            "skill_ids": ["test"]
        })
        assert response.status_code == 400

# tests/test_context_service.py
class TestContextService:
    async def test_calculate_context_usage(self, db_session):
        service = ContextService(db_session)
        
        # 创建测试数据
        session = ChatSession(id="test-session")
        db_session.add(session)
        db_session.commit()
        
        usage = await service.calculate_context_usage("test-session")
        
        assert usage["total_tokens"] >= 0
        assert usage["usage_percent"] >= 0
        assert usage["max_tokens"] == 128000
```

**前端测试** (Vitest):

```typescript
// src/web/src/components/Chat/__tests__/ChatInput.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChatInput } from '../ChatInput'

describe('ChatInput', () => {
  it('should send message on Enter key', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    
    const input = screen.getByPlaceholderText(/输入消息/)
    fireEvent.change(input, { target: { value: 'Hello' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    
    expect(onSend).toHaveBeenCalledWith('Hello', [])
  })
  
  it('should not send empty message', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    
    const button = screen.getByText('发送')
    fireEvent.click(button)
    
    expect(onSend).not.toHaveBeenCalled()
  })
})
```

### 6.2 集成测试

```python
# tests/integration/test_chat_flow.py
import pytest
import asyncio
import websockets
import json

class TestChatFlow:
    async def test_websocket_chat(self):
        # 创建会话
        response = client.post("/api/v1/sessions", json={
            "title": "Test Session"
        })
        session_id = response.json()["id"]
        
        # 连接 WebSocket
        async with websockets.connect(
            f"ws://localhost:8000/api/v1/ws/chat/{session_id}"
        ) as ws:
            # 发送消息
            await ws.send(json.dumps({
                "type": "chat",
                "content": "Hello"
            }))
            
            # 接收确认
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            assert data["type"] == "message_received"
    
    async def test_context_pinning(self, db_session):
        # 测试 Skill 钉选流程
        service = ContextService(db_session)
        
        # 钉选 Skill
        success = await service.pin_skill("session-1", "skill-1")
        assert success
        
        # 验证钉选
        pinned = await service.get_pinned_skills("session-1")
        assert len(pinned) == 1
        assert pinned[0]["id"] == "skill-1"
```

### 6.3 性能测试

```python
# tests/performance/test_websocket_load.py
import asyncio
import websockets
import time

async def test_concurrent_connections():
    """测试 WebSocket 并发连接"""
    connection_count = 100
    
    async def connect_and_ping(idx):
        try:
            async with websockets.connect(
                "ws://localhost:8000/api/v1/ws/chat/test-session"
            ) as ws:
                await ws.send('{"type": "ping"}')
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                return idx, True
        except Exception as e:
            return idx, False
    
    start = time.time()
    results = await asyncio.gather(*[
        connect_and_ping(i) for i in range(connection_count)
    ])
    duration = time.time() - start
    
    success_count = sum(1 for _, success in results if success)
    print(f"Connected {success_count}/{connection_count} in {duration:.2f}s")
    
    assert success_count >= connection_count * 0.95  # 95% 成功率
```

### 6.4 测试覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| API 路由 | 90% |
| 服务层 | 85% |
| 数据模型 | 80% |
| WebSocket 处理 | 80% |
| 前端组件 | 70% |
| 前端 Store | 75% |

---

## 7. 代码示例

### 7.1 完整的 Skill Service 实现

```python
# src/server/services/skill_service.py
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import os
import shutil

from models.skill import Skill, SkillStatus, SkillSource
from schemas.skill import SkillUpdate

class SkillService:
    def __init__(self, db: Session):
        self.db = db
    
    async def list_skills(
        self,
        filters: Dict,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Skill], int]:
        """获取技能列表"""
        query = self.db.query(Skill)
        
        # 应用筛选
        if filters.get("source"):
            query = query.filter(Skill.source == filters["source"])
        if filters.get("status"):
            query = query.filter(Skill.status == filters["status"])
        if filters.get("search"):
            search = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Skill.name.ilike(search),
                    Skill.description.ilike(search)
                )
            )
        if filters.get("pinned") is not None:
            query = query.filter(Skill.is_pinned == filters["pinned"])
        if filters.get("favorited") is not None:
            query = query.filter(Skill.is_favorited == filters["favorited"])
        
        # 排序：钉选优先，然后按优先级和使用次数
        query = query.order_by(
            Skill.is_pinned.desc(),
            Skill.priority.desc(),
            Skill.use_count.desc()
        )
        
        # 分页
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return items, total
    
    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能详情"""
        return self.db.query(Skill).filter(Skill.id == skill_id).first()
    
    async def install_skill(self, skill_id: str) -> Skill:
        """安装技能"""
        skill = await self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        
        # 模拟安装过程
        # 实际实现中，这里会下载/复制 Skill 文件
        skill.status = SkillStatus.INSTALLED
        skill.is_enabled = True
        
        self.db.commit()
        self.db.refresh(skill)
        
        return skill
    
    async def uninstall_skill(self, skill_id: str):
        """卸载技能"""
        skill = await self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        
        # 删除 Skill 文件
        if skill.skill_path and os.path.exists(skill.skill_path):
            shutil.rmtree(skill.skill_path)
        
        skill.status = SkillStatus.NOT_INSTALLED
        skill.is_enabled = False
        
        self.db.commit()
    
    async def update_skill(
        self,
        skill_id: str,
        data: SkillUpdate
    ) -> Optional[Skill]:
        """更新技能"""
        skill = await self.get_skill(skill_id)
        if not skill:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(skill, field, value)
        
        self.db.commit()
        self.db.refresh(skill)
        
        return skill
    
    async def batch_operation(
        self,
        operation: str,
        skill_ids: List[str]
    ) -> Dict:
        """批量操作"""
        results = {
            "succeeded": 0,
            "failed": 0,
            "errors": []
        }
        
        for skill_id in skill_ids:
            try:
                if operation == "install":
                    await self.install_skill(skill_id)
                elif operation == "uninstall":
                    await self.uninstall_skill(skill_id)
                elif operation == "enable":
                    await self.update_skill(skill_id, SkillUpdate(is_enabled=True))
                elif operation == "disable":
                    await self.update_skill(skill_id, SkillUpdate(is_enabled=False))
                elif operation == "pin":
                    await self.update_skill(skill_id, SkillUpdate(is_pinned=True))
                elif operation == "unpin":
                    await self.update_skill(skill_id, SkillUpdate(is_pinned=False))
                elif operation == "favorite":
                    await self.update_skill(skill_id, SkillUpdate(is_favorited=True))
                elif operation == "unfavorite":
                    await self.update_skill(skill_id, SkillUpdate(is_favorited=False))
                
                results["succeeded"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "skill_id": skill_id,
                    "error": str(e)
                })
        
        return results
```

### 7.2 前端 API 客户端

```typescript
// src/web/src/api/client.ts
import axios, { AxiosError, AxiosInstance } from 'axios'

class APIClient {
  private client: AxiosInstance
  
  constructor() {
    this.client = axios.create({
      baseURL: '/api/v1',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        // 可以在这里添加认证 token
        return config
      },
      (error) => Promise.reject(error)
    )
    
    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      (error: AxiosError) => {
        if (error.response) {
          const data = error.response.data as any
          throw new APIError(
            data.error?.code || 'UNKNOWN',
            data.error?.message || 'Unknown error',
            data.error?.details
          )
        }
        throw new APIError('NETWORK_ERROR', '网络连接失败')
      }
    )
  }
  
  // Skills API
  async listSkills(params?: {
    source?: string
    status?: string
    search?: string
    page?: number
    page_size?: number
  }) {
    return this.client.get('/skills', { params })
  }
  
  async getSkill(id: string) {
    return this.client.get(`/skills/${id}`)
  }
  
  async installSkill(id: string) {
    return this.client.post(`/skills/${id}/install`)
  }
  
  async uninstallSkill(id: string) {
    return this.client.post(`/skills/${id}/uninstall`)
  }
  
  async updateSkill(id: string, data: Partial<Skill>) {
    return this.client.patch(`/skills/${id}`, data)
  }
  
  async batchOperation(operation: string, skillIds: string[]) {
    return this.client.post('/skills/batch', {
      operation,
      skill_ids: skillIds
    })
  }
  
  // Sessions API
  async listSessions(params?: {
    status?: string
    search?: string
    page?: number
    page_size?: number
  }) {
    return this.client.get('/sessions', { params })
  }
  
  async createSession(data: { title?: string }) {
    return this.client.post('/sessions', data)
  }
  
  async getSession(id: string) {
    return this.client.get(`/sessions/${id}`)
  }
  
  async updateSession(id: string, data: Partial<Session>) {
    return this.client.patch(`/sessions/${id}`, data)
  }
  
  async deleteSession(id: string) {
    return this.client.delete(`/sessions/${id}`)
  }
  
  async getMessages(sessionId: string, params?: {
    before_id?: string
    limit?: number
  }) {
    return this.client.get(`/sessions/${sessionId}/messages`, { params })
  }
  
  async getContextInfo(sessionId: string) {
    return this.client.get(`/sessions/${sessionId}/context`)
  }
  
  async pinSkill(sessionId: string, skillId: string) {
    return this.client.post(`/sessions/${sessionId}/pin-skill`, { skill_id: skillId })
  }
  
  async unpinSkill(sessionId: string, skillId: string) {
    return this.client.post(`/sessions/${sessionId}/unpin-skill`, { skill_id: skillId })
  }
  
  // Upload
  async uploadFile(file: File, sessionId: string) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('session_id', sessionId)
    
    return this.client.post('/chat/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export const api = new APIClient()
```

---

## 8. 附录

### 8.1 开发环境配置

**后端**:
```bash
# 创建虚拟环境
cd src/server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn main:app --reload --port 8000
```

**前端**:
```bash
cd src/web
npm install
npm run dev
```

### 8.2 目录结构

```
ArtClawToolManager/
├── src/
│   ├── server/              # FastAPI 后端
│   │   ├── api/             # API 路由
│   │   │   ├── skills.py
│   │   │   ├── sessions.py
│   │   │   ├── chat.py
│   │   │   └── system.py
│   │   ├── models/          # SQLAlchemy 模型
│   │   │   ├── base.py
│   │   │   ├── skill.py
│   │   │   └── session.py
│   │   ├── schemas/         # Pydantic Schema
│   │   │   ├── skill.py
│   │   │   └── session.py
│   │   ├── services/        # 业务逻辑
│   │   │   ├── skill_service.py
│   │   │   ├── session_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── context_service.py
│   │   │   └── gateway_client.py
│   │   ├── websocket/       # WebSocket 处理
│   │   │   ├── manager.py
│   │   │   └── chat_ws.py
│   │   ├── core/            # 核心配置
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── main.py
│   │   └── requirements.txt
│   └── web/                 # React 前端
│       ├── src/
│       │   ├── components/  # 组件
│       │   │   ├── Chat/
│       │   │   ├── Skills/
│       │   │   └── Layout/
│       │   ├── pages/       # 页面
│       │   │   ├── Chat.tsx
│       │   │   ├── Skills.tsx
│       │   │   └── ...
│       │   ├── stores/      # Zustand Store
│       │   │   ├── chatStore.ts
│       │   │   └── skillsStore.ts
│       │   ├── api/         # API 客户端
│       │   │   └── client.ts
│       │   ├── utils/       # 工具函数
│       │   ├── App.tsx
│       │   └── main.tsx
│       ├── package.json
│       └── vite.config.ts
├── tests/                   # 测试
├── docs/                    # 文档
└── README.md
```

### 8.3 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例**:
```
feat(skills): 实现 Skill 批量操作 API

- 添加批量安装/卸载/启用/禁用接口
- 支持批量钉选和收藏
- 添加批量操作结果返回

Closes #123
```

---

## 更新记录

### v1.0 (2026-04-10)
- 初始版本
- 完整的 Phase 1 开发文档
- 包含详细的任务分解、API 定义、数据库设计
- 提供完整的代码示例
