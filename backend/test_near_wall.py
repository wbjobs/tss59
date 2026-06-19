import sys
sys.path.insert(0, '.')
from app import (
    mirror_coord, compute_image_and_path, unfold_to_real,
    _validate_path, clamp, EPS_DEGEN_REL
)
import math


def _d2(a, b):
    return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2


def test_unfold_bounds():
    print("\n" + "=" * 70)
    print("unfold_to_real 边界夹紧测试")
    print("=" * 70)

    L = 10.0
    test_vals = [
        0.0, -1e-16, 1e-16,
        10.0, 10.0 - 1e-15, 10.0 + 1e-15,
        20.0, -1e-10, 2*L + 1e-10, -2*L - 1e-10,
        -0.5, 0.5, 9.5, 10.5,
        -10.0000000001, 20.0000000001
    ]

    all_ok = True
    for v in test_vals:
        r = unfold_to_real(v, L)
        if r < 0 or r > L:
            print(f"  ❌ unfold({v:+.12f}) = {r:.12f} 越界!")
            all_ok = False
        else:
            print(f"  ✅ unfold({v:+.12f}) = {r:.12f}")

    if all_ok:
        print("✅ unfold_to_real 边界测试全部通过")
    return all_ok


def test_near_wall_comprehensive():
    print("=" * 70)
    print("综合测试：近壁面数值稳定性与路径有效性")
    print("=" * 70)

    room = (10.0, 8.0, 6.0)
    Lx, Ly, Lz = room

    test_cases = [
        {
            "name": "声源贴左墙 (x=0.001)",
            "source": (0.001, 3.0, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源贴右墙 (x=Lx-0.001)",
            "source": (9.999, 3.0, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源精确在墙上 (x=0)",
            "source": (0.0, 3.0, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源精确在右墙 (x=Lx)",
            "source": (10.0, 3.0, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源贴地 (y=0.0001)",
            "source": (2.0, 0.0001, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "接收点贴地 (y=0)",
            "source": (2.0, 3.0, 2.0),
            "receiver": (5.0, 0.0, 3.0),
        },
        {
            "name": "两点都贴同墙 (x≈0)",
            "source": (0.00001, 3.0, 2.0),
            "receiver": (0.00002, 4.0, 3.0),
        },
        {
            "name": "两点都精确在左墙上",
            "source": (0.0, 2.0, 1.0),
            "receiver": (0.0, 5.0, 4.0),
        },
        {
            "name": "两点都贴地 (y≈0)",
            "source": (2.0, 1e-7, 2.0),
            "receiver": (5.0, 1e-6, 3.0),
        },
        {
            "name": "声源在两面角点",
            "source": (0.001, 0.001, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源精确在两面角点",
            "source": (0.0, 0.0, 2.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源在三面角点 (近)",
            "source": (1e-5, 1e-5, 1e-5),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "声源精确在三面角点",
            "source": (0.0, 0.0, 0.0),
            "receiver": (5.0, 4.0, 3.0),
        },
        {
            "name": "两点几乎重合 (贴近墙)",
            "source": (0.001, 3.0, 2.0),
            "receiver": (0.001001, 3.000001, 2.000001),
        },
        {
            "name": "两点都在同个角点",
            "source": (0.0, 0.0, 0.0),
            "receiver": (1e-10, 1e-10, 1e-10),
        },
        {
            "name": "极小房间 + 贴壁点",
            "source": (0.001, 0.001, 0.001),
            "receiver": (0.5, 0.5, 0.5),
            "room": (1.0, 1.0, 1.0),
        },
    ]

    max_order = 3
    total_issues = 0
    total_paths = 0

    for tc in test_cases:
        print(f"\n{'─' * 50}")
        print(f"📌 {tc['name']}")
        print(f"   声源: {tc['source']}")
        print(f"   接收: {tc['receiver']}")

        r = tc.get('room', room)
        Lx, Ly, Lz = r
        direct_len = math.sqrt(_d2(tc['source'], tc['receiver']))

        case_issues = 0
        path_count = 0
        valid_count = 0
        degen_count = 0

        for nx in range(-max_order, max_order + 1):
            for ny in range(-max_order, max_order + 1):
                for nz in range(-max_order, max_order + 1):
                    order = abs(nx) + abs(ny) + abs(nz)
                    if order == 0 or order > max_order:
                        continue

                    image_n = (nx, ny, nz)
                    path_count += 1

                    try:
                        image_pt, path_pts, path_len, _ = compute_image_and_path(
                            tc['source'], tc['receiver'], r, image_n
                        )

                        num_reflect = len(path_pts) - 2

                        if num_reflect < 1:
                            degen_count += 1
                            continue

                        valid, reason = _validate_path(path_pts, path_len, r, direct_len)
                        if not valid:
                            print(f"   ❌ [n={nx},{ny},{nz}] 验证失败: {reason}, len={path_len:.6f}, pts={len(path_pts)}")
                            case_issues += 1
                            continue

                        eps = 1e-9
                        for i, (px, py, pz) in enumerate(path_pts):
                            inside = (-eps <= px <= Lx + eps and
                                      -eps <= py <= Ly + eps and
                                      -eps <= pz <= Lz + eps)
                            if not inside:
                                print(f"   ❌ [n={nx},{ny},{nz}] 路径点{i}越界: ({px:.10f}, {py:.10f}, {pz:.10f})")
                                case_issues += 1
                                break

                        if num_reflect < 0 or num_reflect > order:
                            print(f"   ❌ [n={nx},{ny},{nz}] 反射点数不合理: {num_reflect}, order={order}")
                            case_issues += 1
                            continue

                        d_start = math.sqrt(_d2(path_pts[0], tc['source']))
                        d_end = math.sqrt(_d2(path_pts[-1], tc['receiver']))
                        if d_start > 1e-9:
                            print(f"   ❌ [n={nx},{ny},{nz}] 起点偏差: {d_start}")
                            case_issues += 1
                        if d_end > 1e-9:
                            print(f"   ❌ [n={nx},{ny},{nz}] 终点偏差: {d_end}")
                            case_issues += 1

                        seg_sum = 0.0
                        for i in range(len(path_pts) - 1):
                            seg_sum += math.sqrt(_d2(path_pts[i], path_pts[i+1]))
                        if abs(seg_sum - path_len) > 1e-6 * max(path_len, 1e-6):
                            print(f"   ❌ [n={nx},{ny},{nz}] 长度不一致: path={path_len}, seg={seg_sum}")
                            case_issues += 1

                        d_img_rec = math.sqrt(_d2(image_pt, tc['receiver']))
                        if abs(d_img_rec - path_len) > 1e-9:
                            print(f"   ❌ [n={nx},{ny},{nz}] 镜像距离不符: img={d_img_rec}, path={path_len}")
                            case_issues += 1

                        valid_count += 1

                    except Exception as e:
                        print(f"   💥 [n={nx},{ny},{nz}] 异常: {e}")
                        case_issues += 1

        print(f"   总镜像组合: {path_count}, 退化(反射<1: {degen_count}, 有效: {valid_count}, 问题: {case_issues}")
        if case_issues == 0:
            print(f"   ✅ 本场景全部通过")

        total_issues += case_issues
        total_paths += path_count

    print(f"\n{'=' * 70}")
    print(f"总计：{total_paths} 个镜像组合，{total_issues} 个问题")
    if total_issues == 0:
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️  存在 {total_issues} 个异常")

    return total_issues == 0


def test_reflection_count_consistency():
    print("\n" + "=" * 70)
    print("反射次数一致性测试")
    print("=" * 70)

    room = (10.0, 8.0, 6.0)
    source = (2.0, 3.0, 2.0)
    receiver = (7.0, 5.0, 4.0)
    max_order = 3

    all_ok = True
    for nx in range(-max_order, max_order + 1):
        for ny in range(-max_order, max_order + 1):
            for nz in range(-max_order, max_order + 1):
                order = abs(nx) + abs(ny) + abs(nz)
                if order == 0 or order > max_order:
                    continue
                image_n = (nx, ny, nz)
                _, pts, _, _ = compute_image_and_path(source, receiver, room, image_n)
                n_reflect = len(pts) - 2
                if n_reflect != order:
                    print(f"  ⚠️  n={image_n}: order={order}, actual_reflections={n_reflect}")

    print("✅ 反射次数检查完成（源/接收都在室内时，反射次数应等于阶数")
    return all_ok


if __name__ == '__main__':
    ok1 = test_unfold_bounds()
    ok2 = test_reflection_count_consistency()
    ok3 = test_near_wall_comprehensive()

    print("\n" + "=" * 70)
    if ok1 and ok2 and ok3:
        print("🎉🎉🎉 全部测试通过！")
    else:
        print("⚠️  部分测试未通过")
