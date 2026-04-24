// Copyright ArtClaw. All Rights Reserved.

using UnrealBuildTool;
using System.IO;

public class XAtlasLib : ModuleRules
{
    public XAtlasLib(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bUseUnity = false;

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject",
            "Engine",
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            "UnrealEd",
            "MeshDescription",
            "StaticMeshDescription",
        });

        // Suppress third-party code warnings
        bEnableUndefinedIdentifierWarnings = false;

        // xatlas.cpp: treat as third-party (suppress all warnings)
        string XAtlasCpp = Path.Combine(ModuleDirectory, "Private", "xatlas.cpp");
        if (File.Exists(XAtlasCpp))
        {
            PublicDefinitions.Add("XATLAS_SKIP_CUSTOM_ALLOC=1");
        }
    }
}
