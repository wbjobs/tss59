from flask import Flask, request, jsonify
from flask_cors import CORS
import math

app = Flask(__name__)
CORS(app)

SOUND_SPEED = 343.0

EPS_T = 1e-10
EPS_MERGE = 1e-9
EPS_DEGEN_REL = 1e-8
EPS_BOUNDS = 1e-9


def mirror_coord(s, L, n):
    result = float(s)
    Lf = float(L)
    if n > 0:
        faces = ['pos', 'neg'] * ((n + 1) // 2)
        for i in range(n):
            if faces[i] == 'pos':
                result = 2.0 * Lf - result
            else:
                result = -result
    elif n < 0:
        faces = ['neg', 'pos'] * ((-n + 1) // 2)
        for i in range(-n):
            if faces[i] == 'neg':
                result = -result
            else:
                result = 2.0 * Lf - result
    return result


def clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def unfold_to_real(x_unfolded, L):
    if L <= 0:
        return 0.0
    Lf = float(L)
    x = float(x_unfolded)
    period = 2.0 * Lf
    x_mod = x % period
    if x_mod < 0:
        x_mod += period

    if x_mod <= Lf:
        result = x_mod
    else:
        result = 2.0 * Lf - x_mod

    return clamp(result, 0.0, Lf)


def _dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


def _dist(a, b):
    return math.sqrt(_dist2(a, b))


def compute_image_and_path(source, receiver, room_dims, image_n):
    Lx, Ly, Lz = room_dims
    nx, ny, nz = image_n
    Sx, Sy, Sz = source
    Rx, Ry, Rz = receiver

    Ix = mirror_coord(Sx, Lx, nx)
    Iy = mirror_coord(Sy, Ly, ny)
    Iz = mirror_coord(Sz, Lz, nz)
    I = (Ix, Iy, Iz)

    dx = Rx - Ix
    dy = Ry - Iy
    dz = Rz - Iz
    path_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    if path_length < 1e-15:
        S = (Sx, Sy, Sz)
        R = (Rx, Ry, Rz)
        image_point = (float(Ix), float(Iy), float(Iz))
        return image_point, [S, R], 0.0, []

    crossings = []
    L_list = [Lx, Ly, Lz]
    dir_vec = (dx, dy, dz)

    for axis_idx in range(3):
        Li = L_list[axis_idx]
        if Li <= 0:
            continue
        dir_val = dir_vec[axis_idx]
        if abs(dir_val) < 1e-15:
            continue
        s_val = I[axis_idx]
        r_val = s_val + dir_val
        min_val = min(s_val, r_val)
        max_val = max(s_val, r_val)

        k_min = int(math.floor(min_val / Li))
        k_max = int(math.ceil(max_val / Li))

        for k in range(k_min, k_max + 1):
            plane = k * Li
            t = (plane - s_val) / dir_val
            if EPS_T < t < 1.0 - EPS_T:
                pt = (Ix + t * dx, Iy + t * dy, Iz + t * dz)
                crossings.append((t, axis_idx, k, pt))

    crossings.sort(key=lambda x: x[0])

    merged = []
    for t, axis_idx, k, pt in crossings:
        if merged:
            prev_t, prev_axis, prev_k, prev_pt = merged[-1]
            if abs(t - prev_t) < EPS_MERGE:
                if _dist2(pt, prev_pt) < EPS_MERGE * EPS_MERGE:
                    continue
        merged.append((t, axis_idx, k, pt))

    min_dim = min(Lx, Ly, Lz)
    eps_degen = EPS_DEGEN_REL * min_dim
    eps_degen2 = eps_degen * eps_degen

    S = (Sx, Sy, Sz)
    R = (Rx, Ry, Rz)
    path_points = [S]
    reflection_faces = []

    face_names = ['x_neg', 'x_pos', 'y_neg', 'y_pos', 'z_neg', 'z_pos']

    for t, axis_idx, k, pt_mirror in merged:
        px = clamp(unfold_to_real(pt_mirror[0], Lx), 0.0, Lx)
        py = clamp(unfold_to_real(pt_mirror[1], Ly), 0.0, Ly)
        pz = clamp(unfold_to_real(pt_mirror[2], Lz), 0.0, Lz)
        pt = (px, py, pz)

        last = path_points[-1]
        if _dist2(pt, last) < eps_degen2:
            continue

        Li = L_list[axis_idx]
        if k % 2 == 0:
            face_idx = axis_idx * 2
        else:
            face_idx = axis_idx * 2 + 1
        face_name = face_names[face_idx]
        reflection_faces.append(face_name)

        path_points.append(pt)

    if _dist2(R, path_points[-1]) < eps_degen2:
        path_points[-1] = R
    else:
        path_points.append(R)

    if len(path_points) < 2:
        path_points = [S, R]

    image_point = (float(Ix), float(Iy), float(Iz))
    return image_point, path_points, float(path_length), reflection_faces


def _is_inside_room(point, room_dims, eps=EPS_BOUNDS):
    px, py, pz = point
    Lx, Ly, Lz = room_dims
    return (-eps <= px <= Lx + eps and
            -eps <= py <= Ly + eps and
            -eps <= pz <= Lz + eps)


def _path_signature(path_points, eps=1e-6):
    key_parts = []
    for p in path_points:
        key_parts.append(f"({round(p[0]/eps):d},{round(p[1]/eps):d},{round(p[2]/eps):d})")
    return "|".join(key_parts)


def _validate_path(path_points, path_length, room_dims, direct_length):
    Lx, Ly, Lz = room_dims
    min_dim = min(Lx, Ly, Lz)
    eps_len = EPS_DEGEN_REL * min_dim

    if path_length < 0:
        return False, "negative_length"

    if path_length < direct_length - eps_len:
        return False, "shorter_than_direct"

    if len(path_points) < 2:
        return False, "too_few_points"

    for pt in path_points:
        if not _is_inside_room(pt, room_dims, EPS_BOUNDS):
            return False, "point_outside_room"

    seg_len = 0.0
    for i in range(len(path_points) - 1):
        seg_len += _dist(path_points[i], path_points[i + 1])

    rel_err = abs(seg_len - path_length) / max(path_length, 1e-6)
    if rel_err > 0.01:
        return False, "length_mismatch"

    return True, "ok"


@app.route('/compute', methods=['POST'])
def compute():
    try:
        data = request.get_json()

        room = data['room']
        Lx = float(room['width'])
        Ly = float(room['height'])
        Lz = float(room['depth'])
        room_dims = (Lx, Ly, Lz)

        if Lx <= 0 or Ly <= 0 or Lz <= 0:
            return jsonify({'error': '房间尺寸必须大于0'}), 400

        source = tuple(float(x) for x in data['source'])
        receiver = tuple(float(x) for x in data['receiver'])
        max_order = int(data.get('max_order', 3))

        default_absorption = data.get('absorption', {})
        abs_x_neg = float(default_absorption.get('x_neg', 0.1))
        abs_x_pos = float(default_absorption.get('x_pos', 0.1))
        abs_y_neg = float(default_absorption.get('y_neg', 0.1))
        abs_y_pos = float(default_absorption.get('y_pos', 0.1))
        abs_z_neg = float(default_absorption.get('z_neg', 0.1))
        abs_z_pos = float(default_absorption.get('z_pos', 0.1))

        abs_x_neg = clamp(abs_x_neg, 0.0, 1.0)
        abs_x_pos = clamp(abs_x_pos, 0.0, 1.0)
        abs_y_neg = clamp(abs_y_neg, 0.0, 1.0)
        abs_y_pos = clamp(abs_y_pos, 0.0, 1.0)
        abs_z_neg = clamp(abs_z_neg, 0.0, 1.0)
        abs_z_pos = clamp(abs_z_pos, 0.0, 1.0)

        absorption_map = {
            'x_neg': abs_x_neg,
            'x_pos': abs_x_pos,
            'y_neg': abs_y_neg,
            'y_pos': abs_y_pos,
            'z_neg': abs_z_neg,
            'z_pos': abs_z_pos,
        }

        Sx, Sy, Sz = source
        Sx = clamp(Sx, 0.0, Lx)
        Sy = clamp(Sy, 0.0, Ly)
        Sz = clamp(Sz, 0.0, Lz)
        source = (Sx, Sy, Sz)

        Rx, Ry, Rz = receiver
        Rx = clamp(Rx, 0.0, Lx)
        Ry = clamp(Ry, 0.0, Ly)
        Rz = clamp(Rz, 0.0, Lz)
        receiver = (Rx, Ry, Rz)

        direct_length = _dist(source, receiver)
        direct_time = direct_length / SOUND_SPEED

        min_dim = min(Lx, Ly, Lz)
        eps_len = max(EPS_DEGEN_REL * min_dim, 1e-10)

        paths = []
        path_signatures = set()
        
        direct_sig = _path_signature([source, receiver])
        path_signatures.add(direct_sig)
        
        direct_path = {
            'order': 0,
            'reflection_count': 0,
            'image_point': list(source),
            'path_points': [list(source), list(receiver)],
            'length': float(direct_length),
            'time': float(direct_time),
            'time_diff_ms': 0.0,
            'type': 'direct',
            'pressure_ratio': 1.0,
            'level_db': 0.0,
            'reflection_faces': []
        }
        paths.append(direct_path)

        rejected = {'invalid': 0, 'degenerate': 0, 'duplicate': 0}

        for nx in range(-max_order, max_order + 1):
            for ny in range(-max_order, max_order + 1):
                for nz in range(-max_order, max_order + 1):
                    order = abs(nx) + abs(ny) + abs(nz)
                    if order == 0 or order > max_order:
                        continue

                    image_n = (nx, ny, nz)
                    image_point, path_points, path_length, reflection_faces = compute_image_and_path(
                        source, receiver, room_dims, image_n
                    )

                    valid, reason = _validate_path(
                        path_points, path_length, room_dims, direct_length
                    )
                    if not valid:
                        rejected['invalid'] += 1
                        continue

                    num_reflections = len(path_points) - 2
                    if num_reflections < 1:
                        rejected['degenerate'] += 1
                        continue

                    travel_time = path_length / SOUND_SPEED
                    time_diff_ms = max(0.0, (travel_time - direct_time) * 1000.0)

                    sig = _path_signature(path_points)
                    if sig in path_signatures:
                        rejected['duplicate'] += 1
                        continue
                    path_signatures.add(sig)

                    pressure_ratio = 1.0
                    for face in reflection_faces:
                        abs_coeff = absorption_map.get(face, 0.1)
                        pressure_ratio *= (1.0 - abs_coeff)

                    level_db = 20.0 * math.log10(max(pressure_ratio, 1e-10)) if pressure_ratio > 0 else -100.0

                    paths.append({
                        'order': order,
                        'reflection_count': num_reflections,
                        'image_n': [nx, ny, nz],
                        'image_point': list(image_point),
                        'path_points': [list(p) for p in path_points],
                        'length': float(path_length),
                        'time': float(travel_time),
                        'time_diff_ms': float(time_diff_ms),
                        'type': f'reflection_{order}',
                        'pressure_ratio': float(pressure_ratio),
                        'level_db': float(level_db),
                        'reflection_faces': reflection_faces
                    })

        paths.sort(key=lambda p: p['time'])

        return jsonify({
            'sound_speed': SOUND_SPEED,
            'direct_time': float(direct_time),
            'paths': paths,
            'total_paths': len(paths),
            'source_clamped': list(source),
            'receiver_clamped': list(receiver),
            'absorption': absorption_map,
            'stats': {
                'total_image_sources': (2 * max_order + 1) ** 3 - 1,
                'valid_reflections': len(paths) - 1,
                'rejected_invalid': rejected['invalid'],
                'rejected_degenerate': rejected['degenerate'],
                'rejected_duplicate': rejected['duplicate']
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
