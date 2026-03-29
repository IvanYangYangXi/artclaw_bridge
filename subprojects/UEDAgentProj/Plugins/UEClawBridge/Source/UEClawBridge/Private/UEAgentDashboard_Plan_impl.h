// Copyright ArtClaw Project. All Rights Reserved. Plan模式模块 - 计划解析、步骤执行、暂停/恢复/取消

#include "UEAgentDashboard.h"
#include "UEAgentLocalization.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// Plan 模式 (任务 5.9)
// ==================================================================

FReply SUEAgentDashboard::OnTogglePlanModeClicked()
{
	bPlanMode = !bPlanMode;
	if (!bPlanMode && CurrentPlan.IsSet())
	{
		if (CurrentPlan->bIsExecuting && bIsWaitingForResponse)
		{
			OnStopClicked();
		}
		CurrentPlan.Reset();
	}
	return FReply::Handled();
}

FText SUEAgentDashboard::GetPlanModeButtonText() const
{
	if (bPlanMode)
	{
		return FUEAgentL10n::Get( TEXT("PlanModeOn"));
	}
	return FUEAgentL10n::Get(TEXT("PlanModeOff"));
}

void SUEAgentDashboard::TryParsePlan(const FString& Response)
{
	// 尝试从 AI 回复中解析 Plan JSON
	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		return;
	}

	// 查找 plan 对象
	const TSharedPtr<FJsonObject>* PlanObj = nullptr;
	if (!JsonObj->TryGetObjectField(TEXT("plan"), PlanObj) || !PlanObj)
	{
		return;
	}

	// 解析步骤
	const TArray<TSharedPtr<FJsonValue>>* StepsArray = nullptr;
	if (!(*PlanObj)->TryGetArrayField(TEXT("steps"), StepsArray) || !StepsArray)
	{
		return;
	}

	FPlan NewPlan;
	NewPlan.PlanId = FGuid::NewGuid().ToString();
	NewPlan.UserRequest = LastPlanRequest;
	NewPlan.bIsExecuting = false;
	NewPlan.bIsPaused = false;
	NewPlan.CurrentStepIndex = -1;

	for (const auto& StepVal : *StepsArray)
	{
		const TSharedPtr<FJsonObject>* StepObj = nullptr;
		if (!StepVal->TryGetObject(StepObj) || !StepObj)
		{
			continue;
		}

		FPlanStep Step;
		Step.Index = (*StepObj)->GetIntegerField(TEXT("index"));
		Step.Title = (*StepObj)->GetStringField(TEXT("title"));
		Step.Description = (*StepObj)->GetStringField(TEXT("description"));
		Step.Status = EPlanStepStatus::Pending;
		NewPlan.Steps.Add( MoveTemp(Step));
	}

	CurrentPlan = MoveTemp(NewPlan);
	AddPlanMessage();
}

void SUEAgentDashboard::AddPlanMessage()
{
	// 在消息流中添加 Plan 展示卡片
	FChatMessage PlanMsg;
	PlanMsg.Sender = TEXT("plan");
	PlanMsg.Content = TEXT(""); // Plan 内容通过 RebuildMessageList 单独渲染
	PlanMsg.Timestamp = FDateTime::Now();
	Messages.Add(MoveTemp(PlanMsg));
	RebuildMessageList();
}

void SUEAgentDashboard::ExecuteNextPlanStep()
{
	if (!CurrentPlan.IsSet() || CurrentPlan->bIsPaused)
	{
		return;
	}

	// 查找下一个 Pending 步骤
	int32 NextStepIdx = -1;
	for (int32 i = 0; i < CurrentPlan->Steps.Num(); ++i)
	{
		if (CurrentPlan->Steps[i].Status == EPlanStepStatus::Pending)
		{
			NextStepIdx = i;
			break;
		}
	}

	if (NextStepIdx < 0)
	{
		// 所有步骤已完成
		CurrentPlan->bIsExecuting = false;
		RebuildMessageList();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanCompleted")));
		return;
	}

	// 更新当前步骤状态
	CurrentPlan->CurrentStepIndex = NextStepIdx;
	CurrentPlan->Steps[NextStepIdx].Status = EPlanStepStatus::Running;
	CurrentPlan->bIsExecuting = true;

	// 执行步骤：发送步骤描述给 AI
	FPlanStep& Step = CurrentPlan->Steps[NextStepIdx];
	FString StepPrompt = FString::Printf(
		TEXT("Execute step %d: %s\n\nDescription: %s\n\nPlease execute this step and report the result."),
		Step.Index, *Step.Title, *Step.Description);

	SendToOpenClaw(StepPrompt);
	RebuildMessageList();
}

FReply SUEAgentDashboard::OnExecutePlanClicked()
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsPaused = false;
	ExecuteNextPlanStep();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnPausePlanClicked()
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsPaused = true;
	CurrentPlan->bIsExecuting = false;

	// 取消正在进行的请求
	if (bIsWaitingForResponse)
	{
		OnStopClicked();
	}

	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanPaused")));

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnResumePlanClicked()
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsPaused = false;
	ExecuteNextPlanStep();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnCancelPlanClicked()
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	// 取消正在进行的请求
	if (bIsWaitingForResponse)
	{
		OnStopClicked();
	}

	CurrentPlan.Reset();
	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanCancelled")));

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDeletePlanStep(int32 StepIndex)
{
	if (!CurrentPlan.IsSet() || !CurrentPlan->Steps.IsValidIndex(StepIndex))
	{
		return FReply::Handled();
	}

	// 标记为 Skipped
	CurrentPlan->Steps[StepIndex].Status = EPlanStepStatus::Skipped;
	RebuildMessageList();

	return FReply::Handled();
}