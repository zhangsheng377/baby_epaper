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
music_gap_time = 2
random_music_time = 10
random_display_start_time = 30
random_display_gap_time = 10
wait_display_to_p_music_time = 15

GPIO.setup(KEY_LEFT, GPIO.IN, GPIO.PUD_UP)  # 设置输入，上拉
GPIO.setup(KEY_RIGHT, GPIO.IN, GPIO.PUD_UP)

mixer.init()


class Items():
    def __init__(self, data_path):
        logging.info("epd4in01f Demo")
        self.epd = epd4in01f.EPD()
        logging.info("init")
        self.epd.init()
        # self.epd.Clear()
        self.mp3_path = None
        mixer_thread = self.Mixer_thread(self)
        mixer_thread.start()

        self.item_list = get_item_list(data_path)
        logging.info(f"len(self.item_list):{len(self.item_list)}")
        self.index = -1

    class Mixer_thread (threading.Thread):  # 继承父类threading.Thread
        def __init__(self, father):
            threading.Thread.__init__(self)
            self.father = father

        def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
            while True:
                if self.father.mp3_path is not None:
                    mixer.music.load(self.father.mp3_path)
                    mixer.music.play()
                    while mixer.music.get_busy():
                        time.sleep(0.1)
                time.sleep(music_gap_time)

    def display_pic(self, pic_path):
        try:
            logging.debug(f"read bmp file. {pic_path}")
            Himage = Image.open(pic_path)
            Himage = Himage.transpose(Image.FLIP_LEFT_RIGHT)  # 水平翻转
            Himage = Himage.transpose(Image.FLIP_TOP_BOTTOM)  # 垂直翻转
            logging.debug(
                f"display start. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.epd.display(self.epd.getbuffer(Himage))
            logging.debug(
                f"display over. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        self.mp3_path = None
        display_thread = self.Display_pic_thread(self, bmp_path)
        display_thread.start()
        display_start_time = time.time()
        while time.time()-display_start_time < wait_display_to_p_music_time:
            time.sleep(0.1)
        self.mp3_path = mp3_path
        while display_thread.is_alive():
            time.sleep(0.1)

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


def get_item_list(data_path):
    item_list = []
    for item_name in os.listdir(data_path):
        bmp_path = os.path.join(data_path, item_name, item_name+'.bmp')
        mp3_path = os.path.join(data_path, item_name, item_name+'.mp3')
        logging.debug(f"bmp_path:{bmp_path} mp3_path:{mp3_path}")
        if os.path.isfile(bmp_path):
            item_list.append((bmp_path, mp3_path))
    item_list = sorted(item_list, key=lambda item: item[0])
    return item_list


key_state = {KEY_LEFT: GPIO.HIGH, KEY_RIGHT: GPIO.HIGH}


def key_callback(channel):
    global last_press_time
    if (key_state[channel] == GPIO.LOW):
        key_state[channel] = GPIO.HIGH
    else:
        key_state[channel] = GPIO.LOW
    last_press_time = time.time()


# 在通道上添加临界值检测，忽略由于开关抖动引起的边缘操作
GPIO.add_event_detect(KEY_LEFT, GPIO.BOTH,
                      callback=key_callback, bouncetime=10)
GPIO.add_event_detect(KEY_RIGHT, GPIO.BOTH,
                      callback=key_callback, bouncetime=10)


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
