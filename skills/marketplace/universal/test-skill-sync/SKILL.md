---
name: test-skill-sync
description: >
  Test skill for verifying Skill management panel operations:
  install, update, publish, uninstall, version tracking, author display.
  This skill has no real functionality — it exists solely for testing.
metadata:
  artclaw:
    author: ArtClaw-Test
    software: universal
    category: testing
    version: 1.0.0
---

# Test Skill Sync

A dummy skill for testing the Skill management panel's install/update/publish/uninstall workflow.

## Purpose

- Verify install from source → runtime
- Verify version display in list
- Verify author display in list
- Verify publish (runtime → source with version bump)
- Verify update (source → runtime)
- Verify modified detection (runtime edited but not published)
- Verify uninstall

## Usage

This skill does nothing. It is a test fixture.
修改测试+1