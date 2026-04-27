// Copyright ArtClaw. All Rights Reserved.
// Shared JSON response helpers for UEClawBridgeAPI.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonReader.h"

namespace ClawJson
{
	/** Serialize a JSON object to a compact string. */
	inline FString ToString(const TSharedPtr<FJsonObject>& Obj)
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

	/** Create an error JSON response: {"success": false, "error": "..."} */
	inline FString MakeError(const FString& Msg)
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), false);
		Obj->SetStringField(TEXT("error"), Msg);
		return ToString(Obj);
	}

	/** Create a success JSON object (caller adds extra fields, then calls ToString). */
	inline TSharedPtr<FJsonObject> MakeSuccess()
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), true);
		return Obj;
	}

	/** Create a success JSON response, merging optional extra data fields. */
	inline FString MakeSuccessStr(const TSharedPtr<FJsonObject>& Data = nullptr)
	{
		auto Obj = MakeSuccess();
		if (Data.IsValid())
		{
			for (auto& Pair : Data->Values)
			{
				Obj->SetField(Pair.Key, Pair.Value);
			}
		}
		return ToString(Obj);
	}

	/** Parse a JSON string into an object. Returns nullptr on failure and sets OutError. */
	inline TSharedPtr<FJsonObject> Parse(const FString& JsonString, FString& OutError)
	{
		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
		if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
		{
			OutError = TEXT("Failed to parse JSON string");
			return nullptr;
		}
		return JsonObject;
	}
}
