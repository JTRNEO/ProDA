# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import torch
import numpy as np
import scipy.misc as m
from tqdm import tqdm

from torch.utils import data
from PIL import Image
import glob

from data.augmentations import *
from data.base_dataset import BaseDataset
from data.randaugment import RandAugmentMC

import random


def recursive_glob(rootdir=".", suffix=""):
    """Performs recursive glob with given suffix and rootdir 
        :param rootdir is the root directory
        :param suffix is the suffix to be searched
    """
    return [
        os.path.join(looproot, filename)
        for looproot, _, filenames in os.walk(rootdir)  #os.walk: traversal all files in rootdir and its subfolders
        for filename in filenames
        if filename.endswith(suffix)
    ]

class Continent_loader(BaseDataset):
    """cityscapesLoader

    https://www.cityscapes-dataset.com

    Data is derived from CityScapes, and can be downloaded from here:
    https://www.cityscapes-dataset.com/downloads/

    Many Thanks to @fvisin for the loader repo:
    https://github.com/fvisin/dataset_loaders/blob/master/dataset_loaders/images/cityscapes.py
    """

    colors = [ [128, 0, 0],
               [0, 255, 36],
               [148, 148, 148],
               [255, 255, 255],
               [34, 97, 38],
               [0, 69, 255],
               [75, 181, 73],
               [222, 31, 7]
    ]

    label_colours = dict(zip(range(8), colors))

    mean_rgb = {
        # "pascal": [103.939, 116.779, 123.68],
        "continent": [0.0, 0.0, 0.0],
    }  # pascal mean for PSPNet and ICNet pre-trained model

    def __init__(self, opt, logger, augmentations = None, split='train', flag='src'):
        """__init__

        :param opt: parameters of dataset
        :param writer: save the result of experiment
        :param logger: logging file
        :param augmentations: 
        """
        
        self.opt = opt
        self.split = split
        self.flag = flag
        self.root = opt.src_rootpath if self.flag == 'src' else opt.tgt_rootpath
        self.augmentations = augmentations
        self.randaug = RandAugmentMC(2, 10)
        self.n_classes = opt.n_class
        self.img_size = (1024, 1024)
        self.mean = np.array(self.mean_rgb['continent'])
        # self.files = {}
        # self.paired_files = {}

        self.images_base = os.path.join(self.root, 'images', self.split)
        self.annotations_base = os.path.join(self.root, "labels", self.split)
        rgb_filepath_list = glob.glob(os.path.join(self.images_base, '*.tif'))
        rgb_filepath_list += glob.glob(os.path.join(self.images_base, '*.png'))
        # files = sorted(recursive_glob(rootdir=self.images_base, suffix=".png")) #find all files from rootdir and subfolders with suffix = ".png"
        # files += sorted(recursive_glob(rootdir=self.images_base, suffix=".tif"))
        rgb_filename_list = [os.path.split(fp)[-1] for fp in rgb_filepath_list]
        cls_filepath_list = []
        if self.annotations_base is not None:
            for fname in rgb_filename_list:
                cls_filepath_list.append(os.path.join(self.annotations_base, fname))
        self.rgb_filepath_list = rgb_filepath_list
        self.cls_filepath_list = cls_filepath_list
        
        self.valid_classes = [1, 2, 3, 4, 5, 6, 7, 8]
        self.class_names = ["bareland", "grass", "pavement", "road", "tree", "water", "cropland", "buildings"]
        self.to8 = dict(zip(range(8), range(8)))

        self.ignore_index = 250
        self.class_map = dict(zip(self.valid_classes, range(self.n_classes)))   #zip: return tuples

        if not self.rgb_filepath_list:
            raise Exception(
                "No files for split=[%s] found in %s" % (self.split, self.images_base)
            )

        print("Found %d %s images" % (len(self.rgb_filepath_list), self.split))
    
    def __len__(self):
        """__len__"""
        return len(self.rgb_filepath_list)

    def __getitem__(self, index):
        """__getitem__

        :param index:
        """
        img_path = self.rgb_filepath_list[index].rstrip()
        lbl_path = self.cls_filepath_list[index].rstrip()

        img = Image.open(img_path)
        lbl = Image.open(lbl_path)
        img = img.resize(self.img_size, Image.BILINEAR)
        lbl = lbl.resize(self.img_size, Image.NEAREST)
        
        img = np.array(img, dtype=np.uint8)
        lbl = np.array(lbl, dtype=np.uint8)
        lbl = self.encode_segmap(np.array(lbl, dtype=np.uint8))

        img_full = img.copy().astype(np.float64)
        img_full -= self.mean
        img_full = img_full.astype(float) / 255.0
        img_full = img_full.transpose(2, 0, 1)

        lp, lpsoft, weak_params = None, None, None
        if self.split == 'val' and self.flag == 'tgt' and self.opt.used_save_pseudo:
            if self.opt.proto_rectify:
                lpsoft = np.load(os.path.join(self.opt.path_soft, os.path.basename(img_path).replace('.tif', '.npy')))
            else:
                lp_path = os.path.join(self.opt.path_LP, os.path.basename(img_path))
                lp = Image.open(lp_path)
                lp = lp.resize(self.img_size, Image.NEAREST)
                lp = np.array(lp, dtype=np.uint8)
                if self.opt.threshold:
                    conf = np.load(os.path.join(self.opt.path_LP, os.path.basename(img_path).replace('.tif', '_conf.npy')))
                    lp[conf <= self.opt.threshold] = 250

        input_dict = {}
        if self.augmentations!=None:
            img, lbl, lp, lpsoft, weak_params = self.augmentations(img, lbl, lp, lpsoft)
            img_strong, params = self.randaug(Image.fromarray(img))
            img_strong, _, _ = self.transform(img_strong, lbl)
            input_dict['img_strong'] = img_strong
            input_dict['params'] = params

        img, lbl_, lp = self.transform(img, lbl, lp)
                
        input_dict['img'] = img
        input_dict['img_full'] = torch.from_numpy(img_full).float()
        input_dict['label'] = lbl_
        input_dict['lp'] = lp
        input_dict['lpsoft'] = lpsoft
        input_dict['weak_params'] = weak_params  #full2weak
        input_dict['img_path'] = self.rgb_filepath_list[index]

        input_dict = {k:v for k, v in input_dict.items() if v is not None}
        return input_dict

    def transform(self, img, lbl, lp=None, check=True):
        """transform

        :param img:
        :param lbl:
        """
        # img = m.imresize(
        #     img, (self.img_size[0], self.img_size[1])
        # )  # uint8 with RGB mode
        img = np.array(img)
        # img = img[:, :, ::-1]  # RGB -> BGR
        img = img.astype(np.float64)
        img -= self.mean
        img = img.astype(float) / 255.0
        # NHWC -> NCHW
        img = img.transpose(2, 0, 1)

        classes = np.unique(lbl)
        lbl = np.array(lbl)
        lbl = lbl.astype(float)
        # lbl = m.imresize(lbl, (self.img_size[0], self.img_size[1]), "nearest", mode="F")
        lbl = lbl.astype(int)

        if not np.all(classes == np.unique(lbl)):
            print("WARN: resizing labels yielded fewer classes")    #TODO: compare the original and processed ones

        if check and not np.all(np.unique(lbl[lbl != self.ignore_index]) < self.n_classes):   #todo: understanding the meaning 
            print("after det", classes, np.unique(lbl))
            raise ValueError("Segmentation map contained invalid class values")

        img = torch.from_numpy(img).float()
        lbl = torch.from_numpy(lbl).long()

        if lp is not None:
            classes = np.unique(lp)
            lp = np.array(lp)
            # if not np.all(np.unique(lp[lp != self.ignore_index]) < self.n_classes):
            #     raise ValueError("lp Segmentation map contained invalid class values")
        
            lp = torch.from_numpy(lp).long()

        return img, lbl, lp

    def decode_segmap(self, temp):
        r = temp.copy()
        g = temp.copy()
        b = temp.copy()
        for l in range(0, self.n_classes):
            r[temp == l] = self.label_colours[self.to8[l]][0]
            g[temp == l] = self.label_colours[self.to8[l]][1]
            b[temp == l] = self.label_colours[self.to8[l]][2]

        rgb = np.zeros((temp.shape[0], temp.shape[1], 3))
        rgb[:, :, 0] = r / 255.0
        rgb[:, :, 1] = g / 255.0
        rgb[:, :, 2] = b / 255.0
        return rgb

    def encode_segmap(self, mask):
        # Put all void classes to zero
        label_copy = 250 * np.ones(mask.shape, dtype=np.uint8)
        for k, v in list(self.class_map.items()):
            label_copy[mask == k] = v
        return label_copy

    def get_cls_num_list(self):
        # cls_num_list = np.array([1557726944,  254364912,  673500400,   18431664,   14431392,
        #                         29361440,    7038112,    7352368,  477239920,   40134240,
        #                         211669120,   36057968,     865184,  264786464,   17128544,
        #                         2385680,     943312,     504112,    2174560])
        return None
