#!/usr/bin/python
# -*- coding:utf-8 -*-
import ctypes
import glob
import inspect
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing import cpu_count

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
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
logging.basicConfig(level=logging.DEBUG, filename="mylog.log",
                    format='%(asctime)s  %(filename)s  %(lineno)d  %(funcName)s : %(levelname)s  %(message)s')

mp3_dir = 'data_pic_music/music'
pic_dir = 'data_pic_music/pic'
# pic_dir = 'data_pic_music/pic_bak'
# pic_dir = 'data_test/pic'
random_display_start_time = 30
random_display_gap_time = 10
pic_display_time = 60

color_act = [
    [255, 255, 255],  # 白色
    [0, 0, 0],  # 黑色
    [0, 0, 255],  # 蓝色
    [255, 128, 0],  # 橙色
    [255, 255, 0],  # 黄色
    [255, 0, 0],  # 红色
    [0, 255, 0],  # 绿色
    # [67, 138, 28],
    # [100, 64, 255],
    # [191, 0, 0],
    # [255, 243, 56],
    # [232, 126, 0],
    # [194 ,164 , 244],
]

GPIO.setup(KEY_LEFT, GPIO.IN, GPIO.PUD_UP)  # 设置输入，上拉
GPIO.setup(KEY_RIGHT, GPIO.IN, GPIO.PUD_UP)

mixer.init()
mixer.music.set_volume(0.3)


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
                logging.info(f"Mixer_thread run mp3_path:{self.mp3_paths[self.index]}")
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


# def _async_raise(tid, exctype):
#     """raises the exception, performs cleanup if needed"""
#     tid = ctypes.c_long(tid)
#     if not inspect.isclass(exctype):
#         exctype = type(exctype)
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         # """if it returns a number greater than one, you're in trouble,
#         # and you should call it again with exc=NULL to revert the effect"""
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")
#
#
# def stop_thread(thread):
#     _async_raise(thread.ident, SystemExit)


def _get_color_distance(color_a, color_b):
    return (color_a[0] - color_b[0]) ** 2 + (color_a[1] - color_b[1]) ** 2 + (color_a[2] - color_b[2]) ** 2


def _get_closest_color(color):
    min_distance = 255 ** 2 + 255 ** 2 + 255 ** 2 + 1
    closest_color = color_act[0]
    try:
        for color_act_ in color_act:
            distance = _get_color_distance(color_act_, color)
            if distance < min_distance:
                min_distance = distance
                closest_color = color_act_
    except:
        traceback.print_exc()
    return closest_color


def _enhance_color(color):
    return np.clip((2.0 * color - 150), 0, 255)


def _trans_pic_color(img):
    img_array = np.array(img)
    height, width, channel_num = img_array.shape
    # for h in range(height):
    #     for w in range(width):
    #         img_array[h][w] = _get_closest_color(img_array[h][w])
    # executor = ThreadPoolExecutor(max_workers=cpu_count())
    executor = ProcessPoolExecutor(max_workers=cpu_count())
    for h in range(height):
        img_color = _enhance_color(img_array[h])
        img_array[h] = np.array(list(executor.map(_get_closest_color, img_color)))
    return Image.fromarray(np.uint8(img_array))


def floyd_steinberg_dither(img):
    pixel = img.load()

    x_lim, y_lim = img.size

    for y in range(1, y_lim):
        for x in range(1, x_lim):
            red_oldpixel, green_oldpixel, blue_oldpixel = pixel[x, y]
            print(f"floyd_steinberg_dither : old pixel[x, y]: {pixel[x, y]}")

            print(f"floyd_steinberg_dither : _get_closest_color(pixel[x, y]): {_get_closest_color(pixel[x, y])}")
            pixel[x, y] = tuple(_get_closest_color(pixel[x, y]))
            red_newpixel, green_newpixel, blue_newpixel = pixel[x, y]

            red_error = red_oldpixel - red_newpixel
            green_error = green_oldpixel - green_newpixel
            blue_error = blue_oldpixel - blue_newpixel

            if x < x_lim - 1:
                red = pixel[x + 1, y][0] + round(red_error * 7 / 16)
                green = pixel[x + 1, y][1] + round(green_error * 7 / 16)
                blue = pixel[x + 1, y][2] + round(blue_error * 7 / 16)

                pixel[x + 1, y] = (red, green, blue)

            if x > 1 and y < y_lim - 1:
                red = pixel[x - 1, y + 1][0] + round(red_error * 3 / 16)
                green = pixel[x - 1, y + 1][1] + round(green_error * 3 / 16)
                blue = pixel[x - 1, y + 1][2] + round(blue_error * 3 / 16)

                pixel[x - 1, y + 1] = (red, green, blue)

            if y < y_lim - 1:
                red = pixel[x, y + 1][0] + round(red_error * 5 / 16)
                green = pixel[x, y + 1][1] + round(green_error * 5 / 16)
                blue = pixel[x, y + 1][2] + round(blue_error * 5 / 16)

                pixel[x, y + 1] = (red, green, blue)

            if x < x_lim - 1 and y < y_lim - 1:
                red = pixel[x + 1, y + 1][0] + round(red_error * 1 / 16)
                green = pixel[x + 1, y + 1][1] + round(green_error * 1 / 16)
                blue = pixel[x + 1, y + 1][2] + round(blue_error * 1 / 16)

                pixel[x + 1, y + 1] = (red, green, blue)

    return img


class ShowPic(threading.Thread):
    def __init__(self, pic_dir):
        threading.Thread.__init__(self)
        logging.info("epd4in01f Demo")
        self.epd = epd4in01f.EPD()
        logging.info("init")
        self.epd.init()
        # self.epd.Clear()
        self.mp3_path = None

        self.item_list = glob.glob(os.path.join(pic_dir, '*[jpg,bmp,png]'))
        logging.info(f"ShowPic len(self.item_list):{len(self.item_list)}")
        self.index = 0
        self.target_index = self.index

        self.display_thread = None

    def _display_pic(self, pic_path):
        try:
            logging.debug(f"read bmp file. {pic_path}")
            (filepath, filename) = os.path.split(pic_path)
            cache_dir = os.path.join(filepath, '__cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file_path = os.path.join(cache_dir, filename + '.bmp')
            try:
                if not os.path.exists(cache_file_path):
                    image = Image.open(pic_path)
                    image = image.resize((640, 400))
                    image = image.transpose(Image.FLIP_LEFT_RIGHT)  # 水平翻转
                    image = image.transpose(Image.FLIP_TOP_BOTTOM)  # 垂直翻转
                    image = ImageEnhance.Color(image)
                    image = image.enhance(factor=1.5)
                    logging.debug(
                        f"_trans_pic_color start. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    # image = _trans_pic_color(image)
                    image = floyd_steinberg_dither(image)
                    image.save(cache_file_path)
                image = Image.open(cache_file_path)
            except:
                traceback.print_exc()
                image = Image.open(pic_path)
                image = image.transpose(Image.FLIP_LEFT_RIGHT)  # 水平翻转
                image = image.transpose(Image.FLIP_TOP_BOTTOM)  # 垂直翻转
            logging.debug(
                f"display start. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.epd.display(self.epd.getbuffer(image))
            logging.debug(
                f"display over. {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(pic_display_time)
        except IOError as e:
            logging.info(e)
        except KeyboardInterrupt:
            logging.info("ctrl + c:")
            epd4in01f.epdconfig.module_exit()
            exit()

    class DisplayPicThread(threading.Thread):  # 继承父类threading.Thread
        def __init__(self, father, pic_path):
            threading.Thread.__init__(self)
            self.pic_path = pic_path
            self.father = father

        def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
            self.father._display_pic(self.pic_path)

    def display_pic(self, bmp_path):
        if self.display_thread and self.display_thread.is_alive():
            logging.debug(f"ShowPic display_pic self.display_thread:{self.display_thread}")
            # stop_thread(self.display_thread)
            # self.display_thread = None
            # logging.debug(f"ShowPic display_pic self.display_thread:{self.display_thread}")
            return
        self.index = self.target_index
        self.display_thread = self.DisplayPicThread(self, bmp_path)
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
            while self.display_thread.is_alive():  # 按键不控制图片
                time.sleep(0.1)
            logging.debug(
                f"ShowPic display_random_pic self.target_index:{self.target_index} self.index:{self.index} self.display_thread:{self.display_thread} thread over")
        if len(self.item_list) > 1:
            while self.target_index == self.index:
                self.target_index = random.choice(range(len(self.item_list)))
        logging.debug(f"ShowPic display_random_pic self.target_index:{self.target_index} self.index:{self.index}")
        bmp_path = self.item_list[self.target_index]
        self.display_pic(bmp_path)

    def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
        while True:
            self.display_random_pic()
            time.sleep(1)


class KeyState(Enum):
    PRESS_DOWN = 0
    PRESS_UP = 1


key_state = {KEY_LEFT: KeyState.PRESS_UP, KEY_RIGHT: KeyState.PRESS_UP}


def key_callback(channel):
    global last_press_time
    if time.time() - last_press_time < 2:
        return
    key_state[channel] = KeyState.PRESS_DOWN
    last_press_time = time.time()


# 在通道上添加临界值检测，忽略由于开关抖动引起的边缘操作
GPIO.add_event_detect(KEY_LEFT, GPIO.RISING,
                      callback=key_callback, bouncetime=20)
GPIO.add_event_detect(KEY_RIGHT, GPIO.RISING,
                      callback=key_callback, bouncetime=20)

last_press_time = time.time()
last_random_display_time = time.time()

if __name__ == '__main__':
    show_pic = ShowPic(pic_dir)
    show_pic.start()
    mixer_thread = Mixer_thread(mp3_dir)
    mixer_thread.start()

    while True:
        if key_state[KEY_LEFT] == KeyState.PRESS_DOWN:
            logging.info("KEY_LEFT PRESS_DOWN")
            # show_pic.display_up_pic()
            mixer_thread.pre_music()
            last_press_time = time.time()
            key_state[KEY_LEFT] = KeyState.PRESS_UP
        elif key_state[KEY_RIGHT] == KeyState.PRESS_DOWN:
            logging.info("KEY_RIGHT low")
            # show_pic.display_down_pic()
            mixer_thread.next_music()
            last_press_time = time.time()
            key_state[KEY_RIGHT] = KeyState.PRESS_UP
        if time.time() - last_press_time > random_display_start_time and time.time() - last_random_display_time > random_display_gap_time:
            # logging.info("display_random_pic")
            # show_pic.display_random_pic()
            last_random_display_time = time.time()
