#!/bin/bash
#$ -S /bin/bash
#$ -cwd
#$ -j y
#$ -jc gs-container_g4.24h
#$ -ac d=nvcr-pytorch-2010
#$ -N stage1

/home/songjian/.conda/envs/loveda/bin/python train.py \
--model_name deeplabv2 \
--stage stage1 \
--n_class 8 \
--used_save_pseudo \
--ema \
--proto_rectify \
--moving_prototype \
--proto_consistW 10 \
--rce