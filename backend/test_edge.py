import sys
sys.path.insert(0, '.')
from app import mirror_coord, compute_image_and_path, unfold_to_real
import math

EPS = 1e-8

def test_edge_cases():
    print("=" * 70)
    print("深度测试：各种极端边界场景")
    print("=" * 70)

    # ========== 测试1：点精确在墙壁上 ==========
    print("\n🔬 测试1：声源精确在墙上 (Sx=0)")
    room = (10.0, 8.0, 6.0)
    Lx, Ly, Lz = room
    source = (0.0, 3.0, 2.0)
    receiver = (5.0, 4.0, 3.0)

    for nx in range(-2, 3):
        for ny in range(-2, 3):
            for nz in range(-2, 3):
                order = abs(nx) + abs(ny) + abs(nz)
                if order == 0 or order > 2:
                    continue
                try:
                    image_pt, path_pts, path_len = compute_image_and_path(
                        source, receiver, room, (nx, ny, nz)
                    )
                    # 检查路径点数
                    expected = order + 2
                    if len(path_pts) != expected:
                        print(f"  ⚠️  n=({nx},{ny},{nz}) order={order}: 点数={len(path_pts)}, 预期={expected}")
                        print(f"     路径点: {[(round(p[0],4),round(p[1],4),round(p[2],4)) for p in path_pts]}")
                except Exception as e:
                    print(f"  💥 n=({nx},{ny},{nz}): {e}")

    # ========== 测试2：两点都在同一面墙上，看反射路径是否退化 ==========
    print("\n🔬 测试2：两点都在左墙上 (Sx=Rx=0)")
    source = (0.0, 2.0, 1.0)
    receiver = (0.0, 5.0, 4.0)

    issues = 0
    for n in [(1,0,0), (-1,0,0), (1,1,0), (0,1,0)]:
        order = sum(abs(x) for x in n)
        try:
            image_pt, path_pts, path_len = compute_image_and_path(source, receiver, room, n)
            print(f"  n={n} order={order}: len={path_len:.4f}, pts={len(path_pts)}")
            print(f"    镜像点: ({image_pt[0]:.3f}, {image_pt[1]:.3f}, {image_pt[2]:.3f})")
            print(f"    路径: {[(round(p[0],4),round(p[1],4),round(p[2],4)) for p in path_pts]}")

            # 当 Sx=Rx=0 时，对 x 方向的反射，理论上路径应该...
            # 比如 n=(1,0,0)：一次x正反射，路径是 S -> 右墙 -> R？不，不对。
            # S 在 x=0 墙上，镜像点 I 在 x=2*Lx - 0 = 20。直线 I->R 穿过 x=0 吗？
            # R 也在 x=0，所以 I->R 从 (20,2,1) 到 (0,5,4)，会在 x=0 处和R重合。
            # 所以路径点应该是 2 个？或者 3 个但其中起点和反射点重合？
        except Exception as e:
            print(f"  💥 n={n}: {e}")
            issues += 1

    # ========== 测试3：路径擦过棱边（同时到达两面墙的交线） ==========
    print("\n🔬 测试3：路径擦过棱边（对称位置）")
    source = (1.0, 1.0, 3.0)
    receiver = (9.0, 7.0, 3.0)
    # 对称，看看会不会有路径点恰好落在 (10,8) 这样的棱上

    for n in [(-1,-1,0), (1,1,0)]:
        try:
            image_pt, path_pts, path_len = compute_image_and_path(source, receiver, room, n)
            print(f"  n={n}: pts={len(path_pts)}, len={path_len:.4f}")
            for p in path_pts:
                on_edge = (abs(p[0]) < 1e-6 or abs(p[0] - Lx) < 1e-6) and \
                          (abs(p[1]) < 1e-6 or abs(p[1] - Ly) < 1e-6)
                if on_edge:
                    print(f"    ⚠️  路径点在棱上: ({p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f})")
        except Exception as e:
            print(f"  💥 n={n}: {e}")

    # ========== 测试4：极小房间尺寸 ==========
    print("\n🔬 测试4：极小房间 (1x1x1)")
    small_room = (1.0, 1.0, 1.0)
    source = (0.1, 0.1, 0.1)
    receiver = (0.9, 0.9, 0.9)

    issues = 0
    total = 0
    for nx in range(-3, 4):
        for ny in range(-3, 4):
            for nz in range(-3, 4):
                order = abs(nx) + abs(ny) + abs(nz)
                if order == 0 or order > 3:
                    continue
                total += 1
                try:
                    image_pt, path_pts, path_len = compute_image_and_path(
                        source, receiver, small_room, (nx, ny, nz)
                    )
                    if path_len <= 0:
                        print(f"  ❌ n=({nx},{ny},{nz}): path_len={path_len}")
                        issues += 1
                    for p in path_pts:
                        if any(v < -1e-6 or v > 1 + 1e-6 for v in p):
                            print(f"  ❌ n=({nx},{ny},{nz}): 点越界 {p}")
                            issues += 1
                            break
                except Exception as e:
                    print(f"  💥 n=({nx},{ny},{nz}): {e}")
                    issues += 1
    print(f"  共 {total} 条路径，{issues} 个问题")

    # ========== 测试5：unfold_to_real 在边界上的行为 ==========
    print("\n🔬 测试5：unfold_to_real 边界数值测试")
    L = 10.0
    test_vals = [0.0, -1e-16, 1e-16, 10.0, 10.0 - 1e-15, 10.0 + 1e-15,
                 20.0, -1e-10, 2*L + 1e-10, -2*L - 1e-10]
    for v in test_vals:
        r = unfold_to_real(v, L)
        if r < -1e-10 or r > L + 1e-10:
            print(f"  ❌ unfold({v}) = {r} 越界!")
        else:
            print(f"  ✅ unfold({v:+.4e}) = {r:.10f}")

    # ========== 测试6：镜像点计算 ==========
    print("\n🔬 测试6：mirror_coord 边界测试")
    L = 10.0
    s = 0.0
    for n in range(-3, 4):
        r = mirror_coord(s, L, n)
        print(f"  s=0, n={n:+d}: {r:.4f}")

    s = 10.0
    for n in range(-3, 4):
        r = mirror_coord(s, L, n)
        print(f"  s=10, n={n:+d}: {r:.4f}")

if __name__ == '__main__':
    test_edge_cases()
