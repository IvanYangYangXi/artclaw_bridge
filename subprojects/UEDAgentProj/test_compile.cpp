// 简单测试文件，检查头文件是否正确
#include "Plugins/UEClawBridge/Source/UEClawBridge/Public/UEAgentSubsystem.h"
#include "EditorDelegates.h"
#include "AssetRegistry/AssetRegistryModule.h"

// 测试编译是否通过
void TestFunction()
{
    // 测试委托是否存在
    FEditorDelegates::OnAssetsPreDelete.AddLambda([](const TArray<FAssetData>&){});
}