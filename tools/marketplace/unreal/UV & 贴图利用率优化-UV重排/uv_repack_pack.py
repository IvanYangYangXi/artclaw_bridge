# Ref: docs/UEClawBridge/features/xatlas-integration/design.md#4.2
"""
MaxRects 装箱模块。
- Best Short Side Fit 策略（比 Best Area Fit 更接近正方形）
- 统一缩放：所有岛用同一 scale 保证纹理密度一致
- 二分搜索最大 scale
- 默认不旋转（避免法线问题）
"""
import math


def _split_free_rect(free_rect, placed_x, placed_y, placed_w, placed_h):
    """将 free_rect 减去已放置矩形，返回 0-2 个新 free rect。"""
    fx, fy, fw, fh = free_rect
    # 无交叉则原样返回
    if (placed_x >= fx + fw or placed_x + placed_w <= fx or
            placed_y >= fy + fh or placed_y + placed_h <= fy):
        return [free_rect]

    result = []
    # 左侧剩余
    if placed_x > fx:
        result.append((fx, fy, placed_x - fx, fh))
    # 右侧剩余
    if placed_x + placed_w < fx + fw:
        result.append((placed_x + placed_w, fy, fx + fw - (placed_x + placed_w), fh))
    # 上方剩余
    if placed_y > fy:
        result.append((fx, fy, fw, placed_y - fy))
    # 下方剩余
    if placed_y + placed_h < fy + fh:
        result.append((fx, placed_y + placed_h, fw, fy + fh - (placed_y + placed_h)))
    return result


def _prune_free_rects(free_rects):
    """移除被其他 free rect 完全包含的冗余矩形。"""
    pruned = []
    for i, r in enumerate(free_rects):
        dominated = False
        for j, other in enumerate(free_rects):
            if i == j:
                continue
            if (other[0] <= r[0] and other[1] <= r[1] and
                    other[0] + other[2] >= r[0] + r[2] and
                    other[1] + other[3] >= r[1] + r[3]):
                dominated = True
                break
        if not dominated:
            pruned.append(r)
    return pruned


def _maxrects_pack(rects, container_w, container_h, pad, allow_rotation=False):
    """
    MaxRects Best Short Side Fit。

    Args:
        rects: list[(w, h, id)]  已按面积降序排列
        container_w/h: 容器尺寸（通常 1.0, 1.0）
        pad: UV 岛间距

    Returns:
        list[(x, y, w, h, id, rotated)] 或 None（放不下）
    """
    free_rects = [(pad, pad, container_w - pad * 2, container_h - pad * 2)]
    placements = []

    for rw, rh, rid in rects:
        pw, ph = rw + pad, rh + pad
        best_score = (1e18, 1e18)
        best_pos = None
        best_fi = -1
        best_rot = False

        for fi, (fx, fy, fw, fh) in enumerate(free_rects):
            # 正常方向
            if pw <= fw and ph <= fh:
                score = (min(fw - pw, fh - ph), max(fw - pw, fh - ph))
                if score < best_score:
                    best_score, best_pos, best_fi, best_rot = score, (fx, fy), fi, False
            # 旋转 90°
            if allow_rotation and ph <= fw and pw <= fh:
                score = (min(fw - ph, fh - pw), max(fw - ph, fh - pw))
                if score < best_score:
                    best_score, best_pos, best_fi, best_rot = score, (fx, fy), fi, True

        if best_fi < 0:
            return None  # 放不下

        if best_rot:
            rw, rh = rh, rw

        px, py = best_pos
        placements.append((px, py, rw, rh, rid, best_rot))

        # 用已放置矩形切割所有 free rect（含 padding）
        new_free = []
        for fr in free_rects:
            new_free.extend(_split_free_rect(fr, px, py, rw + pad, rh + pad))
        free_rects = _prune_free_rects(new_free)

    return placements


def find_best_scale(island_list, padding, allow_rotation=False):
    """
    二分搜索最大统一缩放系数，返回 (placements, scale)。
    所有岛使用相同 scale，保证纹理密度一致。
    排布在 0-1 正方形中（最接近正方形的排布）。
    """
    lo, hi = 0.05, 500.0
    best_placements, best_scale = None, 0.0

    for _ in range(72):  # 精度约 1e-6
        mid = (lo + hi) / 2.0
        rects = sorted(
            [(isl['w'] * mid, isl['h'] * mid, isl['id']) for isl in island_list],
            key=lambda r: r[0] * r[1],
            reverse=True,
        )
        result = _maxrects_pack(rects, 1.0, 1.0, padding, allow_rotation)
        if result is not None:
            best_placements, best_scale = result, mid
            lo = mid
        else:
            hi = mid

    return best_placements, best_scale


def calc_utilization(placements):
    """计算装箱后 UV 面积利用率（0-1）。"""
    if not placements:
        return 0.0
    return sum(p[2] * p[3] for p in placements)
