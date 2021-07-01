#!/usr/bin/python
# -*- coding:utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd4in01f
import traceback
import termios
import tty
import datetime
import time
import logging
import sys
import os
import threading
from pygame import mixer
import random
import RPi.GPIO as GPIO
from enum import Enum

GPIO.setmode(GPIO.BCM)  # 设置BCM编码

KEY_LEFT = 23  # BCM引脚
KEY_RIGHT = 22


# logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG, filename="mylog.log")

data_path = 'data'
music_gap_time = 5
random_music_time = 5
random_display_start_time = 30
random_display_gap_time = 15

GPIO.setup(KEY_LEFT, GPIO.IN, GPIO.PUD_UP)  # 设置输入，上拉
GPIO.setup(KEY_RIGHT, GPIO.IN, GPIO.PUD_UP)


class Items():
    def __init__(self, data_path):
        logging.info("epd4in01f Demo")
        self.epd = epd4in01f.EPD()
        logging.info("init")
        self.epd.init()
        # self.epd.Clear()
        mixer.init()

        self.item_list = []
        for item_name in os.listdir(data_path):
            bmp_path = os.path.join(data_path, item_name, item_name+'.bmp')
            mp3_path = os.path.join(data_path, item_name, item_name+'.mp3')
            logging.debug(f"bmp_path:{bmp_path} mp3_path:{mp3_path}")
            if os.path.isfile(bmp_path):
                self.item_list.append((bmp_path, mp3_path))
        logging.info(f"len(self.item_list):{len(self.item_list)}")
        self.index = -1

    def display_pic(self, pic_path):
        try:
            # pic_path = '/home/pi/baby_epaper/epaper_test.bmp'
            # pic_path = '/home/pi/baby_epaper/test.bmp'
            # pic_path = '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/pic/4in01-1.bmp'
            logging.debug(f"read bmp file. {pic_path}")
            Himage = Image.open(pic_path)
            logging.debug(
                f"display start. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.epd.display(self.epd.getbuffer(Himage))
            logging.debug(
                f"display over. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # time.sleep(10)
        except IOError as e:
            logging.info(e)
        except KeyboardInterrupt:
            logging.info("ctrl + c:")
            epd4in01f.epdconfig.module_exit()
            exit()

    class Display_pic_thread (threading.Thread):  # 继承父类threading.Thread
        def __init__(self, father, pic_path):
            threading.Thread.__init__(self)
            self.pic_path = pic_path
            self.father = father

        def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
            self.father.display_pic(self.pic_path)

    def display_pic_and_play_sound(self, bmp_path, mp3_path, music_time=None):
        thread1 = self.Display_pic_thread(self, bmp_path)
        thread1.start()
        mixer.music.load(mp3_path)
        while threading.activeCount() > 1:
            mixer.music.play()
            time.sleep(music_gap_time)
        display_over_time = time.time()
        while music_time and time.time()-display_over_time < music_time:
            mixer.music.play()
            time.sleep(music_gap_time)

    def display_up_pic(self):
        self.index += 1
        if self.index >= len(self.item_list):
            self.index = 0
        logging.debug(f"self.index:{self.index}")
        bmp_path, mp3_path = self.item_list[self.index]
        self.display_pic_and_play_sound(bmp_path, mp3_path)

    def display_down_pic(self):
        self.index -= 1
        if self.index < 0:
            self.index = len(self.item_list)-1
        logging.debug(f"self.index:{self.index}")
        bmp_path, mp3_path = self.item_list[self.index]
        self.display_pic_and_play_sound(bmp_path, mp3_path)

    def display_random_pic(self):
        bmp_path, mp3_path = random.choice(self.item_list)
        self.display_pic_and_play_sound(
            bmp_path, mp3_path, music_time=random_music_time)


key_state = {KEY_LEFT: GPIO.HIGH, KEY_RIGHT: GPIO.HIGH}


def key_callback(channel):
    if (key_state[channel] == GPIO.LOW):
        key_state[channel] = GPIO.HIGH
    else:
        key_state[channel] = GPIO.LOW


# 在通道上添加临界值检测，忽略由于开关抖动引起的边缘操作
GPIO.add_event_detect(KEY_LEFT, GPIO.BOTH,
                      callback=key_callback, bouncetime=10)
GPIO.add_event_detect(KEY_RIGHT, GPIO.BOTH,
                      callback=key_callback, bouncetime=10)


class State(Enum):
    none = 0
    repeat = 1


state = State.none
last_press_time = time.time()
last_random_display_time = time.time()


if __name__ == '__main__':
    items = Items(data_path)

    while True:
        if key_state[KEY_LEFT] == GPIO.LOW:
            logging.info("KEY_LEFT low")
            items.display_up_pic()
            last_press_time = time.time()
        elif key_state[KEY_RIGHT] == GPIO.LOW:
            logging.info("KEY_RIGHT low")
            items.display_down_pic()
            last_press_time = time.time()

        if time.time()-last_press_time > random_display_start_time and time.time()-last_random_display_time > random_display_gap_time:
            logging.info("display_random_pic")
            items.display_random_pic()
            last_random_display_time = time.time()
