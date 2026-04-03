import unreal

actors = unreal.EditorLevelLibrary.get_selected_level_actors()

if not actors:
    print("没有选中任何对象。")
else:
    print(f"选中了 {len(actors)} 个对象:\n")
    for i, actor in enumerate(actors, 1):
        print(f"--- 对象 {i} ---")
        print(f"名称 (Name): {actor.get_name()}")
        print(f"类 (Class): {actor.get_class().get_name()}")
        print(f"Label: {actor.get_actor_label()}")
        print(f"位置 (Location): {actor.get_actor_location()}")
        print(f"旋转 (Rotation): {actor.get_actor_rotation()}")
        print(f"缩放 (Scale3D): {actor.get_actor_scale3d()}")
        print()
