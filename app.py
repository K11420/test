# -*- coding: utf-8 -*-
"""
高速CV経路検出システム - Python版
高度な二値化処理機能付き

Features:
- 5種類の高度な二値化処理（Otsu法、適応的閾値など）
- A*・BFS・Dijkstraアルゴリズム
- リアルタイムプレビュー
- 高速画像処理とノイズ除去
"""

from flask import Flask, request, render_template, jsonify, send_from_directory
from flask_cors import CORS
import numpy as np
import cv2
import base64
from PIL import Image
import io
import json
import heapq
from collections import deque
from typing import List, Tuple, Dict, Optional, Any
import time
import os
import math
from scipy import stats
from skimage.morphology import skeletonize, thin
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN

def convert_numpy_types(obj):
    """numpy型をPython標準型に再帰的に変換する"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj

app = Flask(__name__)
CORS(app)

class LandmarkDetector:
    """★改良版: OCRを使った実際のランドマーク・店名検出クラス"""
    
    def __init__(self):
        # OCRで認識可能なランドマークキーワード
        self.landmark_keywords = [
            "店", "ショップ", "レストラン", "カフェ", "コーヒー", "銀行", "ATM",
            "エレベーター", "階段", "トイレ", "受付", "案内", "出入口", "入口", "出口",
            "駐車場", "エスカレーター", "自販機", "薬局", "病院", "コンビニ",
            "書店", "図書館", "会議室", "オフィス", "待合室", "ロビー", "Room", "部屋"
        ]
        
        # 方向を示すキーワード
        self.direction_keywords = [
            "角", "曲がり角", "交差点", "分岐", "通路", "廊下", "ホール"
        ]
        
        # OCR初期化（pytesseract）
        try:
            import pytesseract
            self.ocr_available = True
            # Tesseractの設定（日本語＋英語対応）
            self.ocr_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン一二三四五六七八九十室店舗銀行受付案内階段'
        except ImportError:
            self.ocr_available = False
            print("⚠️ pytesseract not available, using fallback landmark detection")
    
    def detect_landmarks_around_position(self, image, position, radius=80):
        """★改良版: 地図画像からOCRでランドマークを検出"""
        if image is None:
            return "未知の地点"
        
        x, y = position
        height, width = image.shape[:2]
        
        # 検索範囲を設定（指定位置周辺）
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(width, x + radius)
        y2 = min(height, y + radius)
        
        # 検索範囲を画像から切り出し
        roi = image[y1:y2, x1:x2]
        
        if roi.size == 0:
            return "不明な地点"
        
        try:
            # OCR処理を実行（pytesseractが必要）
            extracted_text = self.extract_text_from_image(roi)
            
            if extracted_text:
                # 抽出されたテキストをランドマーク名として整理
                cleaned_landmarks = self.clean_extracted_landmarks(extracted_text)
                if cleaned_landmarks:
                    return cleaned_landmarks[0]  # 最も適切なランドマークを返す
                    
        except Exception as e:
            print(f"OCR処理エラー: {e}")
        
        # OCRでテキストが見つからない場合は構造解析ベースのランドマーク検出
        return self.detect_structural_landmarks(image, position, radius)
    
    def extract_text_from_image(self, roi):
        """画像からテキストを抽出（OCR）- 改良版"""
        try:
            import pytesseract
            
            # ROIサイズが小さすぎる場合はスキップ
            if roi.shape[0] < 20 or roi.shape[1] < 20:
                return ""
            
            # 画像をグレースケールに変換
            if len(roi.shape) == 3:
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            else:
                gray_roi = roi
            
            # 画像を拡大してOCR精度を向上
            scale_factor = 3
            upscaled = cv2.resize(gray_roi, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            
            # 二値化処理
            _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # ノイズ除去
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 複数のOCR設定を試行
            configs = [
                '--oem 3 --psm 8 -l jpn+eng',  # 単語認識
                '--oem 3 --psm 7 -l jpn+eng',  # 単行認識
                '--oem 3 --psm 6 -l jpn+eng',  # 単一ブロック
                '--oem 3 --psm 13 -l jpn+eng'  # 文字認識
            ]
            
            best_text = ""
            max_confidence = 0
            
            for config in configs:
                try:
                    # テキスト抽出
                    text = pytesseract.image_to_string(cleaned, config=config)
                    text = text.strip()
                    
                    # 信頼度を取得（利用可能な場合）
                    if text and len(text) >= 2:
                        confidence = len(text) * 10  # 簡易信頼度計算
                        if confidence > max_confidence:
                            max_confidence = confidence
                            best_text = text
                            
                except:
                    continue
            
            return best_text
            
        except ImportError:
            # pytesseractがインストールされていない場合は簡易検出
            print("pytesseract未インストール - 簡易テキスト検出を使用")
            return self.simple_text_detection(roi)
        except Exception as e:
            print(f"OCRエラー: {e}")
            return ""
    
    def simple_text_detection(self, roi):
        """OCRライブラリが利用できない場合の簡易テキスト検出"""
        # 簡易的にエッジ検出でテキスト様のパターンを探す
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi
        
        # テキストの可能性がある領域を検出
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # テキスト様の矩形を検出
        text_areas = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # テキストらしい矩形の条件
            if 15 < w < roi.shape[1] * 0.8 and 8 < h < roi.shape[0] * 0.3 and 1.5 < aspect_ratio < 8:
                text_areas.append((x, y, w, h))
        
        if text_areas:
            return "テキストエリア"
        
        return ""
    
    def clean_extracted_landmarks(self, raw_text):
        """抽出されたテキストを整理してランドマーク名にする - 改良版"""
        if not raw_text:
            return []
        
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        landmarks = []
        
        # よく知られたランドマークキーワード（優先度付き）
        priority_keywords = {
            'エントランス': 'エントランス', 'Entrance': 'エントランス',
            '受付': '受付', 'Reception': '受付',
            'カフェ': 'カフェ', 'Cafe': 'カフェ', 'Coffee': 'カフェ',
            'トイレ': 'トイレ', 'Toilet': 'トイレ', 'WC': 'トイレ',
            '会議室': '会議室', 'Meeting': '会議室',
            'エレベーター': 'エレベーター', 'EV': 'エレベーター', 'Elevator': 'エレベーター',
            '階段': '階段', 'Stairs': '階段',
            '廊下': '廊下', 'Hall': '廊下', 'Hallway': '廊下',
            '案内': '案内所', 'Info': '案内所'
        }
        
        for line in lines:
            # 英数字、ひらがな、カタカナ、漢字、スペースのみ保持
            cleaned = ''.join(c for c in line if c.isalnum() or c in 'ａ-ｚＡ-Ｚあ-んア-ン一-龯　 ・')
            cleaned = cleaned.strip()
            
            if 1 <= len(cleaned) <= 15:
                # 優先キーワードマッチング
                for keyword, standard_name in priority_keywords.items():
                    if keyword.lower() in cleaned.lower():
                        if standard_name not in landmarks:
                            landmarks.append(standard_name)
                        break
                else:
                    # 通常のフィルタリング
                    general_keywords = ['室', '店', 'ルーム', 'Room', '入口', '出口', 'オフィス', 'ホール']
                    
                    if (any(keyword in cleaned for keyword in general_keywords) or 
                        len(cleaned) >= 3 and cleaned.replace(' ', '').replace('　', '')):
                        
                        # 重複チェック
                        if cleaned not in landmarks and len([l for l in landmarks if cleaned in l or l in cleaned]) == 0:
                            landmarks.append(cleaned)
        
        return landmarks[:3]  # 最大3つのランドマークを返す
    
    def detect_structural_landmarks(self, image, position, radius):
        """構造解析ベースのランドマーク検出（OCRでテキストが見つからない場合）"""
        x, y = position
        height, width = image.shape[:2]
        
        # 位置による大まかな分類
        regions = []
        
        if x < width * 0.3:
            regions.append("左側")
        elif x > width * 0.7:
            regions.append("右側")
        else:
            regions.append("中央")
        
        if y < height * 0.3:
            regions.append("上部")
        elif y > height * 0.7:
            regions.append("下部")
        else:
            regions.append("中央")
        
        # 周辺の構造を解析
        roi_large = image[max(0, y-radius):min(height, y+radius), 
                         max(0, x-radius):min(width, x+radius)]
        
        if roi_large.size > 0:
            # エッジ密度による構造判定
            gray = cv2.cvtColor(roi_large, cv2.COLOR_BGR2GRAY) if len(roi_large.shape) == 3 else roi_large
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if edge_density > 0.15:
                structure_type = "複雑な構造"
            elif edge_density > 0.08:
                structure_type = "通路"
            else:
                structure_type = "開放エリア"
        else:
            structure_type = "エリア"
        
        # より自然なランドマーク名を生成
        region_name = "・".join(regions) if len(regions) > 1 else regions[0]
        
        landmark_options = [
            f"{region_name}の{structure_type}",
            f"{region_name}エリア",
            f"{region_name}の分岐点",
            f"{region_name}の角"
        ]
        
        # 位置のハッシュ値を使って一貫したランドマークを選択
        import hashlib
        position_hash = int(hashlib.md5(f"{x},{y}".encode()).hexdigest()[:8], 16)
        selected_landmark = landmark_options[position_hash % len(landmark_options)]
        
        return selected_landmark
    
    def detect_map_region(self, image):
        """★改良版: スマート地図領域検出（複数手法を組み合わせ）"""
        height, width = image.shape[:2] if len(image.shape) == 3 else (image.shape[0], image.shape[1])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        print(f"🔍 地図検出開始: 画像サイズ {width}x{height}")
        
        # 方法1: エッジ検出による境界検出
        edges = cv2.Canny(gray, 30, 100)  # より敏感な設定
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 方法2: 色分布による地図領域推定
        # 画像の周辺部分（余白）の色を分析
        margin = 20
        top_margin = gray[:margin, :]
        bottom_margin = gray[-margin:, :]
        left_margin = gray[:, :margin]
        right_margin = gray[:, -margin:]
        
        # 余白の平均色（背景色）を計算
        bg_color = np.mean([
            np.mean(top_margin),
            np.mean(bottom_margin), 
            np.mean(left_margin),
            np.mean(right_margin)
        ])
        
        # 方法3: 複数の候補から最適な地図領域を選択
        candidates = []
        
        if contours:
            # 適度な大きさの輪郭を候補として収集
            min_area = (width * height) * 0.1  # 最小10%
            max_area = (width * height) * 0.95  # 最大95%
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if min_area < area < max_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 長方形らしさをチェック
                    aspect_ratio = w / h if h > 0 else 0
                    if 0.3 < aspect_ratio < 3.0:  # 極端に細長くない
                        candidates.append({
                            "x": x, "y": y, "width": w, "height": h,
                            "area": area, "score": area * 0.8  # 面積ベーススコア
                        })
        
        # 方法4: 背景色差による地図領域検出
        # グレー値の分散が大きい領域を地図と仮定
        kernel_size = max(20, min(width, height) // 20)
        blur = cv2.GaussianBlur(gray, (kernel_size|1, kernel_size|1), 0)
        
        # 局所分散を計算
        mean_blur = cv2.blur(gray.astype(np.float32), (kernel_size, kernel_size))
        sqr_blur = cv2.blur((gray.astype(np.float32))**2, (kernel_size, kernel_size))
        variance = sqr_blur - mean_blur**2
        
        # 高分散領域を検出
        high_var_mask = variance > np.percentile(variance, 75)
        
        # 高分散領域の境界を検出
        high_var_contours, _ = cv2.findContours(
            high_var_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        for contour in high_var_contours:
            area = cv2.contourArea(contour)
            if area > (width * height) * 0.2:  # 20%以上の領域
                x, y, w, h = cv2.boundingRect(contour)
                candidates.append({
                    "x": x, "y": y, "width": w, "height": h,
                    "area": area, "score": area * 0.6  # 分散ベーススコア
                })
        
        # 候補がない場合は画像全体を使用
        if not candidates:
            print("📦 地図領域が検出できませんでした → 画像全体を使用")
            return {"x": 0, "y": 0, "width": width, "height": height}
        
        # 最適な候補を選択（スコア順）
        best_candidate = max(candidates, key=lambda c: c["score"])
        
        # 少し余白を追加して調整
        padding = 10
        x = max(0, best_candidate["x"] - padding)
        y = max(0, best_candidate["y"] - padding)
        w = min(width - x, best_candidate["width"] + 2 * padding)
        h = min(height - y, best_candidate["height"] + 2 * padding)
        
        result = {"x": x, "y": y, "width": w, "height": h}
        coverage = (w * h) / (width * height)
        print(f"🎯 地図領域検出: {x},{y} サイズ{w}x{h} (カバレッジ{coverage:.1%})")
        
        return result

class NavigationInstructionGenerator:
    """ナビゲーション指示生成クラス"""
    
    def __init__(self):
        self.landmark_detector = LandmarkDetector()
    
    def calculate_direction(self, p1, p2):
        """2点間の方向を計算"""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        
        if abs(dx) > abs(dy):
            return "右" if dx > 0 else "左"
        else:
            return "下" if dy > 0 else "上"
    
    def get_turn_direction(self, prev_direction, current_direction):
        """曲がる方向を判定"""
        direction_map = {"上": 0, "右": 1, "下": 2, "左": 3}
        
        if prev_direction not in direction_map or current_direction not in direction_map:
            return "直進"
        
        prev_idx = direction_map[prev_direction]
        curr_idx = direction_map[current_direction]
        
        diff = (curr_idx - prev_idx + 4) % 4
        
        if diff == 0:
            return "直進"
        elif diff == 1:
            return "右折"
        elif diff == 2:
            return "Uターン"
        elif diff == 3:
            return "左折"
        
        return "直進"
    
    def generate_navigation_instructions(self, path, original_image=None):
        """★改良版: シンプルで実用的なナビゲーション指示生成"""
        if not path or len(path) < 2:
            return []
        
        instructions = []
        
        # 最初の指示 - シンプルに
        instructions.append({
            "step": 1,
            "distance": 0,
            "instruction": "🚩 スタート地点から出発してください",
            "position": {"x": int(path[0][0]), "y": int(path[0][1])},
            "direction": "開始",
            "landmark": "スタート"
        })
        
        # 経路を重要なポイント（方向転換点）で分割
        key_points = self.identify_key_navigation_points(path)
        
        # 各キーポイントでシンプルな方向指示を生成
        for i, (point_idx, point_coord) in enumerate(key_points):
            if i == 0 or i == len(key_points) - 1:
                continue  # 最初と最後は別処理
            
            next_point_coord = key_points[i + 1][1] if i + 1 < len(key_points) else path[-1]
            
            # 方向を計算
            direction = self.calculate_direction(point_coord, next_point_coord)
            
            # 曲がり方向を判定
            prev_point_coord = key_points[i - 1][1]
            prev_direction = self.calculate_direction(prev_point_coord, point_coord)
            turn = self.get_turn_direction(prev_direction, direction)
            
            # 2点間の距離を計算（ピクセル単位）
            distance_pixels = int(math.sqrt(
                (next_point_coord[0] - point_coord[0])**2 + 
                (next_point_coord[1] - point_coord[1])**2
            ))
            
            # シンプルな方向指示
            if turn == "右折":
                instruction_text = f"➡️ 右に曲がって約{distance_pixels}m進んでください"
            elif turn == "左折":
                instruction_text = f"⬅️ 左に曲がって約{distance_pixels}m進んでください"
            elif turn == "Uターン":
                instruction_text = f"🔙 Uターンして約{distance_pixels}m進んでください"
            else:
                instruction_text = f"⬆️ 直進して約{distance_pixels}m進んでください"
            
            instructions.append({
                "step": len(instructions) + 1,
                "distance": distance_pixels,
                "instruction": instruction_text,
                "position": {"x": int(point_coord[0]), "y": int(point_coord[1])},
                "direction": direction,
                "turn": turn,
                "landmark": f"地点{len(instructions)}",
                "next_landmark": f"地点{len(instructions)+1}"
            })
        
        # 最終指示
        instructions.append({
            "step": len(instructions) + 1,
            "distance": 0,
            "instruction": "🏁 目的地に到着しました！",
            "position": {"x": int(path[-1][0]), "y": int(path[-1][1])},
            "direction": "到着",
            "landmark": "ゴール"
        })
        
        return instructions
    
    def identify_key_navigation_points(self, path):
        """経路から重要なナビゲーションポイント（方向転換点）を特定（改善版）"""
        if len(path) < 3:
            return [(0, path[0]), (len(path)-1, path[-1])]
        
        key_points = [(0, path[0])]  # 開始点
        current_direction = None
        
        # 角度変化の閾値（度）- 30度以上の変化を方向転換と見なす
        angle_threshold = 30
        min_distance = 50  # 最小距離50ピクセル（曲がり角の間隔）
        
        for i in range(1, len(path) - 1):
            prev_point = path[i-1]
            current_point = path[i]
            next_point = path[i+1]
            
            # 角度変化を計算
            dx1 = current_point[0] - prev_point[0]
            dy1 = current_point[1] - prev_point[1]
            dx2 = next_point[0] - current_point[0]
            dy2 = next_point[1] - current_point[1]
            
            # ベクトルの長さが0の場合はスキップ
            len1 = math.sqrt(dx1**2 + dy1**2)
            len2 = math.sqrt(dx2**2 + dy2**2)
            
            if len1 == 0 or len2 == 0:
                continue
            
            # 角度を計算（ドット積から）
            dot_product = dx1 * dx2 + dy1 * dy2
            cos_angle = dot_product / (len1 * len2)
            cos_angle = max(-1, min(1, cos_angle))  # 数値誤差対策
            angle = math.degrees(math.acos(cos_angle))
            
            # 角度変化が閾値以上ならキーポイント
            if angle > angle_threshold:
                # 最小距離チェック
                last_key_point = key_points[-1][1]
                distance = math.sqrt(
                    (current_point[0] - last_key_point[0])**2 + 
                    (current_point[1] - last_key_point[1])**2
                )
                
                if distance >= min_distance:
                    key_points.append((i, current_point))
        
        # 終了点を追加
        key_points.append((len(path)-1, path[-1]))
        
        # キーポイントが多すぎる場合は間引く（最大10個）
        if len(key_points) > 10:
            # 等間隔でサンプリング
            indices = np.linspace(0, len(key_points) - 1, 10, dtype=int)
            key_points = [key_points[i] for i in indices]
        
        return key_points

class ImageEnhancer:
    """画像処理とクロップ機能を提供するクラス"""
    
    def __init__(self):
        self.landmark_detector = LandmarkDetector()
    
    def crop_path_area(self, image, path, padding=50):
        """経路周辺をクロップして拡大表示用の画像を作成"""
        if not path or len(path) < 2:
            return image, {"original_bounds": {"x": 0, "y": 0, "width": image.shape[1], "height": image.shape[0]}, "path_offset": {"x": 0, "y": 0}}
        
        # 経路の境界を計算
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # パディングを追加
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(image.shape[1], max_x + padding)
        max_y = min(image.shape[0], max_y + padding)
        
        # クロップ
        cropped = image[min_y:max_y, min_x:max_x]
        
        # クロップ情報を返す
        crop_info = {
            "original_bounds": {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y},
            "path_offset": {"x": -min_x, "y": -min_y}
        }
        
        return cropped, crop_info
    
    def auto_crop_map_region(self, image):
        """★新機能4: 自動地図領域切り出し"""
        map_region = self.landmark_detector.detect_map_region(image)
        
        x, y = map_region["x"], map_region["y"] 
        w, h = map_region["width"], map_region["height"]
        
        # 地図領域をクロップ
        cropped_map = image[y:y+h, x:x+w]
        
        return cropped_map, map_region
    

    
    def draw_path_on_original(self, original_image, path, start_point, end_point, path_color=(255, 165, 0), point_size=8):
        """元の色付き画像に経路を描画"""
        # 画像をコピー
        result_image = original_image.copy()
        
        # 経路を線で描画
        if len(path) > 1:
            for i in range(len(path) - 1):
                pt1 = (int(path[i][0]), int(path[i][1]))
                pt2 = (int(path[i+1][0]), int(path[i+1][1]))
                cv2.line(result_image, pt1, pt2, path_color, 4)
        
        # 経路上に点を描画
        for point in path:
            pt = (int(point[0]), int(point[1]))
            cv2.circle(result_image, pt, 2, path_color, -1)
        
        # 開始点（緑）
        start_pt = (int(start_point[0]), int(start_point[1]))
        cv2.circle(result_image, start_pt, point_size, (0, 255, 0), -1)
        cv2.circle(result_image, start_pt, point_size + 2, (255, 255, 255), 2)
        
        # 終了点（赤）
        end_pt = (int(end_point[0]), int(end_point[1]))
        cv2.circle(result_image, end_pt, point_size, (0, 0, 255), -1)
        cv2.circle(result_image, end_pt, point_size + 2, (255, 255, 255), 2)
        
        return result_image

class AdvancedBinarization:
    """高度な二値化処理クラス"""
    
    @staticmethod
    def otsu_threshold(image: np.ndarray) -> Tuple[int, np.ndarray]:
        """
        Otsu法による自動閾値決定と二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Otsu法で閾値を自動決定
        threshold_value, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return int(threshold_value), binary
    
    @staticmethod
    def simple_threshold(image: np.ndarray, threshold: int = 127) -> np.ndarray:
        """
        単純閾値による二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        return binary
    
    @staticmethod
    def adaptive_threshold_mean(image: np.ndarray, block_size: int = 15, C: int = 5) -> np.ndarray:
        """
        適応的閾値（平均値ベース）による二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # ブロックサイズは奇数である必要がある
        if block_size % 2 == 0:
            block_size += 1
        
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block_size, C
        )
        return binary
    
    @staticmethod
    def adaptive_threshold_gaussian(image: np.ndarray, block_size: int = 15, C: int = 5) -> np.ndarray:
        """
        適応的閾値（ガウシアン重み付き）による二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # ブロックサイズは奇数である必要がある
        if block_size % 2 == 0:
            block_size += 1
        
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C
        )
        return binary
    
    @staticmethod
    def multi_level_threshold(image: np.ndarray, levels: int = 3) -> np.ndarray:
        """
        マルチレベル閾値による二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 複数の閾値を計算
        thresholds = []
        for i in range(1, levels):
            threshold = int(255 * i / levels)
            thresholds.append(threshold)
        
        # 中間の閾値で二値化（簡易版）
        middle_threshold = thresholds[len(thresholds) // 2] if thresholds else 127
        _, binary = cv2.threshold(gray, middle_threshold, 255, cv2.THRESH_BINARY)
        
        return binary
    
    @staticmethod
    def color_map_preprocessing(image: np.ndarray) -> np.ndarray:
        """
        カラーマップ画像用の前処理（フロアマップ特化）
        """
        if len(image.shape) == 3:
            # HSV色空間に変換
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 明度チャンネルを使用（V値）
            gray = hsv[:, :, 2]
        else:
            gray = image.copy()
        
        # ガンマ補正で明度を調整
        gamma = 1.5
        gray_corrected = np.power(gray / 255.0, 1 / gamma) * 255
        gray_corrected = gray_corrected.astype(np.uint8)
        
        # ヒストグラム平坦化
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray_corrected)
        
        return enhanced
    
    @staticmethod
    def edge_enhanced_binarization(image: np.ndarray, method: str = 'canny_otsu') -> np.ndarray:
        """
        エッジ検出を組み合わせた改良二値化
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        if method == 'canny_otsu':
            # エッジ検出（Canny）
            edges = cv2.Canny(gray, 50, 150)
            
            # Otsu二値化
            _, otsu_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # エッジとOtsu結果を組み合わせ
            combined = cv2.bitwise_or(otsu_binary, edges)
            
            # モルフォロジー演算でクリーンアップ
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            result = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
            
        elif method == 'watershed':
            # ウォーターシェッド法による前処理
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # ノイズ除去
            kernel = np.ones((3, 3), np.uint8)
            opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
            
            # 膨張で確実な背景領域を取得
            sure_bg = cv2.dilate(opening, kernel, iterations=3)
            
            result = sure_bg
            
        else:  # デフォルト: 'adaptive_edge'
            # 適応的二値化とエッジ組み合わせ
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            edges = cv2.Canny(gray, 30, 100)
            result = cv2.bitwise_or(adaptive, edges)
        
        return result
    
    @staticmethod
    def contour_based_binarization(image: np.ndarray, min_contour_area: int = 100) -> np.ndarray:
        """
        輪郭抽出ベースの二値化（構造物の形状を重視）
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # ガウシアンブラーでノイズ軽減
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 複数の閾値で輪郭を検出し、最適なものを選択
        best_binary = None
        max_useful_contours = 0
        
        for threshold in range(80, 180, 20):
            _, binary = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)
            
            # 輪郭検出
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 有用な輪郭（適度な大きさ）の数をカウント
            useful_contours = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if min_contour_area <= area <= gray.shape[0] * gray.shape[1] * 0.5:
                    useful_contours += 1
            
            if useful_contours > max_useful_contours:
                max_useful_contours = useful_contours
                best_binary = binary.copy()
        
        if best_binary is None:
            # フォールバック: Otsu法
            _, best_binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return best_binary

class ImageAnalyzer:
    """画像特徴分析クラス - 自動アルゴリズム選択のための画像解析"""
    
    @staticmethod
    def analyze_image_features(image: np.ndarray) -> Dict[str, Any]:
        """
        画像の特徴を包括的に分析
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            color_image = image.copy()
        else:
            gray = image.copy()
            color_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        
        features = {}
        
        # 1. 基本統計情報
        features['mean_brightness'] = np.mean(gray)
        features['brightness_std'] = np.std(gray)
        features['contrast_ratio'] = np.std(gray) / np.mean(gray) if np.mean(gray) > 0 else 0
        
        # 2. 色分布分析（カラー画像の場合）
        if len(image.shape) == 3:
            features.update(ImageAnalyzer._analyze_color_distribution(color_image))
        else:
            features.update({
                'color_complexity': 0.1,
                'dominant_colors': 1,
                'color_variance': 0.0,
                'is_grayscale': True
            })
        
        # 3. エッジ・テクスチャ分析
        features.update(ImageAnalyzer._analyze_edges_texture(gray))
        
        # 4. 構造分析
        features.update(ImageAnalyzer._analyze_structure(gray))
        
        # 5. 画像複雑度
        features['complexity_score'] = ImageAnalyzer._calculate_complexity_score(features)
        
        return features
    
    @staticmethod
    def _analyze_color_distribution(image: np.ndarray) -> Dict[str, Any]:
        """色分布を分析"""
        # HSV色空間での分析
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 色相の分散（色の多様性）
        hue_hist = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        hue_variance = np.var(hue_hist)
        
        # 彩度の平均（色の鮮やかさ）
        saturation_mean = np.mean(hsv[:, :, 1])
        
        # 支配的な色の数を推定（K-means色分類）
        data = image.reshape((-1, 3))
        data = np.float32(data)
        
        # K-meansで主要色を検出
        k = min(8, len(np.unique(data.view(np.dtype((np.void, data.dtype.itemsize*data.shape[1]))))))
        if k > 1:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # 各色の出現頻度
            unique, counts = np.unique(labels, return_counts=True)
            color_distribution = counts / len(labels)
            dominant_colors = len([x for x in color_distribution if x > 0.05])  # 5%以上の色
        else:
            dominant_colors = 1
        
        return {
            'color_complexity': hue_variance / 10000.0,  # 正規化
            'dominant_colors': dominant_colors,
            'color_variance': saturation_mean / 255.0,
            'is_grayscale': False
        }
    
    @staticmethod
    def _analyze_edges_texture(gray: np.ndarray) -> Dict[str, Any]:
        """エッジとテクスチャを分析"""
        # Cannyエッジ検出
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Sobelエッジ強度
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        edge_magnitude = np.sqrt(sobelx**2 + sobely**2)
        edge_strength = np.mean(edge_magnitude)
        
        # テクスチャ分析（局所バイナリパターン風）
        kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
        texture_response = cv2.filter2D(gray, -1, kernel)
        texture_complexity = np.std(texture_response)
        
        return {
            'edge_density': edge_density,
            'edge_strength': edge_strength / 255.0,  # 正規化
            'texture_complexity': texture_complexity / 255.0
        }
    
    @staticmethod
    def _analyze_structure(gray: np.ndarray) -> Dict[str, Any]:
        """画像構造を分析"""
        # 輪郭検出
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 有意な輪郭の数
        significant_contours = [c for c in contours if cv2.contourArea(c) > gray.size * 0.001]
        
        # 矩形性の分析（建物図面らしさ）
        rectangularity = 0.0
        if significant_contours:
            rect_scores = []
            for contour in significant_contours[:10]:  # 上位10個
                # 輪郭の近似
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # 4角形に近いかどうか
                if len(approx) >= 4:
                    rect_scores.append(min(1.0, 4.0 / len(approx)))
            
            rectangularity = np.mean(rect_scores) if rect_scores else 0.0
        
        return {
            'num_objects': len(significant_contours),
            'rectangularity': rectangularity,
            'structural_complexity': min(1.0, len(significant_contours) / 50.0)
        }
    
    @staticmethod
    def _calculate_complexity_score(features: Dict[str, Any]) -> float:
        """画像の総合複雑度スコアを計算"""
        # 各要素に重み付けして複雑度を計算
        weights = {
            'color_complexity': 0.25,
            'edge_density': 0.20,
            'texture_complexity': 0.15,
            'structural_complexity': 0.20,
            'dominant_colors': 0.10,
            'rectangularity': 0.10
        }
        
        score = 0.0
        for feature, weight in weights.items():
            if feature == 'dominant_colors':
                # 色の数が多いほど複雑
                normalized = min(1.0, features.get(feature, 0) / 8.0)
            else:
                normalized = features.get(feature, 0)
            
            score += normalized * weight
        
        return min(1.0, score)

class IntelligentSelector:
    """インテリジェント自動選択エンジン"""
    
    @staticmethod
    def select_optimal_binarization(features: Dict[str, Any]) -> Dict[str, Any]:
        """
        画像特徴に基づいて最適な二値化方法を選択
        """
        complexity = features.get('complexity_score', 0.5)
        color_complexity = features.get('color_complexity', 0.0)
        edge_density = features.get('edge_density', 0.0)
        rectangularity = features.get('rectangularity', 0.0)
        dominant_colors = features.get('dominant_colors', 1)
        contrast_ratio = features.get('contrast_ratio', 0.0)
        
        # 判定ロジック
        if dominant_colors >= 4 and color_complexity > 0.3 and rectangularity > 0.6:
            # フロアマップ・建物図面パターン
            method = 'floor_map_optimized'
            confidence = min(0.95, 0.7 + color_complexity * 0.3 + rectangularity * 0.2)
            reason = "複数の色分けエリアと構造的特徴を検出（フロアマップ/建物図面）"
            
        elif color_complexity > 0.4 and dominant_colors >= 3:
            # カラーマップパターン
            method = 'color_map'
            confidence = min(0.90, 0.6 + color_complexity * 0.4)
            reason = "豊富な色情報を含む画像（カラーマップ）"
            
        elif edge_density > 0.15 and complexity > 0.6:
            # エッジが多い複雑な画像
            method = 'edge_enhanced'
            confidence = min(0.85, 0.5 + edge_density * 0.4)
            reason = "高密度なエッジ情報（複雑な構造図）"
            
        elif rectangularity > 0.7 and edge_density > 0.05:
            # 構造的な画像
            method = 'contour_based'
            confidence = min(0.80, 0.6 + rectangularity * 0.3)
            reason = "矩形構造を多く含む画像（構造図面）"
            
        elif contrast_ratio > 0.8:
            # 高コントラスト画像
            method = 'otsu'
            confidence = min(0.85, 0.7 + contrast_ratio * 0.2)
            reason = "明瞭なコントラスト（標準的な二値画像）"
            
        elif complexity < 0.3:
            # シンプルな画像
            method = 'simple'
            confidence = 0.75
            reason = "シンプルな構造（基本的な図面）"
            
        else:
            # デフォルト: 適応的閾値
            method = 'adaptive_gaussian'
            confidence = 0.70
            reason = "一般的な画像（適応的処理）"
        
        # パラメータ自動調整
        params = IntelligentSelector._get_optimal_parameters(method, features)
        
        return {
            'method': method,
            'confidence': confidence,
            'reason': reason,
            'parameters': params
        }
    
    @staticmethod
    def select_optimal_pathfinding(grid: List[List[int]], image_size: Tuple[int, int]) -> Dict[str, Any]:
        """
        画像サイズとグリッド複雑度に基づいて最適な経路探索アルゴリズムを選択
        """
        width, height = image_size
        total_pixels = width * height
        
        # グリッドの通行可能エリア率を計算
        if grid:
            passable_ratio = sum(row.count(0) for row in grid) / (len(grid) * len(grid[0]))
        else:
            passable_ratio = 0.5
        
        # 判定基準
        if total_pixels > 500000:  # 大画像
            if passable_ratio < 0.3:  # 通路が少ない（複雑）
                method = 'A*'
                reason = "大画像・複雑な経路（A*が効率的）"
                confidence = 0.90
            else:
                method = 'BFS'
                reason = "大画像・単純な経路（BFSが高速）"
                confidence = 0.85
        elif total_pixels > 100000:  # 中画像
            if passable_ratio < 0.4:
                method = 'A*'
                reason = "中画像・やや複雑（A*でバランス良く）"
                confidence = 0.85
            else:
                method = 'BFS'
                reason = "中画像・標準的な経路（BFS推奨）"
                confidence = 0.90
        else:  # 小画像
            method = 'BFS'
            reason = "小画像（BFSが最適・高速）"
            confidence = 0.95
        
        return {
            'algorithm': method,
            'confidence': confidence,
            'reason': reason,
            'estimated_speed': 'HIGH' if method == 'BFS' else 'MEDIUM'
        }
    
    @staticmethod
    def _get_optimal_parameters(method: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """選択された二値化方法に対する最適パラメータを決定"""
        complexity = features.get('complexity_score', 0.5)
        edge_density = features.get('edge_density', 0.0)
        
        if method in ['simple']:
            # シンプル閾値: 画像の明度に応じて調整
            mean_brightness = features.get('mean_brightness', 127)
            threshold = int(mean_brightness * 0.8)  # やや暗めに調整
            return {'threshold': max(80, min(180, threshold))}
            
        elif method in ['adaptive_mean', 'adaptive_gaussian']:
            # 適応的閾値: 複雑度に応じてブロックサイズ調整
            if complexity > 0.6:
                block_size = 21  # 複雑な画像には大きなブロック
                adaptive_c = 8
            elif complexity > 0.3:
                block_size = 15  # 標準
                adaptive_c = 5
            else:
                block_size = 11  # シンプルな画像には小さなブロック
                adaptive_c = 3
            return {'block_size': block_size, 'adaptive_c': adaptive_c}
            
        elif method in ['edge_enhanced', 'contour_based', 'floor_map_optimized']:
            # エッジ密度に応じてノイズ除去強度を調整
            if edge_density > 0.2:
                kernel_size = 5  # 強いノイズ除去
            elif edge_density > 0.1:
                kernel_size = 3  # 標準
            else:
                kernel_size = 3  # 軽微なノイズ除去
            return {'kernel_size': kernel_size}
            
        return {}  # デフォルトパラメータ使用

class NoiseReduction:
    """ノイズ除去・モルフォロジー演算クラス"""
    
    @staticmethod
    def morphology_opening(binary: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """
        Opening演算（収縮→膨張）でノイズ除去
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        return opened
    
    @staticmethod
    def morphology_closing(binary: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """
        Closing演算（膨張→収縮）で隙間埋め
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return closed
    
    @staticmethod
    def remove_small_objects(binary: np.ndarray, min_size: int = 50) -> np.ndarray:
        """
        小さなオブジェクトを除去
        """
        # 連結成分のラベリング
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        # 小さなコンポーネントを除去
        result = np.zeros_like(binary)
        for i in range(1, num_labels):  # 0は背景なのでスキップ
            if stats[i, cv2.CC_STAT_AREA] >= min_size:
                result[labels == i] = 255
                
        return result

class RoadNetworkGenerator:
    """🛣️ 道路ネットワーク生成クラス - GoogleMap風の道路中央線システム"""
    
    def __init__(self):
        self.node_spacing = 15  # ノード間の最小距離
        self.corner_threshold = 30  # 角度変化の閾値（度）
        self.junction_radius = 20  # 交差点検出の半径
        
    def generate_road_network(self, binary_image: np.ndarray) -> Dict[str, Any]:
        """
        バイナリ画像から道路ネットワークを生成
        
        Returns:
            nodes: 道路ノードのリスト [(x, y, node_id), ...]
            edges: エッジのリスト [(node1_id, node2_id, distance), ...]
            skeleton: スケルトン化された道路中央線
            road_grid: 道路のみのグリッド
        """
        print("🛣️ 道路ネットワーク生成開始...")
        
        # 1. 通路部分（白い部分）を抽出
        road_mask = (binary_image == 255).astype(np.uint8)
        
        # 2. スケルトン化による道路中央線の抽出
        skeleton = self.extract_road_skeleton(road_mask)
        
        # 3. ノード候補の検出
        nodes = self.detect_road_nodes(skeleton)
        
        # 4. エッジの生成
        edges = self.generate_edges(nodes, skeleton)
        
        # 5. 道路グリッドの生成
        road_grid = self.create_road_grid(skeleton, binary_image.shape)
        
        print(f"✅ ノード数: {len(nodes)}, エッジ数: {len(edges)}")
        
        return {
            'nodes': nodes,
            'edges': edges, 
            'skeleton': skeleton,
            'road_grid': road_grid,
            'original_binary': binary_image
        }
    
    def extract_road_skeleton(self, road_mask: np.ndarray) -> np.ndarray:
        """道路の中央線をスケルトン化で抽出"""
        
        # モルフォロジー演算でノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(road_mask, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        
        # スケルトン化（細線化）
        skeleton = skeletonize(cleaned > 0).astype(np.uint8) * 255
        
        # さらに細線化でノイズ除去
        skeleton = thin(skeleton > 0).astype(np.uint8) * 255
        
        return skeleton
    
    def detect_road_nodes(self, skeleton: np.ndarray) -> List[Tuple[int, int, int]]:
        """スケルトンから道路ノードを検出"""
        nodes = []
        node_id = 0
        
        # スケルトンの座標を取得
        skeleton_points = np.argwhere(skeleton == 255)
        
        if len(skeleton_points) == 0:
            return nodes
        
        # DBSCANクラスタリングで近い点をグループ化
        clustering = DBSCAN(eps=self.node_spacing, min_samples=1)
        clusters = clustering.fit_predict(skeleton_points)
        
        # 各クラスタの中心をノードとする
        for cluster_id in set(clusters):
            if cluster_id == -1:  # ノイズは除外
                continue
                
            cluster_points = skeleton_points[clusters == cluster_id]
            center_y, center_x = np.mean(cluster_points, axis=0).astype(int)
            
            # 角の検出（方向変化が大きい点を優先）
            is_junction = self.detect_junction(skeleton, center_x, center_y)
            
            nodes.append((center_x, center_y, node_id))
            node_id += 1
        
        # 一定間隔でノードを追加（直線部分にも配置）
        nodes = self.add_regular_nodes(skeleton, nodes, node_id)
        
        return nodes
    
    def detect_junction(self, skeleton: np.ndarray, x: int, y: int) -> bool:
        """交差点・角の検出"""
        height, width = skeleton.shape
        
        # 周辺の方向ベクトルを計算
        directions = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                    
                nx, ny = x + dx * 10, y + dy * 10
                if 0 <= nx < width and 0 <= ny < height:
                    if skeleton[ny, nx] == 255:
                        directions.append((dx, dy))
        
        # 3方向以上の接続があれば交差点
        return len(directions) >= 3
    
    def add_regular_nodes(self, skeleton: np.ndarray, existing_nodes: List, start_id: int) -> List:
        """直線部分に一定間隔でノードを追加"""
        nodes = existing_nodes.copy()
        node_id = start_id
        
        skeleton_points = np.argwhere(skeleton == 255)
        existing_positions = set((node[0], node[1]) for node in existing_nodes)
        
        # 一定間隔で点をサンプリング
        for i in range(0, len(skeleton_points), self.node_spacing):
            y, x = skeleton_points[i]
            
            # 既存ノードから十分離れているかチェック
            min_distance = min([np.sqrt((x - nx)**2 + (y - ny)**2) 
                              for nx, ny, _ in existing_nodes] + [float('inf')])
            
            if min_distance > self.node_spacing:
                nodes.append((x, y, node_id))
                node_id += 1
        
        return nodes
    
    def generate_edges(self, nodes: List, skeleton: np.ndarray) -> List[Tuple[int, int, float]]:
        """ノード間のエッジを生成（改善版）"""
        edges = []
        edge_set = set()  # 重複防止用
        
        # 最大接続距離を画像サイズに基づいて調整
        max_distance = max(self.node_spacing * 8, min(skeleton.shape[0], skeleton.shape[1]) * 0.15)
        
        for i, (x1, y1, id1) in enumerate(nodes):
            for j, (x2, y2, id2) in enumerate(nodes):
                if i >= j:
                    continue
                
                # 距離計算
                distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                # 近い距離かつスケルトン上で接続されているかチェック
                if distance < max_distance and self.is_connected_on_skeleton(
                    skeleton, (x1, y1), (x2, y2)):
                    edge_key = tuple(sorted([id1, id2]))
                    if edge_key not in edge_set:
                        edges.append((id1, id2, distance))
                        edge_set.add(edge_key)
        
        # エッジが少ない場合のフォールバック処理
        if len(edges) < len(nodes) * 0.3:
            print(f"⚠️ エッジ数が少ない（{len(edges)}）、近傍ベースのエッジを追加")
            
            # 各ノードから最も近い3つのノードに接続
            for i, (x1, y1, id1) in enumerate(nodes):
                distances = []
                for j, (x2, y2, id2) in enumerate(nodes):
                    if i != j:
                        dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                        distances.append((dist, id2))
                
                # 最も近い3つのノードに接続
                distances.sort()
                for dist, id2 in distances[:3]:
                    edge_key = tuple(sorted([id1, id2]))
                    if edge_key not in edge_set and dist < max_distance * 2:
                        edges.append((id1, id2, dist))
                        edge_set.add(edge_key)
        
        return edges
    
    def is_connected_on_skeleton(self, skeleton: np.ndarray, point1: Tuple[int, int], 
                               point2: Tuple[int, int]) -> bool:
        """2点がスケルトン上で接続されているかチェック（改善版）"""
        x1, y1 = point1
        x2, y2 = point2
        
        # スケルトンを少し拡張して接続判定を緩和
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        expanded_skeleton = cv2.dilate(skeleton, kernel, iterations=1)
        
        # ブレゼンハムライン上の全点がスケルトンに含まれるかチェック
        points = self.bresenham_line(x1, y1, x2, y2)
        
        skeleton_point_count = 0
        total_points = len(points)
        
        for x, y in points:
            if 0 <= x < expanded_skeleton.shape[1] and 0 <= y < expanded_skeleton.shape[0]:
                if expanded_skeleton[y, x] > 0:  # 拡張スケルトン上の白い点
                    skeleton_point_count += 1
        
        # 経路の50%以上が拡張スケルトン上にあれば接続されているとみなす（緩和）
        return skeleton_point_count >= total_points * 0.5
    
    def bresenham_line(self, x1: int, y1: int, x2: int, y2: int) -> List[Tuple[int, int]]:
        """ブレゼンハム直線アルゴリズム"""
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        while True:
            points.append((x1, y1))
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
        
        return points
    
    def create_road_grid(self, skeleton: np.ndarray, shape: Tuple[int, int]) -> List[List[int]]:
        """道路ネットワーク用のグリッドを生成（0=道路、1=壁）"""
        height, width = shape
        road_grid = [[1 for _ in range(width)] for _ in range(height)]
        
        # スケルトン上の点を道路として設定
        skeleton_points = np.argwhere(skeleton == 255)
        for y, x in skeleton_points:
            road_grid[y][x] = 0
            
            # 周辺も道路として設定（道幅を持たせる）
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        road_grid[ny][nx] = 0
        
        return road_grid
    
    def find_nearest_road_point(self, start_point: Tuple[int, int], 
                               skeleton: np.ndarray) -> Tuple[int, int]:
        """最寄りの道路ポイントを検索"""
        x, y = start_point
        skeleton_points = np.argwhere(skeleton == 255)
        
        if len(skeleton_points) == 0:
            return start_point
        
        # 最短距離の道路ポイントを検索
        distances = np.sqrt(np.sum((skeleton_points - [y, x])**2, axis=1))
        nearest_idx = np.argmin(distances)
        nearest_y, nearest_x = skeleton_points[nearest_idx]
        
        return (nearest_x, nearest_y)


class OptimizedPathfinder:
    """最適化された経路探索アルゴリズムクラス（道路ネットワーク対応版）"""
    
    def __init__(self):
        self.road_network_gen = RoadNetworkGenerator()
    
    def find_path_with_road_network(self, grid: List[List[int]], start: Tuple[int, int], 
                                  end: Tuple[int, int], algorithm: str = 'BFS') -> Dict[str, Any]:
        """
        道路ネットワークベースの経路探索（改善版）
        複数のフォールバック戦略を持つ
        """
        # バイナリ画像を再構築
        binary_image = np.array([[255 if cell == 0 else 0 for cell in row] for row in grid], dtype=np.uint8)
        
        try:
            # 道路ネットワーク生成
            network_data = self.road_network_gen.generate_road_network(binary_image)
            nodes = network_data['nodes']
            edges = network_data['edges']
            skeleton = network_data['skeleton']
            
            print(f"🛣️ 道路ネットワーク生成結果: ノード数={len(nodes)}, エッジ数={len(edges)}")
        except Exception as e:
            print(f"⚠️ 道路ネットワーク生成エラー: {e}")
            return self.fallback_pathfinding(grid, start, end, algorithm)
        
        if not nodes or len(nodes) < 2:
            print("⚠️ 道路ネットワークが不十分、グリッドベース経路探索に切り替え")
            return self.fallback_pathfinding(grid, start, end, algorithm)
        
        # 開始・終了点を最寄りの道路ポイントに移動
        start_road = self.road_network_gen.find_nearest_road_point(start, skeleton)
        end_road = self.road_network_gen.find_nearest_road_point(end, skeleton)
        print(f"🎯 最寄り道路ポイント: 開始={start_road}, 終了={end_road}")
        
        # 戦略1: ノードグラフでの経路探索
        try:
            start_node_id = self.find_nearest_node(start_road, nodes)
            end_node_id = self.find_nearest_node(end_road, nodes)
            print(f"🏷️ 最寄りノードID: 開始={start_node_id}, 終了={end_node_id}")
            
            path_nodes = self.pathfind_on_node_graph(nodes, edges, start_node_id, end_node_id, algorithm)
            
            if path_nodes and len(path_nodes) > 0:
                road_path = self.convert_node_path_to_coordinates(path_nodes, nodes, skeleton)
                full_path = [start] + [start_road] + road_path + [end_road] + [end]
                print(f"✅ ノードグラフ経路成功: {len(full_path)}ステップ")
                
                return {
                    'path': full_path,
                    'nodes': nodes,
                    'edges': edges,
                    'skeleton': skeleton,
                    'start_road': start_road,
                    'end_road': end_road,
                    'road_path': road_path,
                    'algorithm': algorithm
                }
        except Exception as e:
            print(f"⚠️ ノードグラフ経路探索エラー: {e}")
        
        # 戦略2: スケルトン上で直接経路探索
        print("🔄 戦略2: スケルトン直接経路探索")
        try:
            direct_path = self.pathfind_on_skeleton(skeleton, start_road, end_road, algorithm)
            
            if direct_path and len(direct_path) > 0:
                full_path = [start] + direct_path + [end]
                print(f"✅ スケルトン直接経路成功: {len(full_path)}ステップ")
                
                return {
                    'path': full_path,
                    'nodes': nodes,
                    'edges': edges,
                    'skeleton': skeleton,
                    'start_road': start_road,
                    'end_road': end_road,
                    'road_path': direct_path,
                    'algorithm': algorithm
                }
        except Exception as e:
            print(f"⚠️ スケルトン直接経路エラー: {e}")
        
        # 戦略3: 元のグリッドベース経路探索（最終フォールバック）
        print("🔄 戦略3: グリッドベースフォールバック経路探索")
        fallback_result = self.fallback_pathfinding(grid, start, end, algorithm)
        
        # フォールバックでも道路ネットワークデータを含める（表示用）
        if skeleton is not None:
            fallback_result['skeleton'] = skeleton
            fallback_result['nodes'] = nodes
            fallback_result['edges'] = edges
        
        return fallback_result
    
    def find_nearest_node(self, point: Tuple[int, int], nodes: List) -> int:
        """最寄りのノードIDを検索"""
        if not nodes:
            return 0
            
        x, y = point
        min_distance = float('inf')
        nearest_id = 0
        
        for nx, ny, node_id in nodes:
            distance = np.sqrt((x - nx)**2 + (y - ny)**2)
            if distance < min_distance:
                min_distance = distance
                nearest_id = int(node_id)
        
        return nearest_id
    
    def pathfind_on_node_graph(self, nodes: List, edges: List, start_id: int, 
                              end_id: int, algorithm: str) -> List[int]:
        """ノードグラフ上での経路探索"""
        print(f"🔍 ノードグラフ探索: 開始ID={start_id}, 終了ID={end_id}, エッジ数={len(edges)}")
        
        # ノードIDから座標へのマッピング
        node_coords = {node_id: (x, y) for x, y, node_id in nodes}
        
        # 開始・終了ノードが存在するかチェック
        if start_id not in node_coords:
            print(f"❌ 開始ノードID {start_id} が見つかりません")
            return []
        if end_id not in node_coords:
            print(f"❌ 終了ノードID {end_id} が見つかりません") 
            return []
        
        # エッジから隣接リストを構築
        adj_list = {}
        for node_id in node_coords:
            adj_list[node_id] = []
        
        edge_count = 0
        for id1, id2, distance in edges:
            if id1 in adj_list and id2 in adj_list:
                adj_list[id1].append((id2, distance))
                adj_list[id2].append((id1, distance))
                edge_count += 1
        
        print(f"📊 隣接リスト構築完了: 有効エッジ数={edge_count}")
        print(f"🎯 開始ノード接続数: {len(adj_list[start_id])}, 終了ノード接続数: {len(adj_list[end_id])}")
        
        # 選択されたアルゴリズムで経路探索
        if algorithm == 'BFS':
            return self.bfs_on_nodes(adj_list, start_id, end_id)
        elif algorithm == 'A*':
            return self.astar_on_nodes(adj_list, node_coords, start_id, end_id)
        elif algorithm == 'Dijkstra':
            return self.dijkstra_on_nodes(adj_list, start_id, end_id)
        else:
            return self.bfs_on_nodes(adj_list, start_id, end_id)
    
    def bfs_on_nodes(self, adj_list: Dict, start_id: int, end_id: int) -> List[int]:
        """ノード上でのBFS"""
        print(f"🔍 BFS開始: {start_id} → {end_id}")
        
        if start_id == end_id:
            print("✅ 開始と終了が同じノード")
            return [start_id]
        
        visited = set()
        parent = {}
        queue = deque([start_id])
        visited.add(start_id)
        parent[start_id] = None
        
        iterations = 0
        while queue and iterations < 10000:  # 無限ループ防止
            iterations += 1
            current = queue.popleft()
            
            if current == end_id:
                # パスを再構築
                path = []
                while current is not None:
                    path.append(current)
                    current = parent[current]
                result_path = path[::-1]
                print(f"✅ BFS成功: 経路長={len(result_path)}, 反復回数={iterations}")
                return result_path
            
            for neighbor_id, _ in adj_list.get(current, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    parent[neighbor_id] = current
                    queue.append(neighbor_id)
        
        print(f"❌ BFS失敗: 訪問ノード数={len(visited)}, 反復回数={iterations}")
        return []
    
    def astar_on_nodes(self, adj_list: Dict, node_coords: Dict, start_id: int, end_id: int) -> List[int]:
        """ノード上でのA*"""
        if start_id == end_id:
            return [start_id]
        
        def heuristic(id1, id2):
            x1, y1 = node_coords[id1]
            x2, y2 = node_coords[id2]
            return abs(x1 - x2) + abs(y1 - y2)
        
        open_set = []
        heapq.heappush(open_set, (0, start_id))
        came_from = {}
        g_score = {start_id: 0}
        f_score = {start_id: heuristic(start_id, end_id)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == end_id:
                # パスを再構築
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_id)
                return path[::-1]
            
            for neighbor_id, distance in adj_list.get(current, []):
                tentative_g_score = g_score[current] + distance
                
                if neighbor_id not in g_score or tentative_g_score < g_score[neighbor_id]:
                    came_from[neighbor_id] = current
                    g_score[neighbor_id] = tentative_g_score
                    f_score[neighbor_id] = tentative_g_score + heuristic(neighbor_id, end_id)
                    
                    if neighbor_id not in [item[1] for item in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
        
        return []
    
    def dijkstra_on_nodes(self, adj_list: Dict, start_id: int, end_id: int) -> List[int]:
        """ノード上でのDijkstra"""
        if start_id == end_id:
            return [start_id]
        
        distances = {start_id: 0}
        previous = {}
        priority_queue = [(0, start_id)]
        visited = set()
        
        while priority_queue:
            current_distance, current = heapq.heappop(priority_queue)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == end_id:
                # パスを再構築
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(start_id)
                return path[::-1]
            
            for neighbor_id, distance in adj_list.get(current, []):
                if neighbor_id not in visited:
                    new_distance = current_distance + distance
                    
                    if neighbor_id not in distances or new_distance < distances[neighbor_id]:
                        distances[neighbor_id] = new_distance
                        previous[neighbor_id] = current
                        heapq.heappush(priority_queue, (new_distance, neighbor_id))
        
        return []
    
    def pathfind_on_skeleton(self, skeleton: np.ndarray, start: Tuple[int, int], 
                           end: Tuple[int, int], algorithm: str) -> List[Tuple[int, int]]:
        """スケルトン上で直接経路探索（改善版）"""
        print(f"🗺️ スケルトン直接経路探索: {start} → {end}")
        
        height, width = skeleton.shape
        
        # スケルトンを拡張して経路を見つけやすくする
        # スケルトン上の点と、その周囲3ピクセルも通行可能とする
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        expanded_skeleton = cv2.dilate(skeleton, kernel, iterations=1)
        
        # 拡張スケルトンを道路グリッドとして使用（白い部分=通行可能）
        road_grid = []
        for y in range(height):
            row = []
            for x in range(width):
                if expanded_skeleton[y, x] > 0:  # 拡張スケルトン上の白い点
                    row.append(0)  # 通行可能
                else:
                    row.append(1)  # 通行不可
            road_grid.append(row)
        
        # 開始点と終了点が通行不可の場合、最寄りの通行可能点を探す
        start_x, start_y = start
        end_x, end_y = end
        
        # 開始点の補正
        if road_grid[start_y][start_x] == 1:
            new_start = self._find_nearest_passable(road_grid, start)
            if new_start:
                start = new_start
                print(f"📍 開始点を補正: {(start_x, start_y)} → {start}")
        
        # 終了点の補正
        if road_grid[end_y][end_x] == 1:
            new_end = self._find_nearest_passable(road_grid, end)
            if new_end:
                end = new_end
                print(f"📍 終了点を補正: {(end_x, end_y)} → {end}")
        
        # 標準の経路探索アルゴリズムを道路グリッドで実行
        if algorithm == 'BFS':
            path = self.bfs_pathfinding(road_grid, start, end)
        elif algorithm == 'A*':
            path = self.astar_pathfinding(road_grid, start, end)
        elif algorithm == 'Dijkstra':
            path = self.dijkstra_pathfinding(road_grid, start, end)
        else:
            path = self.bfs_pathfinding(road_grid, start, end)
        
        return path if path else []
    
    def _find_nearest_passable(self, grid: List[List[int]], point: Tuple[int, int], 
                               max_radius: int = 30) -> Optional[Tuple[int, int]]:
        """最寄りの通行可能な点を探す"""
        x, y = point
        height, width = len(grid), len(grid[0])
        
        for radius in range(1, max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) == radius or abs(dy) == radius:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == 0:
                            return (nx, ny)
        return None
    
    def convert_node_path_to_coordinates(self, node_path: List[int], nodes: List, 
                                       skeleton: np.ndarray) -> List[Tuple[int, int]]:
        """ノード経路を座標経路に変換"""
        if len(node_path) < 2:
            return []
        
        coord_path = []
        node_coords = {node_id: (x, y) for x, y, node_id in nodes}
        
        for i in range(len(node_path) - 1):
            start_node = node_path[i]
            end_node = node_path[i + 1]
            
            start_coord = node_coords[start_node]
            end_coord = node_coords[end_node]
            
            # ノード間の詳細パスをスケルトンに沿って生成
            segment_path = self.trace_skeleton_between_points(skeleton, start_coord, end_coord)
            coord_path.extend(segment_path)
        
        return coord_path
    
    def trace_skeleton_between_points(self, skeleton: np.ndarray, point1: Tuple[int, int], 
                                    point2: Tuple[int, int]) -> List[Tuple[int, int]]:
        """スケルトンに沿って2点間の詳細パスを生成"""
        # 簡易実装: 直線で結ぶ
        return self.road_network_gen.bresenham_line(point1[0], point1[1], point2[0], point2[1])
    
    def fallback_pathfinding(self, grid: List[List[int]], start: Tuple[int, int], 
                           end: Tuple[int, int], algorithm: str) -> Dict[str, Any]:
        """フォールバック: 従来の経路探索（開始/終了点の自動補正付き）"""
        print(f"🔄 フォールバック経路探索: {start} → {end}, アルゴリズム={algorithm}")
        
        height, width = len(grid), len(grid[0])
        adjusted_start = start
        adjusted_end = end
        start_adjusted = False
        end_adjusted = False
        
        # 開始点が通行不可の場合、最寄りの通行可能点を探す
        if grid[start[1]][start[0]] == 1:
            new_start = self._find_nearest_passable(grid, start, max_radius=200)
            if new_start:
                adjusted_start = new_start
                start_adjusted = True
                print(f"📍 開始点を補正: {start} → {adjusted_start}")
            else:
                print(f"❌ 開始点 {start} の近くに通行可能な点がありません")
                return {'path': [], 'fallback': True, 'algorithm': algorithm, 'error': 'start_impassable'}
        
        # 終了点が通行不可の場合、最寄りの通行可能点を探す
        if grid[end[1]][end[0]] == 1:
            new_end = self._find_nearest_passable(grid, end, max_radius=200)
            if new_end:
                adjusted_end = new_end
                end_adjusted = True
                print(f"📍 終了点を補正: {end} → {adjusted_end}")
            else:
                print(f"❌ 終了点 {end} の近くに通行可能な点がありません")
                return {'path': [], 'fallback': True, 'algorithm': algorithm, 'error': 'end_impassable'}
        
        # 経路探索実行
        if algorithm == 'BFS':
            path = self.bfs_pathfinding(grid, adjusted_start, adjusted_end)
        elif algorithm == 'A*':
            path = self.astar_pathfinding(grid, adjusted_start, adjusted_end)
        elif algorithm == 'Dijkstra':
            path = self.dijkstra_pathfinding(grid, adjusted_start, adjusted_end)
        else:
            path = self.bfs_pathfinding(grid, adjusted_start, adjusted_end)
        
        # 経路が見つかった場合、元の開始/終了点を含める
        if path:
            full_path = []
            if start_adjusted:
                full_path.append(start)  # 元の開始点
            full_path.extend(path)
            if end_adjusted:
                full_path.append(end)  # 元の終了点
            print(f"✅ フォールバック経路成功: {len(full_path)}ステップ")
            return {
                'path': full_path,
                'fallback': True,
                'algorithm': algorithm,
                'adjusted_start': adjusted_start if start_adjusted else None,
                'adjusted_end': adjusted_end if end_adjusted else None
            }
        else:
            print(f"❌ フォールバック経路失敗: 経路が見つかりません")
            return {'path': [], 'fallback': True, 'algorithm': algorithm, 'error': 'no_path_found'}
    
    @staticmethod
    def bfs_pathfinding(grid: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        BFS（幅優先探索）による最短経路検索 - 従来版
        """
        height, width = len(grid), len(grid[0])
        
        # 境界チェック
        if not (0 <= start[0] < width and 0 <= start[1] < height):
            return None
        if not (0 <= end[0] < width and 0 <= end[1] < height):
            return None
        if grid[start[1]][start[0]] == 1 or grid[end[1]][end[0]] == 1:
            return None
        
        # BFS初期化
        visited = set()
        parent = {}
        queue = deque([start])
        visited.add(start)
        parent[start] = None
        
        # 8方向移動
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        
        while queue:
            current = queue.popleft()
            
            if current == end:
                # パスを再構築
                path = []
                while current is not None:
                    path.append(current)
                    current = parent[current]
                return path[::-1]
            
            for dx, dy in directions:
                next_x, next_y = current[0] + dx, current[1] + dy
                next_pos = (next_x, next_y)
                
                if (0 <= next_x < width and 0 <= next_y < height and
                    grid[next_y][next_x] == 0 and next_pos not in visited):
                    
                    visited.add(next_pos)
                    parent[next_pos] = current
                    queue.append(next_pos)
        
        return None
    
    @staticmethod
    def astar_pathfinding(grid: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        A*アルゴリズムによる経路検索 - 従来版
        """
        height, width = len(grid), len(grid[0])
        
        # 境界チェック
        if not (0 <= start[0] < width and 0 <= start[1] < height):
            return None
        if not (0 <= end[0] < width and 0 <= end[1] < height):
            return None
        if grid[start[1]][start[0]] == 1 or grid[end[1]][end[0]] == 1:
            return None
        
        # ヒューリスティック関数（マンハッタン距離）
        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
        # A*初期化
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: heuristic(start, end)}
        
        # 8方向移動（対角線にはコスト1.414）
        directions = [
            (0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
            (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)
        ]
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == end:
                # パスを再構築
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]
            
            for dx, dy, cost in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if (0 <= neighbor[0] < width and 0 <= neighbor[1] < height and
                    grid[neighbor[1]][neighbor[0]] == 0):
                    
                    tentative_g_score = g_score[current] + cost
                    
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score + heuristic(neighbor, end)
                        
                        if neighbor not in [item[1] for item in open_set]:
                            heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return None
    
    @staticmethod
    def dijkstra_pathfinding(grid: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        Dijkstraアルゴリズムによる経路検索 - 従来版
        """
        height, width = len(grid), len(grid[0])
        
        # 境界チェック
        if not (0 <= start[0] < width and 0 <= start[1] < height):
            return None
        if not (0 <= end[0] < width and 0 <= end[1] < height):
            return None
        if grid[start[1]][start[0]] == 1 or grid[end[1]][end[0]] == 1:
            return None
        
        # Dijkstra初期化
        distances = {start: 0}
        previous = {}
        priority_queue = [(0, start)]
        visited = set()
        
        # 8方向移動
        directions = [
            (0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
            (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)
        ]
        
        while priority_queue:
            current_distance, current = heapq.heappop(priority_queue)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == end:
                # パスを再構築
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(start)
                return path[::-1]
            
            for dx, dy, cost in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if (0 <= neighbor[0] < width and 0 <= neighbor[1] < height and
                    grid[neighbor[1]][neighbor[0]] == 0 and neighbor not in visited):
                    
                    distance = current_distance + cost
                    
                    if neighbor not in distances or distance < distances[neighbor]:
                        distances[neighbor] = distance
                        previous[neighbor] = current
                        heapq.heappush(priority_queue, (distance, neighbor))
        
        return None

class ImageProcessor:
    """統合画像処理クラス"""
    
    def __init__(self):
        self.binarizer = AdvancedBinarization()
        self.noise_reducer = NoiseReduction()
        self.analyzer = ImageAnalyzer()
        self.selector = IntelligentSelector()
    
    def process_image(self, image: np.ndarray, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        統合画像処理メソッド
        """
        start_time = time.time()
        
        # パラメータ取得
        binarization_mode = options.get('binarization_mode', 'otsu')
        threshold = options.get('threshold', 127)
        block_size = options.get('block_size', 15)
        adaptive_c = options.get('adaptive_c', 5)
        noise_reduction = options.get('noise_reduction', True)
        kernel_size = options.get('kernel_size', 3)
        target_size = options.get('target_size', 700)
        
        # 画像リサイズ
        height, width = image.shape[:2]
        aspect_ratio = width / height
        new_width = target_size
        new_height = int(new_width / aspect_ratio)
        
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # 二値化処理
        if binarization_mode == 'otsu':
            auto_threshold, binary_image = self.binarizer.otsu_threshold(resized_image)
        elif binarization_mode == 'simple':
            binary_image = self.binarizer.simple_threshold(resized_image, threshold)
            auto_threshold = threshold
        elif binarization_mode == 'adaptive_mean':
            binary_image = self.binarizer.adaptive_threshold_mean(resized_image, block_size, adaptive_c)
            auto_threshold = None
        elif binarization_mode == 'adaptive_gaussian':
            binary_image = self.binarizer.adaptive_threshold_gaussian(resized_image, block_size, adaptive_c)
            auto_threshold = None
        elif binarization_mode == 'multi_level':
            binary_image = self.binarizer.multi_level_threshold(resized_image)
            auto_threshold = None
        elif binarization_mode == 'color_map':
            # カラーマップ用前処理 + Otsu
            preprocessed = self.binarizer.color_map_preprocessing(resized_image)
            auto_threshold, binary_image = self.binarizer.otsu_threshold(preprocessed)
        elif binarization_mode == 'edge_enhanced':
            # エッジ強化二値化
            binary_image = self.binarizer.edge_enhanced_binarization(resized_image, 'canny_otsu')
            auto_threshold = None
        elif binarization_mode == 'contour_based':
            # 輪郭ベース二値化
            binary_image = self.binarizer.contour_based_binarization(resized_image, min_contour_area=50)
            auto_threshold = None
        elif binarization_mode == 'floor_map_optimized':
            # フロアマップ特化モード（組み合わせ処理）
            # 1. 前処理
            preprocessed = self.binarizer.color_map_preprocessing(resized_image)
            # 2. エッジ強化二値化
            binary_image = self.binarizer.edge_enhanced_binarization(preprocessed, 'adaptive_edge')
            auto_threshold = None
        else:
            auto_threshold, binary_image = self.binarizer.otsu_threshold(resized_image)
        
        # ノイズ除去
        if noise_reduction:
            binary_image = self.noise_reducer.morphology_opening(binary_image, kernel_size)
            binary_image = self.noise_reducer.remove_small_objects(binary_image, min_size=20)
        
        # グリッド生成（0=通行可能, 1=壁）
        grid = (binary_image == 0).astype(int).tolist()  # 黒が壁、白が通路
        
        processing_time = time.time() - start_time
        
        return {
            'processed_image': binary_image,
            'grid': grid,
            'width': new_width,
            'height': new_height,
            'auto_threshold': auto_threshold,
            'processing_time': processing_time
        }
    
    def intelligent_auto_process(self, image: np.ndarray, target_size: int = 700) -> Dict[str, Any]:
        """
        🤖 インテリジェント自動処理 - 画像を分析して最適なアルゴリズムを自動選択
        """
        start_time = time.time()
        
        # 1. 画像特徴分析
        analysis_start = time.time()
        features = self.analyzer.analyze_image_features(image)
        analysis_time = time.time() - analysis_start
        
        # 2. 最適な二値化方法を選択
        binarization_choice = self.selector.select_optimal_binarization(features)
        
        # 3. 画像リサイズ
        height, width = image.shape[:2]
        aspect_ratio = width / height
        new_width = target_size
        new_height = int(new_width / aspect_ratio)
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # 4. 選択された方法で二値化処理実行
        binarization_start = time.time()
        method = binarization_choice['method']
        params = binarization_choice['parameters']
        
        if method == 'otsu':
            auto_threshold, binary_image = self.binarizer.otsu_threshold(resized_image)
        elif method == 'simple':
            threshold = params.get('threshold', 127)
            binary_image = self.binarizer.simple_threshold(resized_image, threshold)
            auto_threshold = threshold
        elif method == 'adaptive_mean':
            block_size = params.get('block_size', 15)
            adaptive_c = params.get('adaptive_c', 5)
            binary_image = self.binarizer.adaptive_threshold_mean(resized_image, block_size, adaptive_c)
            auto_threshold = None
        elif method == 'adaptive_gaussian':
            block_size = params.get('block_size', 15)
            adaptive_c = params.get('adaptive_c', 5)
            binary_image = self.binarizer.adaptive_threshold_gaussian(resized_image, block_size, adaptive_c)
            auto_threshold = None
        elif method == 'color_map':
            preprocessed = self.binarizer.color_map_preprocessing(resized_image)
            auto_threshold, binary_image = self.binarizer.otsu_threshold(preprocessed)
        elif method == 'edge_enhanced':
            binary_image = self.binarizer.edge_enhanced_binarization(resized_image, 'canny_otsu')
            auto_threshold = None
        elif method == 'contour_based':
            binary_image = self.binarizer.contour_based_binarization(resized_image, min_contour_area=50)
            auto_threshold = None
        elif method == 'floor_map_optimized':
            preprocessed = self.binarizer.color_map_preprocessing(resized_image)
            binary_image = self.binarizer.edge_enhanced_binarization(preprocessed, 'adaptive_edge')
            auto_threshold = None
        else:
            auto_threshold, binary_image = self.binarizer.otsu_threshold(resized_image)
        
        binarization_time = time.time() - binarization_start
        
        # 5. ノイズ除去（インテリジェント調整）
        noise_start = time.time()
        kernel_size = params.get('kernel_size', 3)
        binary_image = self.noise_reducer.morphology_opening(binary_image, kernel_size)
        binary_image = self.noise_reducer.remove_small_objects(binary_image, min_size=20)
        noise_time = time.time() - noise_start
        
        # 6. グリッド生成
        grid = (binary_image == 0).astype(int).tolist()
        
        # 7. 最適な経路探索アルゴリズム選択
        pathfinding_choice = self.selector.select_optimal_pathfinding(grid, (new_width, new_height))
        
        total_time = time.time() - start_time
        
        return {
            'processed_image': binary_image,
            'grid': grid,
            'width': new_width,
            'height': new_height,
            'auto_threshold': auto_threshold,
            'processing_time': total_time,
            'analysis': {
                'features': features,
                'binarization_choice': binarization_choice,
                'pathfinding_choice': pathfinding_choice,
                'timing': {
                    'analysis_time': analysis_time,
                    'binarization_time': binarization_time,
                    'noise_reduction_time': noise_time,
                    'total_time': total_time
                }
            }
        }

# グローバルインスタンス
image_processor = ImageProcessor()
pathfinder = OptimizedPathfinder()
navigation_generator = NavigationInstructionGenerator()
image_enhancer = ImageEnhancer()

@app.route('/')
def index():
    """メインページ表示"""
    return render_template('index.html')

@app.route('/api/process-image', methods=['POST'])
def process_image():
    """画像処理API"""
    try:
        data = request.get_json()
        
        # Base64画像データをデコード
        image_data = data['image_data'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # PIL Imageから NumPy配列に変換
        pil_image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(pil_image)
        
        # 処理オプション
        options = {
            'binarization_mode': data.get('binarization_mode', 'otsu'),
            'threshold': int(data.get('threshold', 127)),
            'block_size': int(data.get('block_size', 15)),
            'adaptive_c': int(data.get('adaptive_c', 5)),
            'noise_reduction': data.get('noise_reduction', True),
            'kernel_size': int(data.get('kernel_size', 3)),
            'target_size': int(data.get('target_size', 1200))  # 700 → 1200 に拡大
        }
        
        # 画像処理実行
        result = image_processor.process_image(image_array, options)
        
        # 処理結果画像をBase64エンコード
        _, buffer = cv2.imencode('.png', result['processed_image'])
        processed_image_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'processed_image': f"data:image/png;base64,{processed_image_b64}",
            'grid': result['grid'],
            'width': result['width'],
            'height': result['height'],
            'auto_threshold': result['auto_threshold'],
            'processing_time': result['processing_time'],
            'binarization_mode': options['binarization_mode']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligent-process', methods=['POST'])
def intelligent_process_image():
    """🤖 インテリジェント自動画像処理API"""
    try:
        data = request.get_json()
        
        # Base64画像データをデコード
        image_data = data['image_data'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # PIL Imageから NumPy配列に変換
        pil_image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(pil_image)
        
        # ★修正: 目標サイズを大きくして点設定を楽にする
        target_size = int(data.get('target_size', 1200))  # 700 → 1200 に拡大
        
        # インテリジェント自動処理実行
        result = image_processor.intelligent_auto_process(image_array, target_size)
        
        # 処理結果画像をBase64エンコード
        _, buffer = cv2.imencode('.png', result['processed_image'])
        processed_image_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # 分析結果のフォーマット
        analysis = result['analysis']
        binarization_choice = analysis['binarization_choice']
        pathfinding_choice = analysis['pathfinding_choice']
        
        # オリジナル画像データも保存
        original_image_b64 = data['image_data']
        
        # 🛣️ 道路ネットワークを事前生成
        binary_array = result['processed_image']
        try:
            network_data = pathfinder.road_network_gen.generate_road_network(binary_array)
            road_network_preview = {
                'nodes': [{'x': int(float(x)), 'y': int(float(y)), 'id': int(float(node_id))} for x, y, node_id in network_data['nodes']],
                'nodes_count': int(len(network_data['nodes']))
            }
            
            # スケルトン画像を生成
            if network_data['skeleton'] is not None:
                skeleton = network_data['skeleton']
                display_skeleton = np.zeros_like(skeleton)
                display_skeleton[skeleton == 255] = 180
                _, skeleton_buffer = cv2.imencode('.png', display_skeleton)
                skeleton_b64 = base64.b64encode(skeleton_buffer).decode('utf-8')
                road_network_preview['skeleton_image'] = f"data:image/png;base64,{skeleton_b64}"
                print(f"✅ プレビュー用スケルトン画像生成: {skeleton.shape}")
            else:
                road_network_preview['skeleton_image'] = None
        except Exception as e:
            print(f"⚠️ 道路ネットワークプレビュー生成エラー: {e}")
            road_network_preview = None
        
        return jsonify({
            'success': True,
            'processed_image': f"data:image/png;base64,{processed_image_b64}",
            'original_image_base64': original_image_b64,  # 元画像データを返す
            'grid': result['grid'],
            'width': result['width'],
            'height': result['height'],
            'auto_threshold': result['auto_threshold'],
            'processing_time': result['processing_time'],
            'road_network_preview': road_network_preview,  # 🛣️ 道路ネットワークプレビューデータを追加
            'intelligent_analysis': {
                'selected_binarization': {
                    'method': binarization_choice['method'],
                    'confidence': round(binarization_choice['confidence'] * 100, 1),
                    'reason': binarization_choice['reason'],
                    'parameters': binarization_choice['parameters']
                },
                'recommended_pathfinding': {
                    'algorithm': pathfinding_choice['algorithm'],
                    'confidence': round(pathfinding_choice['confidence'] * 100, 1),
                    'reason': pathfinding_choice['reason'],
                    'estimated_speed': pathfinding_choice['estimated_speed']
                },
                'image_features': {
                    'complexity_score': round(analysis['features']['complexity_score'] * 100, 1),
                    'dominant_colors': analysis['features']['dominant_colors'],
                    'edge_density': round(analysis['features']['edge_density'] * 100, 1),
                    'rectangularity': round(analysis['features'].get('rectangularity', 0) * 100, 1),
                    'is_color_image': not analysis['features'].get('is_grayscale', False)
                },
                'timing': analysis['timing']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/find-path', methods=['POST'])
def find_path():
    """経路探索API"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        # データ検証
        if 'grid' not in data:
            return jsonify({'success': False, 'error': 'Grid data is required'}), 400
            
        grid = data['grid']
        
        # JavaScriptからのデータ形式に対応
        start_data = data.get('start_point') or data.get('start')
        end_data = data.get('end_point') or data.get('end')
        
        if not start_data or not end_data:
            return jsonify({'success': False, 'error': 'Start and end points are required'}), 400
            
        if 'x' not in start_data or 'y' not in start_data:
            return jsonify({'success': False, 'error': 'Invalid start point format'}), 400
            
        if 'x' not in end_data or 'y' not in end_data:
            return jsonify({'success': False, 'error': 'Invalid end point format'}), 400
        
        start_point = (start_data['x'], start_data['y'])
        end_point = (end_data['x'], end_data['y'])
        algorithm = data.get('algorithm', 'BFS')
        
        print(f"🔍 経路検索開始: {start_point} → {end_point}, アルゴリズム: {algorithm}")
        
        height, width = len(grid), len(grid[0])
        
        # 🔧 開始点・終了点の検証と自動補正
        adjusted_start = start_point
        adjusted_end = end_point
        point_adjustments = {}
        
        def find_nearest_passable_point(grid, point, max_radius=200):
            """最寄りの通行可能な点を探す（半径200ピクセルまで検索）"""
            x, y = point
            height, width = len(grid), len(grid[0])
            for radius in range(1, max_radius + 1):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if abs(dx) == radius or abs(dy) == radius:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == 0:
                                return (nx, ny)
            return None
        
        # 境界チェック
        if not (0 <= start_point[0] < width and 0 <= start_point[1] < height):
            return jsonify({'success': False, 'error': '開始点が画像の範囲外です'}), 400
        if not (0 <= end_point[0] < width and 0 <= end_point[1] < height):
            return jsonify({'success': False, 'error': '終了点が画像の範囲外です'}), 400
        
        # 開始点が通行不可の場合、自動補正
        if grid[start_point[1]][start_point[0]] == 1:
            new_start = find_nearest_passable_point(grid, start_point)
            if new_start:
                adjusted_start = new_start
                point_adjustments['start'] = {
                    'original': {'x': start_point[0], 'y': start_point[1]},
                    'adjusted': {'x': new_start[0], 'y': new_start[1]},
                    'distance': int(np.sqrt((new_start[0]-start_point[0])**2 + (new_start[1]-start_point[1])**2))
                }
                print(f"📍 開始点を自動補正: {start_point} → {adjusted_start}")
            else:
                return jsonify({
                    'success': False, 
                    'error': '開始点が通行不可能な場所にあり、近くに通行可能な点が見つかりません。別の位置を選択してください。'
                }), 400
        
        # 終了点が通行不可の場合、自動補正
        if grid[end_point[1]][end_point[0]] == 1:
            new_end = find_nearest_passable_point(grid, end_point)
            if new_end:
                adjusted_end = new_end
                point_adjustments['end'] = {
                    'original': {'x': end_point[0], 'y': end_point[1]},
                    'adjusted': {'x': new_end[0], 'y': new_end[1]},
                    'distance': int(np.sqrt((new_end[0]-end_point[0])**2 + (new_end[1]-end_point[1])**2))
                }
                print(f"📍 終了点を自動補正: {end_point} → {adjusted_end}")
            else:
                return jsonify({
                    'success': False, 
                    'error': '終了点が通行不可能な場所にあり、近くに通行可能な点が見つかりません。別の位置を選択してください。'
                }), 400
        
        # 補正後の点で経路探索を実行
        start_point = adjusted_start
        end_point = adjusted_end
        
        start_time = time.time()
        
        # 🛣️ 新しい道路ネットワークベースの経路探索
        use_road_network = data.get('use_road_network', True)  # デフォルトで道路ネットワーク使用
        
        if use_road_network:
            # 道路ネットワークベースの経路探索
            print(f"🛣️ 道路ネットワークベース経路探索: {algorithm}")
            pathfinding_result = pathfinder.find_path_with_road_network(grid, start_point, end_point, algorithm)
            
            if 'fallback' in pathfinding_result and pathfinding_result['fallback']:
                print("⚠️ 道路ネットワーク経路探索失敗、従来アルゴリズムにフォールバック（ネットワークデータは保持）")
                path = pathfinding_result['path']
                # フォールバック時でも道路ネットワークデータがあれば使用
                if 'skeleton' in pathfinding_result and 'nodes' in pathfinding_result:
                    road_network_data = {
                        'nodes': pathfinding_result.get('nodes', []),
                        'edges': pathfinding_result.get('edges', []),
                        'start_road': None,
                        'end_road': None,
                        'road_path': [],
                        'skeleton': pathfinding_result.get('skeleton')
                    }
                else:
                    road_network_data = None
            else:
                path = pathfinding_result['path']
                road_network_data = {
                    'nodes': pathfinding_result.get('nodes', []),
                    'edges': pathfinding_result.get('edges', []),
                    'start_road': pathfinding_result.get('start_road'),
                    'end_road': pathfinding_result.get('end_road'),
                    'road_path': pathfinding_result.get('road_path', [])
                }
        else:
            # 従来のアルゴリズム
            print(f"🔄 従来型経路探索: {algorithm}")
            road_network_data = None
            if algorithm == 'BFS':
                path = pathfinder.bfs_pathfinding(grid, start_point, end_point)
            elif algorithm == 'A*':
                path = pathfinder.astar_pathfinding(grid, start_point, end_point)
            elif algorithm == 'Dijkstra':
                path = pathfinder.dijkstra_pathfinding(grid, start_point, end_point)
            else:
                path = pathfinder.bfs_pathfinding(grid, start_point, end_point)
        
        processing_time = (time.time() - start_time) * 1000  # ミリ秒に変換
        
        if path and len(path) > 0:
            # パスを辞書形式に変換（numpy型を確実にPython標準型に変換）
            path_coords = [{'x': int(float(x)), 'y': int(float(y))} for x, y in path]
            
            # 元画像データを取得（ナビゲーション指示用）
            original_image_for_navigation = None
            
            # 元画像データが存在する場合はデコードして使用
            if 'original_image_base64' in data and data['original_image_base64']:
                try:
                    # Base64デコード（data:image形式の場合はヘッダーを除去）
                    original_base64 = data['original_image_base64']
                    if ',' in original_base64:
                        original_base64 = original_base64.split(',')[1]
                    
                    original_bytes = base64.b64decode(original_base64)
                    original_np = np.frombuffer(original_bytes, np.uint8)
                    original_image_for_navigation = cv2.imdecode(original_np, cv2.IMREAD_COLOR)
                    
                    if original_image_for_navigation is not None:
                        # グリッドサイズに合わせてリサイズ
                        grid_height = len(grid)
                        grid_width = len(grid[0])
                        original_image_for_navigation = cv2.resize(
                            original_image_for_navigation, 
                            (grid_width, grid_height), 
                            interpolation=cv2.INTER_AREA
                        )
                except Exception as e:
                    print(f"ナビゲーション用画像の読み込みエラー: {e}")
                    original_image_for_navigation = None
            
            # ★改良3: ナビゲーション指示を生成（ランドマーク名使用）
            try:
                navigation_instructions = navigation_generator.generate_navigation_instructions(
                    path, original_image_for_navigation
                )
                print(f"✅ ナビゲーション指示生成完了: {len(navigation_instructions) if navigation_instructions else 0}件")
            except Exception as e:
                print(f"❌ ナビゲーション指示生成エラー: {e}")
                import traceback
                traceback.print_exc()
                # フォールバック: シンプルな指示を生成
                navigation_instructions = [
                    {
                        "step": 1,
                        "distance": 0,
                        "instruction": "🚩 出発地点からスタートしてください",
                        "position": {"x": int(path[0][0]), "y": int(path[0][1])},
                        "direction": "開始",
                        "landmark": "出発地点"
                    },
                    {
                        "step": 2,
                        "distance": 0,
                        "instruction": f"🏁 目的地に到着しました！",
                        "position": {"x": int(path[-1][0]), "y": int(path[-1][1])},
                        "direction": "到着",
                        "landmark": "目的地"
                    }
                ]
            
            # ⚡ 後処理を完全に削除 - 画像処理なしでナビゲーション指示のみ提供
            original_image_data = None
            cropped_image_data = None
            crop_info = None
            
            print("⚡ 高速モード: 画像の後処理をスキップしてナビゲーション指示のみ生成")
            
            print(f"⚡ 超高速経路検索成功: {len(path)}ステップ, {processing_time:.1f}ms, ナビ指示: {len(navigation_instructions) if navigation_instructions else 0}件（後処理なし）")
            
            response_data = {
                'success': True,
                'path': path_coords,
                'path_length': int(len(path)),
                'algorithm': algorithm,
                'processing_time': float(processing_time),
                'navigation_instructions': navigation_instructions if navigation_instructions else [],
                'use_road_network': bool(use_road_network)
            }
            
            # 点の自動補正情報を追加
            if point_adjustments:
                response_data['point_adjustments'] = point_adjustments
                print(f"📍 点の自動補正情報: {point_adjustments}")
            
            # numpy型をPython標準型に変換
            response_data = convert_numpy_types(response_data)
            
            # 道路ネットワークデータを追加
            if road_network_data:
                response_data['road_network'] = {
                    'nodes': [{'x': int(float(x)), 'y': int(float(y)), 'id': int(float(node_id))} for x, y, node_id in road_network_data['nodes']],
                    'edges_count': int(len(road_network_data['edges'])),
                    'start_road': {'x': int(float(road_network_data['start_road'][0])), 'y': int(float(road_network_data['start_road'][1]))} if road_network_data['start_road'] else None,
                    'end_road': {'x': int(float(road_network_data['end_road'][0])), 'y': int(float(road_network_data['end_road'][1]))} if road_network_data['end_road'] else None,
                    'road_path': [{'x': int(float(x)), 'y': int(float(y))} for x, y in road_network_data['road_path']]
                }
                
                # スケルトン画像をBase64で追加
                if 'skeleton' in pathfinding_result and pathfinding_result['skeleton'] is not None:
                    skeleton = pathfinding_result['skeleton']
                    # スケルトン画像を可視化用に処理（白い線を灰色に変換）
                    display_skeleton = np.zeros_like(skeleton)
                    display_skeleton[skeleton == 255] = 180  # 薄い灰色
                    _, skeleton_buffer = cv2.imencode('.png', display_skeleton)
                    skeleton_b64 = base64.b64encode(skeleton_buffer).decode('utf-8')
                    response_data['road_network']['skeleton_image'] = f"data:image/png;base64,{skeleton_b64}"
                    print(f"✅ スケルトン画像生成完了: {skeleton.shape}")
                else:
                    print("⚠️ スケルトン画像が見つかりません")
            
            # 画像データが生成された場合は追加
            if original_image_data:
                response_data['path_image'] = f"data:image/png;base64,{original_image_data}"
                
            if cropped_image_data:
                response_data['cropped_path_image'] = f"data:image/png;base64,{cropped_image_data}"
                response_data['crop_info'] = crop_info
            
            # 最終確認：すべてのnumpy型を標準Python型に変換
            final_response = convert_numpy_types(response_data)
            return jsonify(final_response)
        else:
            print("❌ 経路が見つかりませんでした")
            return jsonify({
                'success': False,
                'error': '経路が見つかりませんでした。開始点と終了点が通行可能な場所にあり、互いに接続されているか確認してください。'
            })
        
    except KeyError as e:
        error_msg = f"Missing required field: {str(e)}"
        print(f"❌ データエラー: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 400
        
    except Exception as e:
        error_msg = f"経路検索エラー: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/test-map-detection', methods=['POST'])
def test_map_detection():
    """🗺️ 改良版地図切り出し機能のテスト用エンドポイント"""
    try:
        data = request.get_json()
        
        if 'image_data' not in data:
            return jsonify({'success': False, 'error': '画像データが必要です'})
        
        # Base64画像データをデコード
        image_data = data['image_data'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # PIL Imageから NumPy配列に変換
        pil_image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(pil_image)
        
        print(f"🔍 地図検出テスト開始: 画像サイズ {image_array.shape}")
        
        # 改良版地図切り出し機能をテスト
        auto_cropped_image, map_region = image_enhancer.auto_crop_map_region(image_array)
        print(f"🎯 検出結果: {map_region}")
        
        # 元画像と切り出し画像を比較表示用にエンコード
        _, original_encoded = cv2.imencode('.png', image_array)
        original_b64 = base64.b64encode(original_encoded).decode('utf-8')
        
        _, cropped_encoded = cv2.imencode('.png', auto_cropped_image)
        cropped_b64 = base64.b64encode(cropped_encoded).decode('utf-8')
        
        # カバレッジ率を計算
        original_area = image_array.shape[0] * image_array.shape[1]
        cropped_area = map_region["width"] * map_region["height"]
        coverage = (cropped_area / original_area) * 100
        
        return jsonify({
            'success': True,
            'map_region': map_region,
            'coverage_percent': round(coverage, 1),
            'original_image': f"data:image/png;base64,{original_b64}",
            'cropped_image': f"data:image/png;base64,{cropped_b64}",
            'original_size': {
                'width': image_array.shape[1], 
                'height': image_array.shape[0]
            },
            'cropped_size': {
                'width': auto_cropped_image.shape[1], 
                'height': auto_cropped_image.shape[0]
            },
            'detection_info': {
                'method': 'スマート検出（エッジ + 色分布 + 分散分析）',
                'confidence': 'HIGH' if coverage > 80 else 'MEDIUM' if coverage > 40 else 'LOW'
            }
        })
        
    except Exception as e:
        print(f"❌ 地図検出テスト処理エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/static/<path:filename>')
def static_files(filename):
    """静的ファイル配信"""
    return send_from_directory('static', filename)

@app.route('/presentation')
def presentation():
    """研究発表スライド表示"""
    try:
        with open('/home/user/cv_pathfinding_presentation.html', 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error loading presentation: {e}", 404

def main():
    """メイン関数 - argparseによるコマンドライン引数サポート"""
    import argparse
    
    parser = argparse.ArgumentParser(description='高速CV経路検出システム - Python版（フロアマップ対応）')
    parser.add_argument('--host', default='127.0.0.1', help='ホストアドレス（デフォルト: 127.0.0.1）')
    parser.add_argument('--port', type=int, default=5000, help='ポート番号（デフォルト: 5000）')
    parser.add_argument('--debug', action='store_true', help='デバッグモードで実行')
    
    args = parser.parse_args()
    
    # 必要なディレクトリを作成
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("=" * 60)
    print("🚀 CV画像処理経路検索システム - Python版（フロアマップ対応）")
    print("=" * 60)
    print(f"📍 アクセスURL: http://{args.host}:{args.port}")
    print("🆕 新機能: フロアマップ・建物図面に特化した高度な二値化処理")
    print("📝 使用方法:")
    print("   1. ブラウザで上記URLにアクセス")
    print("   2. フロアマップ画像をアップロード")
    print("   3. 二値化方法で「フロアマップ特化」を選択（推奨）")
    print("   4. 処理実行して経路探索を体験")
    print("=" * 60)
    
    try:
        app.run(debug=args.debug, host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n🛑 アプリケーションを終了しました")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

if __name__ == '__main__':
    main()