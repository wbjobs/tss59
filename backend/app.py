import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
import math

app = Flask(__name__)
CORS(app)

SOUND_SPEED = 343.0


def mirror_coord(s, L, n):
    result = s
    if n > 0:
        faces = ['pos', 'neg'] * ((n + 1) // 2)
        for i in range(n):
            if faces[i] == 'pos':
                result = 2 * L - result
            else:
                result = -result
    elif n < 0:
        faces = ['neg', 'pos'] * ((-n + 1) // 2)
        for i in range(-n):
            if faces[i] == 'neg':
                result = -result
            else:
                result = 2 * L - result
    return result


def unfold_to_real(x_unfolded, L):
    if L <= 0:
        return 0.0
    period = 2 * L
    x_mod = x_unfolded % period
    if x_mod < 0:
        x_mod += period
    if x_mod <= L:
        return x_mod
    else:
        return 2 * L - x_mod


def compute_image_and_path(source, receiver, room_dims, image_n):
    Lx, Ly, Lz = room_dims
    nx, ny, nz = image_n
    Sx, Sy, Sz = source
    Rx, Ry, Rz = receiver

    Ix = mirror_coord(Sx, Lx, nx)
    Iy = mirror_coord(Sy, Ly, ny)
    Iz = mirror_coord(Sz, Lz, nz)
    I = np.array([Ix, Iy, Iz], dtype=np.float64)
    R = np.array([Rx, Ry, Rz], dtype=np.float64)

    path_length = np.linalg.norm(R - I)

    dir_vec = R - I
    crossings = []

    L_list = [Lx, Ly, Lz]

    for axis_idx in range(3):
        Li = L_list[axis_idx]
        if Li <= 0:
            continue
        if abs(dir_vec[axis_idx]) < 1e-15:
            continue
        s_val = I[axis_idx]
        r_val = R[axis_idx]
        min_val = min(s_val, r_val)
        max_val = max(s_val, r_val)

        k_min = int(math.floor(min_val / Li))
        k_max = int(math.ceil(max_val / Li))

        for k in range(k_min, k_max + 1):
            plane = k * Li
            t = (plane - s_val) / dir_vec[axis_idx]
            if 1e-12 < t < 1.0 - 1e-12:
                point_on_line = I + t * dir_vec
                if abs(point_on_line[axis_idx] - plane) < 1e-10:
                    crossings.append((t, axis_idx))

    crossings.sort(key=lambda x: x[0])

    path_points = [(Sx, Sy, Sz)]

    for t, axis_idx in crossings:
        point_mirror = I + t * dir_vec
        px = unfold_to_real(point_mirror[0], Lx) if Lx > 0 else 0.0
        py = unfold_to_real(point_mirror[1], Ly) if Ly > 0 else 0.0
        pz = unfold_to_real(point_mirror[2], Lz) if Lz > 0 else 0.0
        path_points.append((float(px), float(py), float(pz)))

    path_points.append((Rx, Ry, Rz))

    image_point = (float(Ix), float(Iy), float(Iz))
    return image_point, path_points, float(path_length)


@app.route('/compute', methods=['POST'])
def compute():
    try:
        data = request.get_json()

        room = data['room']
        Lx = float(room['width'])
        Ly = float(room['height'])
        Lz = float(room['depth'])
        room_dims = (Lx, Ly, Lz)

        source = tuple(float(x) for x in data['source'])
        receiver = tuple(float(x) for x in data['receiver'])
        max_order = int(data.get('max_order', 3))

        Sx, Sy, Sz = source
        if not (0 <= Sx <= Lx and 0 <= Sy <= Ly and 0 <= Sz <= Lz):
            return jsonify({'error': '声源必须在房间内'}), 400

        Rx, Ry, Rz = receiver
        if not (0 <= Rx <= Lx and 0 <= Ry <= Ly and 0 <= Rz <= Lz):
            return jsonify({'error': '接收点必须在房间内'}), 400

        direct_length = math.sqrt(
            (Sx - Rx) ** 2 + (Sy - Ry) ** 2 + (Sz - Rz) ** 2
        )
        direct_time = direct_length / SOUND_SPEED

        paths = []

        direct_path = {
            'order': 0,
            'image_point': list(source),
            'path_points': [list(source), list(receiver)],
            'length': float(direct_length),
            'time': float(direct_time),
            'time_diff_ms': 0.0,
            'type': 'direct'
        }
        paths.append(direct_path)

        for nx in range(-max_order, max_order + 1):
            for ny in range(-max_order, max_order + 1):
                for nz in range(-max_order, max_order + 1):
                    order = abs(nx) + abs(ny) + abs(nz)
                    if order == 0 or order > max_order:
                        continue
                    image_point, path_points, path_length = compute_image_and_path(
                        source, receiver, room_dims, (nx, ny, nz)
                    )
                    travel_time = path_length / SOUND_SPEED
                    time_diff_ms = (travel_time - direct_time) * 1000.0

                    paths.append({
                        'order': order,
                        'image_n': [nx, ny, nz],
                        'image_point': list(image_point),
                        'path_points': [list(p) for p in path_points],
                        'length': float(path_length),
                        'time': float(travel_time),
                        'time_diff_ms': float(time_diff_ms),
                        'type': f'reflection_{order}'
                    })

        paths.sort(key=lambda p: p['time'])

        return jsonify({
            'sound_speed': SOUND_SPEED,
            'direct_time': float(direct_time),
            'paths': paths,
            'total_paths': len(paths)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
