// 高速CV経路検出システム - Python版フロントエンド
// Flask + AJAX による高度な二値化処理と経路探索

class PythonPathfindingApp {
    constructor() {
        this.currentImageData = null;
        this.currentGrid = null;
        this.currentProcessedImage = null;
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start'; // 'start' or 'end'
        this.selectedAlgorithm = 'BFS';
        this.debounceTimer = null;
        
        this.initializeUI();
        this.bindEvents();
    }

    initializeUI() {
        // 初期パラメータ値を表示
        this.updateSliderValues();
        // デフォルトでBFSアルゴリズムを選択
        this.selectAlgorithm(document.querySelector('[data-algorithm="BFS"]'));
    }

    bindEvents() {
        // 画像選択
        document.getElementById('imageInput').addEventListener('change', (e) => {
            this.handleImageSelect(e);
        });

        // 処理実行
        document.getElementById('processBtn').addEventListener('click', () => {
            this.processImage();
        });

        // スライダー値更新とリアルタイムプレビュー
        const sliders = ['threshold', 'blockSize', 'adaptiveC', 'kernelSize'];
        sliders.forEach(slider => {
            const sliderElement = document.getElementById(`${slider}Slider`);
            sliderElement.addEventListener('input', (e) => {
                this.updateSliderValue(slider, e.target.value);
                this.scheduleRealtimeProcess();
            });
        });

        // 二値化方法変更
        document.getElementById('binarizationMode').addEventListener('change', () => {
            this.scheduleRealtimeProcess();
        });

        // ノイズ除去チェックボックス
        document.getElementById('noiseReduction').addEventListener('change', () => {
            this.scheduleRealtimeProcess();
        });

        // アルゴリズム選択
        document.querySelectorAll('.algorithm-card').forEach(card => {
            card.addEventListener('click', () => {
                this.selectAlgorithm(card);
            });
        });

        // 経路検索実行
        document.getElementById('findPathBtn').addEventListener('click', () => {
            this.findPath();
        });

        // クリア
        document.getElementById('clearPathBtn').addEventListener('click', () => {
            this.clearPath();
        });
    }

    updateSliderValues() {
        // 各スライダーの初期値を表示
        document.getElementById('thresholdValue').textContent = document.getElementById('thresholdSlider').value;
        document.getElementById('blockSizeValue').textContent = document.getElementById('blockSizeSlider').value;
        document.getElementById('adaptiveCValue').textContent = document.getElementById('adaptiveCSlider').value;
        document.getElementById('kernelSizeValue').textContent = document.getElementById('kernelSizeSlider').value;
    }

    updateSliderValue(sliderName, value) {
        document.getElementById(`${sliderName}Value`).textContent = value;
    }

    scheduleRealtimeProcess() {
        if (this.currentImageData) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.processImage();
            }, 300); // 300ms後に処理実行
        }
    }

    handleImageSelect(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            this.currentImageData = event.target.result;
            this.displayOriginalImage(event.target.result);
            document.getElementById('processBtn').disabled = false;
            this.processImage(); // 自動処理
        };
        reader.readAsDataURL(file);
    }

    displayOriginalImage(imageData) {
        const container = document.getElementById('originalImageContainer');
        container.innerHTML = '';
        
        const img = document.createElement('img');
        img.src = imageData;
        img.className = 'max-w-full h-auto mx-auto rounded-lg border';
        img.style.maxHeight = '400px';
        
        container.appendChild(img);
    }

    async processImage() {
        if (!this.currentImageData) return;

        this.showLoading('画像処理中...');

        try {
            const requestData = {
                image_data: this.currentImageData,
                binarization_mode: document.getElementById('binarizationMode').value,
                threshold: parseInt(document.getElementById('thresholdSlider').value),
                block_size: parseInt(document.getElementById('blockSizeSlider').value),
                adaptive_c: parseInt(document.getElementById('adaptiveCSlider').value),
                noise_reduction: document.getElementById('noiseReduction').checked,
                kernel_size: parseInt(document.getElementById('kernelSizeSlider').value),
                target_size: 700
            };

            const response = await axios.post('/api/process-image', requestData, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.data.success) {
                this.currentGrid = response.data.grid;
                this.currentProcessedImage = response.data.processed_image;
                
                this.displayProcessedImage(response.data.processed_image);
                this.enablePathfinding();
                
                // 自動閾値が取得できた場合は表示更新
                if (response.data.auto_threshold !== null) {
                    document.getElementById('autoThreshold').textContent = response.data.auto_threshold;
                }
            } else {
                this.showError('画像処理に失敗しました: ' + response.data.error);
            }
        } catch (error) {
            this.showError('画像処理エラー: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    displayProcessedImage(imageData) {
        const container = document.getElementById('processedImageContainer');
        container.innerHTML = '';
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const img = new Image();
        img.onload = () => {
            // キャンバスサイズを画像に合わせる
            canvas.width = img.width;
            canvas.height = img.height;
            
            // 画像を描画
            ctx.drawImage(img, 0, 0);
            
            // キャンバススタイル設定
            canvas.className = 'max-w-full h-auto mx-auto rounded-lg border cursor-crosshair';
            canvas.style.maxHeight = '400px';
            
            // クリックイベント追加
            canvas.addEventListener('click', (e) => {
                this.handleCanvasClick(e, canvas);
            });
            
            container.appendChild(canvas);
            
            // 既存の点を再描画
            this.redrawCanvas(canvas, ctx, img);
        };
        
        img.src = imageData;
    }

    handleCanvasClick(e, canvas) {
        if (!this.currentGrid) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        const x = Math.floor((e.clientX - rect.left) * scaleX);
        const y = Math.floor((e.clientY - rect.top) * scaleY);

        // グリッド範囲チェック
        if (x < 0 || x >= this.currentGrid[0].length || y < 0 || y >= this.currentGrid.length) {
            return;
        }

        // 壁かどうかチェック
        if (this.currentGrid[y][x] === 1) {
            alert('壁の上には点を設置できません');
            return;
        }

        if (this.clickMode === 'start') {
            this.startPoint = {x, y};
            document.getElementById('startStatus').textContent = `(${x}, ${y})`;
            document.getElementById('startStatus').className = 'font-mono bg-blue-100 text-blue-800 px-2 py-1 rounded';
            this.clickMode = 'end';
        } else {
            this.endPoint = {x, y};
            document.getElementById('endStatus').textContent = `(${x}, ${y})`;
            document.getElementById('endStatus').className = 'font-mono bg-red-100 text-red-800 px-2 py-1 rounded';
            this.clickMode = 'start';
        }

        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.onload = () => {
            this.redrawCanvas(canvas, ctx, img);
        };
        img.src = this.currentProcessedImage;
    }

    redrawCanvas(canvas, ctx, img) {
        // 画像を再描画
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);

        // 開始点と終了点を描画
        if (this.startPoint) {
            this.drawPoint(ctx, this.startPoint, '#3B82F6', 'S');
        }
        if (this.endPoint) {
            this.drawPoint(ctx, this.endPoint, '#EF4444', 'E');
        }
    }

    drawPoint(ctx, point, color, label) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(point.x, point.y, 8, 0, 2 * Math.PI);
        ctx.fill();
        
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        ctx.fillStyle = 'white';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, point.x, point.y);
    }

    selectAlgorithm(card) {
        // 全てのカードから選択状態を削除
        document.querySelectorAll('.algorithm-card').forEach(c => {
            c.classList.remove('selected');
        });
        
        // 選択されたカードにスタイルを適用
        card.classList.add('selected');
        this.selectedAlgorithm = card.dataset.algorithm;
    }

    enablePathfinding() {
        document.getElementById('findPathBtn').disabled = false;
    }

    async findPath() {
        if (!this.currentGrid || !this.startPoint || !this.endPoint || !this.selectedAlgorithm) {
            alert('グリッド、開始点、終了点、アルゴリズムがすべて設定されている必要があります');
            return;
        }

        this.showLoading(`${this.selectedAlgorithm}アルゴリズムで経路検索中...`);

        try {
            const requestData = {
                grid: this.currentGrid,
                start_point: this.startPoint,
                end_point: this.endPoint,
                algorithm: this.selectedAlgorithm
            };

            const response = await axios.post('/api/find-path', requestData, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.data.success) {
                this.drawPath(response.data.path);
                this.showResult(response.data);
            } else {
                this.showError('経路が見つかりませんでした: ' + response.data.error);
            }
        } catch (error) {
            this.showError('経路検索エラー: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    drawPath(path) {
        if (!path || path.length === 0) return;

        const canvas = document.querySelector('#processedImageContainer canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        // グラデーションパス描画
        const gradient = ctx.createLinearGradient(
            path[0].x, path[0].y,
            path[path.length - 1].x, path[path.length - 1].y
        );
        gradient.addColorStop(0, '#10B981');
        gradient.addColorStop(0.5, '#059669');
        gradient.addColorStop(1, '#047857');

        ctx.strokeStyle = gradient;
        ctx.lineWidth = 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        ctx.beginPath();
        path.forEach((point, i) => {
            if (i === 0) {
                ctx.moveTo(point.x, point.y);
            } else {
                ctx.lineTo(point.x, point.y);
            }
        });
        ctx.stroke();

        // 開始点と終了点を再描画
        if (this.startPoint) {
            this.drawPoint(ctx, this.startPoint, '#3B82F6', 'S');
        }
        if (this.endPoint) {
            this.drawPoint(ctx, this.endPoint, '#EF4444', 'E');
        }
    }

    showResult(result) {
        document.getElementById('resultInfo').classList.remove('hidden');
        document.getElementById('usedAlgorithm').textContent = result.algorithm;
        document.getElementById('processingTime').textContent = (result.processing_time * 1000).toFixed(2);
        document.getElementById('pathLength').textContent = result.path_length;
    }

    clearPath() {
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start';
        
        document.getElementById('startStatus').textContent = '未設定';
        document.getElementById('startStatus').className = 'font-mono';
        document.getElementById('endStatus').textContent = '未設定';
        document.getElementById('endStatus').className = 'font-mono';
        document.getElementById('resultInfo').classList.add('hidden');
        
        // キャンバスを再描画
        const canvas = document.querySelector('#processedImageContainer canvas');
        if (canvas && this.currentProcessedImage) {
            const ctx = canvas.getContext('2d');
            const img = new Image();
            img.onload = () => {
                this.redrawCanvas(canvas, ctx, img);
            };
            img.src = this.currentProcessedImage;
        }
    }

    showLoading(message) {
        document.getElementById('loadingText').textContent = message;
        document.getElementById('loadingOverlay').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }

    showError(message) {
        alert(message);
        console.error(message);
    }
}

// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    new PythonPathfindingApp();
});