import pygame
from pygame.math import Vector2

from OpenGL.GL import *


class ImageSprite:
    def __init__(self, img: pygame.surface.Surface, *, want_mipmap: bool):
        self.img = img
        self.width, self.height = self.img.get_size()
        self.want_mipmap = want_mipmap
        self._texture = None

    @classmethod
    def load(cls, filename: str):
        return cls(pygame.image.load(filename).convert_alpha(), want_mipmap=True)

    @property
    def size(self):
        return Vector2(self.width, self.height)

    def _get_texture(self):
        if self._texture is None:
            self._texture = Texture(self, generate_mipmaps=self.want_mipmap)

        return self._texture


class AnimatedImageSprite:
    def __init__(self, frames: list[ImageSprite], *, delay_ms: int):
        self.frames = frames
        self.delay_ms = delay_ms

    def get(self, ctx):
        pos = int((ctx.now * 1000) / self.delay_ms)
        return self.frames[pos % len(self.frames)]


class Texture:
    def __init__(self, sprite: ImageSprite, *, generate_mipmaps: bool):
        self.id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.id)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            sprite.width,
            sprite.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        view = sprite.img.get_buffer()
        for y in range(sprite.height):
            start = y * sprite.img.get_pitch()
            pixeldata = view.raw[
                start : start + sprite.width * sprite.img.get_bytesize()
            ]
            glTexSubImage2D(
                GL_TEXTURE_2D,
                0,
                0,
                y,
                sprite.width,
                1,
                GL_BGRA,
                GL_UNSIGNED_BYTE,
                pixeldata,
            )

        if generate_mipmaps:
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(
                GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR
            )
        else:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glBindTexture(GL_TEXTURE_2D, 0)

    def __del__(self):
        glDeleteTextures([self.id])
