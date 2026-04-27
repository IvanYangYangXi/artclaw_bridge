"""一次性清理 triggers.json 里 tool_id 找不到对应 manifest 的孤儿条目。"""
import json, os, glob
from pathlib import Path

config_path = Path.home() / ".artclaw" / "config.json"
triggers_path = Path.home() / ".artclaw" / "triggers.json"

project_root = json.loads(config_path.read_text(encoding="utf-8")).get("project_root", "")
if not project_root:
    print("ERROR: project_root not set in config.json")
    exit(1)

# 扫描所有工具 manifest，收集合法的 tool_id = "{source}/{name}"
known: set = set()
for mf in glob.glob(os.path.join(project_root, "tools", "**", "manifest.json"), recursive=True):
    try:
        m = json.loads(open(mf, encoding="utf-8").read())
        src = m.get("source", "")
        name = m.get("name", "")
        if src and name:
            known.add(f"{src}/{name}")
    except Exception as e:
        print(f"WARN: failed to read {mf}: {e}")

print(f"Known tool_ids ({len(known)}):")
for t in sorted(known):
    print(f"  {t}")

data = json.loads(triggers_path.read_text(encoding="utf-8"))
before = len(data)

cleaned = []
removed = []
for r in data:
    tid = r.get("tool_id", "")
    mid = r.get("manifest_id", "")
    # 只删除有 manifest_id（非用户手动创建）且 tool_id 找不到对应 manifest 的孤儿
    if mid and tid and tid not in known:
        removed.append(r)
    else:
        cleaned.append(r)

print(f"\nBefore: {before}  After: {len(cleaned)}  Removed: {len(removed)}")
for r in removed:
    print(f"  - REMOVE: tool_id={r['tool_id']} | name={r.get('name','')}")

triggers_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nDone. triggers.json updated.")
