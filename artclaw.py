#!/usr/bin/env python3
"""
artclaw.py - ArtClaw CLI 入口
==============================

用法:
    python artclaw.py skill test [module] [options]
    python artclaw.py skill list
    python artclaw.py skill test --help

当前支持的命令:
    skill test    - 本地测试 Skill（无需 UE 或 OpenClaw）
    skill list    - 列出所有已发现的 Skill
"""

import sys
import os
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("ArtClaw CLI v1.0")
        print()
        print("Usage:")
        print("  artclaw skill test [module] [options]   Test skills locally")
        print("  artclaw skill list                      List discovered skills")
        print("  artclaw skill test --help               Show test options")
        print()
        print("Options for 'skill test':")
        print("  module              Module name to test (e.g., scene_ops)")
        print("  --skill NAME        Test specific skill by name")
        print("  --validate          Validate declarations only")
        print("  --dry-run           Run dry-run tests")
        print("  --skills-dir PATH   Custom Skills directory")
        print("  --verbose, -v       Verbose output")
        sys.exit(0)

    command = sys.argv[1]

    if command == "skill":
        if len(sys.argv) < 3:
            print("Usage: artclaw skill <subcommand>")
            print("  test    Test skills locally")
            print("  list    List discovered skills")
            sys.exit(1)

        subcommand = sys.argv[2]

        if subcommand == "test":
            # 转发到 skill_test.py
            test_script = Path(__file__).parent / "subprojects" / "UEDAgentProj" / \
                          "Plugins" / "UEEditorAgent" / "Content" / "Python" / \
                          "tests" / "skill_test.py"
            
            if not test_script.exists():
                # 尝试相对路径
                test_script = Path(__file__).parent / "tests" / "skill_test.py"
            
            if not test_script.exists():
                print(f"Error: skill_test.py not found")
                print(f"  Tried: {test_script}")
                sys.exit(1)

            # 转发剩余参数
            remaining_args = sys.argv[3:]
            sys.argv = [str(test_script)] + remaining_args
            
            # 添加脚本目录到 path
            sys.path.insert(0, str(test_script.parent))
            
            # 直接执行
            exec(open(str(test_script), encoding='utf-8').read())

        elif subcommand == "list":
            # 等同于 skill test --list
            test_script = Path(__file__).parent / "subprojects" / "UEDAgentProj" / \
                          "Plugins" / "UEEditorAgent" / "Content" / "Python" / \
                          "tests" / "skill_test.py"
            
            if not test_script.exists():
                test_script = Path(__file__).parent / "tests" / "skill_test.py"

            sys.argv = [str(test_script), "--list"]
            sys.path.insert(0, str(test_script.parent))
            exec(open(str(test_script), encoding='utf-8').read())

        else:
            print(f"Unknown subcommand: {subcommand}")
            print("Available: test, list")
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        print("Available: skill")
        sys.exit(1)


if __name__ == "__main__":
    main()
