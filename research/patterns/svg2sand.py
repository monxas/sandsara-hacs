#!/usr/bin/env python3
"""
svg2sand - Convert SVG files to Sandsara sand table patterns

Smart path planning to minimize visible travel lines between shapes.

Usage:
    python svg2sand.py input.svg output.bin
    python svg2sand.py input.svg  # outputs input.bin
    python svg2sand.py --help
"""

import argparse
import struct
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class Shape:
    """A drawable shape with its points."""
    name: str
    points: List[Tuple[float, float]]
    is_closed: bool = False

    def reverse(self):
        """Return a new shape with reversed points."""
        return Shape(self.name, list(reversed(self.points)), self.is_closed)

    def rotate_start(self, new_start_idx: int):
        """For closed shapes, rotate points so a different point is the start."""
        if not self.is_closed or new_start_idx == 0:
            return self
        pts = self.points[:-1]  # Remove closing point (duplicate of first)
        rotated = pts[new_start_idx:] + pts[:new_start_idx] + [pts[new_start_idx]]
        return Shape(self.name, rotated, True)


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def find_closest_point_idx(points: List[Tuple[float, float]], target: Tuple[float, float]) -> int:
    """Find index of point closest to target."""
    min_dist = float('inf')
    min_idx = 0
    for i, p in enumerate(points):
        d = distance(p, target)
        if d < min_dist:
            min_dist = d
            min_idx = i
    return min_idx


def nearest_neighbor_order(shapes: List[Shape], start: Tuple[float, float] = (0, 0)) -> List[Shape]:
    """Order shapes using nearest neighbor heuristic."""
    if not shapes:
        return []

    remaining = list(shapes)
    ordered = []
    current_pos = start

    while remaining:
        # Find shape with closest start or end point
        best_shape = None
        best_dist = float('inf')
        best_reversed = False
        best_rotated_idx = 0

        for shape in remaining:
            # Check start point
            d_start = distance(shape.points[0], current_pos)
            if d_start < best_dist:
                best_dist = d_start
                best_shape = shape
                best_reversed = False
                best_rotated_idx = 0

            # Check end point (draw in reverse)
            d_end = distance(shape.points[-1], current_pos)
            if d_end < best_dist:
                best_dist = d_end
                best_shape = shape
                best_reversed = True
                best_rotated_idx = 0

            # For closed shapes, check all points as potential starts
            if shape.is_closed and len(shape.points) > 2:
                for i, p in enumerate(shape.points[:-1]):  # Exclude last (duplicate)
                    d = distance(p, current_pos)
                    if d < best_dist:
                        best_dist = d
                        best_shape = shape
                        best_reversed = False
                        best_rotated_idx = i

        # Add best shape (possibly modified)
        if best_shape:
            remaining.remove(best_shape)

            if best_shape.is_closed and best_rotated_idx > 0:
                best_shape = best_shape.rotate_start(best_rotated_idx)
            elif best_reversed:
                best_shape = best_shape.reverse()

            ordered.append(best_shape)
            current_pos = best_shape.points[-1]

    return ordered


def retrace_path_full(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Fully retrace a path back to the start."""
    if len(points) < 2:
        return []
    return list(reversed(points[:-1]))  # Go back, excluding the endpoint (we're already there)


def get_shape_center(shape: Shape) -> Tuple[float, float]:
    """Get the centroid of a shape."""
    if not shape.points:
        return (0, 0)
    xs = [p[0] for p in shape.points]
    ys = [p[1] for p in shape.points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def get_shape_angle(shape: Shape, center: Tuple[float, float]) -> float:
    """Get the angle of a shape relative to a center point."""
    shape_center = get_shape_center(shape)
    return math.atan2(shape_center[1] - center[1], shape_center[0] - center[0])


def find_common_center(shapes: List[Shape], tolerance: float = 5.0) -> Optional[Tuple[float, float]]:
    """
    Check if shapes share a common center (like sun rays).
    Returns the common center if found, None otherwise.
    """
    if len(shapes) < 3:
        return None

    # For lines, check if they all point toward/away from a common point
    lines = [s for s in shapes if not s.is_closed and len(s.points) >= 2]
    if len(lines) < 3:
        return None

    # Get the "inner" endpoint of each line (closer to potential center)
    centers_guess = []
    for line in lines:
        p1, p2 = line.points[0], line.points[-1]
        # The inner point is the one with smaller magnitude from origin
        # But we need to find the actual center...
        # Use the midpoint between endpoints as initial guess
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        centers_guess.append(mid)

    # Check if all midpoints cluster around a common center
    avg_x = sum(p[0] for p in centers_guess) / len(centers_guess)
    avg_y = sum(p[1] for p in centers_guess) / len(centers_guess)

    # Check variance
    max_dist = max(distance(p, (avg_x, avg_y)) for p in centers_guess)

    if max_dist < tolerance:
        return (avg_x, avg_y)

    return None


def group_radial_shapes(shapes: List[Shape]) -> Tuple[List[Shape], List[Shape]]:
    """
    Separate shapes into radial (sun-ray-like) and non-radial groups.
    Returns (radial_shapes, other_shapes).
    """
    # Separate open and closed shapes
    open_shapes = [s for s in shapes if not s.is_closed]
    closed_shapes = [s for s in shapes if s.is_closed]

    # Check if open shapes form a radial pattern
    center = find_common_center(open_shapes)

    if center:
        # Sort radial shapes by angle
        radial = sorted(open_shapes, key=lambda s: get_shape_angle(s, center))
        return radial, closed_shapes

    return [], shapes


def travel_to(all_points: List[Tuple[float, float]], target: Tuple[float, float], num_points: int = 5):
    """Add travel points from current position to target."""
    if not all_points:
        all_points.append(target)
        return

    start = all_points[-1]
    for i in range(1, num_points + 1):
        t = i / num_points
        x = start[0] + (target[0] - start[0]) * t
        y = start[1] + (target[1] - start[1]) * t
        all_points.append((x, y))


def find_closest_point_on_shape(shape: Shape, target: Tuple[float, float]) -> int:
    """Find index of point on shape closest to target."""
    min_dist = float('inf')
    min_idx = 0
    for i, p in enumerate(shape.points):
        d = distance(p, target)
        if d < min_dist:
            min_dist = d
            min_idx = i
    return min_idx


def connect_shapes_smart(shapes: List[Shape], use_retrace: bool = True) -> List[Tuple[float, float]]:
    """
    Connect shapes into one continuous path with smart path planning.

    Strategy:
    1. Detect radial patterns (like sun rays)
    2. Find hub shapes (circles near radial centers)
    3. Draw hub, then rays with full retrace, then other shapes
    """
    if not shapes:
        return []

    all_points = []

    # Detect radial patterns
    radial_shapes, other_shapes = group_radial_shapes(shapes)

    if radial_shapes:
        # Find the center of the radial pattern
        center = find_common_center(radial_shapes)

        # Find a hub shape (closed shape near the center)
        hub = None
        hub_dist = float('inf')
        non_hub_others = []

        for shape in other_shapes:
            if shape.is_closed:
                shape_center = get_shape_center(shape)
                d = distance(shape_center, center)
                if d < hub_dist and d < 20:  # Must be close to radial center
                    if hub:
                        non_hub_others.append(hub)
                    hub = shape
                    hub_dist = d
                else:
                    non_hub_others.append(shape)
            else:
                non_hub_others.append(shape)

        # Draw hub first (if found)
        if hub:
            # Start hub from point closest to first ray
            first_ray_start = radial_shapes[0].points[0]
            start_idx = find_closest_point_on_shape(hub, first_ray_start)
            hub = hub.rotate_start(start_idx)
            all_points.extend(hub.points)

        # Draw each ray with full retrace
        for i, ray in enumerate(radial_shapes):
            # Orient ray so we draw outward (start from inner point)
            ray_start = ray.points[0]
            ray_end = ray.points[-1]

            # Inner point is closer to center
            if distance(ray_end, center) < distance(ray_start, center):
                ray = ray.reverse()
                ray_start, ray_end = ray_end, ray_start

            # Travel to ray start
            travel_to(all_points, ray_start, 3)

            # Draw ray
            all_points.extend(ray.points[1:])  # Skip first (we just traveled there)

            # Fully retrace back
            retrace = retrace_path_full(ray.points)
            all_points.extend(retrace)

            # If hub exists and more rays remain, travel along hub to next ray position
            if hub and i < len(radial_shapes) - 1:
                next_ray_start = radial_shapes[i + 1].points[0]
                next_ray_end = radial_shapes[i + 1].points[-1]
                # Find inner point of next ray
                if distance(next_ray_end, center) < distance(next_ray_start, center):
                    next_inner = next_ray_end
                else:
                    next_inner = next_ray_start

                # Find closest points on hub to current position and next ray
                current_pos = all_points[-1]
                curr_hub_idx = find_closest_point_on_shape(hub, current_pos)
                next_hub_idx = find_closest_point_on_shape(hub, next_inner)

                # Travel along hub (shorter direction)
                hub_len = len(hub.points) - 1  # Exclude duplicate closing point
                forward_dist = (next_hub_idx - curr_hub_idx) % hub_len
                backward_dist = (curr_hub_idx - next_hub_idx) % hub_len

                if forward_dist <= backward_dist:
                    # Go forward
                    for j in range(forward_dist + 1):
                        idx = (curr_hub_idx + j) % hub_len
                        all_points.append(hub.points[idx])
                else:
                    # Go backward
                    for j in range(backward_dist + 1):
                        idx = (curr_hub_idx - j) % hub_len
                        all_points.append(hub.points[idx])

        # Now handle remaining shapes
        other_shapes = non_hub_others

    # Handle non-radial shapes with nearest neighbor
    if other_shapes:
        start_pos = all_points[-1] if all_points else (0, 0)
        ordered = nearest_neighbor_order(other_shapes, start_pos)

        for shape in ordered:
            if not shape.points:
                continue

            # Travel to shape
            travel_to(all_points, shape.points[0], 5)

            # Draw shape
            all_points.extend(shape.points[1:])

            # For open shapes, fully retrace
            if not shape.is_closed and use_retrace:
                retrace = retrace_path_full(shape.points)
                all_points.extend(retrace)

    return all_points


# ============================================================================
# SVG Parsing
# ============================================================================

def parse_transform(transform_str: str):
    """Parse SVG transform string into transformation matrix."""
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
            if len(values) == 3:  # rotate around point
                cx, cy = values[1], values[2]
                m = [[cos_a, -sin_a, cx - cos_a*cx + sin_a*cy],
                     [sin_a, cos_a, cy - sin_a*cx - cos_a*cy]]
            else:
                m = [[cos_a, -sin_a, 0], [sin_a, cos_a, 0]]
        elif op == 'scale':
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            m = [[sx, 0, 0], [0, sy, 0]]
        elif op == 'matrix':
            if len(values) == 6:
                m = [[values[0], values[2], values[4]],
                     [values[1], values[3], values[5]]]
            else:
                continue
        else:
            continue

        matrix = multiply_matrices(matrix, m)

    return matrix


def multiply_matrices(m1, m2):
    """Multiply two 2x3 transformation matrices."""
    return [
        [m1[0][0]*m2[0][0] + m1[0][1]*m2[1][0],
         m1[0][0]*m2[0][1] + m1[0][1]*m2[1][1],
         m1[0][0]*m2[0][2] + m1[0][1]*m2[1][2] + m1[0][2]],
        [m1[1][0]*m2[0][0] + m1[1][1]*m2[1][0],
         m1[1][0]*m2[0][1] + m1[1][1]*m2[1][1],
         m1[1][0]*m2[0][2] + m1[1][1]*m2[1][2] + m1[1][2]]
    ]


def apply_transform(point, matrix):
    """Apply transformation matrix to a point."""
    x, y = point
    return (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
            matrix[1][0] * x + matrix[1][1] * y + matrix[1][2])


def sample_bezier_cubic(p0, p1, p2, p3, num_samples=20):
    """Sample points along a cubic bezier curve."""
    points = []
    for i in range(num_samples + 1):
        t = i / num_samples
        x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def sample_bezier_quad(p0, p1, p2, num_samples=15):
    """Sample points along a quadratic bezier curve."""
    points = []
    for i in range(num_samples + 1):
        t = i / num_samples
        x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        points.append((x, y))
    return points


def sample_arc(cx, cy, rx, ry, start_angle, end_angle, num_samples=20):
    """Sample points along an elliptical arc."""
    points = []
    for i in range(num_samples + 1):
        t = i / num_samples
        angle = start_angle + (end_angle - start_angle) * t
        x = cx + rx * math.cos(angle)
        y = cy + ry * math.sin(angle)
        points.append((x, y))
    return points


def sample_circle(cx, cy, r, num_points=50):
    """Sample points along a circle."""
    points = []
    for i in range(num_points + 1):
        angle = (i / num_points) * 2 * math.pi
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def sample_ellipse(cx, cy, rx, ry, num_points=50):
    """Sample points along an ellipse."""
    points = []
    for i in range(num_points + 1):
        angle = (i / num_points) * 2 * math.pi
        points.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return points


def sample_line(x1, y1, x2, y2, num_points=10):
    """Sample points along a line."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return points


def parse_path_d(d: str) -> Tuple[List[Tuple[float, float]], bool]:
    """Parse SVG path d attribute. Returns (points, is_closed)."""
    points = []
    is_closed = False

    tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][+-]?\d+)?)', d)
    tokens = [t[0] or t[1] for t in tokens if t[0] or t[1]]

    i = 0
    current_x, current_y = 0, 0
    start_x, start_y = 0, 0
    last_command = None
    last_control = None

    while i < len(tokens):
        token = tokens[i]

        if token.isalpha():
            command = token
            i += 1
        else:
            command = last_command

        if command in 'Mm':
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            if command == 'm':
                current_x += x
                current_y += y
            else:
                current_x, current_y = x, y
            start_x, start_y = current_x, current_y
            points.append((current_x, current_y))
            last_command = 'L' if command == 'M' else 'l'

        elif command in 'Ll':
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            if command == 'l':
                x, y = current_x + x, current_y + y
            for pt in sample_line(current_x, current_y, x, y, 5)[1:]:
                points.append(pt)
            current_x, current_y = x, y
            last_command = command

        elif command == 'H':
            x = float(tokens[i])
            i += 1
            for pt in sample_line(current_x, current_y, x, current_y, 5)[1:]:
                points.append(pt)
            current_x = x
            last_command = command

        elif command == 'h':
            dx = float(tokens[i])
            i += 1
            x = current_x + dx
            for pt in sample_line(current_x, current_y, x, current_y, 5)[1:]:
                points.append(pt)
            current_x = x
            last_command = command

        elif command == 'V':
            y = float(tokens[i])
            i += 1
            for pt in sample_line(current_x, current_y, current_x, y, 5)[1:]:
                points.append(pt)
            current_y = y
            last_command = command

        elif command == 'v':
            dy = float(tokens[i])
            i += 1
            y = current_y + dy
            for pt in sample_line(current_x, current_y, current_x, y, 5)[1:]:
                points.append(pt)
            current_y = y
            last_command = command

        elif command in 'Cc':
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
            i += 6
            if command == 'c':
                x1, y1 = current_x + x1, current_y + y1
                x2, y2 = current_x + x2, current_y + y2
                x, y = current_x + x, current_y + y
            for pt in sample_bezier_cubic((current_x, current_y), (x1, y1), (x2, y2), (x, y))[1:]:
                points.append(pt)
            last_control = (x2, y2)
            current_x, current_y = x, y
            last_command = command

        elif command in 'Ss':
            # Smooth cubic bezier
            x2, y2 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            i += 4
            if command == 's':
                x2, y2 = current_x + x2, current_y + y2
                x, y = current_x + x, current_y + y
            # Reflect last control point
            if last_control and last_command in 'CcSs':
                x1 = 2 * current_x - last_control[0]
                y1 = 2 * current_y - last_control[1]
            else:
                x1, y1 = current_x, current_y
            for pt in sample_bezier_cubic((current_x, current_y), (x1, y1), (x2, y2), (x, y))[1:]:
                points.append(pt)
            last_control = (x2, y2)
            current_x, current_y = x, y
            last_command = command

        elif command in 'Qq':
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            i += 4
            if command == 'q':
                x1, y1 = current_x + x1, current_y + y1
                x, y = current_x + x, current_y + y
            for pt in sample_bezier_quad((current_x, current_y), (x1, y1), (x, y))[1:]:
                points.append(pt)
            last_control = (x1, y1)
            current_x, current_y = x, y
            last_command = command

        elif command in 'Tt':
            # Smooth quadratic bezier
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            if command == 't':
                x, y = current_x + x, current_y + y
            if last_control and last_command in 'QqTt':
                x1 = 2 * current_x - last_control[0]
                y1 = 2 * current_y - last_control[1]
            else:
                x1, y1 = current_x, current_y
            for pt in sample_bezier_quad((current_x, current_y), (x1, y1), (x, y))[1:]:
                points.append(pt)
            last_control = (x1, y1)
            current_x, current_y = x, y
            last_command = command

        elif command in 'Zz':
            if distance((current_x, current_y), (start_x, start_y)) > 0.01:
                for pt in sample_line(current_x, current_y, start_x, start_y, 5)[1:]:
                    points.append(pt)
            current_x, current_y = start_x, start_y
            is_closed = True
            last_command = command

        else:
            i += 1

    return points, is_closed


def extract_shapes(element, parent_transform=None, depth=0) -> List[Shape]:
    """Recursively extract shapes from SVG element."""
    shapes = []

    if parent_transform is None:
        parent_transform = [[1, 0, 0], [0, 1, 0]]

    transform_str = element.get('transform', '')
    local_transform = parse_transform(transform_str)
    current_transform = multiply_matrices(parent_transform, local_transform)

    tag = element.tag.split('}')[-1]

    if tag == 'circle':
        cx = float(element.get('cx', 0))
        cy = float(element.get('cy', 0))
        r = float(element.get('r', 0))
        if r > 0:
            points = sample_circle(cx, cy, r, 40)
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(Shape(f'circle_{depth}', transformed, is_closed=True))

    elif tag == 'ellipse':
        cx = float(element.get('cx', 0))
        cy = float(element.get('cy', 0))
        rx = float(element.get('rx', 0))
        ry = float(element.get('ry', 0))
        if rx > 0 and ry > 0:
            points = sample_ellipse(cx, cy, rx, ry, 40)
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(Shape(f'ellipse_{depth}', transformed, is_closed=True))

    elif tag == 'line':
        x1 = float(element.get('x1', 0))
        y1 = float(element.get('y1', 0))
        x2 = float(element.get('x2', 0))
        y2 = float(element.get('y2', 0))
        points = sample_line(x1, y1, x2, y2, 10)
        transformed = [apply_transform(p, current_transform) for p in points]
        shapes.append(Shape(f'line_{depth}', transformed, is_closed=False))

    elif tag == 'rect':
        x = float(element.get('x', 0))
        y = float(element.get('y', 0))
        w = float(element.get('width', 0))
        h = float(element.get('height', 0))
        if w > 0 and h > 0:
            points = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(Shape(f'rect_{depth}', transformed, is_closed=True))

    elif tag == 'polygon':
        points_str = element.get('points', '')
        coords = re.findall(r'-?\d*\.?\d+', points_str)
        if len(coords) >= 4:
            points = [(float(coords[i]), float(coords[i+1])) for i in range(0, len(coords)-1, 2)]
            points.append(points[0])  # Close
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(Shape(f'polygon_{depth}', transformed, is_closed=True))

    elif tag == 'polyline':
        points_str = element.get('points', '')
        coords = re.findall(r'-?\d*\.?\d+', points_str)
        if len(coords) >= 4:
            points = [(float(coords[i]), float(coords[i+1])) for i in range(0, len(coords)-1, 2)]
            transformed = [apply_transform(p, current_transform) for p in points]
            shapes.append(Shape(f'polyline_{depth}', transformed, is_closed=False))

    elif tag == 'path':
        d = element.get('d', '')
        if d:
            points, is_closed = parse_path_d(d)
            if points:
                transformed = [apply_transform(p, current_transform) for p in points]
                shapes.append(Shape(f'path_{depth}', transformed, is_closed=is_closed))

    # Recurse
    for child in element:
        shapes.extend(extract_shapes(child, current_transform, depth + 1))

    return shapes


# ============================================================================
# Output
# ============================================================================

def write_sandsara(filepath: Path, points: List[Tuple[float, float]]):
    """Write points to Sandsara .bin format."""
    with open(filepath, 'wb') as f:
        for x, y in points:
            x = max(-32767, min(32767, int(x)))
            y = max(-32767, min(32767, int(y)))
            f.write(struct.pack('<h', x))
            f.write(b',')
            f.write(struct.pack('<h', y))
            f.write(b'\n')


def normalize_and_scale(points: List[Tuple[float, float]],
                        scale: int = 22000,
                        center: bool = True) -> List[Tuple[float, float]]:
    """Normalize points to fit within Sandsara coordinate range."""
    if not points:
        return []

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y
    max_dim = max(width, height)

    if max_dim == 0:
        return [(0, 0)] * len(points)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    scaled = []
    for x, y in points:
        if center:
            x -= center_x
            y -= center_y
        else:
            x -= min_x + width / 2
            y -= min_y + height / 2

        x = x / max_dim * scale * 2
        y = -y / max_dim * scale * 2  # Flip Y
        scaled.append((x, y))

    return scaled


def convert_svg(svg_input: str,
                output_path: Path,
                scale: int = 22000,
                use_retrace: bool = True,
                verbose: bool = False) -> int:
    """
    Convert SVG to Sandsara pattern.

    Args:
        svg_input: SVG content string or path to SVG file
        output_path: Output .bin file path
        scale: Max coordinate value (default 22000 for ~85% of table)
        use_retrace: Use smart retracing to minimize travel lines
        verbose: Print detailed info

    Returns:
        Number of points in output
    """
    # Load SVG
    if svg_input.strip().startswith('<'):
        svg_content = svg_input
    else:
        svg_content = Path(svg_input).read_text()

    # Parse
    root = ET.fromstring(svg_content)
    shapes = extract_shapes(root)

    if verbose:
        print(f"Found {len(shapes)} shapes:")
        for s in shapes:
            status = "closed" if s.is_closed else "open"
            print(f"  - {s.name}: {len(s.points)} points ({status})")

    if not shapes:
        print("Error: No shapes found in SVG")
        return 0

    # Connect with smart path planning
    points = connect_shapes_smart(shapes, use_retrace=use_retrace)

    if verbose:
        print(f"Total points after connecting: {len(points)}")

    # Scale to Sandsara coordinates
    scaled = normalize_and_scale(points, scale)

    # Write output
    write_sandsara(output_path, scaled)

    print(f"Created {output_path} ({len(scaled)} points, {len(scaled) * 6} bytes)")
    return len(scaled)


def main():
    parser = argparse.ArgumentParser(
        description='Convert SVG files to Sandsara sand table patterns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s icon.svg                    # Creates icon.bin
  %(prog)s icon.svg pattern.bin        # Creates pattern.bin
  %(prog)s icon.svg -s 25000           # Larger scale (fills more of table)
  %(prog)s icon.svg --no-retrace       # Disable smart retracing
  %(prog)s icon.svg -v                 # Verbose output
'''
    )

    parser.add_argument('input', help='Input SVG file')
    parser.add_argument('output', nargs='?', help='Output .bin file (default: input with .bin extension)')
    parser.add_argument('-s', '--scale', type=int, default=22000,
                        help='Scale factor (default: 22000, max ~32000)')
    parser.add_argument('--no-retrace', action='store_true',
                        help='Disable smart retracing (faster but more travel lines)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print detailed information')

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.bin')

    count = convert_svg(
        str(input_path),
        output_path,
        scale=args.scale,
        use_retrace=not args.no_retrace,
        verbose=args.verbose
    )

    if count == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
