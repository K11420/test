#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Python版 ナビゲーションシステム - Flask Webアプリケーション
元の色付き画像のみを使用し、詳細な移動指示を提供
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import time
from werkzeug.utils import secure_filename
from navigation_system import ColorMapNavigator, Point
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

# 設定
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# アップロードフォルダを作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 許可されるファイル拡張子
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# ナビゲーターのインスタンスを管理
navigators = {}

def allowed_file(filename):
    """ファイル拡張子をチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """画像ファイルをアップロード"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if file and allowed_file(file.filename):
            # ファイルを保存
            filename = secure_filename(file.filename)
            timestamp = int(time.time())
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # ナビゲーターを作成
            session_id = str(uuid.uuid4())
            navigator = ColorMapNavigator(image_size=(1200, 800))
            
            if navigator.load_image(filepath):
                navigators[session_id] = {
                    'navigator': navigator,
                    'filepath': filepath
                }
                
                # 元画像をbase64で返す
                image_base64 = navigator.get_image_as_base64()
                
                return jsonify({
                    'success': True,
                    'session_id': session_id,
                    'image': f"data:image/png;base64,{image_base64}",
                    'width': navigator.image_size[0],
                    'height': navigator.image_size[1]
                })
            else:
                return jsonify({'error': '画像の読み込みに失敗しました'}), 400
        
        return jsonify({'error': '許可されていないファイル形式です'}), 400
        
    except Exception as e:
        return jsonify({'error': f'アップロードエラー: {str(e)}'}), 500

@app.route('/api/set_points', methods=['POST'])
def set_points():
    """開始点と終了点を設定"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        start_x = data.get('start_x')
        start_y = data.get('start_y')
        end_x = data.get('end_x')
        end_y = data.get('end_y')
        
        if session_id not in navigators:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        navigator = navigators[session_id]['navigator']
        
        # 点を設定
        if start_x is not None and start_y is not None:
            navigator.set_start_point(int(start_x), int(start_y))
        
        if end_x is not None and end_y is not None:
            navigator.set_end_point(int(end_x), int(end_y))
        
        # 更新された画像を取得
        image_base64 = navigator.get_image_as_base64()
        
        return jsonify({
            'success': True,
            'image': f"data:image/png;base64,{image_base64}"
        })
        
    except Exception as e:
        return jsonify({'error': f'点設定エラー: {str(e)}'}), 500

@app.route('/api/find_path', methods=['POST'])
def find_path():
    """経路探索を実行"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        algorithm = data.get('algorithm', 'astar')
        
        if session_id not in navigators:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        navigator = navigators[session_id]['navigator']
        
        # 経路探索実行
        start_time = time.time()
        success = navigator.find_path(algorithm)
        end_time = time.time()
        
        if success:
            # ナビゲーション指示を取得
            instructions = navigator.get_navigation_instructions()
            
            # 結果画像を取得
            image_base64 = navigator.get_image_as_base64()
            
            return jsonify({
                'success': True,
                'image': f"data:image/png;base64,{image_base64}",
                'instructions': instructions,
                'processing_time': round(end_time - start_time, 3),
                'path_length': len(navigator.path)
            })
        else:
            return jsonify({
                'success': False,
                'error': '経路が見つかりません'
            })
        
    except Exception as e:
        return jsonify({'error': f'経路探索エラー: {str(e)}'}), 500

@app.route('/api/get_instructions/<session_id>')
def get_instructions(session_id):
    """詳細なナビゲーション指示を取得"""
    try:
        if session_id not in navigators:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        navigator = navigators[session_id]['navigator']
        instructions = navigator.get_navigation_instructions()
        
        # より詳細な指示を生成
        detailed_instructions = []
        for i, instruction in enumerate(instructions):
            detailed_instructions.append({
                'step': i + 1,
                'instruction': instruction,
                'type': 'navigation'
            })
        
        return jsonify({
            'success': True,
            'instructions': detailed_instructions,
            'total_steps': len(detailed_instructions)
        })
        
    except Exception as e:
        return jsonify({'error': f'指示取得エラー: {str(e)}'}), 500

@app.route('/api/download_result/<session_id>')
def download_result(session_id):
    """結果画像をダウンロード"""
    try:
        if session_id not in navigators:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        navigator = navigators[session_id]['navigator']
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            navigator.save_result(tmp_file.name)
            return send_file(tmp_file.name, 
                           as_attachment=True, 
                           download_name=f'navigation_result_{session_id[:8]}.png')
        
    except Exception as e:
        return jsonify({'error': f'ダウンロードエラー: {str(e)}'}), 500

@app.route('/api/clear/<session_id>', methods=['POST'])
def clear_session(session_id):
    """セッションをクリア"""
    try:
        if session_id in navigators:
            # ファイルを削除
            filepath = navigators[session_id]['filepath']
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # セッションを削除
            del navigators[session_id]
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': f'クリアエラー: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Python版 ナビゲーションシステム - Webアプリケーション")
    print("元の色付き画像のみを使用し、詳細な移動指示を提供")
    print("="*60)
    print("サーバーを起動しています...")
    
    app.run(host='0.0.0.0', port=5000, debug=True)