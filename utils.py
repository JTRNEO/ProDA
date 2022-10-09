# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import os
import datetime
import numpy as np
import random
import torch
import time

def get_logger(logdir):
    logger = logging.getLogger('ptsemseg')
    ts = str(datetime.datetime.now()).split('.')[0].replace(" ", "_")
    ts = ts.replace(":", "_").replace("-","_")
    file_path = os.path.join(logdir, 'run_{}.log'.format(ts))
    hdlr = logging.FileHandler(file_path)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.INFO)
    return logger

def fliplr(img):
    '''flip horizontal'''
    inv_idx = torch.arange(img.size(3)-1,-1,-1).long().cuda()  # N x C x H x W
    img_flip = img.index_select(3,inv_idx)
    return img_flip


def get_console_file_logger(name, level=logging.INFO, logdir='./baseline'):
    logger = logging.Logger(name)
    logger.setLevel(level=level)
    logger.handlers = []
    BASIC_FORMAT = "%(asctime)s, %(levelname)s:%(name)s:%(message)s"
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(BASIC_FORMAT, DATE_FORMAT)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    chlr.setLevel(level=level)

    fhlr = logging.FileHandler(os.path.join(logdir, str(time.time()) + '.log'))
    fhlr.setFormatter(formatter)
    logger.addHandler(chlr)
    logger.addHandler(fhlr)

    return logger