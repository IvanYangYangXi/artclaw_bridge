// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Utils/GraphLayoutUtil.h"
#include "EdGraphSchema_K2.h"
#include "UEClawBridgeAPI.h"

FVector2D FGraphLayoutUtil::CalculateBlueprintNodePosition(
	UEdGraph* Graph,
	UEdGraphNode* TargetNode,
	UEdGraphPin* TargetPin)
{
	if (!Graph)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("CalculateBlueprintNodePosition: Graph is null"));
		return FVector2D::ZeroVector;
	}

	FVector2D Position;

	// Strategy 1: Pin-relative positioning
	if (TargetPin)
	{
		Position = CalculateRelativePosition(TargetPin);
		if (!DoesPositionOverlap(Position, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, Graph))
		{
			return Position;
		}
		UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Pin-relative position overlaps, trying target node"));
	}

	// Strategy 2: Target node side positioning
	if (TargetNode)
	{
		// Position to the right of target node
		Position.X = TargetNode->NodePosX + DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
		Position.Y = TargetNode->NodePosY;

		if (!DoesPositionOverlap(Position, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, Graph))
		{
			return Position;
		}
		UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Target node side position overlaps, using grid scan"));
		
		// Use target node position as starting point for grid scan
		Position = FVector2D(TargetNode->NodePosX, TargetNode->NodePosY);
	}
	else
	{
		// No target, start from graph bounds
		FBox2D Bounds = GetGraphBounds(Graph);
		Position = Bounds.bIsValid ? FVector2D(Bounds.Max.X + DEFAULT_SPACING, Bounds.Min.Y) : FVector2D(0, 0);
	}

	// Strategy 3: Grid scan for empty space
	return FindEmptySpaceInGraph(Graph, Position);
}

FVector2D FGraphLayoutUtil::CalculateMaterialExpressionPosition(
	UMaterial* Material,
	UMaterialExpression* TargetExpression)
{
	if (!Material)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("CalculateMaterialExpressionPosition: Material is null"));
		return FVector2D::ZeroVector;
	}

	FVector2D Position;

	// Strategy 1: Target expression relative positioning
	if (TargetExpression)
	{
		// Position to the left of target expression (Material flows right-to-left)
		Position.X = TargetExpression->MaterialExpressionEditorX - DEFAULT_EXPRESSION_WIDTH - DEFAULT_SPACING;
		Position.Y = TargetExpression->MaterialExpressionEditorY;

		if (!DoesPositionOverlap(Position, DEFAULT_EXPRESSION_WIDTH, DEFAULT_EXPRESSION_HEIGHT, Material))
		{
			return Position;
		}
		UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Target expression position overlaps, using grid scan"));
		
		// Use target expression position as starting point
		Position = FVector2D(TargetExpression->MaterialExpressionEditorX, TargetExpression->MaterialExpressionEditorY);
	}
	else
	{
		// No target, start from material bounds
		FBox2D Bounds = GetMaterialBounds(Material);
		Position = Bounds.bIsValid ? FVector2D(Bounds.Min.X - DEFAULT_SPACING, Bounds.Min.Y) : FVector2D(0, 0);
	}

	// Strategy 2: Grid scan for empty space
	return FindEmptySpaceInMaterial(Material, Position);
}

FVector2D FGraphLayoutUtil::CalculateRelativePosition(UEdGraphPin* TargetPin)
{
	if (!TargetPin || !TargetPin->GetOwningNode())
	{
		return FVector2D::ZeroVector;
	}

	UEdGraphNode* OwningNode = TargetPin->GetOwningNode();
	FVector2D BasePosition(OwningNode->NodePosX, OwningNode->NodePosY);

	// Different offsets based on pin type and direction
	bool bIsExecPin = TargetPin->PinType.PinCategory == UEdGraphSchema_K2::PC_Exec;
	bool bIsOutput = (TargetPin->Direction == EGPD_Output);

	if (bIsExecPin)
	{
		// Exec pins: horizontal flow
		if (bIsOutput)
		{
			// Position to the right for exec output
			BasePosition.X += DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
		}
		else
		{
			// Position to the left for exec input
			BasePosition.X -= DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
		}
	}
	else
	{
		// Data pins: can be more flexible
		if (bIsOutput)
		{
			// Position to the right and slightly down for data output
			BasePosition.X += DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
			BasePosition.Y += 50.0f;
		}
		else
		{
			// Position to the left and slightly down for data input
			BasePosition.X -= DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
			BasePosition.Y += 50.0f;
		}
	}

	return BasePosition;
}

FVector2D FGraphLayoutUtil::FindEmptySpaceInGraph(UEdGraph* Graph, const FVector2D& StartPosition)
{
	if (!Graph)
	{
		return FVector2D::ZeroVector;
	}

	// Grid scan pattern: 10x10 grid, moving right and down
	const float GridSize = DEFAULT_NODE_WIDTH + DEFAULT_SPACING;
	const int32 MaxSearchAttempts = 100;

	for (int32 Attempt = 0; Attempt < MaxSearchAttempts; Attempt++)
	{
		int32 GridX = Attempt % 10;
		int32 GridY = Attempt / 10;

		FVector2D TestPosition = StartPosition + FVector2D(GridX * GridSize, GridY * GridSize);

		if (!DoesPositionOverlap(TestPosition, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, Graph))
		{
			return TestPosition;
		}
	}

	// Fallback: return position far to the right
	UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("Could not find empty space in graph, using fallback position"));
	return StartPosition + FVector2D(1000.0f, 0.0f);
}

FVector2D FGraphLayoutUtil::FindEmptySpaceInMaterial(UMaterial* Material, const FVector2D& StartPosition)
{
	if (!Material)
	{
		return FVector2D::ZeroVector;
	}

	// Grid scan pattern: moving left and down (Material flows right-to-left)
	const float GridSize = DEFAULT_EXPRESSION_WIDTH + DEFAULT_SPACING;
	const int32 MaxSearchAttempts = 100;

	for (int32 Attempt = 0; Attempt < MaxSearchAttempts; Attempt++)
	{
		int32 GridX = Attempt % 10;
		int32 GridY = Attempt / 10;

		// Move leftward for Material layout
		FVector2D TestPosition = StartPosition + FVector2D(-GridX * GridSize, GridY * GridSize);

		if (!DoesPositionOverlap(TestPosition, DEFAULT_EXPRESSION_WIDTH, DEFAULT_EXPRESSION_HEIGHT, Material))
		{
			return TestPosition;
		}
	}

	// Fallback: return position far to the left
	UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("Could not find empty space in material, using fallback position"));
	return StartPosition + FVector2D(-1000.0f, 0.0f);
}

bool FGraphLayoutUtil::DoesPositionOverlap(
	const FVector2D& Position,
	float Width,
	float Height,
	UEdGraph* Graph)
{
	if (!Graph)
	{
		return false;
	}

	FBox2D TestBox(Position, Position + FVector2D(Width, Height));

	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node)
		{
			continue;
		}

		FBox2D NodeBox(
			FVector2D(Node->NodePosX, Node->NodePosY),
			FVector2D(Node->NodePosX + DEFAULT_NODE_WIDTH, Node->NodePosY + DEFAULT_NODE_HEIGHT)
		);

		if (TestBox.Intersect(NodeBox))
		{
			return true;
		}
	}

	return false;
}

bool FGraphLayoutUtil::DoesPositionOverlap(
	const FVector2D& Position,
	float Width,
	float Height,
	UMaterial* Material)
{
	if (!Material)
	{
		return false;
	}

	FBox2D TestBox(Position, Position + FVector2D(Width, Height));

	// UE5 API: GetExpressions() returns TArrayView<const TObjectPtr<UMaterialExpression>>
	for (const TObjectPtr<UMaterialExpression>& Expression : Material->GetExpressions())
	{
		if (!Expression)
		{
			continue;
		}

		FBox2D ExpressionBox(
			FVector2D(Expression->MaterialExpressionEditorX, Expression->MaterialExpressionEditorY),
			FVector2D(Expression->MaterialExpressionEditorX + DEFAULT_EXPRESSION_WIDTH, 
					  Expression->MaterialExpressionEditorY + DEFAULT_EXPRESSION_HEIGHT)
		);

		if (TestBox.Intersect(ExpressionBox))
		{
			return true;
		}
	}

	return false;
}

FBox2D FGraphLayoutUtil::GetGraphBounds(UEdGraph* Graph)
{
	if (!Graph || Graph->Nodes.Num() == 0)
	{
		return FBox2D(ForceInit);
	}

	FBox2D Bounds(ForceInit);

	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (Node)
		{
			FVector2D NodeMin(Node->NodePosX, Node->NodePosY);
			FVector2D NodeMax(Node->NodePosX + DEFAULT_NODE_WIDTH, Node->NodePosY + DEFAULT_NODE_HEIGHT);
			Bounds += FBox2D(NodeMin, NodeMax);
		}
	}

	return Bounds;
}

FBox2D FGraphLayoutUtil::GetMaterialBounds(UMaterial* Material)
{
	if (!Material)
	{
		return FBox2D(ForceInit);
	}

	const auto& Expressions = Material->GetExpressions();
	if (Expressions.Num() == 0)
	{
		return FBox2D(ForceInit);
	}

	FBox2D Bounds(ForceInit);

	for (const TObjectPtr<UMaterialExpression>& Expression : Expressions)
	{
		if (Expression)
		{
			FVector2D ExprMin(Expression->MaterialExpressionEditorX, Expression->MaterialExpressionEditorY);
			FVector2D ExprMax(Expression->MaterialExpressionEditorX + DEFAULT_EXPRESSION_WIDTH,
							  Expression->MaterialExpressionEditorY + DEFAULT_EXPRESSION_HEIGHT);
			Bounds += FBox2D(ExprMin, ExprMax);
		}
	}

	return Bounds;
}