// Copyright ArtClaw Project. All Rights Reserved.
// Skill Tab — 查看/启用/禁用/钉选 + 安装/卸载/同步/发布

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Input/SEditableTextBox.h"

class SUEAgentSkillTab : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentSkillTab) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	void Refresh();

private:
	// 安装状态：只区分"已安装"和"未安装"，去掉 DocOnly 细分
	enum class EInstallStatus : uint8 { Installed, NotInstalled };

	struct FSkillEntry
	{
		FString Name;
		FString DisplayName;
		FString Description;
		FString Version;
		FString Layer;       // official / marketplace / user / custom / platform
		FString Software;
		FString Category;
		FString RiskLevel;
		FString Author;
		bool bEnabled = true;
		bool bPinned = false;
		bool bHasCode = false;
		bool bHasSkillMd = false;
		EInstallStatus InstallStatus = EInstallStatus::Installed;
		FString SourceDir;      // 项目源码路径
		FString InstalledDir;   // 安装运行时路径
		FString SourceVersion;  // 源码版本号（可更新时有值）
		bool bUpdatable = false;
	};
	typedef TSharedPtr<FSkillEntry> FSkillEntryPtr;

	void RefreshData();
	TSharedRef<SWidget> BuildContent();
	TSharedRef<ITableRow> GenerateRow(
		FSkillEntryPtr Item, const TSharedRef<STableViewBase>& OwnerTable);

	void ParseSkillList(const FString& JsonStr);

	// Phase 3 操作
	void OnEnableChanged(ECheckBoxState NewState, FSkillEntryPtr Item);
	FReply OnPinClicked(FSkillEntryPtr Item);
	FReply OnDetailClicked(FSkillEntryPtr Item);
	void ExecuteSkillAction(const FString& Action, const FString& SkillName);

	// Phase 4 操作
	FReply OnInstallClicked(FSkillEntryPtr Item);
	FReply OnUninstallClicked(FSkillEntryPtr Item);
	FReply OnUpdateClicked(FSkillEntryPtr Item);
	FReply OnSyncAllClicked();
	FReply OnPublishClicked(FSkillEntryPtr Item);

	/** 执行 skill_sync 操作并返回 JSON 结果 */
	FString RunSyncAction(const FString& PyCode);

	TArray<FSkillEntryPtr> AllSkills;
	TArray<FSkillEntryPtr> FilteredSkills;
	TSharedPtr<SListView<FSkillEntryPtr>> SkillListView;
	TSharedPtr<SVerticalBox> ContentBox;
	TSharedPtr<SEditableTextBox> SearchBox;

	FString LayerFilter     = TEXT("all");
	FString DccFilter       = TEXT("all");
	FString InstallFilter   = TEXT("all");  // "all" / "installed" / "notinstalled"
	FString SearchKeyword;   // 搜索关键字（空 = 不过滤）

	/** 从数据中动态提取的软件分类列表（去重排序） */
	TArray<FString> DiscoveredSoftwareTypes;
	/** 从数据中动态提取的层级列表（去重排序） */
	TArray<FString> DiscoveredLayers;

	void ApplyFilters();

	/** 延迟刷新：在下一帧执行 Refresh，避免在 Slate 事件回调中同步销毁 widget */
	void RequestRefresh();
	bool bPendingRefresh = false;
};
