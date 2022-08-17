#!/usr/bin/python
# -*- coding:utf-8 -*-
import glob

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

mp3_dir = 'data_pic_music/music'
pic_dir = 'data_pic_music/pic'
random_display_start_time = 30
random_display_gap_time = 10

GPIO.setup(KEY_LEFT, GPIO.IN, GPIO.PUD_UP)  # 设置输入，上拉
GPIO.setup(KEY_RIGHT, GPIO.IN, GPIO.PUD_UP)

mixer.init()


class Mixer_thread(threading.Thread):  # 继承父类threading.Thread
    def __init__(self, mp3_dir):
        threading.Thread.__init__(self)
        self.mp3_paths = glob.glob(os.path.join(mp3_dir, '*.mp3'))
        self.index = 0
        self.target_index = self.index

    def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
        while True:
            if len(self.mp3_paths) > 1:
                while self.target_index == self.index:  # 相等说明没有外界修改
                    self.target_index = random.choice(range(len(self.mp3_paths)))
            if 0 <= self.target_index < len(self.mp3_paths):  # target_index有效
                self.index = self.target_index
                mixer.music.load(self.mp3_paths[self.index])
                mixer.music.play()
                while self.target_index == self.index and mixer.music.get_busy():
                    time.sleep(0.1)
            else:
                self.index = self.target_index

    def pre_music(self):
        self.target_index = (self.index + len(self.mp3_paths) - 1) % len(self.mp3_paths)

    def next_music(self):
        self.target_index = (self.index + 1) % len(self.mp3_paths)


class Items:
    def __init__(self, pic_dir):
        logging.info("epd4in01f Demo")
        self.epd = epd4in01f.EPD()
        logging.info("init")
        self.epd.init()
        # self.epd.Clear()
        self.mp3_path = None

        self.item_list = glob.glob(os.path.join(pic_dir, '*.bmp'))
        logging.info(f"len(self.item_list):{len(self.item_list)}")
        self.index = 0
        self.target_index = self.index

        self.display_thread = None

    def _display_pic(self, pic_path):
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
            self.father._display_pic(self.pic_path)

    def display_pic(self, bmp_path):
        self.index = self.target_index
        display_thread = self.Display_pic_thread(self, bmp_path)
        display_thread.start()
        while self.target_index == self.index and display_thread.is_alive():
            time.sleep(0.1)

    def display_up_pic(self):
        self.target_index = (self.index + 1) % len(self.item_list)
        logging.debug(f"self.target_index:{self.target_index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)

    def display_down_pic(self):
        self.target_index = (self.index + len(self.item_list) - 1) % len(self.item_list)
        logging.debug(f"self.target_index:{self.target_index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)

    def display_random_pic(self):
        self.target_index = random.choice(range(len(self.item_list)))
        logging.debug(f"self.target_index:{self.target_index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)


key_state = {KEY_LEFT: GPIO.HIGH, KEY_RIGHT: GPIO.HIGH}


def key_callback(channel):
    global last_press_time
    if key_state[channel] == GPIO.LOW:
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
    # items = Items(pic_dir)
    mixer_thread = Mixer_thread(mp3_dir)
    mixer_thread.start()

    while True:
        if key_state[KEY_LEFT] == GPIO.LOW:
            logging.info("KEY_LEFT low")
            # items.display_up_pic()
            mixer_thread.pre_music()
            last_press_time = time.time()
        elif key_state[KEY_RIGHT] == GPIO.LOW:
            logging.info("KEY_RIGHT low")
            # items.display_down_pic()
            mixer_thread.next_music()
            last_press_time = time.time()
        if time.time() - last_press_time > random_display_start_time and time.time() - last_random_display_time > random_display_gap_time:
            logging.info("display_random_pic")
            # items.display_random_pic()
            last_random_display_time = time.time()
