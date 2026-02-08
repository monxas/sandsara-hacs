#!/usr/bin/env python3
"""
Generador de patrón Sandsara para el kanji 栄 (prosperidad/gloria)
- Sin saltos: la bola vuelve por caminos ya trazados
- Mínimo 4000 puntos para trazos suaves
- Formato: X,Y por línea (int16 little-endian compatible, pero texto)
"""

import numpy as np
from pathlib import Path
import struct

# Configuración
OUTPUT_BIN = Path("/root/clawd/sandsara-hacs/research/patterns/kanji-ei-v2.bin")
MIN_POINTS = 4000
SCALE = 0.75  # Escala del kanji (deja margen)

def bezier_cubic(p0, p1, p2, p3, num_points=50):
    """Curva de Bézier cúbica entre 4 puntos de control."""
    t = np.linspace(0, 1, num_points)
    points = []
    for ti in t:
        point = (1-ti)**3 * np.array(p0) + \
                3*(1-ti)**2*ti * np.array(p1) + \
                3*(1-ti)*ti**2 * np.array(p2) + \
                ti**3 * np.array(p3)
        points.append(point)
    return points

def bezier_quadratic(p0, p1, p2, num_points=30):
    """Curva de Bézier cuadrática entre 3 puntos de control."""
    t = np.linspace(0, 1, num_points)
    points = []
    for ti in t:
        point = (1-ti)**2 * np.array(p0) + \
                2*(1-ti)*ti * np.array(p1) + \
                ti**2 * np.array(p2)
        points.append(point)
    return points

def line_segment(p0, p1, num_points=20):
    """Línea recta entre dos puntos."""
    return [np.array(p0) + t * (np.array(p1) - np.array(p0)) 
            for t in np.linspace(0, 1, num_points)]

def retrace_path(path, from_idx, to_idx):
    """Vuelve por un camino ya trazado desde from_idx hasta to_idx."""
    if from_idx <= to_idx:
        return [path[i] for i in range(from_idx, to_idx + 1)]
    else:
        return [path[i] for i in range(from_idx, to_idx - 1, -1)]

def find_closest_point(path, target):
    """Encuentra el índice del punto más cercano al target."""
    if not path:
        return 0
    distances = [np.linalg.norm(np.array(p) - np.array(target)) for p in path]
    return np.argmin(distances)

class KanjiPath:
    """Gestiona el camino completo del kanji."""
    
    def __init__(self):
        self.full_path = []  # Todos los puntos dibujados
        self.current_pos = None
        
    def add_points(self, points):
        """Añade puntos al camino."""
        for p in points:
            self.full_path.append(np.array(p))
        if points:
            self.current_pos = np.array(points[-1])
    
    def move_to_via_retrace(self, target):
        """
        Mueve a un nuevo punto volviendo por caminos ya trazados.
        Encuentra el punto más cercano al target en el path existente
        y vuelve hasta allí, luego va al target.
        """
        if not self.full_path:
            return
        
        target = np.array(target)
        current_idx = len(self.full_path) - 1
        
        # Encuentra el punto más cercano al destino
        closest_idx = find_closest_point(self.full_path, target)
        closest_point = self.full_path[closest_idx]
        
        # Retrocede hasta ese punto
        if closest_idx != current_idx:
            retrace = retrace_path(self.full_path, current_idx, closest_idx)
            # No duplicamos el primer punto (ya estamos ahí)
            self.add_points(retrace[1:])
        
        # Ahora va del punto cercano al target
        transition = line_segment(closest_point, target, num_points=25)
        self.add_points(transition[1:])  # Sin duplicar el primero

def create_kanji_ei():
    """
    Crea el kanji 栄 (prosperidad).
    
    Estructura:
    - Arriba: tres marcas pequeñas (火 simplificado / ツ)
    - Medio: 冖 (techo) 
    - Centro: línea horizontal corta
    - Abajo: 木 (árbol)
    """
    kanji = KanjiPath()
    
    # === COORDENADAS BASE (normalizadas, se escalarán después) ===
    # El kanji ocupa aproximadamente de -0.7 a 0.7 en ambos ejes
    
    # ========================================
    # PARTE 1: Las tres marcas superiores (ツ/火)
    # ========================================
    
    # Marca izquierda (diagonal hacia abajo-derecha)
    mark_left_start = (-0.25, 0.75)
    mark_left_end = (-0.15, 0.55)
    
    # Marca central (vertical corta, la más alta)
    mark_center_start = (0.0, 0.85)
    mark_center_end = (0.0, 0.60)
    
    # Marca derecha (diagonal hacia abajo-izquierda)
    mark_right_start = (0.25, 0.75)
    mark_right_end = (0.15, 0.55)
    
    # Trazo 1: Marca izquierda
    stroke1 = bezier_quadratic(
        mark_left_start,
        (-0.22, 0.65),  # control
        mark_left_end,
        num_points=40
    )
    kanji.add_points(stroke1)
    
    # Retrocede y va a marca central
    kanji.move_to_via_retrace(mark_center_start)
    
    # Trazo 2: Marca central
    stroke2 = bezier_quadratic(
        mark_center_start,
        (0.02, 0.72),  # ligera curva
        mark_center_end,
        num_points=45
    )
    kanji.add_points(stroke2)
    
    # Retrocede y va a marca derecha
    kanji.move_to_via_retrace(mark_right_start)
    
    # Trazo 3: Marca derecha
    stroke3 = bezier_quadratic(
        mark_right_start,
        (0.22, 0.65),
        mark_right_end,
        num_points=40
    )
    kanji.add_points(stroke3)
    
    # ========================================
    # PARTE 2: El techo 冖 con extensiones
    # ========================================
    
    # Punto superior del techo (casi horizontal con ligera curva)
    roof_left = (-0.50, 0.40)
    roof_peak = (0.0, 0.45)
    roof_right = (0.50, 0.40)
    
    # Extensiones hacia abajo en los extremos
    roof_left_down = (-0.45, 0.15)
    roof_right_down = (0.45, 0.15)
    
    # Va al inicio del techo
    kanji.move_to_via_retrace(roof_left)
    
    # Trazo 4: Techo izquierdo -> pico -> derecho (curva suave)
    roof_curve = bezier_cubic(
        roof_left,
        (-0.20, 0.48),
        (0.20, 0.48),
        roof_right,
        num_points=80
    )
    kanji.add_points(roof_curve)
    
    # Trazo 5: Extensión derecha hacia abajo
    right_ext = bezier_quadratic(
        roof_right,
        (0.48, 0.30),
        roof_right_down,
        num_points=35
    )
    kanji.add_points(right_ext)
    
    # Vuelve al lado izquierdo del techo para hacer la extensión izq
    kanji.move_to_via_retrace(roof_left)
    
    # Trazo 6: Extensión izquierda hacia abajo
    left_ext = bezier_quadratic(
        roof_left,
        (-0.48, 0.30),
        roof_left_down,
        num_points=35
    )
    kanji.add_points(left_ext)
    
    # ========================================
    # PARTE 3: Línea horizontal central
    # ========================================
    
    horiz_left = (-0.35, 0.05)
    horiz_right = (0.35, 0.05)
    
    kanji.move_to_via_retrace(horiz_left)
    
    # Trazo 7: Línea horizontal
    horiz_line = line_segment(horiz_left, horiz_right, num_points=60)
    kanji.add_points(horiz_line)
    
    # ========================================
    # PARTE 4: Radical 木 (árbol) - parte inferior
    # ========================================
    
    # Línea vertical central
    tree_top = (0.0, 0.05)
    tree_bottom = (0.0, -0.75)
    
    # Diagonales
    diag_center = (0.0, -0.25)  # Punto donde salen las diagonales
    diag_left = (-0.40, -0.65)
    diag_right = (0.40, -0.65)
    
    # Va al centro de la línea horizontal (ya cerca)
    kanji.move_to_via_retrace(tree_top)
    
    # Trazo 8: Línea vertical del árbol
    tree_vertical = line_segment(tree_top, tree_bottom, num_points=70)
    kanji.add_points(tree_vertical)
    
    # Vuelve al punto de las diagonales
    kanji.move_to_via_retrace(diag_center)
    
    # Trazo 9: Diagonal izquierda
    diag_left_stroke = bezier_quadratic(
        diag_center,
        (-0.15, -0.40),
        diag_left,
        num_points=50
    )
    kanji.add_points(diag_left_stroke)
    
    # Vuelve al centro
    kanji.move_to_via_retrace(diag_center)
    
    # Trazo 10: Diagonal derecha
    diag_right_stroke = bezier_quadratic(
        diag_center,
        (0.15, -0.40),
        diag_right,
        num_points=50
    )
    kanji.add_points(diag_right_stroke)
    
    # ========================================
    # REFUERZO: Pasamos de nuevo por trazos principales
    # ========================================
    
    # Vuelve arriba y refuerza algunas líneas
    kanji.move_to_via_retrace(tree_top)
    kanji.move_to_via_retrace(horiz_left)
    
    # Refuerza horizontal
    horiz_reinforced = line_segment(horiz_left, horiz_right, num_points=40)
    kanji.add_points(horiz_reinforced)
    
    # Vuelve al techo y refuerza
    kanji.move_to_via_retrace(roof_left)
    roof_reinforced = bezier_cubic(
        roof_left,
        (-0.20, 0.48),
        (0.20, 0.48),
        roof_right,
        num_points=60
    )
    kanji.add_points(roof_reinforced)
    
    # Refuerza la vertical del árbol
    kanji.move_to_via_retrace(tree_top)
    tree_reinforced = line_segment(tree_top, tree_bottom, num_points=50)
    kanji.add_points(tree_reinforced)
    
    # Refuerza diagonales
    kanji.move_to_via_retrace(diag_center)
    diag_left_reinforced = bezier_quadratic(diag_center, (-0.15, -0.40), diag_left, num_points=40)
    kanji.add_points(diag_left_reinforced)
    kanji.move_to_via_retrace(diag_center)
    diag_right_reinforced = bezier_quadratic(diag_center, (0.15, -0.40), diag_right, num_points=40)
    kanji.add_points(diag_right_reinforced)
    
    # ========================================
    # CIERRE: Vuelve al centro
    # ========================================
    kanji.move_to_via_retrace((0.0, 0.0))
    
    return kanji.full_path

def ensure_min_points(path, min_points):
    """
    Si hay menos puntos que el mínimo, interpola para añadir más.
    """
    if len(path) >= min_points:
        return path
    
    # Necesitamos más puntos - interpolamos entre cada par
    factor = int(np.ceil(min_points / len(path))) + 1
    new_path = []
    
    for i in range(len(path) - 1):
        p0 = path[i]
        p1 = path[i + 1]
        for j in range(factor):
            t = j / factor
            new_path.append(p0 + t * (p1 - p0))
    new_path.append(path[-1])
    
    return new_path[:min_points] if len(new_path) > min_points else new_path

def scale_path(path, scale):
    """Escala el path manteniendo el centro en (0,0)."""
    return [p * scale for p in path]

def to_int16_range(path):
    """
    Convierte coordenadas [-1, 1] a rango int16 [-32767, 32767].
    """
    result = []
    for p in path:
        x = int(np.clip(p[0] * 32767, -32767, 32767))
        y = int(np.clip(p[1] * 32767, -32767, 32767))
        result.append((x, y))
    return result

def write_bin_file(path_int16, filepath):
    """
    Escribe el archivo en formato texto: X,Y\n
    (compatible con el formato Sandsara existente)
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'wb') as f:
        for x, y in path_int16:
            # Formato: "X,Y\n" como bytes
            line = f"{x},{y}\n".encode('ascii')
            f.write(line)

def main():
    print("🎨 Generando patrón Sandsara para kanji 栄 (prosperidad)...")
    print()
    
    # Genera el kanji
    raw_path = create_kanji_ei()
    print(f"   Puntos base generados: {len(raw_path)}")
    
    # Escala
    scaled_path = scale_path(raw_path, SCALE)
    
    # Asegura mínimo de puntos
    final_path = ensure_min_points(scaled_path, MIN_POINTS)
    print(f"   Puntos después de interpolación: {len(final_path)}")
    
    # Convierte a int16
    int16_path = to_int16_range(final_path)
    
    # Escribe archivo
    write_bin_file(int16_path, OUTPUT_BIN)
    
    print()
    print(f"✅ Archivo guardado: {OUTPUT_BIN}")
    print(f"   Total puntos: {len(int16_path)}")
    print(f"   Tamaño estimado: {OUTPUT_BIN.stat().st_size / 1024:.1f} KB")
    
    # Stats adicionales
    xs = [p[0] for p in int16_path]
    ys = [p[1] for p in int16_path]
    print()
    print(f"📊 Estadísticas:")
    print(f"   X range: [{min(xs)}, {max(xs)}]")
    print(f"   Y range: [{min(ys)}, {max(ys)}]")

if __name__ == "__main__":
    main()
