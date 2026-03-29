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
	"            'has_code': os.path.exists(os.path.join(str(src_dir), '__init__.py')) if src_dir else False,\n"
	"            'has_skill_md': os.path.exists(os.path.join(str(src_dir), 'SKILL.md')) if src_dir else False,\n"
	"            'install_status': 'full',\n"
	"            'source_dir': str(src_dir) if src_dir else '',\n"
	"        })\n"
	"\n"
	"# 2) ~/.openclaw/skills/ 仅文档\n"
	"oc_dir = os.path.expanduser('~/.openclaw/skills')\n"
	"if os.path.isdir(oc_dir):\n"
	"    for name in sorted(os.listdir(oc_dir)):\n"
	"        if name in seen_names: continue\n"
	"        sd = os.path.join(oc_dir, name)\n"
	"        sm = os.path.join(sd, 'SKILL.md')\n"
	"        if not os.path.isdir(sd) or not os.path.isfile(sm): continue\n"
	"        seen_names.add(name)\n"
	"        desc = ''\n"
	"        try:\n"
	"            with open(sm, 'r', encoding='utf-8') as f:\n"
	"                for line in f:\n"
	"                    line = line.strip()\n"
	"                    if line and not line.startswith('#'):\n"
	"                        desc = line[:120]; break\n"
	"        except: pass\n"
	"        skills.append({\n"
	"            'name': name, 'display_name': name, 'description': desc,\n"
	"            'version': '', 'layer': 'openclaw', 'software': 'universal',\n"
	"            'category': 'general', 'risk_level': 'low',\n"
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
		Obj->TryGetBoolField(TEXT("enabled"), E->bEnabled);
		Obj->TryGetBoolField(TEXT("pinned"), E->bPinned);
		Obj->TryGetBoolField(TEXT("has_code"), E->bHasCode);
		Obj->TryGetBoolField(TEXT("has_skill_md"), E->bHasSkillMd);
		Obj->TryGetBoolField(TEXT("updatable"), E->bUpdatable);
		E->SourceDir = Obj->GetStringField(TEXT("source_dir"));

		FString InstallStr = Obj->GetStringField(TEXT("install_status"));
		if (InstallStr == TEXT("doc_only"))
			E->InstallStatus = EInstallStatus::DocOnly;
		else if (InstallStr == TEXT("not_installed"))
			E->InstallStatus = EInstallStatus::NotInstalled;
		else
			E->InstallStatus = EInstallStatus::Full;

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

		if (InstallFilter != TEXT("all"))
		{
			if (InstallFilter == TEXT("full") && S->InstallStatus != EInstallStatus::Full) continue;
			if (InstallFilter == TEXT("doc_only") && S->InstallStatus != EInstallStatus::DocOnly) continue;
			if (InstallFilter == TEXT("not_installed") && S->InstallStatus != EInstallStatus::NotInstalled) continue;
		}

		FilteredSkills.Add(S);
	}
}
