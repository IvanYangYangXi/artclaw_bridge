// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
#include "IAgentPlatformBridge.h"
#include "OpenClawPlatformBridge.h"
#include "Editor.h"

// 模块化拆分 - 包含各功能模块
#include "UEAgentDashboard_StatusBar.cpp"
#include "UEAgentDashboard_Chat.cpp"
#include "UEAgentDashboard_OpenClawBridge.cpp"
#include "UEAgentDashboard_QuickInput.cpp"
#include "UEAgentDashboard_Session.cpp"
#include "UEAgentDashboard_Plan.cpp"
#include "UEAgentDashboard_System.cpp"
#include "UEAgentDashboard_Main.cpp"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"


#undef LOCTEXT_NAMESPACE