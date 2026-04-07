// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"

/**
 * Graph node auto-layout utility for Blueprint and Material graphs.
 * Calculates non-overlapping positions for new nodes using multiple strategies.
 */
class UECLAWBRIDGEAPI_API FGraphLayoutUtil
{
public:
	/**
	 * Calculate optimal position for a new Blueprint node.
	 * Uses three-tier strategy: Pin relative → Target node side → Grid scan
	 *
	 * @param Graph The Blueprint graph
	 * @param TargetNode Optional target node for relative positioning
	 * @param TargetPin Optional target pin for pin-relative positioning
	 * @return Calculated position (X, Y coordinates)
	 */
	static FVector2D CalculateBlueprintNodePosition(
		UEdGraph* Graph,
		UEdGraphNode* TargetNode = nullptr,
		UEdGraphPin* TargetPin = nullptr);

	/**
	 * Calculate optimal position for a new Material Expression.
	 * Material flows from right to left, so positions are calculated leftward.
	 *
	 * @param Material The Material asset
	 * @param TargetExpression Optional target expression for relative positioning
	 * @return Calculated position (X, Y coordinates)
	 */
	static FVector2D CalculateMaterialExpressionPosition(
		UMaterial* Material,
		UMaterialExpression* TargetExpression = nullptr);

private:
	// Node sizing constants
	static constexpr float DEFAULT_NODE_WIDTH = 200.0f;
	static constexpr float DEFAULT_NODE_HEIGHT = 100.0f;
	static constexpr float DEFAULT_SPACING = 100.0f;
	static constexpr float DEFAULT_PADDING = 20.0f;
	static constexpr float DEFAULT_EXPRESSION_WIDTH = 150.0f;
	static constexpr float DEFAULT_EXPRESSION_HEIGHT = 80.0f;

	/**
	 * Calculate position relative to a target pin.
	 * Different offsets for Exec vs Data pins, Input vs Output pins.
	 *
	 * @param TargetPin The pin to position relative to
	 * @return Relative position offset
	 */
	static FVector2D CalculateRelativePosition(UEdGraphPin* TargetPin);

	/**
	 * Find empty space in Blueprint graph using grid scanning.
	 * Scans in 10x10 grid pattern, moving right and down.
	 *
	 * @param Graph The graph to scan
	 * @param StartPosition Starting position for scan
	 * @return First empty position found
	 */
	static FVector2D FindEmptySpaceInGraph(UEdGraph* Graph, const FVector2D& StartPosition);

	/**
	 * Find empty space in Material graph using grid scanning.
	 * Material flows right-to-left, so scans leftward.
	 *
	 * @param Material The Material to scan
	 * @param StartPosition Starting position for scan
	 * @return First empty position found
	 */
	static FVector2D FindEmptySpaceInMaterial(UMaterial* Material, const FVector2D& StartPosition);

	/**
	 * Check if a position overlaps with existing nodes using AABB collision.
	 *
	 * @param Position Position to check
	 * @param Width Node width
	 * @param Height Node height
	 * @param Graph Graph containing existing nodes
	 * @return true if position overlaps with any existing node
	 */
	static bool DoesPositionOverlap(
		const FVector2D& Position,
		float Width,
		float Height,
		UEdGraph* Graph);

	/**
	 * Check if a position overlaps with existing Material expressions.
	 *
	 * @param Position Position to check
	 * @param Width Expression width
	 * @param Height Expression height
	 * @param Material Material containing existing expressions
	 * @return true if position overlaps with any existing expression
	 */
	static bool DoesPositionOverlap(
		const FVector2D& Position,
		float Width,
		float Height,
		UMaterial* Material);

	/**
	 * Calculate bounding box of all nodes in a graph.
	 *
	 * @param Graph The graph to analyze
	 * @return Bounding box (Min.X, Min.Y, Max.X, Max.Y)
	 */
	static FBox2D GetGraphBounds(UEdGraph* Graph);

	/**
	 * Calculate bounding box of all expressions in a Material.
	 *
	 * @param Material The Material to analyze
	 * @return Bounding box (Min.X, Min.Y, Max.X, Max.Y)
	 */
	static FBox2D GetMaterialBounds(UMaterial* Material);
};