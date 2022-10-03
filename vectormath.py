import array
import math


def multiply_3x3(a, b):
    return array.array(
        "f",
        (
            a[0] * b[0] + a[1] * b[3] + a[2] * b[6],
            a[0] * b[1] + a[1] * b[4] + a[2] * b[7],
            a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
            a[3] * b[0] + a[4] * b[3] + a[5] * b[6],
            a[3] * b[1] + a[4] * b[4] + a[5] * b[7],
            a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
            a[6] * b[0] + a[7] * b[3] + a[8] * b[6],
            a[6] * b[1] + a[7] * b[4] + a[8] * b[7],
            a[6] * b[2] + a[7] * b[5] + a[8] * b[8],
        ),
    )


class Matrix3x3:
    def __init__(self, initial=None):
        self.m = array.array(
            "f",
            initial.m
            if initial is not None
            else (
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ),
        )

    def apply(self, v):
        m = self.m

        v = (v[0], v[1], 1.0)

        v = (
            m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
            m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
            m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
        )

        return (v[0] / v[2], v[1] / v[2])

    def translate(self, x, y):
        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    1.0,
                    0.0,
                    x,
                    0.0,
                    1.0,
                    y,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def scale(self, x, y):
        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    x,
                    0.0,
                    0.0,
                    0.0,
                    y,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def rotate(self, angle_radians):
        s = math.sin(angle_radians)
        c = math.cos(angle_radians)

        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    c,
                    -s,
                    0.0,
                    s,
                    c,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def ortho(self, left, right, bottom, top):
        w = right - left
        tx = -(right + left) / w
        h = top - bottom
        ty = -(top + bottom) / h

        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    2.0 / w,
                    0.0,
                    tx,
                    0.0,
                    2.0 / h,
                    ty,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )


def test_matrix3x3():
    def degrees_to_radians(deg):
        return deg / 180 * math.pi

    test_ops = [
        ("scale", 0.5, 2.0),
        ("translate", 30, 40),
        ("rotate", degrees_to_radians(-90)),
        ("ortho", 0, 1000, 1000, 0),
    ]

    for method, *args in test_ops:
        m = Matrix3x3()
        for v in ((100, 200), (0, 0)):
            getattr(m, method)(*args)
            # logging.debug(f"{v} -> {method}{tuple(args)} -> {m.apply(v)}")  #  TODO


from pygame import Vector2
from pygame import Rect


# TODO: is this the right place?
def aabb_from_points(points: [Vector2]):
    """
    Compute axis-aligned bounding box from points.
    """
    x = min(point.x for point in points)
    y = min(point.y for point in points)
    w = max(point.x for point in points) - x
    h = max(point.y for point in points) - y
    return Rect(x, y, w, h)
