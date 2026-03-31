// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
#include "UEAgentManageUtils.h"
#include "IAgentPlatformBridge.h"
#include "OpenClawPlatformBridge.h"
#include "Editor.h"
#include "IPythonScriptPlugin.h"

// Slate Widgets
#include "Widgets/SWindow.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Text/SMultiLineEditableText.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMenuAnchor.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "Widgets/Docking/SDockTab.h"
#include "Framework/Application/SlateApplication.h"
#include "Input/Reply.h"

// Serialization
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

// Misc
#include "Misc/MessageDialog.h"
#include "Misc/Guid.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformProcess.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// 模块化拆分 - 包含各功能模块 (使用 _impl.h 后缀避免被 UE 编译系统当作独立编译单元)
// 注意: 所有 include 集中在本文件，_impl.h 不应有自己的 #include 或 #define LOCTEXT
#include "UEAgentDashboard_StatusBar_impl.h"
#include "UEAgentDashboard_Chat_impl.h"
#include "UEAgentDashboard_MessageList_impl.h"
#include "UEAgentDashboard_OpenClawBridge_impl.h"
#include "UEAgentDashboard_QuickInput_impl.h"
#include "UEAgentDashboard_Session_impl.h"
#include "UEAgentDashboard_Plan_impl.h"
#include "UEAgentDashboard_System_impl.h"
#include "UEAgentDashboard_Settings_impl.h"
#include "UEAgentDashboard_Main_impl.h"

#undef LOCTEXT_NAMESPACE