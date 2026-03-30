// Copyright ArtClaw Project. All Rights Reserved.
// Skill Tab — 数据刷新与解析

#include "UEAgentSkillTab.h"
#include "UEAgentManageUtils.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

#define LOCTEXT_NAMESPACE "UEAgentSkillTab"

// ==================================================================
// Python 脚本常量 — 集中管理，避免主文件臃肿
// ==================================================================

static const TCHAR* SkillRefreshPyScript = TEXT(
	"from skill_hub import get_skill_hub\n"
	"import json, os, sys\n"
	"\n"
	"# 确保 skill_sync 可导入\n"
	"py_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else ''\n"
	"\n"
	"hub = get_skill_hub()\n"
	"skills = []\n"
	"seen_names = set()\n"
	"\n"
	"# 1) skill_hub 代码包\n"
	"if hub:\n"
	"    for m in hub._all_manifests:\n"
	"        if m.name in seen_names: continue\n"
	"        seen_names.add(m.name)\n"
	"        src_dir = getattr(m, 'source_dir', '')\n"
	"        skills.append({\n"
	"            'name': m.name,\n"
	"            'display_name': getattr(m, 'display_name', m.name),\n"
	"            'description': getattr(m, 'description', ''),\n"
	"            'version': getattr(m, 'version', ''),\n"
	"            'layer': getattr(m, 'source_layer', 'custom'),\n"
	"            'software': getattr(m, 'software', 'universal'),\n"
	"            'category': getattr(m, 'category', 'general'),\n"
	"            'risk_level': getattr(m, 'risk_level', 'low'),\n"
	"            'author': getattr(m, 'author', ''),\n"
	"            'has_code': os.path.exists(os.path.join(str(src_dir), '__init__.py')) if src_dir else False,\n"
	"            'has_skill_md': os.path.exists(os.path.join(str(src_dir), 'SKILL.md')) if src_dir else False,\n"
	"            'install_status': 'full',\n"
	"            'source_dir': str(src_dir) if src_dir else '',\n"
	"        })\n"
	"\n"
	"# 2) 平台已安装 Skills 目录 (config 驱动)\n"
	"_ac_cfg = {}\n"
	"_ac_path = os.path.expanduser('~/.artclaw/config.json')\n"
	"if os.path.exists(_ac_path):\n"
	"    try:\n"
	"        with open(_ac_path, 'r', encoding='utf-8') as f: _ac_cfg = json.load(f)\n"
	"    except: pass\n"
	"_installed_path = _ac_cfg.get('skills', {}).get('installed_path', '')\n"
	"if not _installed_path:\n"
	"    _pt = _ac_cfg.get('platform', {}).get('type', 'openclaw')\n"
	"    _defaults = {'openclaw': '~/.openclaw/skills', 'workbuddy': '~/.workbuddy/skills', 'claude': '~/.claude/skills'}\n"
	"    _installed_path = _defaults.get(_pt, '~/.openclaw/skills')\n"
	"oc_dir = os.path.expanduser(_installed_path)\n"
	"if os.path.isdir(oc_dir):\n"
	"    # 从项目源码判断 layer: 检查 official / marketplace 目录是否有同名 skill\n"
	"    _project_root = _ac_cfg.get('project_root', '')\n"
	"    _official_names = set()\n"
	"    _marketplace_names = set()\n"
	"    if _project_root and os.path.isdir(_project_root):\n"
	"        for _subdir in ['universal', 'unreal', 'maya', 'max']:\n"
	"            _odir = os.path.join(_project_root, 'skills', 'official', _subdir)\n"
	"            if os.path.isdir(_odir):\n"
	"                _official_names.update(os.listdir(_odir))\n"
	"            _mdir = os.path.join(_project_root, 'skills', 'marketplace', _subdir)\n"
	"            if os.path.isdir(_mdir):\n"
	"                _marketplace_names.update(os.listdir(_mdir))\n"
	"    for name in sorted(os.listdir(oc_dir)):\n"
	"        if name in seen_names: continue\n"
	"        sd = os.path.join(oc_dir, name)\n"
	"        sm = os.path.join(sd, 'SKILL.md')\n"
	"        if not os.path.isdir(sd) or not os.path.isfile(sm): continue\n"
	"        seen_names.add(name)\n"
	"        desc = ''; _author = ''\n"
	"        try:\n"
	"            with open(sm, 'r', encoding='utf-8') as f:\n"
	"                _raw = f.read(4096)\n"
	"            # 解析 YAML frontmatter (--- ... ---)\n"
	"            if _raw.startswith('---'):\n"
	"                _end = _raw.find('---', 3)\n"
	"                if _end > 0:\n"
	"                    _fm = _raw[3:_end]\n"
	"                    for _fl in _fm.split('\\n'):\n"
	"                        _fl = _fl.strip()\n"
	"                        if _fl.startswith('author:'):\n"
	"                            _author = _fl[7:].strip()\n"
	"                        elif _fl.startswith('description:') and not desc:\n"
	"                            _dv = _fl[12:].strip()\n"
	"                            if _dv and _dv != '>':\n"
	"                                desc = _dv[:120]\n"
	"            # fallback: 第一行非标题文本\n"
	"            if not desc:\n"
	"                for _fl in _raw.split('\\n'):\n"
	"                    _fl = _fl.strip()\n"
	"                    if _fl and not _fl.startswith('#') and not _fl.startswith('---'):\n"
	"                        desc = _fl[:120]; break\n"
	"        except: pass\n"
	"        # 判断 layer: 优先匹配项目源码中的 official/marketplace\n"
	"        _layer = 'platform'\n"
	"        if name in _official_names:\n"
	"            _layer = 'official'\n"
	"        elif name in _marketplace_names:\n"
	"            _layer = 'marketplace'\n"
	"        skills.append({\n"
	"            'name': name, 'display_name': name, 'description': desc,\n"
	"            'version': '', 'layer': _layer, 'software': 'universal',\n"
	"            'category': 'general', 'risk_level': 'low', 'author': _author,\n"
	"            'has_code': False, 'has_skill_md': True,\n"
	"            'install_status': 'doc_only', 'source_dir': sd,\n"
	"        })\n"
	"\n"
	"# 3) Phase 4: 未安装的 Skill (源码有但运行时没有)\n"
	"try:\n"
	"    from skill_sync import compare_source_vs_runtime\n"
	"    diff = compare_source_vs_runtime()\n"
	"    if not diff.get('error'):\n"
	"        for info in diff.get('available', []):\n"
	"            n = info['name']\n"
	"            if n in seen_names: continue\n"
	"            seen_names.add(n)\n"
	"            skills.append({\n"
	"                'name': n, 'display_name': n,\n"
	"                'description': '',\n"
	"                'version': info.get('version', ''),\n"
	"                'layer': info.get('layer', 'marketplace'),\n"
	"                'software': info.get('dcc', 'universal'),\n"
	"                'category': 'general', 'risk_level': 'low',\n"
	"                'has_code': info.get('has_code', False),\n"
	"                'has_skill_md': info.get('has_skill_md', False),\n"
	"                'install_status': 'not_installed',\n"
	"                'source_dir': info.get('path', ''),\n"
	"            })\n"
	"        # 标记可更新\n"
	"        updatable_names = {i['name'] for i in diff.get('updatable', [])}\n"
	"        for s in skills:\n"
	"            if s['name'] in updatable_names:\n"
	"                s['updatable'] = True\n"
	"                for u in diff.get('updatable', []):\n"
	"                    if u['name'] == s['name']:\n"
	"                        s['source_version'] = u.get('version', '')\n"
	"                        break\n"
	"except Exception as e:\n"
	"    pass\n"
	"\n"
	"# 4) 启用/禁用/钉选\n"
	"config_path = os.path.expanduser('~/.artclaw/config.json')\n"
	"pinned = []; disabled = []\n"
	"if os.path.exists(config_path):\n"
	"    try:\n"
	"        with open(config_path, 'r', encoding='utf-8') as f:\n"
	"            cfg = json.load(f)\n"
	"        pinned = cfg.get('pinned_skills', [])\n"
	"        disabled = cfg.get('disabled_skills', [])\n"
	"    except: pass\n"
	"for s in skills:\n"
	"    s['enabled'] = s['name'] not in disabled\n"
	"    s['pinned'] = s['name'] in pinned\n"
	"\n"
	"_result = {'skills': skills, 'count': len(skills)}\n"
);

// ==================================================================
// 数据刷新与解析
// ==================================================================

void SUEAgentSkillTab::RefreshData()
{
	AllSkills.Empty();
	FilteredSkills.Empty();

	FString JsonStr = FUEAgentManageUtils::RunPythonAndCapture(SkillRefreshPyScript);
	ParseSkillList(JsonStr);
}

void SUEAgentSkillTab::ParseSkillList(const FString& JsonStr)
{
	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid()) return;

	const TArray<TSharedPtr<FJsonValue>>* Arr;
	if (!JsonObj->TryGetArrayField(TEXT("skills"), Arr)) return;

	for (const auto& Val : *Arr)
	{
		TSharedPtr<FJsonObject> Obj = Val->AsObject();
		if (!Obj.IsValid()) continue;

		FSkillEntryPtr E = MakeShared<FSkillEntry>();
		E->Name = Obj->GetStringField(TEXT("name"));
		E->DisplayName = Obj->GetStringField(TEXT("display_name"));
		E->Description = Obj->GetStringField(TEXT("description"));
		E->Version = Obj->GetStringField(TEXT("version"));
		E->Layer = Obj->GetStringField(TEXT("layer"));
		E->Software = Obj->GetStringField(TEXT("software"));
		E->Category = Obj->GetStringField(TEXT("category"));
		E->RiskLevel = Obj->GetStringField(TEXT("risk_level"));
		Obj->TryGetStringField(TEXT("author"), E->Author);
		Obj->TryGetBoolField(TEXT("enabled"), E->bEnabled);
		Obj->TryGetBoolField(TEXT("pinned"), E->bPinned);
		Obj->TryGetBoolField(TEXT("has_code"), E->bHasCode);
		Obj->TryGetBoolField(TEXT("has_skill_md"), E->bHasSkillMd);
		Obj->TryGetBoolField(TEXT("updatable"), E->bUpdatable);
		E->SourceDir = Obj->GetStringField(TEXT("source_dir"));

		FString InstallStr = Obj->GetStringField(TEXT("install_status"));
		// doc_only / full → Installed；not_installed → NotInstalled
		E->InstallStatus = (InstallStr == TEXT("not_installed"))
			? EInstallStatus::NotInstalled
			: EInstallStatus::Installed;

		Obj->TryGetStringField(TEXT("source_version"), E->SourcePath);

		AllSkills.Add(E);
	}

	ApplyFilters();
}

void SUEAgentSkillTab::ApplyFilters()
{
	FilteredSkills.Empty();
	for (const auto& S : AllSkills)
	{
		if (LayerFilter != TEXT("all") && S->Layer != LayerFilter) continue;

		// 安装状态过滤
		if (InstallFilter != TEXT("all"))
		{
			if (InstallFilter == TEXT("installed") && S->InstallStatus != EInstallStatus::Installed) continue;
			if (InstallFilter == TEXT("notinstalled") && S->InstallStatus != EInstallStatus::NotInstalled) continue;
		}

		if (DccFilter != TEXT("all"))
		{
			if (DccFilter == TEXT("unreal"))
			{
				if (S->Software != TEXT("unreal_engine") && S->Software != TEXT("universal")
					&& S->Software != TEXT("unreal"))
					continue;
			}
			else if (S->Software != DccFilter)
				continue;
		}

		// 搜索关键字过滤（名称 / DisplayName / 描述 不区分大小写）
		if (!SearchKeyword.IsEmpty())
		{
			const FString KW = SearchKeyword.ToLower();
			bool bMatch = S->Name.ToLower().Contains(KW)
				|| S->DisplayName.ToLower().Contains(KW)
				|| S->Description.ToLower().Contains(KW);
			if (!bMatch) continue;
		}

		FilteredSkills.Add(S);
	}
}
