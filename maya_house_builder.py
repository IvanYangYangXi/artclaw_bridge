# -*- coding: utf-8 -*-
"""
Maya 房子模型生成器
在 Maya 中运行此脚本创建简单的房子模型
"""

import maya.cmds as cmds

def create_house():
    """创建简单的房子模型"""
    
    # 清理场景
    cmds.file(new=True, force=True)
    
    # 创建房子组
    house_grp = cmds.group(em=True, n='House_GRP')
    
    # 参数
    width = 10
    depth = 8
    height = 6
    wall_thickness = 0.3
    
    # 1. 创建地板
    floor = cmds.polyCube(w=width, h=0.2, d=depth, n='Floor')[0]
    cmds.move(0, 0, 0, floor)
    cmds.parent(floor, house_grp)
    
    # 2. 创建四面墙
    # 后墙
    back_wall = cmds.polyCube(w=width, h=height, d=wall_thickness, n='Back_Wall')[0]
    cmds.move(0, height/2, -depth/2 + wall_thickness/2, back_wall)
    cmds.parent(back_wall, house_grp)
    
    # 前墙
    front_wall = cmds.polyCube(w=width, h=height, d=wall_thickness, n='Front_Wall')[0]
    cmds.move(0, height/2, depth/2 - wall_thickness/2, front_wall)
    cmds.parent(front_wall, house_grp)
    
    # 左墙
    left_wall = cmds.polyCube(w=wall_thickness, h=height, d=depth - wall_thickness*2, n='Left_Wall')[0]
    cmds.move(-width/2 + wall_thickness/2, height/2, 0, left_wall)
    cmds.parent(left_wall, house_grp)
    
    # 右墙
    right_wall = cmds.polyCube(w=wall_thickness, h=height, d=depth - wall_thickness*2, n='Right_Wall')[0]
    cmds.move(width/2 - wall_thickness/2, height/2, 0, right_wall)
    cmds.parent(right_wall, house_grp)
    
    # 3. 创建屋顶（三角屋顶）
    roof_height = 3
    roof = cmds.polyCone(r=width/1.5, h=roof_height, n='Roof')[0]
    cmds.move(0, height + roof_height/2, 0, roof)
    cmds.scale(1, 1, depth/width, roof)
    cmds.parent(roof, house_grp)
    
    # 4. 创建门
    door = cmds.polyCube(w=1.5, h=3, d=0.2, n='Door')[0]
    cmds.move(0, 1.5, depth/2 - 0.1, door)
    cmds.parent(door, house_grp)
    
    # 5. 创建窗户（左右各一个）
    window_l = cmds.polyCube(w=1.2, h=1.2, d=0.2, n='Window_L')[0]
    cmds.move(-2, 3.5, depth/2 - 0.1, window_l)
    cmds.parent(window_l, house_grp)
    
    window_r = cmds.polyCube(w=1.2, h=1.2, d=0.2, n='Window_R')[0]
    cmds.move(2, 3.5, depth/2 - 0.1, window_r)
    cmds.parent(window_r, house_grp)
    
    # 应用简单材质
    # 地板 - 木质色
    floor_mat = cmds.shadingNode('lambert', asShader=True, n='Floor_MAT')
    cmds.setAttr(floor_mat + '.color', 0.6, 0.4, 0.2)
    cmds.sets(floor, e=True, forceElement=floor_mat + 'SG')
    
    # 墙 - 白色
    wall_mat = cmds.shadingNode('lambert', asShader=True, n='Wall_MAT')
    cmds.setAttr(wall_mat + '.color', 0.9, 0.9, 0.9)
    for wall in [back_wall, front_wall, left_wall, right_wall]:
        cmds.sets(wall, e=True, forceElement=wall_mat + 'SG')
    
    # 屋顶 - 红色
    roof_mat = cmds.shadingNode('lambert', asShader=True, n='Roof_MAT')
    cmds.setAttr(roof_mat + '.color', 0.8, 0.2, 0.2)
    cmds.sets(roof, e=True, forceElement=roof_mat + 'SG')
    
    # 门 - 深棕色
    door_mat = cmds.shadingNode('lambert', asShader=True, n='Door_MAT')
    cmds.setAttr(door_mat + '.color', 0.4, 0.25, 0.1)
    cmds.sets(door, e=True, forceElement=door_mat + 'SG')
    
    # 窗户 - 浅蓝色
    window_mat = cmds.shadingNode('lambert', asShader=True, n='Window_MAT')
    cmds.setAttr(window_mat + '.color', 0.6, 0.8, 0.9)
    for win in [window_l, window_r]:
        cmds.sets(win, e=True, forceElement=window_mat + 'SG')
    
    # 调整视图
    cmds.viewFit()
    
    print('===== 房子模型创建完成！=====')
    print('包含：地板、四面墙、三角屋顶、门、两个窗户')
    print('所有部件已分组到 House_GRP')
    
    return house_grp

# 执行
if __name__ == '__main__':
    create_house()
