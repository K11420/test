#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
サンプル地図画像を作成するスクリプト
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

def create_sample_map():
    """色付きサンプル地図を作成"""
    
    # 画像サイズ
    width, height = 1200, 800
    
    # 背景（道路）を作成 - 明るいグレー
    image = np.full((height, width, 3), (220, 220, 220), dtype=np.uint8)
    
    # 建物エリアを追加 - 様々な色
    buildings = [
        # (x, y, w, h, color)
        (50, 50, 200, 150, (100, 150, 200)),    # 青い建物
        (300, 100, 150, 100, (150, 200, 100)),  # 緑の建物
        (500, 80, 180, 120, (200, 150, 100)),   # 茶色の建物
        (750, 60, 200, 180, (180, 100, 150)),   # 紫の建物
        (1000, 100, 150, 140, (150, 180, 200)), # 水色の建物
        
        (80, 300, 160, 120, (200, 200, 100)),   # 黄色い建物
        (300, 350, 140, 160, (150, 100, 200)),  # 青紫の建物
        (520, 320, 200, 180, (100, 200, 150)),  # 緑青の建物
        (800, 380, 180, 140, (200, 150, 150)),  # ピンクの建物
        
        (100, 600, 180, 120, (120, 200, 200)),  # シアンの建物
        (350, 580, 160, 140, (200, 180, 120)),  # オレンジの建物
        (600, 620, 220, 100, (180, 120, 200)),  # 薄紫の建物
        (900, 600, 200, 150, (120, 180, 120)),  # 薄緑の建物
    ]
    
    # 建物を描画
    for x, y, w, h, color in buildings:
        cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)
        # 建物の輪郭を描画
        cv2.rectangle(image, (x, y), (x + w, y + h), (80, 80, 80), 2)
    
    # 道路を描画 - 白い道路
    roads = [
        # 水平道路
        (0, 270, width, 30),     # 上部水平道路
        (0, 550, width, 30),     # 下部水平道路
        
        # 垂直道路
        (270, 0, 30, height),    # 左側垂直道路
        (480, 0, 30, height),    # 中央垂直道路
        (750, 0, 30, height),    # 右側垂直道路
    ]
    
    for x, y, w, h in roads:
        cv2.rectangle(image, (x, y), (x + w, y + h), (255, 255, 255), -1)
    
    # 公園エリアを追加 - 緑色
    parks = [
        (320, 430, 140, 100, (100, 180, 100)),   # 小さな公園
        (550, 200, 180, 100, (80, 160, 80)),     # 中央公園
    ]
    
    for x, y, w, h, color in parks:
        cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)
        # 公園に木を表現する円を追加
        for i in range(3):
            for j in range(2):
                tree_x = x + 30 + i * 40
                tree_y = y + 25 + j * 40
                if tree_x < x + w - 20 and tree_y < y + h - 20:
                    cv2.circle(image, (tree_x, tree_y), 12, (60, 140, 60), -1)
    
    # 川を追加 - 青色
    river_points = np.array([
        [0, 450], [150, 440], [300, 460], [450, 450], 
        [600, 470], [750, 460], [900, 480], [width, 475]
    ], np.int32)
    
    # 川の太さを作るために上下にオフセットした点を作成
    river_top = river_points + [0, -15]
    river_bottom = river_points + [0, 15]
    
    # 川の領域を塗りつぶし
    combined_points = np.concatenate([river_top, river_bottom[::-1]])
    cv2.fillPoly(image, [combined_points], (100, 150, 200))
    
    # 橋を追加 - 道路との交差点
    bridge_positions = [270, 480, 750]  # 垂直道路との交差点
    for bridge_x in bridge_positions:
        # 川との交差点を見つけて橋を描画
        y_start = 435
        y_end = 485
        cv2.rectangle(image, (bridge_x, y_start), (bridge_x + 30, y_end), (200, 200, 200), -1)
        # 橋の欄干
        cv2.line(image, (bridge_x, y_start), (bridge_x + 30, y_start), (150, 150, 150), 2)
        cv2.line(image, (bridge_x, y_end), (bridge_x + 30, y_end), (150, 150, 150), 2)
    
    # 駐車場エリアを追加 - アスファルト色
    parking_lots = [
        (50, 500, 200, 40, (140, 140, 140)),
        (350, 250, 120, 60, (140, 140, 140)),
        (850, 250, 140, 80, (140, 140, 140)),
    ]
    
    for x, y, w, h, color in parking_lots:
        cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)
        # 駐車枠を描画
        for i in range(0, w, 25):
            cv2.line(image, (x + i, y), (x + i, y + h), (100, 100, 100), 1)
    
    return image

def save_sample_map(filename="sample_map.png"):
    """サンプル地図を保存"""
    image = create_sample_map()
    
    # BGRからRGBに変換（OpenCVはBGRで保存するため）
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # PIL Imageとして保存
    pil_image = Image.fromarray(image_rgb)
    pil_image.save(filename)
    
    print(f"サンプル地図を作成しました: {filename}")
    print("特徴:")
    print("- 色付きの建物（複数の色）")
    print("- 白い道路ネットワーク")
    print("- 緑の公園（木付き）")
    print("- 青い川（橋付き）")
    print("- グレーの駐車場")
    print("- サイズ: 1200x800ピクセル")

if __name__ == "__main__":
    save_sample_map("/home/user/webapp/sample_map.png")