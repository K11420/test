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

app = Flask(__name__)
CORS(app)

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

class OptimizedPathfinder:
    """最適化された経路探索アルゴリズムクラス"""
    
    @staticmethod
    def bfs_pathfinding(grid: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        BFS（幅優先探索）による最短経路検索
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
        A*アルゴリズムによる経路検索
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
        Dijkstraアルゴリズムによる経路検索
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

# グローバルインスタンス
image_processor = ImageProcessor()
pathfinder = OptimizedPathfinder()

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
            'target_size': int(data.get('target_size', 700))
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

@app.route('/api/find-path', methods=['POST'])
def find_path():
    """経路探索API"""
    try:
        data = request.get_json()
        
        grid = data['grid']
        start_point = (data['start_point']['x'], data['start_point']['y'])
        end_point = (data['end_point']['x'], data['end_point']['y'])
        algorithm = data.get('algorithm', 'BFS')
        
        start_time = time.time()
        
        # アルゴリズム選択
        if algorithm == 'BFS':
            path = pathfinder.bfs_pathfinding(grid, start_point, end_point)
        elif algorithm == 'A*':
            path = pathfinder.astar_pathfinding(grid, start_point, end_point)
        elif algorithm == 'Dijkstra':
            path = pathfinder.dijkstra_pathfinding(grid, start_point, end_point)
        else:
            path = pathfinder.bfs_pathfinding(grid, start_point, end_point)
        
        processing_time = time.time() - start_time
        
        if path:
            # パスを辞書形式に変換
            path_coords = [{'x': x, 'y': y} for x, y in path]
            
            return jsonify({
                'success': True,
                'path': path_coords,
                'path_length': len(path),
                'algorithm': algorithm,
                'processing_time': processing_time
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No path found'
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    """静的ファイル配信"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # 静的ファイルディレクトリを作成
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, host='0.0.0.0', port=5000)