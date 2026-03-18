// UEAgentLocalization.h — UE Editor Agent 本地化模块
// 支持中英文运行时切换，不依赖 UE Localization Dashboard

#pragma once

#include "CoreMinimal.h"

/**
 * UE Editor Agent 本地化工具类
 * 
 * 用法:
 *   FUEAgentL10n::Get("ConnectBtn")       // 返回 FText
 *   FUEAgentL10n::SetLanguage(EUEAgentLanguage::English)
 *   FUEAgentL10n::ToggleLanguage()
 */

enum class EUEAgentLanguage : uint8
{
	Chinese,
	English,
};

class UECLAWBRIDGE_API FUEAgentL10n
{
public:
	/** 获取当前语言下的本地化文本 */
	static FText Get(const FString& Key);

	/** 获取当前语言下的本地化字符串 (FString) */
	static FString GetStr(const FString& Key);

	/** 设置语言 */
	static void SetLanguage(EUEAgentLanguage Lang);

	/** 获取当前语言 */
	static EUEAgentLanguage GetLanguage();

	/** 切换语言（中↔英） */
	static void ToggleLanguage();

	/** 获取语言显示名称（用于 UI 按钮） */
	static FText GetLanguageDisplayName();

	/** 初始化（注册所有文本，启动时调用一次） */
	static void Initialize();

private:
	static bool bInitialized;
	static EUEAgentLanguage CurrentLanguage;
	static TMap<FString, FString> ZhTexts;
	static TMap<FString, FString> EnTexts;

	/** 注册一条中英文本 */
	static void Reg(const FString& Key, const FString& Zh, const FString& En);
};
