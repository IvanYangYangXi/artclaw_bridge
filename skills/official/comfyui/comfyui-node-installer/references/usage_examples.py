"""
ComfyUI Node Installer - 实际使用示例
=====================================

此代码可以直接通过 run_python 在 ComfyUI 进程中执行
"""

# ============================================================
# 示例 1: 快速诊断 workflow
# ============================================================

def example_quick_diagnose():
    """快速诊断示例 workflow"""
    
    # 示例 workflow（包含一些可能需要额外节点的类型）
    sample_workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sdxl_base.safetensors"}
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a beautiful landscape", "clip": ["1", 1]}
        },
        "3": {
            "class_type": "CannyEdgePreprocessor",  # 需要 ComfyUI-ControlNet-Aux
            "inputs": {"image": ["4", 0], "low_threshold": 100}
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": "input.png"}
        },
        "5": {
            "class_type": "VHS_LoadVideo",  # 需要 ComfyUI-VideoHelperSuite
            "inputs": {"video": "input.mp4"}
        }
    }
    
    # 使用内置函数诊断
    import sys
    sys.path.insert(0, 'C:/Users/yangjili/.openclaw/skills/comfyui-node-installer/references')
    
    from node_installer_impl import quick_diagnose, diagnose_workflow
    
    print("=" * 60)
    print("示例 1: 快速诊断")
    print("=" * 60)
    
    report = quick_diagnose(sample_workflow)
    print(report)
    
    return diagnose_workflow(sample_workflow)


# ============================================================
# 示例 2: 检测并安装缺失节点
# ============================================================

def example_detect_and_install():
    """检测并安装缺失节点"""
    
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "2": {"class_type": "CannyEdgePreprocessor", "inputs": {}},  # 需要安装
    }
    
    import sys
    sys.path.insert(0, 'C:/Users/yangjili/.openclaw/skills/comfyui-node-installer/references')
    
    from node_installer_impl import diagnose_workflow, install_missing_nodes
    
    print("\n" + "=" * 60)
    print("示例 2: 检测并安装")
    print("=" * 60)
    
    # 第一步：诊断
    diagnosis = diagnose_workflow(workflow)
    print(f"\n诊断结果: {diagnosis['status']}")
    print(f"缺失节点: {diagnosis['missing_count']}")
    
    if diagnosis['missing_count'] > 0:
        for m in diagnosis['missing']:
            print(f"  - {m['node_type']}: {m['suggestion']}")
        
        # 第二步：生成安装计划（不自动安装）
        print("\n安装计划:")
        result = install_missing_nodes(workflow, auto_install=False)
        if result.get('plan'):
            for item in result['plan']:
                print(f"  • {item['package']}")
                print(f"    节点: {', '.join(item['nodes'])}")
                print(f"    地址: {item['url']}")
        
        # 如需自动安装，取消下面注释：
        # install_result = install_missing_nodes(workflow, auto_install=True)
        # print(f"\n安装结果: {install_result}")


# ============================================================
# 示例 3: 搜索节点包
# ============================================================

def example_search():
    """搜索节点包"""
    
    import sys
    sys.path.insert(0, 'C:/Users/yangjili/.openclaw/skills/comfyui-node-installer/references')
    
    from node_installer_impl import search_packages
    
    print("\n" + "=" * 60)
    print("示例 3: 搜索节点包")
    print("=" * 60)
    
    # 搜索 controlnet 相关
    results = search_packages("controlnet", limit=5)
    print(f"\n搜索 'controlnet'，找到 {len(results)} 个结果:")
    for r in results:
        print(f"  • {r['node_type']}")
        print(f"    包: {r['package_name']}")
        print(f"    地址: {r['url']}")
        print()


# ============================================================
# 示例 4: 实际使用 - 加载 workflow 前检查
# ============================================================

def example_real_usage():
    """实际使用场景：加载 workflow 前自动检查"""
    
    import sys
    sys.path.insert(0, 'C:/Users/yangjili/.openclaw/skills/comfyui-node-installer/references')
    
    from node_installer_impl import diagnose_workflow, install_missing_nodes
    
    print("\n" + "=" * 60)
    print("示例 4: 实际使用场景")
    print("=" * 60)
    
    # 模拟从文件加载的 workflow
    workflow_from_file = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece", "clip": ["1", 1]}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
        "4": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0]}},
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0]}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0]}},
    }
    
    print("\n检查 workflow 兼容性...")
    diagnosis = diagnose_workflow(workflow_from_file)
    
    if diagnosis['status'] == 'ok':
        print("✅ 所有节点已安装，可以直接使用")
    else:
        print(f"⚠️ 发现 {diagnosis['missing_count']} 个缺失节点")
        
        for m in diagnosis['missing']:
            print(f"  • {m['node_type']}")
        
        if diagnosis['can_auto_install']:
            print("\n💡 可以自动安装缺失的节点")
            print("执行: install_missing_nodes(workflow, auto_install=True)")
        else:
            print("\n⚠️ 部分节点无法自动识别，请手动安装")


# ============================================================
# 运行所有示例
# ============================================================

if __name__ == "__main__":
    print("ComfyUI Node Installer - 使用示例")
    print("=" * 60)
    
    try:
        example_quick_diagnose()
    except Exception as e:
        print(f"示例 1 错误: {e}")
    
    try:
        example_detect_and_install()
    except Exception as e:
        print(f"示例 2 错误: {e}")
    
    try:
        example_search()
    except Exception as e:
        print(f"示例 3 错误: {e}")
    
    try:
        example_real_usage()
    except Exception as e:
        print(f"示例 4 错误: {e}")
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)
