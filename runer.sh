#!/bin/bash


# 首先确保 pip3 对应的是 /usr/bin/python3
# 如果是，则用它来安装

/usr/bin/python3 -m pip install --user google-ai-generativelanguage Pillow --break-system-packages
sudo /usr/bin/pip3 install google-ai-generativelanguage Pillow --break-system-packages
