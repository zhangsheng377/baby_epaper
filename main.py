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


logging.basicConfig(level=logging.INFO)

data_path = 'data'


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
    
    def display_pic_and_play_sound(self, bmp_path, mp3_path):
        thread1 = self.Display_pic_thread(self, bmp_path)
        thread1.start()
        mixer.music.load(mp3_path)
        while threading.activeCount() > 1:
            mixer.music.play()
            time.sleep(5)

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
        self.display_pic_and_play_sound(bmp_path, mp3_path)


def readchar():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def readkey(getchar_fn=None):
    getchar = getchar_fn or readchar
    c1 = getchar()
    if ord(c1) != 0x1b:
        return c1
    c2 = getchar()
    if ord(c2) != 0x5b:
        return c1
    c3 = getchar()
    return chr(0x10 + ord(c3) - 65)


items = Items(data_path)

while True:
    key = readkey()
    logging.debug(f"key:{key} ord(key):{ord(key)}")
    if key == 'q' or ord(key) == 27:
        break
    elif ord(key) == 16 or ord(key) == 19:
        # 16:up 19:left
        items.display_up_pic()
    elif ord(key) == 17 or ord(key) == 18:
        # 17:down 18:right
        items.display_down_pic()
    elif key == 'r':
        while True:
            items.display_random_pic()
            time.sleep(10)
