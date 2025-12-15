// 🚀 高速CV経路検出システム - 高度な二値化処理対応版
// Canvas-based image processing with advanced binarization techniques

class AdvancedImageProcessor {
    constructor() {
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
    }

    // 二値化モード
    static BinarizationModes = {
        SIMPLE: 'simple',           // 単純閾値
        OTSU: 'otsu',              // Otsu法
        ADAPTIVE_MEAN: 'adaptive_mean',     // 適応的閾値（平均）
        ADAPTIVE_GAUSSIAN: 'adaptive_gaussian', // 適応的閾値（ガウシアン）
        MULTI_LEVEL: 'multi_level'  // マルチレベル閾値
    };

    // 画像をCanvas ImageDataから読み込み
    loadImageData(imageElement, width = 700, height = null) {
        // アスペクト比を維持してリサイズ
        const aspectRatio = imageElement.naturalWidth / imageElement.naturalHeight;
        this.canvas.width = width;
        this.canvas.height = height || Math.round(width / aspectRatio);
        
        this.ctx.drawImage(imageElement, 0, 0, this.canvas.width, this.canvas.height);
        return this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    }

    // グレースケール変換
    toGrayscale(imageData) {
        const data = imageData.data;
        const grayscale = new Uint8Array(imageData.width * imageData.height);
        
        for (let i = 0; i < data.length; i += 4) {
            // 輝度計算（ITU-R BT.709の重み）
            const gray = Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]);
            grayscale[i / 4] = gray;
        }
        
        return grayscale;
    }

    // Otsu法による自動閾値決定
    calculateOtsuThreshold(grayscale) {
        const histogram = new Array(256).fill(0);
        const total = grayscale.length;
        
        // ヒストグラム作成
        for (let i = 0; i < grayscale.length; i++) {
            histogram[grayscale[i]]++;
        }
        
        let sum = 0;
        for (let i = 0; i < 256; i++) {
            sum += i * histogram[i];
        }
        
        let sumB = 0;
        let wB = 0;
        let wF = 0;
        let varMax = 0;
        let threshold = 0;
        
        for (let i = 0; i < 256; i++) {
            wB += histogram[i];
            if (wB === 0) continue;
            
            wF = total - wB;
            if (wF === 0) break;
            
            sumB += i * histogram[i];
            const mB = sumB / wB;
            const mF = (sum - sumB) / wF;
            
            const varBetween = wB * wF * (mB - mF) * (mB - mF);
            
            if (varBetween > varMax) {
                varMax = varBetween;
                threshold = i;
            }
        }
        
        return threshold;
    }

    // 適応的閾値（ローカル閾値）
    adaptiveThreshold(grayscale, width, height, blockSize = 15, method = 'mean', C = 5) {
        const binary = new Uint8Array(grayscale.length);
        const halfBlock = Math.floor(blockSize / 2);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const idx = y * width + x;
                
                // ローカル領域の統計を計算
                let sum = 0;
                let count = 0;
                let sumSq = 0; // ガウシアン用
                
                for (let dy = -halfBlock; dy <= halfBlock; dy++) {
                    for (let dx = -halfBlock; dx <= halfBlock; dx++) {
                        const ny = y + dy;
                        const nx = x + dx;
                        
                        if (ny >= 0 && ny < height && nx >= 0 && nx < width) {
                            const neighborIdx = ny * width + nx;
                            const value = grayscale[neighborIdx];
                            sum += value;
                            sumSq += value * value;
                            count++;
                        }
                    }
                }
                
                let localThreshold;
                if (method === 'mean') {
                    localThreshold = (sum / count) - C;
                } else if (method === 'gaussian') {
                    // ガウシアン重み付き平均の近似
                    const mean = sum / count;
                    const variance = (sumSq / count) - (mean * mean);
                    localThreshold = mean - Math.sqrt(variance) / 2 - C;
                }
                
                binary[idx] = grayscale[idx] > localThreshold ? 255 : 0;
            }
        }
        
        return binary;
    }

    // マルチレベル閾値処理
    multiLevelThreshold(grayscale, levels = 3) {
        const histogram = new Array(256).fill(0);
        for (let i = 0; i < grayscale.length; i++) {
            histogram[grayscale[i]]++;
        }
        
        // 複数の閾値を自動計算（簡易版）
        const thresholds = [];
        for (let i = 1; i < levels; i++) {
            thresholds.push(Math.round(255 * i / levels));
        }
        
        const binary = new Uint8Array(grayscale.length);
        for (let i = 0; i < grayscale.length; i++) {
            const value = grayscale[i];
            binary[i] = value > thresholds[Math.floor(thresholds.length / 2)] ? 255 : 0;
        }
        
        return binary;
    }

    // ノイズ除去（モルフォロジー演算）
    morphologyOperation(binary, width, height, operation = 'opening', kernelSize = 3) {
        const kernel = this.createKernel(kernelSize);
        
        if (operation === 'opening') {
            // 収縮→膨張
            const eroded = this.erode(binary, width, height, kernel);
            return this.dilate(eroded, width, height, kernel);
        } else if (operation === 'closing') {
            // 膨張→収縮
            const dilated = this.dilate(binary, width, height, kernel);
            return this.erode(dilated, width, height, kernel);
        }
        
        return binary;
    }

    createKernel(size) {
        const kernel = [];
        const center = Math.floor(size / 2);
        
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const dx = x - center;
                const dy = y - center;
                // 円形カーネル
                if (dx * dx + dy * dy <= center * center) {
                    kernel.push({x: dx, y: dy});
                }
            }
        }
        
        return kernel;
    }

    erode(binary, width, height, kernel) {
        const result = new Uint8Array(binary.length);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const idx = y * width + x;
                let minVal = 255;
                
                for (const {x: dx, y: dy} of kernel) {
                    const nx = x + dx;
                    const ny = y + dy;
                    
                    if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
                        const neighborIdx = ny * width + nx;
                        minVal = Math.min(minVal, binary[neighborIdx]);
                    }
                }
                
                result[idx] = minVal;
            }
        }
        
        return result;
    }

    dilate(binary, width, height, kernel) {
        const result = new Uint8Array(binary.length);
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const idx = y * width + x;
                let maxVal = 0;
                
                for (const {x: dx, y: dy} of kernel) {
                    const nx = x + dx;
                    const ny = y + dy;
                    
                    if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
                        const neighborIdx = ny * width + nx;
                        maxVal = Math.max(maxVal, binary[neighborIdx]);
                    }
                }
                
                result[idx] = maxVal;
            }
        }
        
        return result;
    }

    // 総合画像処理
    processBinarization(imageElement, options = {}) {
        const {
            mode = AdvancedImageProcessor.BinarizationModes.OTSU,
            threshold = 127,
            adaptiveBlockSize = 15,
            adaptiveC = 5,
            noiseReduction = true,
            morphologyOperation = 'opening',
            kernelSize = 3
        } = options;

        // 画像データ読み込み
        const imageData = this.loadImageData(imageElement);
        const grayscale = this.toGrayscale(imageData);
        const { width, height } = this.canvas;

        let binary;

        // 二値化処理
        switch (mode) {
            case AdvancedImageProcessor.BinarizationModes.SIMPLE:
                binary = grayscale.map(v => v > threshold ? 255 : 0);
                break;
                
            case AdvancedImageProcessor.BinarizationModes.OTSU:
                const otsuThreshold = this.calculateOtsuThreshold(grayscale);
                binary = grayscale.map(v => v > otsuThreshold ? 255 : 0);
                break;
                
            case AdvancedImageProcessor.BinarizationModes.ADAPTIVE_MEAN:
                binary = this.adaptiveThreshold(grayscale, width, height, adaptiveBlockSize, 'mean', adaptiveC);
                break;
                
            case AdvancedImageProcessor.BinarizationModes.ADAPTIVE_GAUSSIAN:
                binary = this.adaptiveThreshold(grayscale, width, height, adaptiveBlockSize, 'gaussian', adaptiveC);
                break;
                
            case AdvancedImageProcessor.BinarizationModes.MULTI_LEVEL:
                binary = this.multiLevelThreshold(grayscale);
                break;
                
            default:
                binary = grayscale.map(v => v > threshold ? 255 : 0);
        }

        // ノイズ除去
        if (noiseReduction) {
            binary = this.morphologyOperation(binary, width, height, morphologyOperation, kernelSize);
        }

        // バイナリ画像をCanvasに描画
        const processedImageData = this.ctx.createImageData(width, height);
        for (let i = 0; i < binary.length; i++) {
            const value = binary[i];
            processedImageData.data[i * 4] = value;     // R
            processedImageData.data[i * 4 + 1] = value; // G
            processedImageData.data[i * 4 + 2] = value; // B
            processedImageData.data[i * 4 + 3] = 255;   // A
        }

        this.ctx.putImageData(processedImageData, 0, 0);

        // グリッドデータ生成（0=白/通行可能, 1=黒/壁）
        const grid = [];
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const idx = y * width + x;
                row.push(binary[idx] === 0 ? 1 : 0); // 黒が壁（1）、白が通路（0）
            }
            grid.push(row);
        }

        return {
            canvas: this.canvas,
            imageData: processedImageData,
            grid: grid,
            binaryData: binary,
            width: width,
            height: height
        };
    }
}

// ===========================================
// パス検索アルゴリズム（最適化版）
// ===========================================

class OptimizedPathfinder {
    
    static Algorithms = {
        BFS: 'BFS',
        ASTAR: 'A*',
        DIJKSTRA: 'Dijkstra'
    };

    // BFS（幅優先探索）- 最も高速
    static findPathBFS(grid, start, end) {
        const height = grid.length;
        const width = grid[0].length;
        
        // 範囲チェック
        if (!this.isValidPoint(start, width, height) || 
            !this.isValidPoint(end, width, height) ||
            grid[start.y][start.x] === 1 || 
            grid[end.y][end.x] === 1) {
            return null;
        }

        const visited = new Set();
        const parent = new Map();
        const queue = [{x: start.x, y: start.y}];
        
        visited.add(`${start.x},${start.y}`);
        parent.set(`${start.x},${start.y}`, null);

        // 8方向移動
        const directions = [
            [0, 1], [0, -1], [1, 0], [-1, 0],
            [1, 1], [1, -1], [-1, 1], [-1, -1]
        ];

        while (queue.length > 0) {
            const current = queue.shift();
            
            if (current.x === end.x && current.y === end.y) {
                return this.reconstructPath(parent, start, end);
            }

            for (const [dx, dy] of directions) {
                const newX = current.x + dx;
                const newY = current.y + dy;
                const newKey = `${newX},${newY}`;

                if (newX >= 0 && newX < width && 
                    newY >= 0 && newY < height &&
                    grid[newY][newX] === 0 && 
                    !visited.has(newKey)) {
                    
                    visited.add(newKey);
                    parent.set(newKey, {x: current.x, y: current.y});
                    queue.push({x: newX, y: newY});
                }
            }
        }

        return null;
    }

    // A*アルゴリズム
    static findPathAStar(grid, start, end) {
        const height = grid.length;
        const width = grid[0].length;
        
        if (!this.isValidPoint(start, width, height) || 
            !this.isValidPoint(end, width, height) ||
            grid[start.y][start.x] === 1 || 
            grid[end.y][end.x] === 1) {
            return null;
        }

        const openSet = new PriorityQueue((a, b) => a.f < b.f);
        const closedSet = new Set();
        const gScore = new Map();
        const fScore = new Map();
        const cameFrom = new Map();

        const startKey = `${start.x},${start.y}`;
        const endKey = `${end.x},${end.y}`;

        gScore.set(startKey, 0);
        fScore.set(startKey, this.heuristic(start, end));
        
        openSet.enqueue({
            x: start.x, 
            y: start.y, 
            g: 0, 
            h: this.heuristic(start, end),
            f: this.heuristic(start, end)
        });

        const directions = [
            [0, 1, 1.0], [0, -1, 1.0], [1, 0, 1.0], [-1, 0, 1.0],
            [1, 1, 1.414], [1, -1, 1.414], [-1, 1, 1.414], [-1, -1, 1.414]
        ];

        while (!openSet.isEmpty()) {
            const current = openSet.dequeue();
            const currentKey = `${current.x},${current.y}`;
            
            if (closedSet.has(currentKey)) continue;
            closedSet.add(currentKey);

            if (current.x === end.x && current.y === end.y) {
                return this.reconstructPathAStar(cameFrom, start, end);
            }

            for (const [dx, dy, cost] of directions) {
                const newX = current.x + dx;
                const newY = current.y + dy;
                const newKey = `${newX},${newY}`;

                if (newX >= 0 && newX < width && 
                    newY >= 0 && newY < height &&
                    grid[newY][newX] === 0 && 
                    !closedSet.has(newKey)) {
                    
                    const tentativeG = gScore.get(currentKey) + cost;
                    
                    if (!gScore.has(newKey) || tentativeG < gScore.get(newKey)) {
                        gScore.set(newKey, tentativeG);
                        const h = this.heuristic({x: newX, y: newY}, end);
                        fScore.set(newKey, tentativeG + h);
                        cameFrom.set(newKey, {x: current.x, y: current.y});
                        
                        openSet.enqueue({
                            x: newX, 
                            y: newY, 
                            g: tentativeG, 
                            h: h,
                            f: tentativeG + h
                        });
                    }
                }
            }
        }

        return null;
    }

    // Dijkstraアルゴリズム
    static findPathDijkstra(grid, start, end) {
        // A*のヒューリスティック関数を0にしたもの
        return this.findPathAStar(grid, start, end);
    }

    static heuristic(a, b) {
        // マンハッタン距離
        return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
    }

    static isValidPoint(point, width, height) {
        return point.x >= 0 && point.x < width && point.y >= 0 && point.y < height;
    }

    static reconstructPath(parent, start, end) {
        const path = [];
        let current = `${end.x},${end.y}`;
        
        while (current !== null) {
            const [x, y] = current.split(',').map(Number);
            path.unshift({x, y});
            current = parent.get(current);
            if (current) {
                current = `${current.x},${current.y}`;
            }
        }
        
        return path;
    }

    static reconstructPathAStar(cameFrom, start, end) {
        const path = [];
        let current = `${end.x},${end.y}`;
        
        while (cameFrom.has(current)) {
            const [x, y] = current.split(',').map(Number);
            path.unshift({x, y});
            const parent = cameFrom.get(current);
            current = `${parent.x},${parent.y}`;
        }
        
        // 開始点を追加
        path.unshift(start);
        return path;
    }

    static findPath(grid, start, end, algorithm = OptimizedPathfinder.Algorithms.BFS) {
        const startTime = performance.now();
        
        let path = null;
        switch (algorithm) {
            case OptimizedPathfinder.Algorithms.BFS:
                path = this.findPathBFS(grid, start, end);
                break;
            case OptimizedPathfinder.Algorithms.ASTAR:
                path = this.findPathAStar(grid, start, end);
                break;
            case OptimizedPathfinder.Algorithms.DIJKSTRA:
                path = this.findPathDijkstra(grid, start, end);
                break;
        }
        
        const endTime = performance.now();
        const processingTime = endTime - startTime;
        
        return {
            path: path,
            algorithm: algorithm,
            processingTime: processingTime,
            pathLength: path ? path.length : 0
        };
    }
}

// 優先度キュー実装
class PriorityQueue {
    constructor(compareFn) {
        this.items = [];
        this.compare = compareFn;
    }
    
    enqueue(item) {
        this.items.push(item);
        this.items.sort(this.compare);
    }
    
    dequeue() {
        return this.items.shift();
    }
    
    isEmpty() {
        return this.items.length === 0;
    }
}

// ===========================================
// メインアプリケーション
// ===========================================

class PathfindingApp {
    constructor() {
        this.imageProcessor = new AdvancedImageProcessor();
        this.currentGrid = null;
        this.currentImage = null;
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start'; // 'start' or 'end'
        
        this.initializeUI();
        this.bindEvents();
    }

    initializeUI() {
        const app = document.getElementById('app');
        app.innerHTML = `
            <div class="max-w-7xl mx-auto">
                <!-- 画像アップロード -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">
                        <i class="fas fa-upload mr-2 text-blue-600"></i>
                        1. 画像アップロード
                    </h2>
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                フロアマップ画像を選択
                            </label>
                            <input type="file" id="imageInput" accept="image/*" 
                                   class="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">
                        </div>
                        <div class="flex items-end">
                            <button id="processBtn" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400" disabled>
                                <i class="fas fa-magic mr-2"></i>
                                画像を処理
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 二値化設定 -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">
                        <i class="fas fa-sliders-h mr-2 text-green-600"></i>
                        2. 二値化処理設定
                    </h2>
                    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">二値化方法</label>
                            <select id="binarizationMode" class="w-full p-2 border border-gray-300 rounded-lg">
                                <option value="otsu">Otsu法（自動閾値）</option>
                                <option value="simple">単純閾値</option>
                                <option value="adaptive_mean">適応的閾値（平均）</option>
                                <option value="adaptive_gaussian">適応的閾値（ガウシアン）</option>
                                <option value="multi_level">マルチレベル閾値</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                閾値: <span id="thresholdValue">127</span>
                            </label>
                            <input type="range" id="thresholdSlider" min="0" max="255" value="127" 
                                   class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                適応ブロックサイズ: <span id="blockSizeValue">15</span>
                            </label>
                            <input type="range" id="blockSizeSlider" min="3" max="31" step="2" value="15" 
                                   class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                適応定数C: <span id="adaptiveCValue">5</span>
                            </label>
                            <input type="range" id="adaptiveCSlider" min="0" max="20" value="5" 
                                   class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        </div>
                        <div>
                            <label class="flex items-center">
                                <input type="checkbox" id="noiseReduction" checked class="mr-2">
                                <span class="text-sm font-medium text-gray-700">ノイズ除去</span>
                            </label>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                カーネルサイズ: <span id="kernelSizeValue">3</span>
                            </label>
                            <input type="range" id="kernelSizeSlider" min="3" max="15" step="2" value="3" 
                                   class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        </div>
                    </div>
                </div>

                <!-- アルゴリズム選択 -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">
                        <i class="fas fa-route mr-2 text-purple-600"></i>
                        3. 経路探索アルゴリズム選択
                    </h2>
                    <div class="grid md:grid-cols-3 gap-4">
                        <div class="algorithm-card bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg border-2 border-green-200 cursor-pointer" data-algorithm="BFS">
                            <div class="flex justify-between items-center mb-2">
                                <h3 class="font-bold text-green-800">BFS</h3>
                                <span class="text-xs bg-green-500 text-white px-2 py-1 rounded-full">最高速</span>
                            </div>
                            <p class="text-sm text-green-700">幅優先探索 - 最短経路保証</p>
                            <div class="mt-2 bg-green-200 rounded-full h-2">
                                <div class="bg-green-500 h-2 rounded-full" style="width: 95%"></div>
                            </div>
                        </div>
                        <div class="algorithm-card bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg border-2 border-blue-200 cursor-pointer" data-algorithm="A*">
                            <div class="flex justify-between items-center mb-2">
                                <h3 class="font-bold text-blue-800">A*</h3>
                                <span class="text-xs bg-blue-500 text-white px-2 py-1 rounded-full">高速</span>
                            </div>
                            <p class="text-sm text-blue-700">ヒューリスティック探索</p>
                            <div class="mt-2 bg-blue-200 rounded-full h-2">
                                <div class="bg-blue-500 h-2 rounded-full" style="width: 80%"></div>
                            </div>
                        </div>
                        <div class="algorithm-card bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg border-2 border-purple-200 cursor-pointer" data-algorithm="Dijkstra">
                            <div class="flex justify-between items-center mb-2">
                                <h3 class="font-bold text-purple-800">Dijkstra</h3>
                                <span class="text-xs bg-purple-500 text-white px-2 py-1 rounded-full">標準</span>
                            </div>
                            <p class="text-sm text-purple-700">重み付き最短経路</p>
                            <div class="mt-2 bg-purple-200 rounded-full h-2">
                                <div class="bg-purple-500 h-2 rounded-full" style="width: 60%"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 点設定と実行 -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">
                        <i class="fas fa-map-marked-alt mr-2 text-red-600"></i>
                        4. 経路設定と実行
                    </h2>
                    <div class="grid md:grid-cols-2 gap-6">
                        <div>
                            <div class="mb-4">
                                <p class="text-sm text-gray-600 mb-2">画像をクリックして開始点と終了点を設定してください</p>
                                <div class="flex gap-4">
                                    <div class="flex items-center">
                                        <div class="w-4 h-4 bg-blue-500 rounded-full mr-2"></div>
                                        <span class="text-sm">開始点: <span id="startStatus" class="font-mono">未設定</span></span>
                                    </div>
                                    <div class="flex items-center">
                                        <div class="w-4 h-4 bg-red-500 rounded-full mr-2"></div>
                                        <span class="text-sm">終了点: <span id="endStatus" class="font-mono">未設定</span></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="flex items-end gap-2">
                            <button id="findPathBtn" class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400" disabled>
                                <i class="fas fa-search mr-2"></i>
                                経路検索実行
                            </button>
                            <button id="clearPathBtn" class="bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition-colors">
                                <i class="fas fa-eraser mr-2"></i>
                                クリア
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 結果表示エリア -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">
                        <i class="fas fa-image mr-2 text-indigo-600"></i>
                        処理結果
                    </h2>
                    <div class="grid lg:grid-cols-2 gap-6">
                        <!-- 元画像 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">元画像</h3>
                            <div id="originalImageContainer" class="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center text-gray-500 min-h-[300px] flex items-center justify-center">
                                画像を選択してください
                            </div>
                        </div>
                        <!-- 処理後画像 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">処理後画像（経路表示）</h3>
                            <div id="processedImageContainer" class="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center text-gray-500 min-h-[300px] flex items-center justify-center">
                                処理を実行してください
                            </div>
                        </div>
                    </div>
                    
                    <!-- 結果情報 -->
                    <div id="resultInfo" class="mt-6 p-4 bg-gray-50 rounded-lg hidden">
                        <h3 class="text-lg font-semibold text-gray-700 mb-2">処理結果</h3>
                        <div class="grid md:grid-cols-3 gap-4 text-sm">
                            <div>
                                <strong>アルゴリズム:</strong> <span id="usedAlgorithm">-</span>
                            </div>
                            <div>
                                <strong>処理時間:</strong> <span id="processingTime">-</span>ms
                            </div>
                            <div>
                                <strong>経路長:</strong> <span id="pathLength">-</span>ステップ
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
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

        // スライダー値更新
        const sliders = ['threshold', 'blockSize', 'adaptiveC', 'kernelSize'];
        sliders.forEach(slider => {
            const sliderElement = document.getElementById(`${slider}Slider`);
            const valueElement = document.getElementById(`${slider}Value`);
            
            sliderElement.addEventListener('input', (e) => {
                valueElement.textContent = e.target.value;
                if (this.currentImage) {
                    this.processImage(); // リアルタイム更新
                }
            });
        });

        // 二値化方法変更
        document.getElementById('binarizationMode').addEventListener('change', () => {
            if (this.currentImage) {
                this.processImage();
            }
        });

        // ノイズ除去チェックボックス
        document.getElementById('noiseReduction').addEventListener('change', () => {
            if (this.currentImage) {
                this.processImage();
            }
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

        // デフォルトでBFSを選択
        this.selectAlgorithm(document.querySelector('[data-algorithm="BFS"]'));
    }

    handleImageSelect(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                this.currentImage = img;
                this.displayOriginalImage(img);
                document.getElementById('processBtn').disabled = false;
                this.processImage(); // 自動処理
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    }

    displayOriginalImage(img) {
        const container = document.getElementById('originalImageContainer');
        container.innerHTML = '';
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // アスペクト比を維持してリサイズ
        const maxWidth = 400;
        const aspectRatio = img.naturalWidth / img.naturalHeight;
        canvas.width = maxWidth;
        canvas.height = maxWidth / aspectRatio;
        
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.className = 'max-w-full h-auto mx-auto border rounded-lg';
        container.appendChild(canvas);
    }

    processImage() {
        if (!this.currentImage) return;

        const options = {
            mode: document.getElementById('binarizationMode').value,
            threshold: parseInt(document.getElementById('thresholdSlider').value),
            adaptiveBlockSize: parseInt(document.getElementById('blockSizeSlider').value),
            adaptiveC: parseInt(document.getElementById('adaptiveCSlider').value),
            noiseReduction: document.getElementById('noiseReduction').checked,
            morphologyOperation: 'opening',
            kernelSize: parseInt(document.getElementById('kernelSizeSlider').value)
        };

        const result = this.imageProcessor.processBinarization(this.currentImage, options);
        this.currentGrid = result.grid;
        
        this.displayProcessedImage(result.canvas);
        this.enablePathfinding();
    }

    displayProcessedImage(canvas) {
        const container = document.getElementById('processedImageContainer');
        container.innerHTML = '';
        
        // キャンバスのコピーを作成（経路描画用）
        this.displayCanvas = document.createElement('canvas');
        this.displayCanvas.width = canvas.width;
        this.displayCanvas.height = canvas.height;
        this.displayCtx = this.displayCanvas.getContext('2d');
        
        // 処理結果をコピー
        this.displayCtx.drawImage(canvas, 0, 0);
        
        this.displayCanvas.className = 'max-w-full h-auto mx-auto border rounded-lg cursor-crosshair';
        this.displayCanvas.style.maxWidth = '400px';
        
        // クリックイベント
        this.displayCanvas.addEventListener('click', (e) => {
            this.handleCanvasClick(e);
        });
        
        container.appendChild(this.displayCanvas);
    }

    enablePathfinding() {
        document.getElementById('findPathBtn').disabled = false;
    }

    handleCanvasClick(e) {
        if (!this.currentGrid) return;

        const rect = this.displayCanvas.getBoundingClientRect();
        const scaleX = this.displayCanvas.width / rect.width;
        const scaleY = this.displayCanvas.height / rect.height;
        
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
            this.clickMode = 'end';
        } else {
            this.endPoint = {x, y};
            document.getElementById('endStatus').textContent = `(${x}, ${y})`;
            this.clickMode = 'start';
        }

        this.redrawCanvas();
    }

    redrawCanvas() {
        if (!this.displayCanvas || !this.currentGrid) return;

        // 元の二値化画像を再描画
        const result = this.imageProcessor.processBinarization(this.currentImage, this.getProcessingOptions());
        this.displayCtx.drawImage(result.canvas, 0, 0);

        // 開始点と終了点を描画
        if (this.startPoint) {
            this.drawPoint(this.startPoint, '#3B82F6', 'S');
        }
        if (this.endPoint) {
            this.drawPoint(this.endPoint, '#EF4444', 'E');
        }
    }

    drawPoint(point, color, label) {
        this.displayCtx.fillStyle = color;
        this.displayCtx.beginPath();
        this.displayCtx.arc(point.x, point.y, 8, 0, 2 * Math.PI);
        this.displayCtx.fill();
        
        this.displayCtx.strokeStyle = 'white';
        this.displayCtx.lineWidth = 2;
        this.displayCtx.stroke();
        
        this.displayCtx.fillStyle = 'white';
        this.displayCtx.font = 'bold 12px sans-serif';
        this.displayCtx.textAlign = 'center';
        this.displayCtx.textBaseline = 'middle';
        this.displayCtx.fillText(label, point.x, point.y);
    }

    getProcessingOptions() {
        return {
            mode: document.getElementById('binarizationMode').value,
            threshold: parseInt(document.getElementById('thresholdSlider').value),
            adaptiveBlockSize: parseInt(document.getElementById('blockSizeSlider').value),
            adaptiveC: parseInt(document.getElementById('adaptiveCSlider').value),
            noiseReduction: document.getElementById('noiseReduction').checked,
            morphologyOperation: 'opening',
            kernelSize: parseInt(document.getElementById('kernelSizeSlider').value)
        };
    }

    selectAlgorithm(card) {
        // 全てのカードから選択状態を削除
        document.querySelectorAll('.algorithm-card').forEach(c => {
            c.classList.remove('ring-4', 'ring-offset-2');
        });
        
        // 選択されたカードにスタイルを適用
        card.classList.add('ring-4', 'ring-offset-2');
        
        if (card.dataset.algorithm === 'BFS') {
            card.classList.add('ring-green-400');
        } else if (card.dataset.algorithm === 'A*') {
            card.classList.add('ring-blue-400');
        } else {
            card.classList.add('ring-purple-400');
        }
        
        this.selectedAlgorithm = card.dataset.algorithm;
    }

    findPath() {
        if (!this.currentGrid || !this.startPoint || !this.endPoint || !this.selectedAlgorithm) {
            alert('グリッド、開始点、終了点、アルゴリズムがすべて設定されている必要があります');
            return;
        }

        const result = OptimizedPathfinder.findPath(
            this.currentGrid,
            this.startPoint,
            this.endPoint,
            this.selectedAlgorithm
        );

        if (result.path) {
            this.drawPath(result.path);
            this.showResult(result);
        } else {
            alert('経路が見つかりませんでした');
        }
    }

    drawPath(path) {
        if (!path || path.length === 0) return;

        // グラデーションパス描画
        const gradient = this.displayCtx.createLinearGradient(
            path[0].x, path[0].y,
            path[path.length - 1].x, path[path.length - 1].y
        );
        gradient.addColorStop(0, '#10B981');
        gradient.addColorStop(0.5, '#059669');
        gradient.addColorStop(1, '#047857');

        this.displayCtx.strokeStyle = gradient;
        this.displayCtx.lineWidth = 4;
        this.displayCtx.lineCap = 'round';
        this.displayCtx.lineJoin = 'round';

        this.displayCtx.beginPath();
        path.forEach((point, i) => {
            if (i === 0) {
                this.displayCtx.moveTo(point.x, point.y);
            } else {
                this.displayCtx.lineTo(point.x, point.y);
            }
        });
        this.displayCtx.stroke();

        // 開始点と終了点を再描画
        if (this.startPoint) {
            this.drawPoint(this.startPoint, '#3B82F6', 'S');
        }
        if (this.endPoint) {
            this.drawPoint(this.endPoint, '#EF4444', 'E');
        }
    }

    showResult(result) {
        document.getElementById('resultInfo').classList.remove('hidden');
        document.getElementById('usedAlgorithm').textContent = result.algorithm;
        document.getElementById('processingTime').textContent = result.processingTime.toFixed(2);
        document.getElementById('pathLength').textContent = result.pathLength;
    }

    clearPath() {
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start';
        
        document.getElementById('startStatus').textContent = '未設定';
        document.getElementById('endStatus').textContent = '未設定';
        document.getElementById('resultInfo').classList.add('hidden');
        
        if (this.currentImage) {
            this.redrawCanvas();
        }
    }
}

// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    new PathfindingApp();
});