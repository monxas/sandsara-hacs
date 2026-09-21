#!/usr/bin/env python3
"""
SVG to Sandsara - Multiple strategies to compare.
"""

import struct
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class Shape:
    name: str
    points: List[Tuple[float, float]]
    is_closed: bool = False

    def reverse(self):
        return Shape(self.name, list(reversed(self.points)), self.is_closed)

    def rotate_start(self, new_start_idx: int):
        if not self.is_closed or new_start_idx == 0:
            return self
        pts = self.points[:-1]
        rotated = pts[new_start_idx:] + pts[:new_start_idx] + [pts[new_start_idx]]
        return Shape(self.name, rotated, True)


def distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def shape_center(shape):
    xs = [p[0] for p in shape.points]
    ys = [p[1] for p in shape.points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def shape_angle(shape, center):
    c = shape_center(shape)
    return math.atan2(c[1] - center[1], c[0] - center[0])


# ============================================================================
# SVG PARSING (same as before)
# ============================================================================

def parse_transform(transform_str):
    if not transform_str:
        return [[1, 0, 0], [0, 1, 0]]
    matrix = [[1, 0, 0], [0, 1, 0]]
    ops = re.findall(r'(\w+)\s*\(([^)]+)\)', transform_str)
    for op, args in ops:
        values = [float(v.strip()) for v in args.replace(',', ' ').split()]
        if op == 'translate':
            tx, ty = values[0], values[1] if len(values) > 1 else 0
            m = [[1, 0, tx], [0, 1, ty]]
        elif op == 'rotate':
            angle = math.radians(values[0])
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            m = [[cos_a, -sin_a, 0], [sin_a, cos_a, 0]]
        elif op == 'scale':
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            m = [[sx, 0, 0], [0, sy, 0]]
        elif op == 'matrix':
            if len(values) >= 6:
                # SVG matrix(a,b,c,d,e,f) -> [[a,c,e],[b,d,f]]
                m = [[values[0], values[2], values[4]],
                     [values[1], values[3], values[5]]]
            else:
                continue
        else:
            continue
        matrix = [[matrix[0][0]*m[0][0] + matrix[0][1]*m[1][0],
                   matrix[0][0]*m[0][1] + matrix[0][1]*m[1][1],
                   matrix[0][0]*m[0][2] + matrix[0][1]*m[1][2] + matrix[0][2]],
                  [matrix[1][0]*m[0][0] + matrix[1][1]*m[1][0],
                   matrix[1][0]*m[0][1] + matrix[1][1]*m[1][1],
                   matrix[1][0]*m[0][2] + matrix[1][1]*m[1][2] + matrix[1][2]]]
    return matrix


def apply_transform(point, matrix):
    x, y = point
    return (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
            matrix[1][0] * x + matrix[1][1] * y + matrix[1][2])


def sample_line(x1, y1, x2, y2, n=10):
    return [(x1 + (x2-x1)*i/n, y1 + (y2-y1)*i/n) for i in range(n+1)]


def sample_circle(cx, cy, r, n=40):
    return [(cx + r*math.cos(2*math.pi*i/n), cy + r*math.sin(2*math.pi*i/n)) for i in range(n+1)]


def sample_bezier_cubic(p0, p1, p2, p3, n=20):
    pts = []
    for i in range(n+1):
        t = i/n
        x = (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0]
        y = (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def parse_path_d(d):
    points = []
    is_closed = False
    tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][+-]?\d+)?)', d)
    tokens = [t[0] or t[1] for t in tokens if t[0] or t[1]]

    i = 0
    cx, cy = 0, 0
    sx, sy = 0, 0
    last_cmd = None
    last_ctrl = None

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
        else:
            cmd = last_cmd

        if cmd in 'Mm':
            x, y = float(tokens[i]), float(tokens[i+1])
            i += 2
            if cmd == 'm': cx, cy = cx+x, cy+y
            else: cx, cy = x, y
            sx, sy = cx, cy
            points.append((cx, cy))
            last_cmd = 'L' if cmd == 'M' else 'l'
        elif cmd in 'Ll':
            x, y = float(tokens[i]), float(tokens[i+1])
            i += 2
            if cmd == 'l': x, y = cx+x, cy+y
            points.extend(sample_line(cx, cy, x, y, 5)[1:])
            cx, cy = x, y
            last_cmd = cmd
        elif cmd == 'H':
            x = float(tokens[i]); i += 1
            points.extend(sample_line(cx, cy, x, cy, 5)[1:])
            cx = x; last_cmd = cmd
        elif cmd == 'h':
            x = cx + float(tokens[i]); i += 1
            points.extend(sample_line(cx, cy, x, cy, 5)[1:])
            cx = x; last_cmd = cmd
        elif cmd == 'V':
            y = float(tokens[i]); i += 1
            points.extend(sample_line(cx, cy, cx, y, 5)[1:])
            cy = y; last_cmd = cmd
        elif cmd == 'v':
            y = cy + float(tokens[i]); i += 1
            points.extend(sample_line(cx, cy, cx, y, 5)[1:])
            cy = y; last_cmd = cmd
        elif cmd in 'Cc':
            x1, y1 = float(tokens[i]), float(tokens[i+1])
            x2, y2 = float(tokens[i+2]), float(tokens[i+3])
            x, y = float(tokens[i+4]), float(tokens[i+5])
            i += 6
            if cmd == 'c':
                x1, y1 = cx+x1, cy+y1
                x2, y2 = cx+x2, cy+y2
                x, y = cx+x, cy+y
            points.extend(sample_bezier_cubic((cx,cy), (x1,y1), (x2,y2), (x,y))[1:])
            last_ctrl = (x2, y2)
            cx, cy = x, y
            last_cmd = cmd
        elif cmd in 'Zz':
            if distance((cx,cy), (sx,sy)) > 0.01:
                points.extend(sample_line(cx, cy, sx, sy, 5)[1:])
            cx, cy = sx, sy
            is_closed = True
            last_cmd = cmd
        else:
            i += 1

    return points, is_closed


def extract_shapes(element, parent_transform=None, depth=0):
    shapes = []
    if parent_transform is None:
        parent_transform = [[1, 0, 0], [0, 1, 0]]

    transform_str = element.get('transform', '')
    local_transform = parse_transform(transform_str)
    # Multiply matrices
    m1, m2 = parent_transform, local_transform
    current_transform = [[m1[0][0]*m2[0][0] + m1[0][1]*m2[1][0],
                          m1[0][0]*m2[0][1] + m1[0][1]*m2[1][1],
                          m1[0][0]*m2[0][2] + m1[0][1]*m2[1][2] + m1[0][2]],
                         [m1[1][0]*m2[0][0] + m1[1][1]*m2[1][0],
                          m1[1][0]*m2[0][1] + m1[1][1]*m2[1][1],
                          m1[1][0]*m2[0][2] + m1[1][1]*m2[1][2] + m1[1][2]]]

    tag = element.tag.split('}')[-1]

    if tag == 'circle':
        cx, cy, r = float(element.get('cx', 0)), float(element.get('cy', 0)), float(element.get('r', 0))
        if r > 0:
            pts = [apply_transform(p, current_transform) for p in sample_circle(cx, cy, r)]
            shapes.append(Shape(f'circle', pts, is_closed=True))
    elif tag == 'line':
        x1, y1 = float(element.get('x1', 0)), float(element.get('y1', 0))
        x2, y2 = float(element.get('x2', 0)), float(element.get('y2', 0))
        pts = [apply_transform(p, current_transform) for p in sample_line(x1, y1, x2, y2)]
        shapes.append(Shape(f'line', pts, is_closed=False))
    elif tag == 'path':
        d = element.get('d', '')
        if d:
            pts, closed = parse_path_d(d)
            if pts:
                pts = [apply_transform(p, current_transform) for p in pts]
                shapes.append(Shape(f'path', pts, is_closed=closed))
    elif tag == 'polygon':
        points_str = element.get('points', '')
        coords = re.findall(r'-?\d*\.?\d+', points_str)
        if len(coords) >= 4:
            pts = [(float(coords[i]), float(coords[i+1])) for i in range(0, len(coords)-1, 2)]
            pts.append(pts[0])  # Close the polygon
            pts = [apply_transform(p, current_transform) for p in pts]
            shapes.append(Shape(f'polygon', pts, is_closed=True))
    elif tag == 'polyline':
        points_str = element.get('points', '')
        coords = re.findall(r'-?\d*\.?\d+', points_str)
        if len(coords) >= 4:
            pts = [(float(coords[i]), float(coords[i+1])) for i in range(0, len(coords)-1, 2)]
            pts = [apply_transform(p, current_transform) for p in pts]
            shapes.append(Shape(f'polyline', pts, is_closed=False))

    for child in element:
        shapes.extend(extract_shapes(child, current_transform, depth+1))

    return shapes


# ============================================================================
# CONNECTION STRATEGIES
# ============================================================================

def strategy_naive(shapes):
    """Strategy 1: Just connect in order, no optimization."""
    all_points = []
    for shape in shapes:
        if all_points:
            # Simple travel line
            start, end = all_points[-1], shape.points[0]
            all_points.extend(sample_line(start[0], start[1], end[0], end[1], 3)[1:])
        all_points.extend(shape.points)
    return all_points


def strategy_full_retrace(shapes):
    """Strategy 2: Full retrace on every open shape."""
    all_points = []
    for shape in shapes:
        if all_points:
            start, end = all_points[-1], shape.points[0]
            all_points.extend(sample_line(start[0], start[1], end[0], end[1], 3)[1:])
        all_points.extend(shape.points)
        # Full retrace for open shapes
        if not shape.is_closed:
            all_points.extend(reversed(shape.points[:-1]))
    return all_points


def strategy_nearest_neighbor_retrace(shapes):
    """Strategy 3: Nearest neighbor ordering + full retrace."""
    if not shapes:
        return []

    remaining = list(shapes)
    ordered = []
    pos = (0, 0)

    while remaining:
        best = None
        best_dist = float('inf')
        best_rev = False

        for s in remaining:
            d1 = distance(pos, s.points[0])
            d2 = distance(pos, s.points[-1])
            if d1 < best_dist:
                best_dist, best, best_rev = d1, s, False
            if d2 < best_dist:
                best_dist, best, best_rev = d2, s, True

        remaining.remove(best)
        if best_rev:
            best = best.reverse()
        ordered.append(best)
        pos = best.points[-1]

    # Now connect with retrace
    all_points = []
    for shape in ordered:
        if all_points:
            start, end = all_points[-1], shape.points[0]
            all_points.extend(sample_line(start[0], start[1], end[0], end[1], 3)[1:])
        all_points.extend(shape.points)
        if not shape.is_closed:
            all_points.extend(reversed(shape.points[:-1]))

    return all_points


def strategy_hub_and_spokes(shapes):
    """Strategy 4: Find hub (circle), draw rays from hub with retrace."""
    # Separate lines and other shapes
    lines = [s for s in shapes if not s.is_closed]
    others = [s for s in shapes if s.is_closed]

    if not lines:
        return strategy_nearest_neighbor_retrace(shapes)

    # Find center of all lines
    all_line_centers = [shape_center(s) for s in lines]
    center = (sum(c[0] for c in all_line_centers) / len(all_line_centers),
              sum(c[1] for c in all_line_centers) / len(all_line_centers))

    # Find hub (closest closed shape to center)
    hub = None
    hub_dist = float('inf')
    non_hub = []
    for s in others:
        d = distance(shape_center(s), center)
        if d < hub_dist:
            if hub:
                non_hub.append(hub)
            hub = s
            hub_dist = d
        else:
            non_hub.append(s)

    # Sort lines by angle around center
    lines_sorted = sorted(lines, key=lambda s: shape_angle(s, center))

    # Orient each line: inner point (closer to center) first
    oriented_lines = []
    for line in lines_sorted:
        p0, p1 = line.points[0], line.points[-1]
        if distance(p1, center) < distance(p0, center):
            oriented_lines.append(line.reverse())
        else:
            oriented_lines.append(line)

    all_points = []

    # Start with hub if exists
    if hub:
        # Find point on hub closest to first line's inner point
        first_inner = oriented_lines[0].points[0]
        best_idx = 0
        best_dist = float('inf')
        for i, p in enumerate(hub.points):
            d = distance(p, first_inner)
            if d < best_dist:
                best_dist, best_idx = d, i
        hub = hub.rotate_start(best_idx)
        all_points.extend(hub.points)

    # Draw each line with full retrace
    for i, line in enumerate(oriented_lines):
        inner = line.points[0]

        # Travel to inner point
        if all_points:
            start = all_points[-1]
            all_points.extend(sample_line(start[0], start[1], inner[0], inner[1], 3)[1:])

        # Draw line outward
        all_points.extend(line.points)

        # Full retrace back
        all_points.extend(reversed(line.points[:-1]))

        # We're back at inner point - if hub exists and more lines, travel along hub
        if hub and i < len(oriented_lines) - 1:
            next_inner = oriented_lines[i + 1].points[0]
            # Find closest point on hub to next line
            best_idx = 0
            best_dist = float('inf')
            for j, p in enumerate(hub.points[:-1]):
                d = distance(p, next_inner)
                if d < best_dist:
                    best_dist, best_idx = d, j
            # Travel to that hub point
            hub_point = hub.points[best_idx]
            start = all_points[-1]
            all_points.extend(sample_line(start[0], start[1], hub_point[0], hub_point[1], 3)[1:])

    # Add remaining non-hub shapes
    if non_hub:
        pos = all_points[-1] if all_points else (0, 0)
        # Sort by distance
        non_hub_sorted = sorted(non_hub, key=lambda s: min(distance(pos, p) for p in s.points))
        for shape in non_hub_sorted:
            start = all_points[-1]
            end = shape.points[0]
            all_points.extend(sample_line(start[0], start[1], end[0], end[1], 5)[1:])
            all_points.extend(shape.points)

    return all_points


def strategy_angular_from_center(shapes):
    """Strategy 5: Sort ALL shapes by angle from center, connect in angular order."""
    if not shapes:
        return []

    # Find overall center
    all_centers = [shape_center(s) for s in shapes]
    center = (sum(c[0] for c in all_centers) / len(all_centers),
              sum(c[1] for c in all_centers) / len(all_centers))

    # Sort by angle
    sorted_shapes = sorted(shapes, key=lambda s: shape_angle(s, center))

    all_points = []
    for shape in sorted_shapes:
        if all_points:
            # Connect to closest point of shape
            best_idx = 0
            best_dist = float('inf')
            for i, p in enumerate(shape.points):
                d = distance(all_points[-1], p)
                if d < best_dist:
                    best_dist, best_idx = d, i

            # Rotate closed shapes to start from closest point
            if shape.is_closed:
                shape = shape.rotate_start(best_idx)

            start, end = all_points[-1], shape.points[0]
            all_points.extend(sample_line(start[0], start[1], end[0], end[1], 3)[1:])

        all_points.extend(shape.points)

        # Retrace open shapes
        if not shape.is_closed:
            all_points.extend(reversed(shape.points[:-1]))

    return all_points


def find_closest_points_between_shapes(shape_a, shape_b):
    """Find the indices of closest points between two shapes."""
    best_dist = float('inf')
    best_i, best_j = 0, 0

    for i, pa in enumerate(shape_a.points):
        for j, pb in enumerate(shape_b.points):
            d = distance(pa, pb)
            if d < best_dist:
                best_dist = d
                best_i, best_j = i, j

    return best_i, best_j, best_dist


def strategy_intersection_aware(shapes):
    """Strategy 6: Find closest/intersection points between shapes and transition there.

    For two closed shapes A and B:
    1. Find where they're closest
    2. Draw A from start to the closest point
    3. Jump to B, draw B completely (full loop)
    4. Jump back to A, complete A (the rest of the loop)
    """
    if not shapes:
        return []

    if len(shapes) == 1:
        return shapes[0].points

    shapes = list(shapes)
    all_points = []

    # Start with the largest shape (most points)
    shapes.sort(key=lambda s: len(s.points), reverse=True)

    drawn = [False] * len(shapes)

    # Build closest points between all pairs
    closest_pairs = {}
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            idx_i, idx_j, dist = find_closest_points_between_shapes(shapes[i], shapes[j])
            closest_pairs[(i, j)] = (idx_i, idx_j, dist)
            closest_pairs[(j, i)] = (idx_j, idx_i, dist)

    # Start with shape 0, find closest other shape
    best_exit = None
    best_next = None
    best_dist = float('inf')

    for j in range(1, len(shapes)):
        if (0, j) in closest_pairs:
            idx_i, idx_j, dist = closest_pairs[(0, j)]
            if dist < best_dist:
                best_dist = dist
                best_exit = idx_i
                best_next = j

    shape_a = shapes[0]
    pts_a = shape_a.points[:-1] if shape_a.is_closed else shape_a.points
    n_a = len(pts_a)

    if best_exit is not None and shape_a.is_closed:
        # Draw shape A from point 0 to exit point (short way)
        forward = best_exit
        backward = n_a - best_exit

        if forward <= backward:
            for i in range(forward + 1):
                all_points.append(pts_a[i])
        else:
            for i in range(backward + 1):
                all_points.append(pts_a[(n_a - i) % n_a])

        exit_point = all_points[-1]

        # Jump to shape B
        shape_b = shapes[best_next]
        entry_idx_b = closest_pairs[(0, best_next)][1]
        pts_b = shape_b.points[:-1] if shape_b.is_closed else shape_b.points
        n_b = len(pts_b)

        # Travel to B
        entry_point = pts_b[entry_idx_b]
        all_points.extend(sample_line(exit_point[0], exit_point[1],
                                       entry_point[0], entry_point[1], 2)[1:])

        # Draw B fully (complete loop back to entry)
        for i in range(n_b + 1):
            all_points.append(pts_b[(entry_idx_b + i) % n_b])

        drawn[best_next] = True

        # Jump back to A at exit point
        all_points.extend(sample_line(all_points[-1][0], all_points[-1][1],
                                       exit_point[0], exit_point[1], 2)[1:])

        # Complete A - draw the remaining part back to start
        if forward <= backward:
            # We went forward 0->exit, now go forward exit->0 (the long way)
            for i in range(1, n_a - forward + 1):
                all_points.append(pts_a[(best_exit + i) % n_a])
        else:
            # We went backward 0->exit, now go backward exit->0 (the long way)
            for i in range(1, n_a - backward + 1):
                all_points.append(pts_a[(n_a - backward - i) % n_a])

        drawn[0] = True
    else:
        # Just draw first shape fully
        all_points.extend(shape_a.points)
        drawn[0] = True

    # Draw any remaining shapes
    for i in range(len(shapes)):
        if drawn[i]:
            continue

        shape = shapes[i]
        pts = shape.points[:-1] if shape.is_closed else shape.points
        n = len(pts)

        # Find closest point to current position
        best_idx = 0
        best_d = float('inf')
        for j, p in enumerate(pts):
            d = distance(all_points[-1], p)
            if d < best_d:
                best_d, best_idx = d, j

        # Travel to shape
        all_points.extend(sample_line(all_points[-1][0], all_points[-1][1],
                                       pts[best_idx][0], pts[best_idx][1], 3)[1:])

        # Draw full loop
        if shape.is_closed:
            for j in range(n + 1):
                all_points.append(pts[(best_idx + j) % n])
        else:
            all_points.extend(shape.points)
            all_points.extend(reversed(shape.points[:-1]))

        drawn[i] = True

    return all_points


def strategy_minimal_travel(shapes):
    """Strategy 7: Minimize total travel distance using closest-point transitions."""
    if not shapes:
        return []

    shapes = list(shapes)
    all_points = []

    # Find all pairwise closest points
    n = len(shapes)
    closest = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                idx_i, idx_j, dist = find_closest_points_between_shapes(shapes[i], shapes[j])
                closest[(i, j)] = (idx_i, idx_j, dist)

    # Order shapes by a greedy nearest-neighbor on closest points
    remaining = set(range(n))
    order = [0]  # Start with first shape
    remaining.remove(0)

    while remaining:
        current = order[-1]
        best_next = None
        best_dist = float('inf')

        for j in remaining:
            _, _, dist = closest[(current, j)]
            if dist < best_dist:
                best_dist = dist
                best_next = j

        order.append(best_next)
        remaining.remove(best_next)

    # Now draw in order, using closest points as entry/exit
    for idx, shape_idx in enumerate(order):
        shape = shapes[shape_idx]

        if idx == 0:
            # First shape: start from point closest to second shape (if exists)
            if len(order) > 1:
                exit_idx, _, _ = closest[(shape_idx, order[1])]
                # Start just after the exit point so we end at exit
                if shape.is_closed:
                    pts = shape.points[:-1]
                    start = (exit_idx + 1) % len(pts)
                    # Draw full circle back to exit point
                    for i in range(len(pts) + 1):
                        all_points.append(pts[(start + i) % len(pts)])
                else:
                    all_points.extend(shape.points)
            else:
                all_points.extend(shape.points)
        else:
            prev_shape_idx = order[idx - 1]
            _, entry_idx, _ = closest[(prev_shape_idx, shape_idx)]

            # Travel from current position to entry point
            start = all_points[-1]
            entry_point = shape.points[entry_idx]
            all_points.extend(sample_line(start[0], start[1],
                                          entry_point[0], entry_point[1], 2)[1:])

            # Determine exit point (closest to next shape, or just complete the loop)
            if idx < len(order) - 1:
                next_shape_idx = order[idx + 1]
                exit_idx, _, _ = closest[(shape_idx, next_shape_idx)]
            else:
                exit_idx = None  # Just complete the shape

            # Draw shape from entry point
            if shape.is_closed:
                pts = shape.points[:-1]
                n_pts = len(pts)

                if exit_idx is None:
                    # Last shape - just draw the full loop
                    for i in range(n_pts + 1):
                        all_points.append(pts[(entry_idx + i) % n_pts])
                else:
                    # Draw to exit, then complete back to entry, then retrace to exit
                    forward = (exit_idx - entry_idx) % n_pts
                    backward = (entry_idx - exit_idx) % n_pts

                    # Go the short way to exit
                    if forward <= backward:
                        for i in range(forward + 1):
                            all_points.append(pts[(entry_idx + i) % n_pts])
                    else:
                        for i in range(backward + 1):
                            all_points.append(pts[(entry_idx - i) % n_pts])

                    # Now complete the loop: go the long way back to entry, then back to exit
                    long_way = max(forward, backward)
                    if forward <= backward:
                        # We went forward to exit, now go backward to entry
                        for i in range(1, long_way + 1):
                            all_points.append(pts[(exit_idx - i) % n_pts])
                        # Now retrace forward back to exit
                        for i in range(1, long_way + 1):
                            all_points.append(pts[(entry_idx + i) % n_pts])
                    else:
                        # We went backward to exit, now go forward to entry
                        for i in range(1, long_way + 1):
                            all_points.append(pts[(exit_idx + i) % n_pts])
                        # Now retrace backward back to exit
                        for i in range(1, long_way + 1):
                            all_points.append(pts[(entry_idx - i) % n_pts])

            else:
                # Open shape - draw and full retrace
                all_points.extend(shape.points)
                all_points.extend(reversed(shape.points[:-1]))

    return all_points


# ============================================================================
# OUTPUT
# ============================================================================

def write_sandsara(filepath, points):
    with open(filepath, 'wb') as f:
        for x, y in points:
            x = max(-32767, min(32767, int(x)))
            y = max(-32767, min(32767, int(y)))
            f.write(struct.pack('<h', x))
            f.write(b',')
            f.write(struct.pack('<h', y))
            f.write(b'\n')


def normalize_and_scale(points, scale=22000):
    if not points:
        return []
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    max_dim = max(max_x - min_x, max_y - min_y) or 1
    return [((x - cx) / max_dim * scale * 2, -(y - cy) / max_dim * scale * 2) for x, y in points]


def convert_all_strategies(svg_path, output_dir, prefix="svg"):
    """Convert SVG using all strategies."""
    svg_content = Path(svg_path).read_text()
    root = ET.fromstring(svg_content)
    shapes = extract_shapes(root)

    print(f"Found {len(shapes)} shapes:")
    for s in shapes:
        print(f"  - {s.name}: {len(s.points)} pts, {'closed' if s.is_closed else 'open'}")

    strategies = [
        ("naive", strategy_naive),
        ("retrace", strategy_full_retrace),
        ("nearest", strategy_nearest_neighbor_retrace),
        ("hub", strategy_hub_and_spokes),
        ("angular", strategy_angular_from_center),
        ("intersect", strategy_intersection_aware),
        ("minimal", strategy_minimal_travel),
    ]

    for name, strategy in strategies:
        points = strategy(list(shapes))  # Copy shapes list
        scaled = normalize_and_scale(points)
        out_path = Path(output_dir) / f"{prefix}-{name}.bin"
        write_sandsara(out_path, scaled)
        print(f"  {name}: {len(scaled)} points -> {out_path.name}")


if __name__ == '__main__':
    import sys
    samples_dir = Path(__file__).parent / 'samples'

    if len(sys.argv) > 1:
        svg_file = sys.argv[1]
        prefix = Path(svg_file).stem
        convert_all_strategies(svg_file, samples_dir, prefix)
    else:
        # Default: convert both test files
        print("=== Weather (sun + cloud) ===")
        convert_all_strategies('test-weather.svg', samples_dir, 'svg-weather')
        print("\n=== Storm (cloud + lightning) ===")
        convert_all_strategies('test-storm.svg', samples_dir, 'svg-storm')
