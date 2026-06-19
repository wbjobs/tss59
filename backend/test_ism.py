import sys
sys.path.insert(0, '.')
from app import mirror_coord, compute_image_and_path, unfold_to_real
import math

def test_mirror_coord():
    print("=== 测试镜像坐标计算 ===")
    
    L = 10.0
    s = 3.0
    
    tests = [
        (0, 3.0, "0次反射"),
        (1, 17.0, "正方向1次(x=L)"),
        (-1, -3.0, "负方向1次(x=0)"),
        (2, -17.0, "正方向2次"),
        (-2, 23.0, "负方向2次"),
    ]
    
    all_ok = True
    for n, expected, desc in tests:
        result = mirror_coord(s, L, n)
        ok = abs(result - expected) < 1e-10
        status = "✅" if ok else "❌"
        if not ok: all_ok = False
        print(f"{status} {desc}: n={n}, expected={expected}, got={result}")
    
    return all_ok

def test_unfold_to_real():
    print("\n=== 测试展开坐标映射回真实房间 ===")
    L = 10.0
    tests = [
        (3.0, 3.0),
        (17.0, 3.0),
        (-3.0, 3.0),
        (13.0, 7.0),
        (-7.0, 7.0),
        (23.0, 3.0),
        (-17.0, 3.0),
    ]
    all_ok = True
    for unfolded, expected in tests:
        result = unfold_to_real(unfolded, L)
        ok = abs(result - expected) < 1e-10
        status = "✅" if ok else "❌"
        if not ok: all_ok = False
        print(f"{status} unfolded={unfolded}, expected={expected}, got={result}")
    return all_ok

def test_path_computation():
    print("\n=== 测试路径计算 ===")
    room = (10.0, 8.0, 6.0)
    source = (2.0, 3.0, 1.0)
    receiver = (7.0, 5.0, 4.0)
    
    print(f"房间: {room}, 声源: {source}, 接收: {receiver}")
    
    direct_dist = math.sqrt(sum((s-r)**2 for s,r in zip(source, receiver)))
    print(f"直达距离: {direct_dist:.4f}")
    
    test_cases = [
        ((0,0,0), "直达(应该是镜像点=声源)"),
        ((1,0,0), "1次x正反射"),
        ((-1,0,0), "1次x负反射"),
        ((0,1,0), "1次y正反射"),
        ((0,0,1), "1次z正反射"),
        ((1,1,0), "2次反射x正,y正"),
        ((1,-1,1), "3次反射"),
    ]
    
    all_ok = True
    for image_n, desc in test_cases:
        image_pt, path_pts, path_len = compute_image_and_path(source, receiver, room, image_n)
        order = sum(abs(x) for x in image_n)
        
        print(f"\n{desc} (n={image_n}, order={order}):")
        print(f"  镜像点: {image_pt}")
        print(f"  路径点数: {len(path_pts)} (应为 {order+2})")
        print(f"  路径点: {[(round(x,2), round(y,2), round(z,2)) for x,y,z in path_pts]}")
        print(f"  路径长度: {path_len:.4f}")
        
        expected_num_points = order + 2
        if len(path_pts) != expected_num_points:
            print(f"  ❌ 路径点数错误! 应得 {expected_num_points}")
            all_ok = False
        else:
            print(f"  ✅ 路径点数正确")
        
        if order == 0:
            if abs(path_len - direct_dist) > 1e-8:
                print(f"  ❌ 直达距离错误")
                all_ok = False
            else:
                print(f"  ✅ 直达距离正确")
        
        start_ok = all(abs(a-b) < 1e-8 for a,b in zip(path_pts[0], source))
        end_ok = all(abs(a-b) < 1e-8 for a,b in zip(path_pts[-1], receiver))
        if start_ok and end_ok:
            print(f"  ✅ 路径首尾正确")
        else:
            print(f"  ❌ 路径首尾错误")
            all_ok = False
    
    return all_ok

if __name__ == '__main__':
    ok1 = test_mirror_coord()
    ok2 = test_unfold_to_real()
    ok3 = test_path_computation()
    
    print("\n" + "="*50)
    if ok1 and ok2 and ok3:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败!")
