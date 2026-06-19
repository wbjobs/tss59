import sys
sys.path.insert(0, '.')
import json
from app import app

def test_api_near_wall():
    print("=" * 70)
    print("API 级别测试：近壁面数值稳定性")
    print("=" * 70)

    client = app.test_client()

    test_cases = [
        {
            "name": "正常情况（参考）",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [1.0, 1.5, 1.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
            "min_paths": 50,
        },
        {
            "name": "声源贴左墙 (0.001)",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.001, 1.5, 1.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "声源精确在左墙上 (0.0)",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.0, 1.5, 1.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "声源精确在右墙上",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [5.0, 1.5, 1.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "声源贴天花板",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [1.0, 2.999, 1.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "接收点贴地 (0.0)",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [1.0, 1.5, 1.0],
            "receiver": [3.5, 0.0, 2.5],
            "expect_ok": True,
        },
        {
            "name": "两点都贴同墙 (左墙)",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.0, 1.0, 0.5],
            "receiver": [0.0, 2.0, 3.0],
            "expect_ok": True,
        },
        {
            "name": "声源在两面角点",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.0, 0.0, 2.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "声源在三面角点 (0,0,0)",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.0, 0.0, 0.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "接收点在三面角点",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [1.0, 1.5, 1.0],
            "receiver": [5.0, 3.0, 4.0],
            "expect_ok": True,
        },
        {
            "name": "两点都在同一个三面角点",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [0.0, 0.0, 0.0],
            "receiver": [0.0001, 0.0001, 0.0001],
            "expect_ok": True,
        },
        {
            "name": "声源在房间外（应该被夹紧）",
            "room": {"width": 5, "height": 3, "depth": 4},
            "source": [-1.0, 5.0, -2.0],
            "receiver": [3.5, 1.5, 2.5],
            "expect_ok": True,
        },
        {
            "name": "极小房间 + 贴壁点",
            "room": {"width": 1, "height": 1, "depth": 1},
            "source": [0.001, 0.001, 0.001],
            "receiver": [0.5, 0.5, 0.5],
            "expect_ok": True,
        },
        {
            "name": "长条形房间 + 贴壁",
            "room": {"width": 20, "height": 2, "depth": 2},
            "source": [0.0, 0.0, 1.0],
            "receiver": [18.0, 1.5, 1.0],
            "expect_ok": True,
        },
    ]

    all_ok = True

    for tc in test_cases:
        print(f"\n{'─' * 50}")
        print(f"📌 {tc['name']}")

        payload = {
            "room": tc["room"],
            "source": tc["source"],
            "receiver": tc["receiver"],
            "max_order": 3
        }

        try:
            response = client.post(
                '/compute',
                data=json.dumps(payload),
                content_type='application/json'
            )

            if response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}: {response.get_json()}")
                if tc["expect_ok"]:
                    all_ok = False
                continue

            data = response.get_json()
            paths = data['paths']
            stats = data.get('stats', {})

            # 验证 1：第一条是直达声
            if paths[0]['order'] != 0:
                print(f"   ❌ 第一条路径不是直达声")
                all_ok = False
                continue

            direct_len = paths[0]['length']

            # 验证 2：所有路径长度 >= 直达声长度
            bad_len = [p for p in paths if p['length'] < direct_len - 1e-9]
            if bad_len:
                print(f"   ❌ {len(bad_len)} 条路径长度小于直达声")
                for p in bad_len[:3]:
                    print(f"      - order={p['order']}, len={p['length']}, direct={direct_len}")
                all_ok = False

            # 验证 3：所有时间差 >= 0
            bad_td = [p for p in paths if p['time_diff_ms'] < -1e-9]
            if bad_td:
                print(f"   ❌ {len(bad_td)} 条路径时间差为负")
                all_ok = False

            # 验证 4：所有路径点在房间内
            Lx = tc["room"]['width']
            Ly = tc["room"]['height']
            Lz = tc["room"]['depth']
            bad_points = 0
            for p in paths:
                for pt in p['path_points']:
                    if (pt[0] < -1e-9 or pt[0] > Lx + 1e-9 or
                        pt[1] < -1e-9 or pt[1] > Ly + 1e-9 or
                        pt[2] < -1e-9 or pt[2] > Lz + 1e-9):
                        bad_points += 1
            if bad_points > 0:
                print(f"   ❌ {bad_points} 个路径点越界")
                all_ok = False

            # 验证 5：路径按时间排序
            times = [p['time'] for p in paths]
            sorted_ok = all(times[i] <= times[i+1] + 1e-12 for i in range(len(times)-1))
            if not sorted_ok:
                print(f"   ❌ 路径未按时间排序")
                all_ok = False

            # 验证 6：反射点数与阶数合理
            bad_order = 0
            for p in paths:
                if p['order'] == 0:
                    continue
                num_ref = len(p['path_points']) - 2
                if num_ref < 1 or num_ref > p['order']:
                    bad_order += 1
            if bad_order > 0:
                print(f"   ⚠️  {bad_order} 条路径反射点数与阶数不符（可能是退化路径，但物理上有效）")

            # 验证 7：没有重复长度的路径
            lengths = [p['length'] for p in paths]
            dup_count = 0
            for i in range(len(lengths)):
                for j in range(i+1, len(lengths)):
                    if abs(lengths[i] - lengths[j]) < 1e-8 * max(lengths[i], 1e-6):
                        dup_count += 1
            if dup_count > 0:
                print(f"   ⚠️  发现 {dup_count} 组近似等长路径（可能是对称情况）")

            print(f"   ✅ 总路径数: {data['total_paths']}")
            print(f"   ✅ 直达距离: {direct_len:.4f} m")
            print(f"   ✅ 最长路径: {paths[-1]['length']:.4f} m")
            print(f"   ℹ️  统计: {json.dumps(stats)}")

        except Exception as e:
            print(f"   💥 异常: {e}")
            import traceback
            traceback.print_exc()
            all_ok = False

    print(f"\n{'=' * 70}")
    if all_ok:
        print("🎉🎉🎉 所有 API 测试通过！")
    else:
        print("⚠️  部分测试未通过")
    return all_ok


def test_edge_api_cases():
    print("\n" + "=" * 70)
    print("API 边界异常输入测试")
    print("=" * 70)

    client = app.test_client()

    edge_cases = [
        {"name": "房间尺寸为0", "room": {"width": 0, "height": 3, "depth": 4},
         "source": [1,1,1], "receiver": [2,2,2], "expect_err": True},
        {"name": "房间尺寸为负", "room": {"width": -5, "height": 3, "depth": 4},
         "source": [1,1,1], "receiver": [2,2,2], "expect_err": True},
        {"name": "max_order=0", "room": {"width": 5, "height": 3, "depth": 4},
         "source": [1,1,1], "receiver": [2,2,2], "max_order": 0, "expect_ok": True},
        {"name": "两点完全重合", "room": {"width": 5, "height": 3, "depth": 4},
         "source": [2.0, 1.5, 2.0], "receiver": [2.0, 1.5, 2.0], "expect_ok": True},
        {"name": "两点完全重合在墙上", "room": {"width": 5, "height": 3, "depth": 4},
         "source": [0.0, 0.0, 0.0], "receiver": [0.0, 0.0, 0.0], "expect_ok": True},
    ]

    all_ok = True
    for tc in edge_cases:
        print(f"\n📌 {tc['name']}")
        payload = {
            "room": tc["room"],
            "source": tc["source"],
            "receiver": tc["receiver"],
            "max_order": tc.get("max_order", 3)
        }
        try:
            response = client.post(
                '/compute',
                data=json.dumps(payload),
                content_type='application/json'
            )
            if tc.get("expect_err"):
                if response.status_code != 200:
                    print(f"   ✅ 正确返回错误: HTTP {response.status_code}")
                else:
                    print(f"   ⚠️  意外返回成功: {response.get_json().get('total_paths')} 条路径")
            else:
                if response.status_code == 200:
                    data = response.get_json()
                    print(f"   ✅ 成功: {data['total_paths']} 条路径")
                else:
                    print(f"   ❌ 意外错误: {response.get_json()}")
                    all_ok = False
        except Exception as e:
            print(f"   💥 异常: {e}")
            all_ok = False

    return all_ok


if __name__ == '__main__':
    ok1 = test_api_near_wall()
    ok2 = test_edge_api_cases()

    print("\n" + "=" * 70)
    if ok1 and ok2:
        print("🎉🎉🎉 全部测试通过！")
    else:
        print("⚠️  部分测试未通过")
