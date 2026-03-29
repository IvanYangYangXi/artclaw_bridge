"""临时脚本: 从 Main_impl.h 移除静默模式按钮和创建Skill按钮"""
import re

filepath = 'Plugins/UEClawBridge/Source/UEClawBridge/Private/UEAgentDashboard_Main_impl.h'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到需要移除的代码块
result = []
i = 0
skip_until_bracket = False
bracket_depth = 0
removed_silent = False
removed_skill = False

while i < len(lines):
    line = lines[i]
    
    # 检测 SilentMedium 按钮开始
    if 'SilentMediumOff' in line and 'Text_Lambda' in line:
        # 向前找到 SNew(SButton) 开始的行
        # 从当前行回溯找到 + SHorizontalBox::Slot()
        start = i
        while start > 0 and '+ SHorizontalBox::Slot()' not in lines[start]:
            start -= 1
        # 从 start 跳过整个 [...] 块
        depth = 0
        j = start
        while j < len(lines):
            depth += lines[j].count('[') - lines[j].count(']')
            if depth <= 0 and j > start:
                break
            j += 1
        # 跳过这些行
        i = j + 1
        removed_silent = True
        continue
    
    # 检测 SilentHigh 按钮开始
    if 'SilentHighOff' in line and 'Text_Lambda' in line:
        start = i
        while start > 0 and '+ SHorizontalBox::Slot()' not in lines[start]:
            start -= 1
        depth = 0
        j = start
        while j < len(lines):
            depth += lines[j].count('[') - lines[j].count(']')
            if depth <= 0 and j > start:
                break
            j += 1
        i = j + 1
        removed_silent = True
        continue
    
    # 检测 CreateSkill 按钮开始
    if 'CreateSkillBtn' in line and 'Text_Lambda' in line:
        start = i
        while start > 0 and ('+ SHorizontalBox::Slot()' not in lines[start] or 'AutoWidth' not in lines[start]):
            start -= 1
        # 确保我们找到了正确的起始行
        while start > 0 and '+ SHorizontalBox::Slot()' not in lines[start]:
            start -= 1
        depth = 0
        j = start
        while j < len(lines):
            depth += lines[j].count('[') - lines[j].count(']')
            if depth <= 0 and j > start:
                break
            j += 1
        i = j + 1
        removed_skill = True
        continue
    
    result.append(line)
    i += 1

print(f"Removed SilentMedium/SilentHigh: {removed_silent}")
print(f"Removed CreateSkill: {removed_skill}")

with open(filepath, 'w', encoding='utf-8', newline='') as f:
    f.writelines(result)

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Remaining SilentMediumOff: {content.count('SilentMediumOff')}")
print(f"Remaining SilentHighOff: {content.count('SilentHighOff')}")
print(f"Remaining CreateSkillBtn: {content.count('CreateSkillBtn')}")
print("Done")
