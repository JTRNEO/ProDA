#!/bin/bash
#$ -S /bin/bash
#$ -cwd
#$ -j y
#$ -jc gs-container_g4.24h
#$ -ac d=nvcr-pytorch-2010
#$ -N ProDA

files=(Asia Africa Europe CentralAmerica NorthAmerica SouthAmerica Oceania)
S=()
T=()
max=${#files[@]}
for ((idxA=0; idxA<max; idxA++)); do
  for ((idxB=idxA+1; idxB<max; idxB++)); do
    S+=(${files[$idxA]})
    S+=(${files[$idxB]})
    T+=(${files[$idxB]})
    T+=(${files[$idxA]})
  done  
done
#warm-up stage
/home/songjian/.conda/envs/loveda/bin/python train.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--n_class=8 \
--model_name=deeplabv2 \
--stage=warm_up \
--freeze_bn \
--gan=LS \
--lr=2.5e-4 \
--adv=0.01 \
--no_resume
#generate pseudo labels at warm-up
/home/songjian/.conda/envs/loveda/bin/python generate_pseudo_label.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--soft \
--stage=stage1 \
--n_class=8 \
--save_path=Pseudo/warmup \
--no_droplast
#calculate init centroid
/home/songjian/.conda/envs/loveda/bin/python calc_prototype.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--stage=stage1 \
--n_class=8
#stage1
/home/songjian/.conda/envs/loveda/bin/python train.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--n_class=8 \
--path_soft=Pseudo/warmup \
--model_name=deeplabv2 \
--stage=stage1 \
--used_save_pseudo \
--ema \
--proto_rectify \
--moving_prototype \
--proto_consistW=10 \
--rce
#generate pseudo labels at stage1
/home/songjian/.conda/envs/loveda/bin/python generate_pseudo_label.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--flip \
--stage=stage2 \
--n_class=8 \
--save_path=Pseudo/stage1 \
--no_droplast
#stage2
/home/songjian/.conda/envs/loveda/bin/python train.py \
--src_dataset=${S[$(($SGE_TASK_ID-1))]} \
--tgt_dataset=${T[$(($SGE_TASK_ID-1))]} \
--n_class=8 \
--path_LP=Pseudo/stage1 \
--model_name=deeplabv2 \
--stage=stage2 \
--S_pseudo=1 \
--threshold=0.95 \
--used_save_pseudo \
--distillation=1 \
--student_init=simclr \
--finetune \
--lr=6e-4 \
--bn_clr \
--no_resume