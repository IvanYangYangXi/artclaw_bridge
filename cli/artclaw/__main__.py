"""
ArtClaw CLI - 主入口
=====================

命令结构: artclaw <command> <subcommand> [options]

用法:
    artclaw skill create <name> [--category scene] [--software unreal_engine]
    artclaw skill generate "自然语言描述"
    artclaw skill test <name> [--dry-run]
    artclaw skill list [--category material]
    artclaw skill info <name>
    artclaw skill package <name>
    artclaw skill publish <name> [--target 01_team]
    artclaw skill install <source>
    artclaw skill uninstall <name>
    artclaw skill enable <name>
    artclaw skill disable <name>
    artclaw skill update <name>
"""

import argparse
import sys

from artclaw.commands import skill as skill_cmd


def main():
    parser = argparse.ArgumentParser(
        prog="artclaw",
        description="ArtClaw - AI-powered DCC Skill management CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- skill ----
    skill_parser = subparsers.add_parser("skill", help="Skill management")
    skill_subparsers = skill_parser.add_subparsers(dest="subcommand", help="Skill subcommands")

    # skill create
    p_create = skill_subparsers.add_parser("create", help="Create a new Skill scaffold")
    p_create.add_argument("name", help="Skill name (snake_case)")
    p_create.add_argument("--category", "-c", default="general",
                          help="Category (scene/asset/material/lighting/render/blueprint/animation/ui/utils)")
    p_create.add_argument("--software", "-s", default="unreal_engine",
                          help="Target software (unreal_engine/maya/3ds_max/universal)")
    p_create.add_argument("--template", "-t", default="basic",
                          help="Template to use (basic/advanced/material_doc)")
    p_create.add_argument("--description", "-d", default="",
                          help="Brief description of the Skill")
    p_create.add_argument("--target-dir", default="",
                          help="Custom output directory (default: auto-detect)")
    p_create.add_argument("--layer", default="02_user",
                          help="Target layer (00_official/01_team/02_user/99_custom)")

    # skill generate
    p_generate = skill_subparsers.add_parser("generate", help="Generate Skill from natural language")
    p_generate.add_argument("description", help="Natural language description of desired Skill")
    p_generate.add_argument("--category", "-c", default="",
                            help="Category hint (auto-detected if omitted)")
    p_generate.add_argument("--software", "-s", default="unreal_engine",
                            help="Target software")
    p_generate.add_argument("--target-dir", default="",
                            help="Custom output directory")
    p_generate.add_argument("--layer", default="02_user",
                            help="Target layer")
    p_generate.add_argument("--dry-run", action="store_true",
                            help="Show what would be generated without writing files")

    # skill test
    p_test = skill_subparsers.add_parser("test", help="Test a Skill for compliance")
    p_test.add_argument("name", nargs="?", default="",
                        help="Skill name or path (test all if omitted)")
    p_test.add_argument("--dir", default="",
                        help="Skills directory to scan")
    p_test.add_argument("--dry-run", action="store_true",
                        help="Show test plan without executing")
    p_test.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    # skill package
    p_package = skill_subparsers.add_parser("package", help="Package a Skill for distribution")
    p_package.add_argument("name", help="Skill name")
    p_package.add_argument("--output", "-o", default="",
                           help="Output directory")
    p_package.add_argument("--format", default="zip",
                           help="Package format (zip)")

    # skill publish
    p_publish = skill_subparsers.add_parser("publish", help="Publish a Skill to a layer")
    p_publish.add_argument("name", help="Skill name")
    p_publish.add_argument("--target", default="01_team",
                           help="Target layer (01_team/00_official)")
    p_publish.add_argument("--message", "-m", default="",
                           help="Publish message")

    # skill install
    p_install = skill_subparsers.add_parser("install", help="Install a Skill from source")
    p_install.add_argument("source", help="Source path, git URL, or package file")
    p_install.add_argument("--source-type", default="local",
                           help="Source type (local/git/registry)")
    p_install.add_argument("--layer", default="02_user",
                           help="Target layer")

    # skill uninstall
    p_uninstall = skill_subparsers.add_parser("uninstall", help="Uninstall a Skill")
    p_uninstall.add_argument("name", help="Skill name")

    # skill list
    p_list = skill_subparsers.add_parser("list", help="List installed Skills")
    p_list.add_argument("--category", "-c", default="",
                        help="Filter by category")
    p_list.add_argument("--software", "-s", default="",
                        help="Filter by software")
    p_list.add_argument("--source", default="",
                        help="Filter by layer")
    p_list.add_argument("--all", action="store_true",
                        help="Include disabled skills")

    # skill info
    p_info = skill_subparsers.add_parser("info", help="Show Skill details")
    p_info.add_argument("name", help="Skill name")

    # skill enable
    p_enable = skill_subparsers.add_parser("enable", help="Enable a Skill")
    p_enable.add_argument("name", help="Skill name")

    # skill disable
    p_disable = skill_subparsers.add_parser("disable", help="Disable a Skill")
    p_disable.add_argument("name", help="Skill name")

    # skill update
    p_update = skill_subparsers.add_parser("update", help="Update a Skill")
    p_update.add_argument("name", help="Skill name")

    # skill check-deps
    p_checkdeps = skill_subparsers.add_parser("check-deps", help="Check Skill dependencies")
    p_checkdeps.add_argument("name", nargs="?", default="",
                             help="Skill name (check all if omitted)")

    # ---- Parse ----
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "skill":
        if not args.subcommand:
            skill_parser.print_help()
            sys.exit(0)
        skill_cmd.dispatch(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
