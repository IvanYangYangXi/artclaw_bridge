"""
device_auth.py — OpenClaw device identity 签名模块
===================================================

提供 Gateway connect 握手所需的 device identity 加载与 Ed25519 签名。
所有 WS 客户端（UE/DCC/ToolManager）共享此模块。

用法::

    from device_auth import get_device_identity, build_device_auth

    identity = get_device_identity()
    if identity:
        params["device"] = build_device_auth(
            identity, "operator", scopes, signed_at_ms, nonce, auth_token)

容错:
  - device.json 不存在 → 返回 None（跳过签名）
  - cryptography 未安装 → 返回 None（跳过签名）
  - 签名异常 → 调用方 try/except 处理
"""

import json
import os
import time
from typing import Optional, Tuple, Dict, List

# ---------------------------------------------------------------------------
# Device identity 缓存
# ---------------------------------------------------------------------------

_cached_identity: Optional[Tuple[str, str, str]] = None
_identity_loaded: bool = False


def _load_device_identity() -> Optional[Tuple[str, str, str]]:
    """加载 ~/.openclaw/identity/device.json。

    Returns:
        (device_id, public_key_raw_b64url, private_key_pem) 或 None
    """
    identity_path = os.path.join(
        os.path.expanduser("~"), ".openclaw", "identity", "device.json"
    )
    if not os.path.isfile(identity_path):
        return None
    try:
        import base64

        with open(identity_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        device_id = data.get("deviceId", "")
        pub_pem = data.get("publicKeyPem", "")
        priv_pem = data.get("privateKeyPem", "")
        if not (device_id and pub_pem and priv_pem):
            return None

        # 从 PEM 提取 raw 32-byte Ed25519 public key → base64url
        from cryptography.hazmat.primitives.serialization import (
            load_pem_public_key,
            Encoding,
            PublicFormat,
        )

        pub_key = load_pem_public_key(pub_pem.encode())
        spki_der = pub_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        # Ed25519 SPKI DER = 12-byte ASN.1 prefix + 32-byte raw key
        raw_pub = spki_der[12:]
        pub_b64url = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()
        return (device_id, pub_b64url, priv_pem)
    except Exception:
        return None


def get_device_identity() -> Optional[Tuple[str, str, str]]:
    """获取 device identity（带缓存，只加载一次）。

    Returns:
        (device_id, public_key_raw_b64url, private_key_pem) 或 None
    """
    global _cached_identity, _identity_loaded
    if not _identity_loaded:
        _cached_identity = _load_device_identity()
        _identity_loaded = True
    return _cached_identity


def build_device_auth(
    identity: Tuple[str, str, str],
    role: str,
    scopes: List[str],
    signed_at_ms: int,
    nonce: str,
    auth_token: str = "",
    client_id: str = "cli",
    client_mode: str = "cli",
    platform: str = "win32",
    device_family: str = "",
) -> Dict:
    """构建 v3 格式的 device auth 参数。

    Args:
        identity: (device_id, public_key_raw_b64url, private_key_pem)
        role: 连接角色，通常 "operator"
        scopes: scope 列表
        signed_at_ms: 签名时间戳（毫秒）
        nonce: Gateway challenge nonce
        auth_token: Gateway auth token
        client_id: 客户端 ID（白名单值，默认 "cli"）
        client_mode: 客户端模式（默认 "cli"）
        platform: 平台标识（默认 "win32"）
        device_family: 设备系列（默认空）

    Returns:
        dict: 可直接作为 connect.params.device 的对象
    """
    import base64
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    device_id, pub_b64url, priv_pem = identity

    # v3 payload 格式
    scopes_str = ",".join(scopes)
    payload = "|".join([
        "v3",
        device_id,
        client_id,
        client_mode,
        role,
        scopes_str,
        str(signed_at_ms),
        auth_token,
        nonce,
        platform,
        device_family,
    ])

    # Ed25519 签名
    priv_key = load_pem_private_key(priv_pem.encode(), password=None)
    signature = priv_key.sign(payload.encode())
    sig_b64url = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return {
        "id": device_id,
        "publicKey": pub_b64url,
        "signature": sig_b64url,
        "signedAt": signed_at_ms,
        "nonce": nonce,
    }
