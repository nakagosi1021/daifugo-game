from __future__ import annotations

from dataclasses import dataclass

import pygame

from card import Card


WHITE = (252, 250, 244)
BLACK = (30, 31, 34)
RED = (190, 36, 50)
PURPLE = (110, 61, 158)
GOLD = (225, 176, 52)
BLUE = (45, 78, 145)
BACK_BLUE = (31, 66, 130)
BACK_LIGHT = (113, 157, 216)
SHADOW = (14, 61, 39)
SELECTED = (255, 219, 68)
CREAM = (242, 235, 210)
SKIN = (242, 199, 158)


@dataclass(slots=True)
class CardFonts:
    corner: pygame.font.Font
    suit: pygame.font.Font
    center: pygame.font.Font
    face: pygame.font.Font
    tiny: pygame.font.Font


def _card_color(card: Card) -> tuple[int, int, int]:
    if card.is_joker:
        return PURPLE
    return RED if card.suit in ("♥", "♦") else BLACK


def _corner_stack(
    rank: str,
    suit: str,
    fonts: CardFonts,
    color: tuple[int, int, int],
) -> pygame.Surface:
    """数字とスートを1つの部品にまとめ、重なりを防ぐ。"""
    rank_surface = fonts.corner.render(rank, True, color)
    suit_surface = fonts.tiny.render(suit, True, color)
    gap = -1
    width = max(rank_surface.get_width(), suit_surface.get_width()) + 2
    height = rank_surface.get_height() + suit_surface.get_height() + gap
    stack = pygame.Surface((width, height), pygame.SRCALPHA)
    stack.blit(
        rank_surface,
        ((width - rank_surface.get_width()) // 2, 0),
    )
    stack.blit(
        suit_surface,
        (
            (width - suit_surface.get_width()) // 2,
            rank_surface.get_height() + gap,
        ),
    )
    return stack


def _draw_corners(
    surface: pygame.Surface,
    rect: pygame.Rect,
    rank: str,
    suit: str,
    fonts: CardFonts,
    color: tuple[int, int, int],
) -> None:
    stack = _corner_stack(rank, suit, fonts, color)
    surface.blit(stack, (rect.x + 5, rect.y + 4))

    rotated = pygame.transform.rotate(stack, 180)
    surface.blit(
        rotated,
        (
            rect.right - rotated.get_width() - 5,
            rect.bottom - rotated.get_height() - 4,
        ),
    )


def _pip_positions(count: int) -> tuple[tuple[float, float], ...]:
    patterns: dict[int, tuple[tuple[float, float], ...]] = {
        2: ((0.50, 0.15), (0.50, 0.85)),
        3: ((0.50, 0.13), (0.50, 0.50), (0.50, 0.87)),
        4: ((0.24, 0.18), (0.76, 0.18), (0.24, 0.82), (0.76, 0.82)),
        5: ((0.24, 0.17), (0.76, 0.17), (0.50, 0.50), (0.24, 0.83), (0.76, 0.83)),
        6: ((0.24, 0.13), (0.76, 0.13), (0.24, 0.50), (0.76, 0.50), (0.24, 0.87), (0.76, 0.87)),
        7: ((0.24, 0.10), (0.76, 0.10), (0.50, 0.30), (0.24, 0.50), (0.76, 0.50), (0.24, 0.90), (0.76, 0.90)),
        8: ((0.24, 0.08), (0.76, 0.08), (0.24, 0.36), (0.76, 0.36), (0.24, 0.64), (0.76, 0.64), (0.24, 0.92), (0.76, 0.92)),
        9: ((0.24, 0.07), (0.76, 0.07), (0.24, 0.34), (0.76, 0.34), (0.50, 0.50), (0.24, 0.66), (0.76, 0.66), (0.24, 0.93), (0.76, 0.93)),
        10: ((0.24, 0.05), (0.76, 0.05), (0.24, 0.27), (0.76, 0.27), (0.24, 0.50), (0.76, 0.50), (0.24, 0.73), (0.76, 0.73), (0.24, 0.95), (0.76, 0.95)),
    }
    return patterns.get(count, ())


def _draw_number_art(
    surface: pygame.Surface,
    card: Card,
    rect: pygame.Rect,
    fonts: CardFonts,
) -> None:
    color = _card_color(card)
    art = pygame.Rect(
        rect.x + 16,
        rect.y + 28,
        rect.width - 32,
        rect.height - 56,
    )

    if card.rank == "A":
        pip = fonts.center.render(card.suit, True, color)
        surface.blit(pip, pip.get_rect(center=art.center))
        return

    count = int(card.rank)
    pip_font = fonts.suit if count <= 6 else fonts.tiny

    for x_ratio, y_ratio in _pip_positions(count):
        center = (
            int(art.left + art.width * x_ratio),
            int(art.top + art.height * y_ratio),
        )
        pip = pip_font.render(card.suit, True, color)
        surface.blit(pip, pip.get_rect(center=center))


def _draw_face_art(
    surface: pygame.Surface,
    card: Card,
    rect: pygame.Rect,
    fonts: CardFonts,
) -> None:
    color = _card_color(card)
    art = pygame.Rect(
        rect.x + 14,
        rect.y + 27,
        rect.width - 28,
        rect.height - 54,
    )

    pygame.draw.rect(surface, CREAM, art, border_radius=5)
    pygame.draw.rect(surface, color, art, width=1, border_radius=5)
    pygame.draw.line(
        surface,
        (214, 198, 160),
        (art.left + 4, art.centery),
        (art.right - 4, art.centery),
        1,
    )

    center_x = art.centerx
    head_y = art.top + 18
    radius = max(5, art.width // 7)
    body_color = BLUE if card.rank == "J" else RED if card.rank == "Q" else PURPLE

    # 胴体
    pygame.draw.polygon(
        surface,
        body_color,
        [
            (art.left + 7, art.bottom - 5),
            (center_x - 7, head_y + radius - 1),
            (center_x + 7, head_y + radius - 1),
            (art.right - 7, art.bottom - 5),
        ],
    )
    pygame.draw.polygon(
        surface,
        GOLD,
        [
            (center_x - 6, head_y + radius + 2),
            (center_x, head_y + radius + 10),
            (center_x + 6, head_y + radius + 2),
        ],
    )

    # 顔
    pygame.draw.circle(surface, SKIN, (center_x, head_y), radius)
    pygame.draw.circle(surface, BLACK, (center_x - 2, head_y - 1), 1)
    pygame.draw.circle(surface, BLACK, (center_x + 2, head_y - 1), 1)
    pygame.draw.line(
        surface,
        BLACK,
        (center_x - 2, head_y + 3),
        (center_x + 2, head_y + 3),
        1,
    )

    if card.rank == "K":
        crown_y = head_y - radius - 5
        pygame.draw.polygon(
            surface,
            GOLD,
            [
                (center_x - radius, crown_y + 6),
                (center_x - 3, crown_y),
                (center_x, crown_y + 5),
                (center_x + 3, crown_y),
                (center_x + radius, crown_y + 6),
            ],
        )
        pygame.draw.arc(
            surface,
            (95, 55, 30),
            pygame.Rect(center_x - radius, head_y, radius * 2, radius * 2),
            0,
            3.14,
            2,
        )
    elif card.rank == "Q":
        crown_y = head_y - radius - 4
        pygame.draw.polygon(
            surface,
            GOLD,
            [
                (center_x - radius, crown_y + 6),
                (center_x - 3, crown_y),
                (center_x, crown_y + 5),
                (center_x + 3, crown_y),
                (center_x + radius, crown_y + 6),
            ],
        )
        pygame.draw.arc(
            surface,
            (80, 47, 32),
            pygame.Rect(
                center_x - radius - 2,
                head_y - radius,
                radius * 2 + 4,
                radius * 3,
            ),
            0.15,
            2.99,
            2,
        )
    else:
        hat_y = head_y - radius - 4
        pygame.draw.polygon(
            surface,
            BLUE,
            [
                (center_x - radius - 1, hat_y + 7),
                (center_x, hat_y),
                (center_x + radius + 1, hat_y + 7),
            ],
        )
        pygame.draw.circle(surface, GOLD, (center_x, hat_y), 2)

    # 下部に小さなスートを置く。人物や隅の記号と重ならない。
    suit = fonts.tiny.render(card.suit, True, color)
    surface.blit(suit, suit.get_rect(center=(center_x, art.bottom - 8)))


def _draw_joker_art(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fonts: CardFonts,
) -> None:
    art = pygame.Rect(
        rect.x + 14,
        rect.y + 27,
        rect.width - 28,
        rect.height - 54,
    )
    pygame.draw.rect(surface, (239, 229, 247), art, border_radius=5)
    pygame.draw.rect(surface, PURPLE, art, width=1, border_radius=5)

    center_x = art.centerx
    face_y = art.top + 19
    radius = max(5, art.width // 7)

    pygame.draw.circle(surface, SKIN, (center_x, face_y), radius)
    pygame.draw.polygon(
        surface,
        PURPLE,
        [
            (center_x - radius - 3, face_y - radius + 2),
            (center_x - 3, face_y - radius - 9),
            (center_x + 1, face_y - radius + 1),
            (center_x + radius + 3, face_y - radius - 7),
            (center_x + radius, face_y - radius + 5),
            (center_x - radius, face_y - radius + 5),
        ],
    )
    pygame.draw.circle(surface, GOLD, (center_x - 3, face_y - radius - 9), 2)
    pygame.draw.circle(surface, GOLD, (center_x + radius + 3, face_y - radius - 7), 2)
    pygame.draw.circle(surface, BLACK, (center_x - 2, face_y - 1), 1)
    pygame.draw.circle(surface, BLACK, (center_x + 2, face_y - 1), 1)
    pygame.draw.arc(
        surface,
        RED,
        pygame.Rect(center_x - 4, face_y + 1, 8, 6),
        0,
        3.14,
        1,
    )

    collar_y = face_y + radius + 3
    pygame.draw.polygon(
        surface,
        RED,
        [
            (art.left + 5, collar_y),
            (center_x - 7, collar_y + 8),
            (center_x, collar_y),
            (center_x + 7, collar_y + 8),
            (art.right - 5, collar_y),
        ],
    )

    label = fonts.tiny.render("JOKER", True, PURPLE)
    surface.blit(label, label.get_rect(center=(center_x, art.bottom - 8)))


def draw_card_front(
    surface: pygame.Surface,
    card: Card,
    rect: pygame.Rect,
    fonts: CardFonts,
    selected: bool = False,
    draw_shadow: bool = True,
    dimmed: bool = False,
) -> None:
    if draw_shadow:
        pygame.draw.rect(surface, SHADOW, rect.move(4, 5), border_radius=8)

    pygame.draw.rect(surface, WHITE, rect, border_radius=8)
    pygame.draw.rect(
        surface,
        SELECTED if selected else BLACK,
        rect,
        width=4 if selected else 2,
        border_radius=8,
    )

    previous_clip = surface.get_clip()
    surface.set_clip(rect.inflate(-2, -2))

    color = _card_color(card)
    if card.is_joker:
        rank, suit = "JK", "★"
    else:
        rank, suit = card.rank, card.suit

    _draw_corners(surface, rect, rank, suit, fonts, color)

    if card.is_joker:
        _draw_joker_art(surface, rect, fonts)
    elif card.rank in ("J", "Q", "K"):
        _draw_face_art(surface, card, rect, fonts)
    else:
        _draw_number_art(surface, card, rect, fonts)

    surface.set_clip(previous_clip)

    if dimmed:
        overlay = pygame.Surface(
            (rect.width, rect.height),
            pygame.SRCALPHA,
        )
        pygame.draw.rect(
            overlay,
            (18, 25, 23, 165),
            overlay.get_rect(),
            border_radius=8,
        )
        surface.blit(overlay, rect.topleft)
        pygame.draw.rect(
            surface,
            (75, 82, 79),
            rect,
            width=2,
            border_radius=8,
        )


def draw_card_back(
    surface: pygame.Surface,
    rect: pygame.Rect,
    draw_shadow: bool = True,
) -> None:
    if draw_shadow:
        pygame.draw.rect(surface, SHADOW, rect.move(3, 4), border_radius=7)

    pygame.draw.rect(surface, WHITE, rect, border_radius=7)
    pygame.draw.rect(surface, BLACK, rect, width=2, border_radius=7)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, BACK_BLUE, inner, border_radius=5)
    pygame.draw.rect(surface, WHITE, inner, width=2, border_radius=5)

    previous_clip = surface.get_clip()
    surface.set_clip(inner)
    step = 10
    for x in range(inner.x - inner.height, inner.right + inner.height, step):
        pygame.draw.line(
            surface,
            BACK_LIGHT,
            (x, inner.bottom),
            (x + inner.height, inner.top),
            1,
        )
        pygame.draw.line(
            surface,
            (22, 47, 105),
            (x, inner.top),
            (x + inner.height, inner.bottom),
            1,
        )
    surface.set_clip(previous_clip)

    center = pygame.Rect(
        0,
        0,
        max(12, rect.width // 3),
        max(18, rect.height // 3),
    )
    center.center = rect.center
    pygame.draw.rect(surface, WHITE, center, width=2, border_radius=4)
    pygame.draw.circle(surface, GOLD, center.center, max(3, center.width // 7))
