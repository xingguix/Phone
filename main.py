import pygame.mixer as mixer

from time import sleep
from phone_control import get_call_state, pick_up, hang_up, PhoneState
from enum import Enum

class BotState(Enum):
    IDLE = 0
    PLAYING = 1

mixer.init()
state :BotState = BotState.IDLE


def play_music(path: str):
    mixer.music.stop()
    mixer.music.load(path)
    mixer.music.play()

def stop_music():
    mixer.music.stop()


def main():
    global state
    while True:
        phone_state = get_call_state()
        match state:
            case BotState.IDLE:
                if phone_state == PhoneState.RINGING:
                    sleep(1)
                    pick_up()
                    sleep(0.3)
                    play_music("Nicky Youre - Mile Away.mp3")
                    state = BotState.PLAYING
            case BotState.PLAYING:
                if phone_state == PhoneState.IDLE \
                or (phone_state == PhoneState.CALLING and not mixer.music.get_busy()):
                    hang_up()
                    stop_music()
                    state = BotState.IDLE
            
        sleep(0.5)

if __name__ == "__main__":
    main()
