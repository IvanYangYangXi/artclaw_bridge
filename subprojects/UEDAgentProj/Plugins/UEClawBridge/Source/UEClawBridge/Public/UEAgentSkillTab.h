// Copyright ArtClaw Project. All Rights Reserved.
// Skill Tab — 查看/启用/禁用/钉选 + 安装/卸载/同步/发布

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/Views/SListView.h"

class SUEAgentSkillTab : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentSkillTab) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	void Refresh();

private:
	enum class EInstallStatus : uint8 { Full, DocOnly, NotInstalled };

	struct FSkillEntry
	{
		FString Name;
		FString DisplayName;
		FString Description;
		FString Version;
		FString Layer;
		FString Software;
		FString Category;
		FString RiskLevel;
		bool bEnabled = true;
		bool bPinned = false;
		bool bHasCode = false;
		bool bHasSkillMd = false;
		EInstallStatus InstallStatus = EInstallStatus::Full;
		FString SourceDir;
		// Phase 4: 同步信息
		FString RuntimeVersion;   // 运行时版本（用于更新检测）
		FString SourcePath;       // 源码路径
		bool bUpdatable = false;  // 版本不一致
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

	FString LayerFilter = TEXT("all");
	FString DccFilter = TEXT("all");
	FString InstallFilter = TEXT("all");  // all / full / doc_only / not_installed

	void ApplyFilters();
};
