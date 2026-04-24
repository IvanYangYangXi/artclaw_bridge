// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/UE全能力API开发清单.md

using UnrealBuildTool;

public class UEClawBridgeAPI : ModuleRules
{
    public UEClawBridgeAPI(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // 各 API cpp 文件在匿名命名空间中定义了同名辅助函数 (ClawJsonToString 等)
        // Unity Build 合并编译会导致重定义冲突，必须禁用
        bUseUnity = false;

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject",
            "Engine",
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            // === xatlas UV Repack ===
            "XAtlasLib",

            // === 基础 ===
            "UnrealEd",
            "Slate",
            "SlateCore",
            "Json",
            "JsonUtilities",
            "InputCore",
            "EditorFramework",
            "EditorSubsystem",
            "ToolMenus",
            "ImageWrapper",
            "SourceControl",
            "Projects",

            // === Blueprint 图操作 ===
            "BlueprintGraph",
            "KismetCompiler",
            "Kismet",
            "AnimGraph",
            "AnimGraphRuntime",

            // === PIE 控制 ===
            "LevelEditor",

            // === 资产管理 / Widget ===
            "MaterialEditor",
            "UMG",
            "UMGEditor",

            // === Sequencer ===
            "LevelSequence",
            "MovieScene",
            "MovieSceneTracks",

            // === AI / 行为树 ===
            "AIModule",
            "GameplayTasks",
            "GameplayTags",

            // === Enhanced Input (引擎内置，UE 5.1+) ===
            "EnhancedInput",

            // === Niagara (引擎内置插件，UE 5.x 默认启用) ===
            "Niagara",
            "NiagaraEditor",

            // === Gameplay Ability System (需要项目启用 GameplayAbilities 插件) ===
            "GameplayAbilities",

            // === StateTree (UE 5.1+，内置模块) ===
            "StateTreeModule",
            "StateTreeEditorModule",
            "StructUtils",
        });

        // 条件编译宏 — 默认全部启用
        // 如果项目未启用某个插件导致编译失败，将对应模块从上方移除并把宏改为 0
        PublicDefinitions.AddRange(new string[] {
            "WITH_NIAGARA=1",
            "WITH_GAMEPLAY_ABILITIES=1",
            "WITH_STATETREE=1",
            "WITH_ENHANCED_INPUT=1",
        });
    }
}
