import pygame

from deck import Deck


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60


def create_and_show_hands() -> None:
    """カードを作成し、4人に配った結果をターミナルに表示する。"""
    deck = Deck()

    print(f"作成されたカードの枚数：{len(deck.cards)}枚")

    deck.shuffle()
    hands = deck.deal(number_of_players=4)

    player_names = ("あなた", "CPU1", "CPU2", "CPU3")

    print("\n===== カード配布結果 =====")

    for player_name, hand in zip(player_names, hands):
        hand_text = " ".join(str(card) for card in hand)

        print(f"\n{player_name}：{len(hand)}枚")
        print(hand_text)


def main() -> None:
    create_and_show_hands()

    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )
    pygame.display.set_caption("大富豪ゲーム")

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((30, 120, 70))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()