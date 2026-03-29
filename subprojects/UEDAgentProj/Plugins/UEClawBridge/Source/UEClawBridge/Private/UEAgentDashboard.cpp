// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
#include "IAgentPlatformBridge.h"
#include "OpenClawPlatformBridge.h"
#include "Editor.h"

// 模块化拆分 - 包含各功能模块 (使用 _impl.h 后缀避免被 UE 编译系统当作独立编译单元)
#include "UEAgentDashboard_StatusBar_impl.h"
#include "UEAgentDashboard_Chat_impl.h"
#include "UEAgentDashboard_MessageList_impl.h"
#include "UEAgentDashboard_OpenClawBridge_impl.h"
#include "UEAgentDashboard_QuickInput_impl.h"
#include "UEAgentDashboard_Session_impl.h"
#include "UEAgentDashboard_Plan_impl.h"
#include "UEAgentDashboard_System_impl.h"
#include "UEAgentDashboard_Main_impl.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"


#undef LOCTEXT_NAMESPACE