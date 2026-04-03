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
	"hub = get_skill_hub()\n"
	"if hub:\n"
	"    hub.scan_and_register(metadata_only=True)  # 轻量重扫 manifest，不加载 Python 模块\n"
	"skills = []\n"
	"seen_names = set()  # 用目录名+manifest名双重去重\n"
	"\n"
	"# --- 加载配置 ---\n"
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
	"\n"
	"# --- 项目源码 Skill 目录映射 (name -> {layer, path, dcc_subdir}) ---\n"
	"_project_root = _ac_cfg.get('project_root', '')\n"
	"_source_skill_map = {}  # skill_dir_name -> {layer, path, dcc}\n"
	"_KNOWN_LAYERS = {'official', 'marketplace', 'user'}\n"
	"_SKIP_DIRS = {'templates', '__pycache__', '.git'}\n"
	"if _project_root and os.path.isdir(_project_root):\n"
	"    _skills_root = os.path.join(_project_root, 'skills')\n"
	"    if os.path.isdir(_skills_root):\n"
	"        for _layer_name in os.listdir(_skills_root):\n"
	"            _layer_path = os.path.join(_skills_root, _layer_name)\n"
	"            if not os.path.isdir(_layer_path) or _layer_name in _SKIP_DIRS: continue\n"
	"            for _dcc_name in os.listdir(_layer_path):\n"
	"                _dcc_path = os.path.join(_layer_path, _dcc_name)\n"
	"                if not os.path.isdir(_dcc_path) or _dcc_name in _SKIP_DIRS: continue\n"
	"                for _sn in os.listdir(_dcc_path):\n"
	"                    _sp = os.path.join(_dcc_path, _sn)\n"
	"                    if os.path.isdir(_sp) and _sn not in _SKIP_DIRS:\n"
	"                        _source_skill_map[_sn] = {'layer': _layer_name, 'path': _sp, 'dcc': _dcc_name}\n"
	"\n"
	"# --- 名称别名映射 (旧名 -> 新名, 与 skill_hub._NAME_ALIAS_MAP 一致) ---\n"
	"_ALIAS = {\n"
	"    'artclaw_material': 'ue57_material_node_edit',\n"
	"    'ue54_artclaw_material': 'ue57_material_node_edit',\n"
	"    'ue54_material_node_edit': 'ue57_material_node_edit',\n"
	"    'get_material_nodes': 'ue57_get_material_nodes',\n"
	"    'ue54_get_material_nodes': 'ue57_get_material_nodes',\n"
	"    'generate_material_documentation': 'ue57_generate_material_documentation',\n"
	"    'ue54_generate_material_documentation': 'ue57_generate_material_documentation',\n"
	"    'artclaw-context': 'ue57-artclaw-context',\n"
	"    'artclaw-highlight': 'ue57-artclaw-highlight',\n"
	"}\n"
	"\n"
	"def _canonical(n):\n"
	"    return _ALIAS.get(n, n)\n"
	"\n"
	"def _norm_layer(layer):\n"
	"    \"\"\"非标准 layer 统一归为 platform\"\"\"\n"
	"    return layer if layer in _KNOWN_LAYERS else 'platform'\n"
	"\n"
	"# 1) skill_hub 代码包（运行时已加载的 Skill）\n"
	"if hub:\n"
	"    for m in hub._all_manifests:\n"
	"        cn = _canonical(m.name)\n"
	"        if cn in seen_names: continue\n"
	"        seen_names.add(cn)\n"
	"        seen_names.add(m.name)  # 也加原名防重复\n"
	"        src_dir = str(getattr(m, 'source_dir', '') or '')\n"
	"        _layer = getattr(m, 'source_layer', 'custom')\n"
	"        # 从项目源码提升 layer\n"
	"        if cn in _source_skill_map:\n"
	"            _layer = _source_skill_map[cn]['layer']\n"
	"        _layer = _norm_layer(_layer)\n"
	"        # installed_dir = 运行时路径, source_path = 项目源码路径\n"
	"        _src_info = _source_skill_map.get(cn, {})\n"
	"        # software: 项目源码 dcc 优先, 否则用 manifest 值\n"
	"        _sw = _src_info.get('dcc', '') or getattr(m, 'software', 'universal')\n"
	"        if _sw == 'unreal': _sw = 'unreal_engine'\n"
	"        skills.append({\n"
	"            'name': cn,\n"
	"            'display_name': getattr(m, 'display_name', cn),\n"
	"            'description': getattr(m, 'description', ''),\n"
	"            'version': getattr(m, 'version', ''),\n"
	"            'layer': _layer,\n"
	"            'software': _sw,\n"
	"            'category': getattr(m, 'category', 'general'),\n"
	"            'risk_level': getattr(m, 'risk_level', 'low'),\n"
	"            'author': getattr(m, 'author', ''),\n"
	"            'has_code': os.path.exists(os.path.join(src_dir, '__init__.py')) if src_dir else False,\n"
	"            'has_skill_md': os.path.exists(os.path.join(src_dir, 'SKILL.md')) if src_dir else False,\n"
	"            'install_status': 'full',\n"
	"            'installed_dir': src_dir,\n"
	"            'source_dir': _src_info.get('path', ''),\n"
	"        })\n"
	"\n"
	"# 2) 平台已安装 Skills 目录 (config 驱动)\n"
	"if os.path.isdir(oc_dir):\n"
	"    for name in sorted(os.listdir(oc_dir)):\n"
	"        cn = _canonical(name)\n"
	"        if cn in seen_names: continue\n"
	"        sd = os.path.join(oc_dir, name)\n"
	"        sm = os.path.join(sd, 'SKILL.md')\n"
	"        if not os.path.isdir(sd) or not os.path.isfile(sm): continue\n"
	"        seen_names.add(cn)\n"
	"        seen_names.add(name)\n"
	"        desc = ''; _author = ''; _fm_software = ''; _version = ''\n"
	"        try:\n"
	"            with open(sm, 'r', encoding='utf-8') as f:\n"
	"                _raw = f.read(4096)\n"
	"            if _raw.startswith('---'):\n"
	"                _end = _raw.find('---', 3)\n"
	"                if _end > 0:\n"
	"                    _fm = _raw[3:_end]\n"
	"                    _in_ac = False\n"
	"                    for _fl in _fm.split('\\n'):\n"
	"                        _stripped = _fl.strip()\n"
	"                        _indent = len(_fl) - len(_fl.lstrip())\n"
	"                        if _indent == 0: _in_ac = False\n"
	"                        if _stripped.startswith('author:'):\n"
	"                            _author = _stripped[7:].strip()\n"
	"                        elif _stripped.startswith('version:') and not _stripped.startswith('version: >'):\n"
	"                            _v = _stripped[8:].strip()\n"
	"                            if _v: _version = _v\n"
	"                        elif _stripped.startswith('software:'):\n"
	"                            _fm_software = _stripped[9:].strip()\n"
	"                        elif _stripped.startswith('description:') and not desc:\n"
	"                            _dv = _stripped[12:].strip()\n"
	"                            if _dv and _dv != '>':\n"
	"                                desc = _dv[:120]\n"
	"                        elif _stripped == 'artclaw:':\n"
	"                            _in_ac = True\n"
	"            if not desc:\n"
	"                for _fl in _raw.split('\\n'):\n"
	"                    _fl = _fl.strip()\n"
	"                    if _fl and not _fl.startswith('#') and not _fl.startswith('---'):\n"
	"                        desc = _fl[:120]; break\n"
	"        except: pass\n"
	"        _src_info = _source_skill_map.get(cn, _source_skill_map.get(name, {}))\n"
	"        _layer = _src_info.get('layer', 'platform')\n"
	"        _layer = _norm_layer(_layer)\n"
	"        # software 优先级: frontmatter > 项目源码 dcc > 名称前缀推断 > universal\n"
	"        _dcc = _fm_software or _src_info.get('dcc', '')\n"
	"        if not _dcc:\n"
	"            if cn.startswith('ue') and len(cn) > 2 and cn[2:3].isdigit():\n"
	"                _dcc = 'unreal_engine'\n"
	"            elif cn.startswith('maya'):\n"
	"                _dcc = 'maya'\n"
	"            elif cn.startswith('max'):\n"
	"                _dcc = 'max'\n"
	"            else:\n"
	"                _dcc = 'universal'\n"
	"        # manifest.json 优先提供 version/author\n"
	"        _mj = os.path.join(sd, 'manifest.json')\n"
	"        if os.path.isfile(_mj):\n"
	"            try:\n"
	"                with open(_mj, 'r', encoding='utf-8') as _mf:\n"
	"                    _md = json.load(_mf)\n"
	"                if _md.get('version'): _version = _md['version']\n"
	"                if _md.get('author') and not _author: _author = _md['author']\n"
	"            except: pass\n"
	"        skills.append({\n"
	"            'name': cn, 'display_name': name, 'description': desc,\n"
	"            'version': _version, 'layer': _layer, 'software': _dcc,\n"
	"            'category': 'general', 'risk_level': 'low', 'author': _author,\n"
	"            'has_code': False, 'has_skill_md': True,\n"
	"            'install_status': 'doc_only',\n"
	"            'installed_dir': sd,\n"
	"            'source_dir': _src_info.get('path', ''),\n"
	"        })\n"
	"\n"
	"# 3) Phase 4: 未安装的 Skill (源码有但运行时没有)\n"
	"try:\n"
	"    from skill_sync import compare_source_vs_runtime\n"
	"    diff = compare_source_vs_runtime()\n"
	"    if not diff.get('error'):\n"
	"        for info in diff.get('available', []):\n"
	"            n = _canonical(info['name'])\n"
	"            if n in seen_names: continue\n"
	"            seen_names.add(n)\n"
	"            _raw_layer = info.get('layer', 'marketplace')\n"
	"            skills.append({\n"
	"                'name': n, 'display_name': n,\n"
	"                'description': '',\n"
	"                'version': info.get('version', ''),\n"
	"                'layer': _norm_layer(_raw_layer),\n"
	"                'software': info.get('dcc', 'universal'),\n"
	"                'category': 'general', 'risk_level': 'low',\n"
	"                'has_code': info.get('has_code', False),\n"
	"                'has_skill_md': info.get('has_skill_md', False),\n"
	"                'install_status': 'not_installed',\n"
	"                'installed_dir': '',\n"
	"                'source_dir': info.get('path', ''),\n"
	"            })\n"
	"        updatable_names = {_canonical(i['name']) for i in diff.get('updatable', [])}\n"
	"        modified_names = {_canonical(i['name']) for i in diff.get('modified', [])}\n"
	"        for s in skills:\n"
	"            if s['name'] in updatable_names:\n"
	"                s['updatable'] = True\n"
	"                for u in diff.get('updatable', []):\n"
	"                    if _canonical(u['name']) == s['name']:\n"
	"                        s['source_version'] = u.get('version', '')\n"
	"                        break\n"
	"            if s['name'] in modified_names:\n"
	"                s['modified'] = True\n"
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
		Obj->TryGetBoolField(TEXT("modified"), E->bModified);
		Obj->TryGetStringField(TEXT("source_dir"), E->SourceDir);
		Obj->TryGetStringField(TEXT("installed_dir"), E->InstalledDir);

		FString InstallStr = Obj->GetStringField(TEXT("install_status"));
		// doc_only / full → Installed；not_installed → NotInstalled
		E->InstallStatus = (InstallStr == TEXT("not_installed"))
			? EInstallStatus::NotInstalled
			: EInstallStatus::Installed;

		Obj->TryGetStringField(TEXT("source_version"), E->SourceVersion);

		AllSkills.Add(E);
	}

	// 动态提取软件分类和层级列表（去重排序）
	{
		TSet<FString> SoftwareSet, LayerSet;
		for (const auto& S : AllSkills)
		{
			if (!S->Software.IsEmpty()) SoftwareSet.Add(S->Software);
			if (!S->Layer.IsEmpty()) LayerSet.Add(S->Layer);
		}
		DiscoveredSoftwareTypes = SoftwareSet.Array();
		DiscoveredSoftwareTypes.Sort();
		DiscoveredLayers = LayerSet.Array();
		DiscoveredLayers.Sort();
	}

	ApplyFilters();
}

void SUEAgentSkillTab::ApplyFilters()
{
	FilteredSkills.Empty();
	for (const auto& S : AllSkills)
	{
		// Layer 筛选: "platform" 包含所有非 official/marketplace/user 的 layer
		if (LayerFilter != TEXT("all"))
		{
			if (LayerFilter == TEXT("platform"))
			{
				if (S->Layer == TEXT("official") || S->Layer == TEXT("marketplace")
					|| S->Layer == TEXT("user"))
					continue;
			}
			else if (S->Layer != LayerFilter)
			{
				continue;
			}
		}

		// 安装状态过滤
		if (InstallFilter != TEXT("all"))
		{
			if (InstallFilter == TEXT("installed") && S->InstallStatus != EInstallStatus::Installed) continue;
			if (InstallFilter == TEXT("notinstalled") && S->InstallStatus != EInstallStatus::NotInstalled) continue;
		}

		// DCC/软件分类过滤（严格匹配，不混入通用）
		if (DccFilter != TEXT("all"))
		{
			if (DccFilter == TEXT("unreal"))
			{
				if (S->Software != TEXT("unreal_engine") && S->Software != TEXT("unreal"))
					continue;
			}
			else if (DccFilter == TEXT("universal"))
			{
				if (S->Software != TEXT("universal")) continue;
			}
			else if (S->Software != DccFilter)
			{
				continue;
			}
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
