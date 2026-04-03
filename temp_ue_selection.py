import unreal

selected = unreal.EditorLevelLibrary.get_selected_level_actors()

if not selected:
    print('当前没有选中的对象')
else:
    print(f'选中对象数量：{len(selected)}\n')
    for actor in selected:
        name = actor.get_name()
        class_name = actor.get_class().get_name()
        label = actor.get_actor_label()
        
        transform = actor.get_actor_transform()
        location = transform.translation
        rotation = transform.rotation
        scale = transform.scale3d
        
        print(f'名称：{name}')
        print(f'类别：{class_name}')
        print(f'Label: {label}')
        print(f'位置：X={location.x:.2f}, Y={location.y:.2f}, Z={location.z:.2f}')
        print(f'旋转：Pitch={rotation.pitch:.2f}°, Yaw={rotation.yaw:.2f}°, Roll={rotation.roll:.2f}°')
        print(f'缩放：X={scale.x:.3f}, Y={scale.y:.3f}, Z={scale.z:.3f}')
        print('-' * 50)
