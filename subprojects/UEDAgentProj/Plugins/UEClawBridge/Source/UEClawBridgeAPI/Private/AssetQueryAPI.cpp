// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "AssetQueryAPI.h"
#include "UEClawBridgeAPI.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Utils/PropertySerializer.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
	FString ClawJsonToString(const TSharedPtr<FJsonObject>& Obj)
	{
		if (!Obj.IsValid())
		{
			return TEXT("{}");
		}
		FString Output;
		auto Writer = TJsonWriterFactory<>::Create(&Output);
		FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
		return Output;
	}

	FString ClawMakeError(const FString& Msg)
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), false);
		Obj->SetStringField(TEXT("error"), Msg);
		return ClawJsonToString(Obj);
	}
}

FString UAssetQueryAPI::QueryAsset(const FString& Name, const FString& ClassFilter, const FString& PathFilter, int32 Limit)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryAsset: name='%s', class='%s', path='%s', limit=%d"),
		*Name, *ClassFilter, *PathFilter, Limit);

	// Validate input
	if (Name.IsEmpty() && ClassFilter.IsEmpty() && PathFilter.IsEmpty())
	{
		return ClawMakeError(TEXT("At least one filter parameter (Name, ClassFilter, or PathFilter) must be provided"));
	}

	IAssetRegistry& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();

	// Build filter
	FARFilter Filter;

	// Path filter
	if (!PathFilter.IsEmpty())
	{
		Filter.PackagePaths.Add(FName(*PathFilter));
		Filter.bRecursivePaths = true;
	}

	// Class filter
	if (!ClassFilter.IsEmpty())
	{
		FString ClassError;
		UClass* FilterClass = FPropertySerializer::ResolveClass(ClassFilter, ClassError);
		if (!FilterClass)
		{
			// Try common prefixes
			FilterClass = FPropertySerializer::ResolveClass(TEXT("U") + ClassFilter, ClassError);
			if (!FilterClass)
			{
				FilterClass = FPropertySerializer::ResolveClass(TEXT("A") + ClassFilter, ClassError);
			}
		}

		if (FilterClass)
		{
			Filter.ClassPaths.Add(FilterClass->GetClassPathName());
			Filter.bRecursiveClasses = true;
		}
		else
		{
			UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("QueryAsset: Could not resolve class filter '%s', ignoring"), *ClassFilter);
		}
	}

	// Get assets
	TArray<FAssetData> AssetDataList;
	AssetRegistry.GetAssets(Filter, AssetDataList);

	// Apply name filter and build results
	TArray<TSharedPtr<FJsonValue>> AssetsArray;
	int32 Count = 0;
	int32 TotalMatching = 0;

	for (const FAssetData& AssetData : AssetDataList)
	{
		// Apply name filter
		if (!Name.IsEmpty())
		{
			FString AssetName = AssetData.AssetName.ToString();
			if (!MatchesWildcard(AssetName, Name))
			{
				continue;
			}
		}

		TotalMatching++;

		// Check limit
		if (Count >= Limit)
		{
			continue;
		}

		// Build asset entry
		TSharedPtr<FJsonObject> AssetJson = MakeShareable(new FJsonObject);
		AssetJson->SetStringField(TEXT("name"), AssetData.AssetName.ToString());
		AssetJson->SetStringField(TEXT("path"), AssetData.GetObjectPathString());
		AssetJson->SetStringField(TEXT("class"), AssetData.AssetClassPath.GetAssetName().ToString());
		AssetJson->SetStringField(TEXT("package"), AssetData.PackageName.ToString());

		// Add asset tags if any
		if (AssetData.TagsAndValues.Num() > 0)
		{
			TSharedPtr<FJsonObject> TagsJson = MakeShareable(new FJsonObject);
			for (const auto& Tag : AssetData.TagsAndValues)
			{
				TagsJson->SetStringField(Tag.Key.ToString(), Tag.Value.AsString());
			}
			AssetJson->SetObjectField(TEXT("tags"), TagsJson);
		}

		AssetsArray.Add(MakeShareable(new FJsonValueObject(AssetJson)));
		Count++;
	}

	// Build result
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetArrayField(TEXT("assets"), AssetsArray);
	Result->SetNumberField(TEXT("count"), AssetsArray.Num());
	Result->SetNumberField(TEXT("total_matching"), TotalMatching);
	Result->SetBoolField(TEXT("limit_reached"), TotalMatching > Limit);

	// Add filter info
	TSharedPtr<FJsonObject> FiltersJson = MakeShareable(new FJsonObject);
	if (!Name.IsEmpty()) FiltersJson->SetStringField(TEXT("name"), Name);
	if (!ClassFilter.IsEmpty()) FiltersJson->SetStringField(TEXT("class"), ClassFilter);
	if (!PathFilter.IsEmpty()) FiltersJson->SetStringField(TEXT("path"), PathFilter);
	FiltersJson->SetNumberField(TEXT("limit"), Limit);
	Result->SetObjectField(TEXT("filters"), FiltersJson);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryAsset: Found %d assets (total matching: %d)"), Count, TotalMatching);
	
	return ClawJsonToString(Result);
}

FString UAssetQueryAPI::FindReferences(const FString& AssetPath, bool bReferencedBy)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("FindReferences: path='%s', referencedBy=%s"), *AssetPath, bReferencedBy ? TEXT("true") : TEXT("false"));

	if (AssetPath.IsEmpty())
	{
		return ClawMakeError(TEXT("AssetPath parameter is required"));
	}

	// Get package name from asset path
	FString PackagePath = FPackageName::ObjectPathToPackageName(AssetPath);
	FName PackageName = FName(*PackagePath);

	IAssetRegistry& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();

	TArray<FAssetIdentifier> References;
	
	if (bReferencedBy)
	{
		// Find what references this asset
		AssetRegistry.GetReferencers(PackageName, References);
	}
	else
	{
		// Find what this asset references
		AssetRegistry.GetDependencies(PackageName, References);
	}

	// Build results
	TArray<TSharedPtr<FJsonValue>> ReferencesArray;

	for (const FAssetIdentifier& Ref : References)
	{
		if (Ref.PackageName == NAME_None)
		{
			continue;
		}

		// Get assets in this package
		TArray<FAssetData> Assets;
		AssetRegistry.GetAssetsByPackageName(Ref.PackageName, Assets);

		for (const FAssetData& Asset : Assets)
		{
			TSharedPtr<FJsonObject> RefObj = MakeShareable(new FJsonObject);
			RefObj->SetStringField(TEXT("name"), Asset.AssetName.ToString());
			RefObj->SetStringField(TEXT("path"), Asset.GetObjectPathString());
			RefObj->SetStringField(TEXT("package"), Asset.PackageName.ToString());
			RefObj->SetStringField(TEXT("class"), Asset.AssetClassPath.GetAssetName().ToString());

			ReferencesArray.Add(MakeShareable(new FJsonValueObject(RefObj)));
		}
	}

	// Build result
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetBoolField(TEXT("referenced_by"), bReferencedBy);
	Result->SetStringField(TEXT("query_type"), bReferencedBy ? TEXT("referencers") : TEXT("dependencies"));
	Result->SetArrayField(TEXT("references"), ReferencesArray);
	Result->SetNumberField(TEXT("count"), ReferencesArray.Num());

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("FindReferences: Found %d references"), ReferencesArray.Num());

	return ClawJsonToString(Result);
}

FString UAssetQueryAPI::ClassHierarchy(const FString& ClassName, const FString& Direction, int32 MaxDepth)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ClassHierarchy: class='%s', direction='%s', maxDepth=%d"), *ClassName, *Direction, MaxDepth);

	if (ClassName.IsEmpty())
	{
		return ClawMakeError(TEXT("ClassName parameter is required"));
	}

	// Validate direction
	FString Dir = Direction.ToLower();
	if (Dir != TEXT("ancestors") && Dir != TEXT("descendants") && Dir != TEXT("both"))
	{
		return ClawMakeError(TEXT("Direction must be 'ancestors', 'descendants', or 'both'"));
	}

	// Resolve class
	FString ClassError;
	UClass* ResolvedClass = FPropertySerializer::ResolveClass(ClassName, ClassError);
	if (!ResolvedClass)
	{
		return ClawMakeError(FString::Printf(TEXT("Could not resolve class '%s': %s"), *ClassName, *ClassError));
	}

	// Build result
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("class_name"), ClassName);
	Result->SetStringField(TEXT("resolved_class"), ResolvedClass->GetName());
	Result->SetStringField(TEXT("direction"), Direction);
	Result->SetNumberField(TEXT("max_depth"), MaxDepth);

	// Track processed classes to avoid infinite loops
	TSet<UClass*> ProcessedClasses;
	
	// Build hierarchy
	BuildClassHierarchy(ResolvedClass, Result, Dir, 0, MaxDepth, ProcessedClasses);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ClassHierarchy: Generated hierarchy for '%s'"), *ResolvedClass->GetName());

	return ClawJsonToString(Result);
}

bool UAssetQueryAPI::MatchesWildcard(const FString& Text, const FString& Pattern)
{
	// Simple wildcard matching (* and ? support)
	FString RegexPattern = Pattern;
	RegexPattern.ReplaceInline(TEXT("*"), TEXT(".*"));
	RegexPattern.ReplaceInline(TEXT("?"), TEXT("."));
	
	// Use case-insensitive matching
	FRegexPattern Regex(RegexPattern, ERegexPatternFlags::CaseInsensitive);
	FRegexMatcher Matcher(Regex, Text);
	
	return Matcher.FindNext();
}

void UAssetQueryAPI::BuildClassHierarchy(UClass* Class, TSharedPtr<FJsonObject> Result, const FString& Direction, int32 CurrentDepth, int32 MaxDepth, TSet<UClass*>& ProcessedClasses)
{
	if (!Class || CurrentDepth > MaxDepth || ProcessedClasses.Contains(Class))
	{
		return;
	}

	ProcessedClasses.Add(Class);

	// Build ancestors (parent classes)
	if (Direction == TEXT("ancestors") || Direction == TEXT("both"))
	{
		TArray<TSharedPtr<FJsonValue>> AncestorsArray;
		UClass* SuperClass = Class->GetSuperClass();
		int32 Depth = 0;
		
		while (SuperClass && Depth < MaxDepth)
		{
			TSharedPtr<FJsonObject> ClassInfo = MakeShareable(new FJsonObject);
			ClassInfo->SetStringField(TEXT("name"), SuperClass->GetName());
			ClassInfo->SetStringField(TEXT("path"), SuperClass->GetPathName());
			ClassInfo->SetNumberField(TEXT("depth"), Depth);
			ClassInfo->SetBoolField(TEXT("is_blueprint"), SuperClass->HasAnyClassFlags(CLASS_CompiledFromBlueprint));
			ClassInfo->SetBoolField(TEXT("is_native"), SuperClass->HasAnyClassFlags(CLASS_Native));

			AncestorsArray.Add(MakeShareable(new FJsonValueObject(ClassInfo)));
			
			SuperClass = SuperClass->GetSuperClass();
			Depth++;
		}
		
		if (AncestorsArray.Num() > 0)
		{
			Result->SetArrayField(TEXT("ancestors"), AncestorsArray);
			Result->SetNumberField(TEXT("ancestor_count"), AncestorsArray.Num());
		}
	}

	// Build descendants (child classes)
	if (Direction == TEXT("descendants") || Direction == TEXT("both"))
	{
		TArray<TSharedPtr<FJsonValue>> DescendantsArray;
		
		// Find all classes derived from this one
		for (TObjectIterator<UClass> ClassIterator; ClassIterator; ++ClassIterator)
		{
			UClass* TestClass = *ClassIterator;
			if (TestClass && TestClass != Class && TestClass->IsChildOf(Class))
			{
				// Calculate depth from base class
				int32 Depth = 0;
				UClass* Parent = TestClass->GetSuperClass();
				while (Parent && Parent != Class && Depth < MaxDepth)
				{
					Parent = Parent->GetSuperClass();
					Depth++;
				}
				
				if (Depth <= MaxDepth)
				{
					TSharedPtr<FJsonObject> ClassInfo = MakeShareable(new FJsonObject);
					ClassInfo->SetStringField(TEXT("name"), TestClass->GetName());
					ClassInfo->SetStringField(TEXT("path"), TestClass->GetPathName());
					ClassInfo->SetNumberField(TEXT("depth"), Depth);
					ClassInfo->SetBoolField(TEXT("is_blueprint"), TestClass->HasAnyClassFlags(CLASS_CompiledFromBlueprint));
					ClassInfo->SetBoolField(TEXT("is_native"), TestClass->HasAnyClassFlags(CLASS_Native));

					DescendantsArray.Add(MakeShareable(new FJsonValueObject(ClassInfo)));
				}
			}
		}
		
		if (DescendantsArray.Num() > 0)
		{
			Result->SetArrayField(TEXT("descendants"), DescendantsArray);
			Result->SetNumberField(TEXT("descendant_count"), DescendantsArray.Num());
		}
	}
}