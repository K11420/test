#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Python版 高度ナビゲーションシステム
元の色付き画像のみを使用し、詳細な移動指示を提供
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional
import math
import heapq
from dataclasses import dataclass
import base64
from io import BytesIO

@dataclass
class Point:
    """座標点を表すクラス"""
    x: int
    y: int
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))

@dataclass
class NavigationStep:
    """ナビゲーション手順を表すクラス"""
    position: Point
    direction: str  # 'straight', 'right', 'left', 'u_turn'
    distance: float
    instruction: str
    landmark: Optional[str] = None

class ColorMapNavigator:
    """色付き地図を使用したナビゲーションシステム"""
    
    def __init__(self, image_size: Tuple[int, int] = (1200, 800)):
        """
        初期化
        Args:
            image_size: 表示する画像サイズ (width, height)
        """
        self.image_size = image_size
        self.original_image = None
        self.processed_image = None
        self.binary_map = None
        self.start_point = None
        self.end_point = None
        self.path = []
        self.navigation_steps = []
        
        # 色の定義
        self.colors = {
            'path': (0, 255, 0),      # 緑色
            'start': (0, 0, 255),     # 青色  
            'end': (255, 0, 0),       # 赤色
            'obstacle': (0, 0, 0),    # 黒色
            'free': (255, 255, 255)   # 白色
        }
    
    def load_image(self, image_path: str) -> bool:
        """
        画像を読み込んで処理
        Args:
            image_path: 画像ファイルのパス
        Returns:
            bool: 読み込み成功の可否
        """
        try:
            # 画像読み込み
            self.original_image = cv2.imread(image_path)
            if self.original_image is None:
                return False
            
            # BGRからRGBに変換
            self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
            
            # 指定サイズにリサイズ
            self.original_image = cv2.resize(self.original_image, self.image_size)
            
            # 処理用のコピーを作成
            self.processed_image = self.original_image.copy()
            
            # 二値マップを生成（経路探索用）
            self._create_binary_map()
            
            return True
        except Exception as e:
            print(f"画像読み込みエラー: {e}")
            return False
    
    def _create_binary_map(self):
        """元画像から二値マップを作成（内部処理用のみ）"""
        try:
            # グレースケール変換
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2GRAY)
            
            # 適応的二値化を使用
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # ノイズ除去
            kernel = np.ones((3, 3), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            
            # 二値マップ作成（0=障害物, 1=通行可能）
            self.binary_map = (binary > 128).astype(np.uint8)
            
        except Exception as e:
            print(f"二値マップ作成エラー: {e}")
            # フォールバック: 全て通行可能
            self.binary_map = np.ones(self.image_size[::-1], dtype=np.uint8)
    
    def set_start_point(self, x: int, y: int):
        """開始点を設定"""
        self.start_point = Point(x, y)
        self._update_display()
    
    def set_end_point(self, x: int, y: int):
        """終了点を設定"""
        self.end_point = Point(x, y)
        self._update_display()
    
    def _update_display(self):
        """表示を更新（元の色付き画像上に点を描画）"""
        self.processed_image = self.original_image.copy()
        
        # 開始点を描画
        if self.start_point:
            cv2.circle(self.processed_image, (self.start_point.x, self.start_point.y), 
                      10, self.colors['start'], -1)
            cv2.circle(self.processed_image, (self.start_point.x, self.start_point.y), 
                      12, (255, 255, 255), 2)
        
        # 終了点を描画
        if self.end_point:
            cv2.circle(self.processed_image, (self.end_point.x, self.end_point.y), 
                      10, self.colors['end'], -1)
            cv2.circle(self.processed_image, (self.end_point.x, self.end_point.y), 
                      12, (255, 255, 255), 2)
        
        # パスを描画
        if len(self.path) > 1:
            self._draw_path()
    
    def find_path(self, algorithm: str = 'astar') -> bool:
        """
        経路探索を実行
        Args:
            algorithm: 使用するアルゴリズム ('astar', 'bfs', 'dijkstra')
        Returns:
            bool: 経路発見の成功可否
        """
        if not self.start_point or not self.end_point:
            print("開始点と終了点を設定してください")
            return False
        
        if algorithm == 'astar':
            self.path = self._astar()
        elif algorithm == 'bfs':
            self.path = self._bfs()
        elif algorithm == 'dijkstra':
            self.path = self._dijkstra()
        else:
            print("未対応のアルゴリズムです")
            return False
        
        if self.path:
            self._generate_navigation_instructions()
            self._update_display()
            return True
        else:
            print("経路が見つかりません")
            return False
    
    def _astar(self) -> List[Point]:
        """A*アルゴリズムによる経路探索"""
        def heuristic(a: Point, b: Point) -> float:
            return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
        
        def get_neighbors(point: Point) -> List[Point]:
            neighbors = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    new_x, new_y = point.x + dx, point.y + dy
                    
                    if (0 <= new_x < self.image_size[0] and 
                        0 <= new_y < self.image_size[1] and
                        self.binary_map[new_y, new_x] == 1):
                        neighbors.append(Point(new_x, new_y))
            return neighbors
        
        open_set = [(0, self.start_point)]
        came_from = {}
        g_score = {self.start_point: 0}
        f_score = {self.start_point: heuristic(self.start_point, self.end_point)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == self.end_point:
                # パスを再構築
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(self.start_point)
                return list(reversed(path))
            
            for neighbor in get_neighbors(current):
                tentative_g_score = g_score[current] + heuristic(current, neighbor)
                
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + heuristic(neighbor, self.end_point)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return []
    
    def _bfs(self) -> List[Point]:
        """BFS（幅優先探索）による経路探索"""
        from collections import deque
        
        def get_neighbors(point: Point) -> List[Point]:
            neighbors = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    new_x, new_y = point.x + dx, point.y + dy
                    
                    if (0 <= new_x < self.image_size[0] and 
                        0 <= new_y < self.image_size[1] and
                        self.binary_map[new_y, new_x] == 1):
                        neighbors.append(Point(new_x, new_y))
            return neighbors
        
        queue = deque([self.start_point])
        visited = {self.start_point}
        came_from = {}
        
        while queue:
            current = queue.popleft()
            
            if current == self.end_point:
                # パスを再構築
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(self.start_point)
                return list(reversed(path))
            
            for neighbor in get_neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    came_from[neighbor] = current
                    queue.append(neighbor)
        
        return []
    
    def _dijkstra(self) -> List[Point]:
        """Dijkstraアルゴリズムによる経路探索"""
        def get_neighbors(point: Point) -> List[Tuple[Point, float]]:
            neighbors = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    new_x, new_y = point.x + dx, point.y + dy
                    
                    if (0 <= new_x < self.image_size[0] and 
                        0 <= new_y < self.image_size[1] and
                        self.binary_map[new_y, new_x] == 1):
                        # 対角線移動は√2倍のコスト
                        cost = math.sqrt(2) if abs(dx) + abs(dy) == 2 else 1
                        neighbors.append((Point(new_x, new_y), cost))
            return neighbors
        
        distances = {self.start_point: 0}
        came_from = {}
        pq = [(0, self.start_point)]
        
        while pq:
            current_dist, current = heapq.heappop(pq)
            
            if current == self.end_point:
                # パスを再構築
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(self.start_point)
                return list(reversed(path))
            
            if current_dist > distances[current]:
                continue
            
            for neighbor, weight in get_neighbors(current):
                distance = current_dist + weight
                
                if neighbor not in distances or distance < distances[neighbor]:
                    distances[neighbor] = distance
                    came_from[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))
        
        return []
    
    def _draw_path(self):
        """パスを元の色付き画像上に描画"""
        if len(self.path) < 2:
            return
        
        # パスラインを描画
        for i in range(len(self.path) - 1):
            pt1 = (self.path[i].x, self.path[i].y)
            pt2 = (self.path[i + 1].x, self.path[i + 1].y)
            cv2.line(self.processed_image, pt1, pt2, self.colors['path'], 4)
        
        # 方向矢印を描画
        self._draw_direction_arrows()
    
    def _draw_direction_arrows(self):
        """パス上に方向矢印を描画"""
        arrow_interval = max(20, len(self.path) // 10)  # 矢印の間隔
        
        for i in range(0, len(self.path) - 1, arrow_interval):
            if i + 1 < len(self.path):
                start = self.path[i]
                end = self.path[i + 1]
                
                # 矢印の方向を計算
                dx = end.x - start.x
                dy = end.y - start.y
                
                if dx == 0 and dy == 0:
                    continue
                
                # 矢印を描画
                arrow_length = 15
                angle = math.atan2(dy, dx)
                
                # 矢印の先端
                arrow_end = (int(start.x + arrow_length * math.cos(angle)),
                           int(start.y + arrow_length * math.sin(angle)))
                
                # 矢印の羽根
                wing_angle = 0.5
                wing_length = 8
                wing1 = (int(arrow_end[0] - wing_length * math.cos(angle - wing_angle)),
                        int(arrow_end[1] - wing_length * math.sin(angle - wing_angle)))
                wing2 = (int(arrow_end[0] - wing_length * math.cos(angle + wing_angle)),
                        int(arrow_end[1] - wing_length * math.sin(angle + wing_angle)))
                
                # 矢印を描画
                cv2.line(self.processed_image, (start.x, start.y), arrow_end, (255, 255, 0), 3)
                cv2.line(self.processed_image, arrow_end, wing1, (255, 255, 0), 3)
                cv2.line(self.processed_image, arrow_end, wing2, (255, 255, 0), 3)
    
    def _generate_navigation_instructions(self):
        """詳細なナビゲーション指示を生成"""
        if len(self.path) < 3:
            return
        
        self.navigation_steps = []
        
        for i in range(len(self.path) - 2):
            current = self.path[i]
            next_point = self.path[i + 1]
            after_next = self.path[i + 2]
            
            # 現在の方向と次の方向を計算
            current_direction = math.atan2(next_point.y - current.y, next_point.x - current.x)
            next_direction = math.atan2(after_next.y - next_point.y, after_next.x - next_point.x)
            
            # 角度の差を計算
            angle_diff = next_direction - current_direction
            
            # 角度を-πからπの範囲に正規化
            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi
            
            # 距離を計算
            distance = math.sqrt((next_point.x - current.x) ** 2 + (next_point.y - current.y) ** 2)
            
            # 方向を判定
            if abs(angle_diff) < 0.3:  # 約17度
                direction = 'straight'
                instruction = f"{distance:.0f}ピクセル直進"
            elif angle_diff > 0.3:
                if angle_diff > 2.8:  # 約160度
                    direction = 'u_turn'
                    instruction = f"{distance:.0f}ピクセル先でUターン"
                else:
                    direction = 'left'
                    instruction = f"{distance:.0f}ピクセル先で左に曲がる"
            else:
                if angle_diff < -2.8:  # 約160度
                    direction = 'u_turn'
                    instruction = f"{distance:.0f}ピクセル先でUターン"
                else:
                    direction = 'right'
                    instruction = f"{distance:.0f}ピクセル先で右に曲がる"
            
            step = NavigationStep(
                position=current,
                direction=direction,
                distance=distance,
                instruction=instruction
            )
            self.navigation_steps.append(step)
        
        # 最後のステップ（目的地到着）
        if len(self.path) >= 2:
            last_point = self.path[-2]
            final_point = self.path[-1]
            final_distance = math.sqrt((final_point.x - last_point.x) ** 2 + 
                                     (final_point.y - last_point.y) ** 2)
            
            final_step = NavigationStep(
                position=last_point,
                direction='arrival',
                distance=final_distance,
                instruction=f"あと{final_distance:.0f}ピクセルで目的地に到着"
            )
            self.navigation_steps.append(final_step)
    
    def get_navigation_instructions(self) -> List[str]:
        """ナビゲーション指示のリストを取得"""
        return [step.instruction for step in self.navigation_steps]
    
    def get_image_as_base64(self) -> str:
        """処理済み画像をbase64エンコードして取得"""
        if self.processed_image is None:
            return ""
        
        # PIL Imageに変換
        image_pil = Image.fromarray(self.processed_image)
        
        # BytesIOオブジェクトに保存
        buffer = BytesIO()
        image_pil.save(buffer, format='PNG')
        
        # Base64エンコード
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return image_base64
    
    def save_result(self, output_path: str):
        """結果画像を保存"""
        if self.processed_image is not None:
            image_pil = Image.fromarray(self.processed_image)
            image_pil.save(output_path)
            print(f"結果を保存しました: {output_path}")

# テスト用メイン関数
if __name__ == "__main__":
    # ナビゲーターを初期化
    navigator = ColorMapNavigator(image_size=(1200, 800))
    
    print("🚀 Python版 高度ナビゲーションシステム")
    print("元の色付き画像のみを使用し、詳細な移動指示を提供")
    print("="*60)
    
    # 使用例
    print("\n使用例:")
    print("1. navigator.load_image('map.jpg')  # 地図画像を読み込み")
    print("2. navigator.set_start_point(100, 100)  # 開始点を設定")
    print("3. navigator.set_end_point(800, 600)    # 終了点を設定")
    print("4. navigator.find_path('astar')          # 経路探索実行")
    print("5. instructions = navigator.get_navigation_instructions()  # 指示取得")
    print("6. navigator.save_result('result.png')   # 結果保存")