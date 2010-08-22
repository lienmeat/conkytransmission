#!/bin/bash

luatxt='######################################################\n# - load lua script for use with conkytransmission - #\n######################################################\nlua_load ~/.conkytransmission/conkytransmission.lua\n'

pytxt1='#############################################'
pytxt2='# - run conkytransmission every 3 seconds - #'
pytxt3='#############################################'
pytxt4='${execpi 3 ~/.conkytransmission/conkytransmission.py}'

cp -R .conkytransmission ~/
chmod 775 ~/.conkytransmission/conkytransmission.py

if [ -f ~/.conkyrc ]
then
  cp ~/.conkyrc ~/.conkyrc_bkp
  sed -i "1i $luatxt" ~/.conkyrc
  echo $pytxt1 >> ~/.conkyrc
  echo $pytxt2 >> ~/.conkyrc
  echo $pytxt3 >> ~/.conkyrc
  echo $pytxt4 >> ~/.conkyrc
else
  cp ~/.conkytransmission/example.conkyrc ~/.conkyrc
fi
