# core/schemas/

本目录存放 ArtClaw Bridge 的机器可读 JSON Schema 文件，用于配置文件和 Skill Manifest 的结构校验。

## 文件列表

| 文件 | 用途 | 对应规范 |
|------|------|---------|
| `config.schema.json` | `~/.artclaw/config.json` 主配置文件校验 | `docs/specs/sdk-core-api-spec.md` C2, `docs/specs/sdk-platform-adapter-spec.md` P8 |

## 使用方式

### CLI 校验

```bash
# 校验当前配置文件
artclaw config validate

# 对 Skill manifest 做 Schema 校验（由 artclaw skill test 调用）
artclaw skill test my_skill
```

### IDE 集成

在 VSCode 中，可将以下配置加入 `.vscode/settings.json` 以获得配置文件的自动补全和校验：

```json
{
  "json.schemas": [
    {
      "fileMatch": ["**/config.json"],
      "url": "./core/schemas/config.schema.json"
    }
  ]
}
```

### Python 代码校验

```python
import json
import jsonschema
from pathlib import Path

schema_path = Path(__file__).parent / "config.schema.json"
schema = json.loads(schema_path.read_text())

config = json.loads(Path("~/.artclaw/config.json").expanduser().read_text())
jsonschema.validate(config, schema)  # 不符合 schema 时抛出 ValidationError
```

## 新增 Schema 规范

添加新 Schema 文件时请遵守：
1. 文件名格式：`{name}.schema.json`
2. 必须包含 `$schema`、`$id`、`title`、`description` 字段
3. 在本 README 的文件列表中补充说明
