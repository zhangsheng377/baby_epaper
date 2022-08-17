#!/usr/bin/python
# -*- coding:utf-8 -*-
import ctypes
import glob
import inspect

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
        logging.info(f"len(self.mp3_paths):{len(self.mp3_paths)}")
        self.index = 0
        self.target_index = self.index

    def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
        while True:
            if len(self.mp3_paths) > 1:
                while self.target_index == self.index:  # 相等说明没有外界修改
                    self.target_index = random.choice(range(len(self.mp3_paths)))
            logging.debug(f"Mixer_thread run self.target_index:{self.target_index}")
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
        logging.debug(f"pre_music self.target_index:{self.target_index}")

    def next_music(self):
        self.target_index = (self.index + 1) % len(self.mp3_paths)
        logging.debug(f"next_music self.target_index:{self.target_index}")


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


class ShowPic:
    def __init__(self, pic_dir):
        logging.info("epd4in01f Demo")
        self.epd = epd4in01f.EPD()
        logging.info("init")
        self.epd.init()
        # self.epd.Clear()
        self.mp3_path = None

        self.item_list = glob.glob(os.path.join(pic_dir, '*.bmp'))
        logging.info(f"ShowPic len(self.item_list):{len(self.item_list)}")
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

    class Display_pic_thread(threading.Thread):  # 继承父类threading.Thread
        def __init__(self, father, pic_path):
            threading.Thread.__init__(self)
            self.pic_path = pic_path
            self.father = father

        def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
            self.father._display_pic(self.pic_path)

    def display_pic(self, bmp_path):
        if self.display_thread:
            logging.debug(f"ShowPic display_pic self.display_thread:{self.display_thread}")
            stop_thread(self.display_thread)
            self.display_thread = None
            logging.debug(f"ShowPic display_pic self.display_thread:{self.display_thread}")
        self.index = self.target_index
        self.display_thread = self.Display_pic_thread(self, bmp_path)
        self.display_thread.start()

    def display_up_pic(self):
        self.target_index = (self.index + 1) % len(self.item_list)
        logging.debug(f"ShowPic self.target_index:{self.target_index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)

    def display_down_pic(self):
        self.target_index = (self.index + len(self.item_list) - 1) % len(self.item_list)
        logging.debug(f"ShowPic self.target_index:{self.target_index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)

    def display_random_pic(self):
        if self.display_thread:
            logging.debug(
                f"ShowPic display_random_pic self.target_index:{self.target_index} self.index:{self.index} self.display_thread:{self.display_thread}")
            while self.target_index == self.index and self.display_thread.is_alive():
                time.sleep(0.1)
            logging.debug(
                f"ShowPic display_random_pic self.target_index:{self.target_index} self.index:{self.index} self.display_thread:{self.display_thread} thread over")
        while self.target_index == self.index:
            self.target_index = random.choice(range(len(self.item_list)))
        logging.debug(f"ShowPic display_random_pic self.target_index:{self.target_index} self.index:{self.index}")
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
    show_pic = ShowPic(pic_dir)
    show_pic.display_random_pic()
    mixer_thread = Mixer_thread(mp3_dir)
    mixer_thread.start()

    while True:
        if key_state[KEY_LEFT] == GPIO.LOW:
            logging.info("KEY_LEFT low")
            # show_pic.display_up_pic()
            mixer_thread.pre_music()
            last_press_time = time.time()
        elif key_state[KEY_RIGHT] == GPIO.LOW:
            logging.info("KEY_RIGHT low")
            # show_pic.display_down_pic()
            mixer_thread.next_music()
            last_press_time = time.time()
        if time.time() - last_press_time > random_display_start_time and time.time() - last_random_display_time > random_display_gap_time:
            logging.info("display_random_pic")
            show_pic.display_random_pic()
            last_random_display_time = time.time()
