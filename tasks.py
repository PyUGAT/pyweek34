import array

from OpenGL.GL import *
from pygame import Color, Vector2

from sprite import ImageSprite


class IDrawTask:
    def draw(self):
        raise NotImplementedError("Do not know how to draw this task")


class DrawSpriteTask(IDrawTask):
    def __init__(self, sprite: ImageSprite):
        self.sprite = sprite
        self.data = array.array("f")

    def append(self, position: Vector2, scale: Vector2, apply_modelview_matrix):
        if scale is None:
            scale = Vector2(1, 1)

        right = Vector2(self.sprite.width * scale.x, 0)
        bottom = Vector2(0, self.sprite.height * scale.y)

        tl = Vector2(position)
        tr = tl + right
        bl = tl + bottom
        br = bl + right

        corners_in_modelview_space = [tl, tr, bl, br]

        tl = apply_modelview_matrix(tl)
        tr = apply_modelview_matrix(tr)
        bl = apply_modelview_matrix(bl)
        br = apply_modelview_matrix(br)

        self.data.extend(
            (
                0.0,
                0.0,
                tl.x,
                tl.y,
                1.0,
                0.0,
                tr.x,
                tr.y,
                1.0,
                1.0,
                br.x,
                br.y,
                0.0,
                0.0,
                tl.x,
                tl.y,
                1.0,
                1.0,
                br.x,
                br.y,
                0.0,
                1.0,
                bl.x,
                bl.y,
            )
        )

        return corners_in_modelview_space

    def draw(self):
        texture = self.sprite._get_texture()
        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glColor4f(1, 1, 1, 1)

        buf = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buf)
        glBufferData(GL_ARRAY_BUFFER, self.data.tobytes(), GL_STATIC_DRAW)

        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(
            2, GL_FLOAT, 4 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0)
        )

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(
            2,
            GL_FLOAT,
            4 * ctypes.sizeof(ctypes.c_float),
            ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)),
        )

        glDrawArrays(GL_TRIANGLES, 0, int(len(self.data) / 4))

        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glDeleteBuffers(1, [buf])

        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)


class DrawColoredVerticesTask(IDrawTask):
    def __init__(self, mode):
        self.data = array.array("f")
        self.mode = mode

    def append(self, color: Color, vertices: [Vector2], apply_modelview_matrix):
        r, g, b, a = color.normalize()

        for v in vertices:
            vertex = apply_modelview_matrix(v)
            self.data.extend((vertex.x, vertex.y, r, g, b, a))

    def append_separate(
        self, colors: [Color], vertices: [Vector2], apply_modelview_matrix
    ):
        for color, vertex in zip(colors, vertices):
            vertex = apply_modelview_matrix(vertex)
            r, g, b, a = color.normalize()

            self.data.extend((vertex.x, vertex.y, r, g, b, a))

    def draw(self):
        buf = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buf)
        glBufferData(GL_ARRAY_BUFFER, self.data.tobytes(), GL_STATIC_DRAW)

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(
            2, GL_FLOAT, 6 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0)
        )

        glEnableClientState(GL_COLOR_ARRAY)
        glColorPointer(
            4,
            GL_FLOAT,
            6 * ctypes.sizeof(ctypes.c_float),
            ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)),
        )

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glDrawArrays(self.mode, 0, int(len(self.data) / 6))

        glDisable(GL_BLEND)

        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glDeleteBuffers(1, [buf])
