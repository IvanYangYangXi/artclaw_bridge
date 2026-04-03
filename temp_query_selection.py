import asyncio
import json
import websockets

async def query_ue_selection():
    """Connect to UE MCP server and call run_ue_python tool"""
    
    uri = "ws://localhost:8080"
    
    # JSON-RPC 2.0 request to call run_ue_python tool
    python_code = '''
import unreal

selected = unreal.EditorLevelLibrary.get_selected_level_actors()

if not selected:
    result = "当前没有选中任何对象"
else:
    lines = [f"选中对象数量：{len(selected)}", ""]
    for actor in selected:
        name = actor.get_name()
        class_name = actor.get_class().get_name()
        label = actor.get_actor_label()
        location = actor.get_actor_location()
        rotation = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        
        lines.append(f"名称：{name}")
        lines.append(f"类：{class_name}")
        lines.append(f"Label: {label}")
        lines.append(f"位置：({location.x:.2f}, {location.y:.2f}, {location.z:.2f})")
        lines.append(f"旋转：({rotation.pitch:.2f}, {rotation.yaw:.2f}, {rotation.roll:.2f})")
        lines.append(f"缩放：({scale.x:.2f}, {scale.y:.2f}, {scale.z:.2f})")
        lines.append("-" * 50)
    result = "\\n".join(lines)

print(result)
'''
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "run_ue_python",
            "arguments": {
                "code": python_code,
                "inject_context": True
            }
        }
    }
    
    try:
        async with websockets.connect(uri) as websocket:
            # Send request
            await websocket.send(json.dumps(request))
            
            # Wait for response
            response = await websocket.recv()
            result = json.loads(response)
            
            print("Response:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Extract output from result
            if "result" in result:
                content = result.get("result", {}).get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        print("\n--- Output ---")
                        print(item.get("text", ""))
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(query_ue_selection())
