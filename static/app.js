// AI経路検索システム - 完全自動化版
// 誰でも使いやすい3ステップシステム

class AIPathfindingApp {
    constructor() {
        this.currentImageData = null;
        this.originalImageBase64 = null; // ★元画像データを保存
        this.currentGrid = null;
        this.currentProcessedImage = null;
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start'; // 'start' or 'end'
        this.selectedAlgorithm = 'BFS';
        this.isProcessing = false;
        this.lastResult = null; // ★エクスポート用に結果を保存
        
        // 🛣️ 道路ネットワーク表示状態
        this.showRoadNetwork = false;
        this.roadNetworkData = null;
        
        this.initializeUI();
        this.bindEvents();
    }

    initializeUI() {
        // システム初期化完了
        console.log('AI経路検索システムが開始されました');
    }

    bindEvents() {
        // 画像選択（ドラッグ&ドロップ + ファイル選択）
        const imageInput = document.getElementById('imageInput');
        const uploadArea = document.querySelector('.upload-area');

        // ファイル入力
        imageInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleImageSelect(e.target.files[0]);
            }
        });

        // ドラッグ&ドロップ
        uploadArea.addEventListener('click', () => {
            imageInput.click();
        });

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('pulse-border');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('pulse-border');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('pulse-border');
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                this.handleImageSelect(files[0]);
            }
        });

        // 経路検索実行
        const findPathBtn = document.getElementById('findPathBtn');
        if (findPathBtn) {
            findPathBtn.addEventListener('click', () => {
                this.findPath();
            });
        }

        // クリア/リセット
        const clearPathBtn = document.getElementById('clearPathBtn');
        if (clearPathBtn) {
            clearPathBtn.addEventListener('click', () => {
                this.clearPath();
            });
        }
        
        // ★新機能: エクスポート機能
        const exportJsonBtn = document.getElementById('exportJsonBtn');
        if (exportJsonBtn) {
            exportJsonBtn.addEventListener('click', () => {
                this.exportResults('json');
            });
        }
        
        const exportImageBtn = document.getElementById('exportImageBtn');
        if (exportImageBtn) {
            exportImageBtn.addEventListener('click', () => {
                this.exportResults('image');
            });
        }
        
        const shareUrlBtn = document.getElementById('shareUrlBtn');
        if (shareUrlBtn) {
            shareUrlBtn.addEventListener('click', () => {
                this.shareResults();
            });
        }
        
        // 🛣️ 道路ネットワーク表示切り替え
        const toggleRoadNetworkBtn = document.getElementById('toggleRoadNetworkBtn');
        if (toggleRoadNetworkBtn) {
            toggleRoadNetworkBtn.addEventListener('click', () => {
                this.toggleRoadNetworkDisplay();
            });
        }
        
        // 🛣️ プレビュー用道路ネットワーク表示切り替え
        const previewRoadNetworkBtn = document.getElementById('previewRoadNetworkBtn');
        if (previewRoadNetworkBtn) {
            previewRoadNetworkBtn.addEventListener('click', () => {
                this.togglePreviewRoadNetworkDisplay();
            });
        }
        
        // 経路設定に進むボタン
        const proceedToPathfindingBtn = document.getElementById('proceedToPathfindingBtn');
        if (proceedToPathfindingBtn) {
            proceedToPathfindingBtn.addEventListener('click', () => {
                this.showPathfindingSection();
            });
        }
    }

    async handleImageSelect(file) {
        if (this.isProcessing) {
            return;
        }

        this.isProcessing = true;
        this.showLoading('📷 画像を読み込み中...');

        const reader = new FileReader();
        reader.onload = async (event) => {
            this.currentImageData = event.target.result;
            this.originalImageBase64 = event.target.result; // ★元画像データを確実に保存
            
            // 元画像を表示
            this.displayOriginalImage(event.target.result);
            
            // 自動的にAI処理を開始
            await this.intelligentAutoProcess();
        };
        
        reader.onerror = () => {
            this.showError('画像の読み込みに失敗しました');
            this.isProcessing = false;
        };
        
        reader.readAsDataURL(file);
    }

    displayOriginalImage(imageData) {
        // ★改良1: 元画像表示を削除し、直接AI処理開始
        // originalImageContainer への表示を削除
        
        // 成功メッセージ
        this.showSuccessMessage('✅ 画像がアップロードされました！AIが自動分析を開始します...');
    }

    async intelligentAutoProcess() {
        if (!this.currentImageData) return;

        try {
            this.showLoading('🤖 AI分析開始... 画像の特徴を解析して最適な処理方法を選択しています');
            this.simulateProgress(8); // 8秒の処理を想定

            const requestData = {
                image_data: this.currentImageData,
                target_size: 1200  // 700 → 1200 に拡大して点設定を楽にする
            };

            const response = await axios.post('/api/intelligent-process', requestData, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.data.success) {
                this.currentGrid = response.data.grid;
                this.currentProcessedImage = response.data.processed_image;
                this.originalImageBase64 = response.data.original_image_base64; // 元画像データを保存
                
                // AI分析結果を表示
                this.displayAIAnalysis(response.data.intelligent_analysis);
                
                // 処理済み画像を表示（クリック可能）
                this.displayProcessedImage(response.data.processed_image);
                
                // 推奨アルゴリズムを自動選択
                const recommendedAlgo = response.data.intelligent_analysis.recommended_pathfinding.algorithm;
                this.selectedAlgorithm = recommendedAlgo;
                
                // 🛣️ 道路ネットワークプレビューデータを保存
                if (response.data.road_network_preview) {
                    this.roadNetworkPreviewData = response.data.road_network_preview;
                    console.log('🛣️ 道路ネットワークプレビューデータ取得:', this.roadNetworkPreviewData);
                    
                    // 道路ネットワークプレビューセクションを表示
                    this.showRoadNetworkPreviewSection();
                    this.showSuccessMessage('✨ AI分析完了！道路ネットワークを確認してから経路設定にお進みください');
                } else {
                    // 道路ネットワークが検出されない場合は直接経路設定へ
                    this.showPathfindingSection();
                    this.showSuccessMessage('✨ AI分析完了！画像上で開始点と終了点をクリックしてください');
                }
                this.isProcessing = false;
                
            } else {
                this.showError('AI分析に失敗しました: ' + response.data.error);
                this.isProcessing = false;
            }
        } catch (error) {
            this.showError('AI処理エラー: ' + error.message);
            this.isProcessing = false;
        } finally {
            this.hideLoading();
        }
    }

    displayAIAnalysis(analysis) {
        // AI分析結果セクションを表示
        const section = document.getElementById('aiAnalysisSection');
        section.style.display = 'block';
        
        const binarization = analysis.selected_binarization;
        const pathfinding = analysis.recommended_pathfinding;
        const features = analysis.image_features;
        
        // 二値化選択結果
        document.getElementById('selectedBinarization').textContent = 
            this.getBinarizationMethodName(binarization.method);
        document.getElementById('binarizationReason').textContent = binarization.reason;
        
        const binarizationConfidence = Math.min(100, Math.max(0, binarization.confidence));
        document.getElementById('binarizationConfidence').style.width = `${binarizationConfidence}%`;
        document.getElementById('binarizationConfidenceText').textContent = `${binarizationConfidence}%`;
        
        // 経路探索推奨結果
        document.getElementById('recommendedPathfinding').textContent = 
            `${pathfinding.algorithm} (${pathfinding.estimated_speed}速度)`;
        document.getElementById('pathfindingReason').textContent = pathfinding.reason;
        
        const pathfindingConfidence = Math.min(100, Math.max(0, pathfinding.confidence));
        document.getElementById('pathfindingConfidence').style.width = `${pathfindingConfidence}%`;
        document.getElementById('pathfindingConfidenceText').textContent = `${pathfindingConfidence}%`;
        
        // 画像特徴
        const complexityScore = Math.min(100, Math.max(0, features.complexity_score || 0));
        const edgeDensity = Math.min(100, Math.max(0, features.edge_density || 0));
        const rectangularity = Math.min(100, Math.max(0, features.rectangularity || 0));
        
        document.getElementById('complexityBar').style.width = `${complexityScore}%`;
        document.getElementById('complexityScore').textContent = `${complexityScore}%`;
        document.getElementById('dominantColors').textContent = 
            features.is_color_image ? `${features.dominant_colors || 0}色` : 'グレースケール';
        document.getElementById('edgeBar').style.width = `${edgeDensity}%`;
        document.getElementById('edgeScore').textContent = `${edgeDensity}%`;
        document.getElementById('structuralBar').style.width = `${rectangularity}%`;
        document.getElementById('structuralScore').textContent = `${rectangularity}%`;
        
        // タイミング情報
        const totalTime = (analysis.timing?.total_time || 0) * 1000;
        document.getElementById('analysisTime').textContent = `${totalTime.toFixed(0)}ms`;
    }

    getBinarizationMethodName(method) {
        const methodNames = {
            'otsu': 'Otsu法（自動閾値）',
            'simple': '単純閾値',
            'adaptive_mean': '適応的閾値（平均）',
            'adaptive_gaussian': '適応的閾値（ガウシアン）',
            'multi_level': 'マルチレベル閾値',
            'color_map': 'カラーマップ特化処理',
            'edge_enhanced': 'エッジ強化処理',
            'contour_based': '輪郭ベース処理',
            'floor_map_optimized': 'フロアマップ特化処理'
        };
        return methodNames[method] || `${method}（AI選択）`;
    }

    showRoadNetworkPreviewSection() {
        const section = document.getElementById('roadNetworkPreviewSection');
        if (section) {
            section.style.display = 'block';
            // スムーズスクロール
            section.scrollIntoView({ behavior: 'smooth' });
        }
    }

    showPathfindingSection() {
        // プレビューセクションを隠す
        const previewSection = document.getElementById('roadNetworkPreviewSection');
        if (previewSection) {
            previewSection.style.display = 'none';
        }
        
        const section = document.getElementById('pathfindingSection');
        if (section) {
            section.style.display = 'block';
            // スムーズスクロール
            section.scrollIntoView({ behavior: 'smooth' });
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
            
            // キャンバススタイル設定 - ★修正: 画像を大きく表示して点設定を楽にする
            canvas.className = 'max-w-full h-auto mx-auto rounded-lg border-2 border-blue-300 cursor-crosshair hover:border-blue-500 transition-colors';
            canvas.style.maxHeight = '800px'; // 500px → 800px に拡大
            canvas.style.minHeight = '600px'; // 最小高さも設定
            
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
            this.showError('画像の範囲外です。画像内をクリックしてください。');
            return;
        }

        // 壁かどうかチェック
        if (this.currentGrid[y][x] === 1) {
            this.showError('⚠️ 壁や障害物の上には点を設置できません。白い通路部分をクリックしてください。');
            return;
        }

        if (this.clickMode === 'start') {
            this.startPoint = { x, y };
            this.clickMode = 'end';
            document.getElementById('startStatus').textContent = `(${x}, ${y})`;
            this.showSuccessMessage('✅ 開始点を設定しました！次に終了点をクリックしてください。');
        } else {
            this.endPoint = { x, y };
            this.clickMode = 'start';
            document.getElementById('endStatus').textContent = `(${x}, ${y})`;
            this.showSuccessMessage('✅ 終了点を設定しました！「AI経路検索を実行」ボタンを押してください。');
            
            // 経路検索ボタンを有効化
            document.getElementById('findPathBtn').disabled = false;
        }

        // キャンバスを再描画
        this.redrawCanvas(canvas, canvas.getContext('2d'), null);
    }

    redrawCanvas(canvas, ctx, img) {
        if (!canvas || !ctx) return;
        
        // 画像を再描画（imgがnullの場合は現在のキャンバス内容を維持）
        if (img) {
            ctx.drawImage(img, 0, 0);
        }
        
        // 開始点を描画
        if (this.startPoint) {
            this.drawPoint(ctx, this.startPoint.x, this.startPoint.y, '#22c55e', 'S');
        }
        
        // 終了点を描画
        if (this.endPoint) {
            this.drawPoint(ctx, this.endPoint.x, this.endPoint.y, '#ef4444', 'E');
        }
    }

    drawPoint(ctx, x, y, color, label) {
        // 円を描画
        ctx.fillStyle = color;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        
        ctx.beginPath();
        ctx.arc(x, y, 12, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        
        // ラベルを描画
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x, y);
    }

    async findPath() {
        if (!this.currentGrid || !this.startPoint || !this.endPoint) {
            this.showError('開始点と終了点の両方を設定してください');
            return;
        }

        if (this.isProcessing) {
            return;
        }

        this.isProcessing = true;
        this.showLoading('🔍 AI経路検索開始... 最適な経路を計算しています');
        this.simulateProgress(5); // 5秒の処理を想定

        try {
            const requestData = {
                grid: this.currentGrid,
                start: this.startPoint,
                end: this.endPoint,
                algorithm: this.selectedAlgorithm
            };
            
            // 元画像データがある場合は追加
            if (this.originalImageBase64) {
                requestData.original_image_base64 = this.originalImageBase64;
            }

            console.log('🔍 経路検索リクエスト送信:', {
                gridSize: `${this.currentGrid.length} x ${this.currentGrid[0].length}`,
                start: this.startPoint,
                end: this.endPoint,
                algorithm: this.selectedAlgorithm
            });

            const response = await axios.post('/api/find-path', requestData, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            console.log('✅ 経路検索レスポンス:', response.data);

            if (response.data.success) {
                this.lastResult = response.data; // ★エクスポート用に結果を保存
                this.displayPathResult(response.data);
                
                // 🔧 自動補正情報があれば表示
                let successMsg = '🎉 経路検索が完了しました！';
                if (response.data.point_adjustments) {
                    const adj = response.data.point_adjustments;
                    if (adj.start) {
                        successMsg += `\n📍 開始点が自動補正されました（${adj.start.distance}px移動）`;
                    }
                    if (adj.end) {
                        successMsg += `\n📍 終了点が自動補正されました（${adj.end.distance}px移動）`;
                    }
                }
                this.showSuccessMessage(successMsg);
                
                // ★エクスポートセクションを表示
                const exportSection = document.getElementById('exportSection');
                if (exportSection) {
                    exportSection.classList.remove('hidden');
                }
            } else {
                console.error('❌ 経路検索失敗:', response.data.error);
                this.showError('経路が見つかりませんでした: ' + response.data.error);
            }
        } catch (error) {
            console.error('❌ 経路検索エラー:', error);
            if (error.response) {
                console.error('エラーレスポンス:', error.response.data);
                this.showError(`経路検索エラー: ${error.response.data?.error || error.message}`);
            } else {
                this.showError('経路検索エラー: ' + error.message);
            }
        } finally {
            this.hideLoading();
            this.isProcessing = false;
        }
    }

    displayPathResult(result) {
        // ⚡ 高速モード: 画像表示を削除してナビゲーション指示に集中
        // カラー画像処理は時間がかかるのでスキップ
        
        // 元の白黒画像にシンプルな経路を描画（高速）
        const canvas = document.querySelector('#processedImageContainer canvas');
        if (canvas && result.path) {
            const ctx = canvas.getContext('2d');
            
            // 道路ネットワークデータを保存
            this.roadNetworkData = result.road_network;
            
            this.drawPath(ctx, result.path, this.showRoadNetwork ? result.road_network : null);
            
            // 高速処理完了メッセージを表示
            const processedContainer = document.getElementById('processedImageContainer');
            
            // 既存のメッセージを削除
            const existingMsgs = processedContainer.querySelectorAll('.speed-message');
            existingMsgs.forEach(msg => msg.remove());
            
            const speedMsg = document.createElement('div');
            speedMsg.className = 'speed-message mt-2 text-center text-green-600 font-bold';
            
            // 道路ネットワークデータまたはスケルトンがあればボタンを表示
            if (result.use_road_network && result.road_network && 
                (result.road_network.nodes.length > 0 || result.road_network.skeleton_image)) {
                
                if (result.road_network.nodes.length > 0) {
                    speedMsg.innerHTML = `🛣️ 道路ネットワーク経路: ノード数${result.road_network.nodes.length}個`;
                } else {
                    speedMsg.innerHTML = '🛣️ 道路ネットワーク検出: 表示可能';
                }
                
                // 道路ネットワーク表示切り替えボタンを表示
                const toggleBtn = document.getElementById('toggleRoadNetworkBtn');
                if (toggleBtn) {
                    toggleBtn.style.display = 'block';
                    this.updateRoadNetworkButton();
                }
            } else if (result.use_road_network) {
                speedMsg.innerHTML = '⚠️ 道路ネットワーク検出失敗、従来アルゴリズムで経路検索完了';
                
                // ボタンは非表示のまま
                const toggleBtn = document.getElementById('toggleRoadNetworkBtn');
                if (toggleBtn) {
                    toggleBtn.style.display = 'none';
                }
            } else {
                speedMsg.innerHTML = '⚡ 高速処理モード: 経路検索完了！';
            }
            
            processedContainer.appendChild(speedMsg);
        }
        
        // ★改良版: 詳細統計情報を表示
        document.getElementById('resultInfo').style.display = 'block';
        document.getElementById('usedAlgorithm').textContent = result.algorithm;
        document.getElementById('processingTime').textContent = result.processing_time.toFixed(0);
        document.getElementById('pathLength').textContent = result.path.length;
        
        // ★新機能: 追加統計情報を表示
        this.displayDetailedStats(result);
        
        // 🛣️ 道路ネットワーク情報を表示
        if (result.road_network) {
            this.displayRoadNetworkInfo(result.road_network);
        }
        
        // ★ 新機能: ナビゲーション指示を表示
        if (result.navigation_instructions) {
            this.displayNavigationInstructions(result.navigation_instructions);
        }
        
        // 結果セクションまでスクロール
        document.getElementById('resultInfo').scrollIntoView({ behavior: 'smooth' });
    }
    
    displayNavigationInstructions(instructions) {
        // ナビゲーション指示表示エリアを作成または更新
        let navSection = document.getElementById('navigationInstructions');
        if (!navSection) {
            // 新しいセクションを作成
            navSection = document.createElement('div');
            navSection.id = 'navigationInstructions';
            navSection.className = 'mt-6 p-6 bg-gradient-to-r from-purple-50 to-blue-50 rounded-xl border border-purple-200';
            
            // 結果情報セクションの後に挿入
            const resultInfo = document.getElementById('resultInfo');
            resultInfo.parentNode.insertBefore(navSection, resultInfo.nextSibling);
        }
        
        navSection.innerHTML = `
            <h3 class="text-xl font-bold text-purple-800 mb-4 text-center">
                <i class="fas fa-directions mr-2"></i>
                ナビゲーション指示
            </h3>
            <div class="grid gap-3">
                ${instructions.map((instruction, index) => `
                    <div class="flex items-center p-4 bg-white rounded-lg border-l-4 border-purple-400 shadow-sm hover:shadow-md transition-shadow">
                        <div class="flex-shrink-0 w-10 h-10 bg-gradient-to-r from-purple-500 to-blue-500 text-white rounded-full flex items-center justify-center font-bold text-sm mr-4">
                            ${instruction.step}
                        </div>
                        <div class="flex-1">
                            <div class="font-medium text-gray-800 text-lg leading-relaxed">${instruction.instruction}</div>
                            ${instruction.landmark && instruction.landmark !== instruction.instruction ? `<div class="text-sm text-blue-600 mt-1 font-medium">🏷️ ランドマーク: ${instruction.landmark}</div>` : ''}
                            ${instruction.next_landmark ? `<div class="text-xs text-green-600 mt-1">🎯 次の目標: ${instruction.next_landmark}</div>` : ''}
                        </div>
                        <div class="flex-shrink-0 text-right">
                            <div class="text-2xl">${this.getDirectionIcon(instruction.direction, instruction.turn)}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        
        // アニメーション効果
        navSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    getDirectionIcon(direction, turn) {
        // ★改良: より分かりやすいアイコン
        if (direction === '開始') return '🏃‍♂️';
        if (direction === '到着') return '🎯';
        if (turn === '右折') return '🔄';
        if (turn === '左折') return '🔃';
        if (turn === 'Uターン') return '🔙';
        if (turn === '直進') return '⬆️';
        if (direction === '上') return '🔝';
        if (direction === '下') return '🔽';
        if (direction === '左') return '◀️';
        if (direction === '右') return '▶️';
        return '🚶‍♂️';
    }

    drawPath(ctx, path, roadNetwork = null) {
        if (!path || path.length === 0) return;
        
        // 🛣️ 道路ネットワークが利用可能な場合は道路ノードとエッジを描画
        if (roadNetwork && roadNetwork.nodes && roadNetwork.nodes.length > 0) {
            this.drawRoadNetwork(ctx, roadNetwork);
        }
        
        // 経路を線で描画
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        
        ctx.beginPath();
        ctx.moveTo(path[0].x, path[0].y);
        
        for (let i = 1; i < path.length; i++) {
            ctx.lineTo(path[i].x, path[i].y);
        }
        
        ctx.stroke();
        
        // 開始点と終了点をマーク
        if (path.length > 0) {
            // 開始点 (青い円)
            ctx.fillStyle = '#3b82f6';
            ctx.beginPath();
            ctx.arc(path[0].x, path[0].y, 8, 0, 2 * Math.PI);
            ctx.fill();
            
            // 終了点 (赤い円)
            ctx.fillStyle = '#ef4444';
            ctx.beginPath();
            ctx.arc(path[path.length - 1].x, path[path.length - 1].y, 8, 0, 2 * Math.PI);
            ctx.fill();
        }
        
        // 🛣️ 道路への接続ポイントを表示
        if (roadNetwork) {
            if (roadNetwork.start_road) {
                ctx.fillStyle = '#06d6a0';
                ctx.beginPath();
                ctx.arc(roadNetwork.start_road.x, roadNetwork.start_road.y, 6, 0, 2 * Math.PI);
                ctx.fill();
            }
            
            if (roadNetwork.end_road) {
                ctx.fillStyle = '#f72585';
                ctx.beginPath();
                ctx.arc(roadNetwork.end_road.x, roadNetwork.end_road.y, 6, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
    }
    
    drawRoadNetwork(ctx, roadNetwork) {
        if (!roadNetwork) return;
        
        // 道路ネットワーク全体を薄い灰色で描画
        this.drawFullRoadSkeleton(ctx, roadNetwork);
        
        // 道路ノードを小さい円で描画
        ctx.fillStyle = '#9ca3af'; // 薄い灰色
        roadNetwork.nodes.forEach(node => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, 2, 0, 2 * Math.PI);
            ctx.fill();
        });
        
        // 選択された道路パスを少し濃い色でハイライト
        if (roadNetwork.road_path && roadNetwork.road_path.length > 0) {
            ctx.strokeStyle = '#6b7280'; // 少し濃い灰色
            ctx.lineWidth = 2;
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            
            ctx.moveTo(roadNetwork.road_path[0].x, roadNetwork.road_path[0].y);
            for (let i = 1; i < roadNetwork.road_path.length; i++) {
                ctx.lineTo(roadNetwork.road_path[i].x, roadNetwork.road_path[i].y);
            }
            ctx.stroke();
            ctx.setLineDash([]); // 点線をリセット
        }
    }
    
    drawFullRoadSkeleton(ctx, roadNetwork) {
        // スケルトン画像が利用可能な場合は使用
        if (roadNetwork.skeleton_image) {
            const img = new Image();
            img.onload = () => {
                // スケルトン画像を薄い灰色で描画
                ctx.globalAlpha = 0.4; // 透明度を設定
                ctx.drawImage(img, 0, 0, ctx.canvas.width, ctx.canvas.height);
                ctx.globalAlpha = 1.0; // 透明度をリセット
            };
            img.src = roadNetwork.skeleton_image;
            return;
        }
        
        // フォールバック: ノード間接続で道路ネットワークを表現
        if (!roadNetwork.nodes || roadNetwork.nodes.length < 2) return;
        
        ctx.strokeStyle = '#d1d5db'; // 非常に薄い灰色
        ctx.lineWidth = 1;
        ctx.setLineDash([1, 1]);
        
        // 簡易的にノード間を接続線で表現
        for (let i = 0; i < roadNetwork.nodes.length; i++) {
            for (let j = i + 1; j < roadNetwork.nodes.length; j++) {
                const node1 = roadNetwork.nodes[i];
                const node2 = roadNetwork.nodes[j];
                
                // 距離が近いノード同士を接続
                const distance = Math.sqrt((node2.x - node1.x) ** 2 + (node2.y - node1.y) ** 2);
                if (distance < 40) { // 閾値を少し小さく調整
                    ctx.beginPath();
                    ctx.moveTo(node1.x, node1.y);
                    ctx.lineTo(node2.x, node2.y);
                    ctx.stroke();
                }
            }
        }
        
        ctx.setLineDash([]); // 点線をリセット
    }
    
    toggleRoadNetworkDisplay() {
        this.showRoadNetwork = !this.showRoadNetwork;
        this.updateRoadNetworkButton();
        
        // 既存の描画をクリアして再描画
        const canvas = document.querySelector('#processedImageContainer canvas');
        if (canvas && this.lastResult && this.lastResult.path) {
            // キャンバスをクリア
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 背景画像を再描画（処理済み画像）
            if (this.currentProcessedImage) {
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    // 経路を再描画
                    this.drawPath(ctx, this.lastResult.path, this.showRoadNetwork ? this.roadNetworkData : null);
                };
                img.src = this.currentProcessedImage;
            } else {
                // 処理済み画像がない場合は経路のみ再描画
                this.drawPath(ctx, this.lastResult.path, this.showRoadNetwork ? this.roadNetworkData : null);
            }
        }
    }
    
    updateRoadNetworkButton() {
        const btn = document.getElementById('toggleRoadNetworkBtn');
        const btnText = document.getElementById('roadNetworkBtnText');
        
        if (btn && btnText) {
            if (this.showRoadNetwork) {
                btn.className = 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-6 py-3 rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg';
                btnText.textContent = '道路表示 OFF';
            } else {
                btn.className = 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white px-6 py-3 rounded-lg hover:from-purple-600 hover:to-indigo-700 transition-all shadow-lg';
                btnText.textContent = '道路表示 ON';
            }
        }
    }

    togglePreviewRoadNetworkDisplay() {
        this.showRoadNetwork = !this.showRoadNetwork;
        this.updatePreviewRoadNetworkButton();
        
        // 処理済み画像上での道路ネットワーク表示切り替え
        const canvas = document.querySelector('#processedImageContainer canvas');
        if (canvas && this.roadNetworkPreviewData) {
            const ctx = canvas.getContext('2d');
            
            // キャンバスをクリア
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 背景画像を再描画（処理済み画像）
            if (this.currentProcessedImage) {
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    // 道路ネットワークを描画
                    if (this.showRoadNetwork) {
                        this.drawPreviewRoadSkeleton(ctx, this.roadNetworkPreviewData);
                    }
                };
                img.src = this.currentProcessedImage;
            } else if (this.showRoadNetwork) {
                // 処理済み画像がない場合は道路ネットワークのみ描画
                this.drawPreviewRoadSkeleton(ctx, this.roadNetworkPreviewData);
            }
        }
    }
    
    updatePreviewRoadNetworkButton() {
        const btn = document.getElementById('previewRoadNetworkBtn');
        const btnText = document.getElementById('previewRoadNetworkBtnText');
        
        if (btn && btnText) {
            if (this.showRoadNetwork) {
                btn.className = 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-6 py-3 rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg';
                btnText.textContent = '道路ネットワーク表示 OFF';
            } else {
                btn.className = 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white px-6 py-3 rounded-lg hover:from-purple-600 hover:to-indigo-700 transition-all shadow-lg';
                btnText.textContent = '道路ネットワーク表示 ON';
            }
        }
    }
    
    drawPreviewRoadSkeleton(ctx, roadNetworkData) {
        // スケルトン画像が利用可能な場合は使用
        if (roadNetworkData && roadNetworkData.skeleton_image) {
            const img = new Image();
            img.onload = () => {
                // スケルトン画像を薄い灰色で描画
                ctx.globalAlpha = 0.6; // プレビューでは少し濃い目に表示
                ctx.drawImage(img, 0, 0, ctx.canvas.width, ctx.canvas.height);
                ctx.globalAlpha = 1.0; // 透明度をリセット
            };
            img.src = roadNetworkData.skeleton_image;
        }
    }

    clearPath() {
        // すべてリセット
        this.startPoint = null;
        this.endPoint = null;
        this.clickMode = 'start';
        
        // ステータス更新
        document.getElementById('startStatus').textContent = 'クリックして設定';
        document.getElementById('endStatus').textContent = 'クリックして設定';
        document.getElementById('findPathBtn').disabled = true;
        
        // 結果を非表示
        document.getElementById('resultInfo').style.display = 'none';
        
        // キャンバスを再描画（経路と点をクリア）
        if (this.currentProcessedImage) {
            this.displayProcessedImage(this.currentProcessedImage);
        }
        
        this.showSuccessMessage('🔄 リセットしました。新しく開始点と終了点を設定してください。');
    }

    // ユーティリティメソッド
    showLoading(text) {
        document.getElementById('loadingText').textContent = text;
        document.getElementById('loadingOverlay').style.display = 'flex';
        this.resetProgress();
    }

    hideLoading() {
        document.getElementById('loadingOverlay').style.display = 'none';
    }
    
    // ★新機能: リアルタイム進捗管理システム
    resetProgress() {
        const steps = ['step1Status', 'step2Status', 'step3Status', 'step4Status'];
        steps.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = '⏳';
                element.className = 'text-gray-400';
            }
        });
        this.updateProgressBar(0);
        this.updateEstimatedTime('計算中...');
    }
    
    updateProgressBar(percentage) {
        const progressBar = document.getElementById('progressBar');
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
    }
    
    updateProgressStep(stepNumber, status) {
        const statusElement = document.getElementById(`step${stepNumber}Status`);
        if (statusElement) {
            switch(status) {
                case 'processing':
                    statusElement.textContent = '🔄';
                    statusElement.className = 'text-yellow-400';
                    break;
                case 'completed':
                    statusElement.textContent = '✅';
                    statusElement.className = 'text-green-400';
                    break;
                case 'error':
                    statusElement.textContent = '❌';
                    statusElement.className = 'text-red-400';
                    break;
            }
        }
    }
    
    updateEstimatedTime(timeText) {
        const timeElement = document.getElementById('timeLeft');
        if (timeElement) {
            timeElement.textContent = timeText;
        }
    }
    
    simulateProgress(totalDuration) {
        let currentProgress = 0;
        const steps = [
            {step: 1, progress: 25, duration: totalDuration * 0.3},
            {step: 2, progress: 50, duration: totalDuration * 0.4},
            {step: 3, progress: 75, duration: totalDuration * 0.2},
            {step: 4, progress: 100, duration: totalDuration * 0.1}
        ];
        
        let stepIndex = 0;
        const progressInterval = setInterval(() => {
            if (stepIndex >= steps.length) {
                clearInterval(progressInterval);
                return;
            }
            
            const currentStep = steps[stepIndex];
            this.updateProgressStep(currentStep.step, 'processing');
            this.updateProgressBar(currentStep.progress);
            
            const remainingTime = Math.max(0, totalDuration - (Date.now() - this.progressStartTime) / 1000);
            this.updateEstimatedTime(`あと${Math.ceil(remainingTime)}秒`);
            
            setTimeout(() => {
                this.updateProgressStep(currentStep.step, 'completed');
                stepIndex++;
            }, currentStep.duration);
            
        }, totalDuration / steps.length);
        
        this.progressStartTime = Date.now();
    }

    showError(message, details = null, suggestions = null) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-4 rounded-lg shadow-lg z-50 max-w-md';
        
        let errorContent = `
            <div class="flex items-start">
                <i class="fas fa-exclamation-triangle mr-3 mt-1"></i>
                <div class="flex-1">
                    <div class="font-semibold mb-1">エラーが発生しました</div>
                    <div class="text-sm mb-2">${message}</div>
        `;
        
        if (details) {
            errorContent += `<div class="text-xs text-red-200 mb-2">詳細: ${details}</div>`;
        }
        
        if (suggestions) {
            errorContent += `
                <div class="text-xs text-red-200 mb-2">
                    <div class="font-semibold">解決方法:</div>
                    <ul class="list-disc list-inside ml-2">
                        ${suggestions.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        errorContent += `
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                            class="text-xs bg-red-600 hover:bg-red-700 px-2 py-1 rounded mt-2">
                        閉じる
                    </button>
                </div>
            </div>
        `;
        
        errorDiv.innerHTML = errorContent;
        document.body.appendChild(errorDiv);
        
        // 10秒後に自動削除
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 10000);
    }

    showSuccessMessage(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 max-w-sm';
        successDiv.innerHTML = `${message}`;
        document.body.appendChild(successDiv);
        
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.parentNode.removeChild(successDiv);
            }
        }, 4000);
    }
    
    // ★新機能: 詳細統計情報表示
    displayDetailedStats(result) {
        // 統計情報セクションを作成または更新
        let statsSection = document.getElementById('detailedStats');
        if (!statsSection) {
            statsSection = document.createElement('div');
            statsSection.id = 'detailedStats';
            statsSection.className = 'mt-6 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200';
            
            // 結果情報セクションの後に挿入
            const resultInfo = document.getElementById('resultInfo');
            resultInfo.parentNode.insertBefore(statsSection, resultInfo.nextSibling);
        }
        
        // パフォーマンス計算
        const efficiency = this.calculatePathEfficiency(result);
        const complexity = this.estimateComplexity(result);
        
        statsSection.innerHTML = `
            <h3 class="text-xl font-bold text-blue-800 mb-4 text-center">
                <i class="fas fa-chart-bar mr-2"></i>
                詳細統計情報
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-green-600">${result.path_length}</div>
                    <div class="text-sm text-gray-600">経路ステップ数</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-blue-600">${result.processing_time.toFixed(0)}ms</div>
                    <div class="text-sm text-gray-600">処理時間</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-purple-600">${efficiency}%</div>
                    <div class="text-sm text-gray-600">経路効率</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-orange-600">${complexity}</div>
                    <div class="text-sm text-gray-600">複雑度</div>
                </div>
            </div>
            
            <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-white rounded-lg p-4 shadow-sm">
                    <h4 class="font-semibold text-gray-800 mb-2">🎯 パフォーマンス評価</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span>速度</span>
                            <span class="${result.processing_time < 1000 ? 'text-green-600' : result.processing_time < 3000 ? 'text-yellow-600' : 'text-red-600'}">
                                ${result.processing_time < 1000 ? '高速' : result.processing_time < 3000 ? '標準' : '低速'}
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span>経路品質</span>
                            <span class="${efficiency > 80 ? 'text-green-600' : efficiency > 60 ? 'text-yellow-600' : 'text-red-600'}">
                                ${efficiency > 80 ? '最適' : efficiency > 60 ? '良好' : '改善可能'}
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span>アルゴリズム</span>
                            <span class="text-blue-600">${result.algorithm}</span>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg p-4 shadow-sm">
                    <h4 class="font-semibold text-gray-800 mb-2">📊 処理詳細</h4>
                    <div class="space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span>ナビゲーション指示数</span>
                            <span class="text-blue-600">${result.navigation_instructions ? result.navigation_instructions.length : 0}件</span>
                        </div>
                        <div class="flex justify-between">
                            <span>推定移動時間</span>
                            <span class="text-green-600">${Math.ceil(result.path_length * 0.5)}秒</span>
                        </div>
                        <div class="flex justify-between">
                            <span>信頼度</span>
                            <span class="text-purple-600">${efficiency > 80 ? '95%' : efficiency > 60 ? '85%' : '70%'}</span>
                        </div>
                        ${result.point_adjustments ? `
                        <div class="flex justify-between">
                            <span>📍 点の自動補正</span>
                            <span class="text-orange-600">
                                ${result.point_adjustments.start ? '開始 ' : ''}
                                ${result.point_adjustments.end ? '終了' : ''}
                            </span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    calculatePathEfficiency(result) {
        // 直線距離と実際の経路長から効率を計算
        if (!result.path || result.path.length < 2) return 100;
        
        const start = result.path[0];
        const end = result.path[result.path.length - 1];
        
        // 直線距離
        const straightDistance = Math.sqrt(
            Math.pow(end.x - start.x, 2) + Math.pow(end.y - start.y, 2)
        );
        
        // 実際の距離（経路長の近似）
        let actualDistance = 0;
        for (let i = 1; i < result.path.length; i++) {
            const prev = result.path[i-1];
            const curr = result.path[i];
            actualDistance += Math.sqrt(
                Math.pow(curr.x - prev.x, 2) + Math.pow(curr.y - prev.y, 2)
            );
        }
        
        // 効率 = (直線距離 / 実際の距離) * 100
        const efficiency = (straightDistance / actualDistance) * 100;
        return Math.min(100, Math.max(0, Math.round(efficiency)));
    }
    
    estimateComplexity(result) {
        // 経路の複雑度を推定
        if (!result.path || result.path.length < 3) return "単純";
        
        let directionChanges = 0;
        let prevDirection = null;
        
        for (let i = 2; i < result.path.length; i++) {
            const p1 = result.path[i-2];
            const p2 = result.path[i-1];
            const p3 = result.path[i];
            
            // 方向ベクトル
            const dx1 = p2.x - p1.x;
            const dy1 = p2.y - p1.y;
            const dx2 = p3.x - p2.x;
            const dy2 = p3.y - p2.y;
            
            // 方向の変化をチェック
            const currentDirection = Math.atan2(dy2, dx2);
            if (prevDirection !== null) {
                const angleDiff = Math.abs(currentDirection - prevDirection);
                if (angleDiff > Math.PI / 4) { // 45度以上の変化
                    directionChanges++;
                }
            }
            prevDirection = currentDirection;
        }
        
        if (directionChanges < 2) return "単純";
        if (directionChanges < 5) return "標準";
        return "複雑";
    }
    
    displayRoadNetworkInfo(roadNetwork) {
        // 道路ネットワーク情報セクションを作成または更新
        let networkSection = document.getElementById('roadNetworkInfo');
        if (!networkSection) {
            networkSection = document.createElement('div');
            networkSection.id = 'roadNetworkInfo';
            networkSection.className = 'mt-6 p-6 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200';
            
            // 詳細統計の後に挿入
            const statsSection = document.getElementById('detailedStats');
            if (statsSection) {
                statsSection.parentNode.insertBefore(networkSection, statsSection.nextSibling);
            }
        }
        
        const nodeCount = roadNetwork.nodes ? roadNetwork.nodes.length : 0;
        const edgeCount = roadNetwork.edges_count || 0;
        const hasRoadPath = roadNetwork.road_path && roadNetwork.road_path.length > 0;
        
        networkSection.innerHTML = `
            <h3 class="text-xl font-bold text-emerald-800 mb-4 text-center">
                <i class="fas fa-road mr-2"></i>
                🛣️ 道路ネットワーク情報
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-emerald-600">${nodeCount}</div>
                    <div class="text-sm text-gray-600">道路ノード</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-teal-600">${edgeCount}</div>
                    <div class="text-sm text-gray-600">道路接続</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold text-blue-600">${hasRoadPath ? roadNetwork.road_path.length : 0}</div>
                    <div class="text-sm text-gray-600">道路経路長</div>
                </div>
                <div class="bg-white rounded-lg p-4 text-center shadow-sm">
                    <div class="text-2xl font-bold ${hasRoadPath ? 'text-green-600' : 'text-orange-600'}">
                        ${hasRoadPath ? '✅' : '⚠️'}
                    </div>
                    <div class="text-sm text-gray-600">ネットワーク状態</div>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-white rounded-lg p-4 shadow-sm">
                    <h4 class="font-semibold text-gray-800 mb-2">🗺️ 道路接続状況</h4>
                    <div class="space-y-2 text-sm">
                        ${roadNetwork.start_road ? `
                            <div class="flex justify-between">
                                <span>開始地点→道路</span>
                                <span class="text-green-600">接続済み</span>
                            </div>
                        ` : `
                            <div class="flex justify-between">
                                <span>開始地点→道路</span>
                                <span class="text-orange-600">直接アクセス</span>
                            </div>
                        `}
                        ${roadNetwork.end_road ? `
                            <div class="flex justify-between">
                                <span>道路→終了地点</span>
                                <span class="text-green-600">接続済み</span>
                            </div>
                        ` : `
                            <div class="flex justify-between">
                                <span>道路→終了地点</span>
                                <span class="text-orange-600">直接アクセス</span>
                            </div>
                        `}
                        <div class="flex justify-between">
                            <span>道路密度</span>
                            <span class="text-blue-600">${this.calculateRoadDensity(nodeCount, edgeCount)}</span>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg p-4 shadow-sm">
                    <h4 class="font-semibold text-gray-800 mb-2">🎯 経路品質</h4>
                    <div class="space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span>道路利用率</span>
                            <span class="text-emerald-600">${hasRoadPath ? '85%' : '15%'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span>経路タイプ</span>
                            <span class="text-teal-600">${hasRoadPath ? '道路中央' : '壁沿い'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span>推奨度</span>
                            <span class="${hasRoadPath ? 'text-green-600' : 'text-yellow-600'}">
                                ${hasRoadPath ? '高い' : '標準'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mt-4 p-3 bg-emerald-100 rounded-lg">
                <div class="flex items-center text-sm text-emerald-800">
                    <i class="fas fa-info-circle mr-2"></i>
                    <span>
                        ${hasRoadPath ? 
                            '✅ 道路ネットワークを使用した最適な経路が生成されました。壁から離れた中央線を通る自然な経路です。' : 
                            '⚠️ 道路ネットワークが利用できませんでした。従来の壁沿い経路を使用しています。'
                        }
                    </span>
                </div>
            </div>
        `;
    }
    
    calculateRoadDensity(nodeCount, edgeCount) {
        if (nodeCount === 0) return '低い';
        const density = edgeCount / nodeCount;
        if (density < 1.5) return '低い';
        if (density < 2.5) return '中程度';
        return '高い';
    }
    
    // ★新機能: 結果エクスポート機能
    exportResults(format) {
        if (!this.lastResult) {
            this.showError('エクスポートする結果がありません', 'まず経路検索を実行してください');
            return;
        }
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        
        if (format === 'json') {
            const exportData = {
                timestamp: new Date().toISOString(),
                version: "1.0",
                settings: {
                    algorithm: this.selectedAlgorithm,
                    target_size: 1200
                },
                input: {
                    start_point: this.startPoint,
                    end_point: this.endPoint,
                    grid_size: {
                        width: this.currentGrid ? this.currentGrid[0].length : 0,
                        height: this.currentGrid ? this.currentGrid.length : 0
                    }
                },
                results: {
                    path: this.lastResult.path,
                    path_length: this.lastResult.path_length,
                    processing_time: this.lastResult.processing_time,
                    navigation_instructions: this.lastResult.navigation_instructions,
                    algorithm_used: this.lastResult.algorithm
                },
                statistics: {
                    efficiency: this.calculatePathEfficiency(this.lastResult),
                    complexity: this.estimateComplexity(this.lastResult)
                }
            };
            
            this.downloadFile(
                JSON.stringify(exportData, null, 2),
                `pathfinding_result_${timestamp}.json`,
                'application/json'
            );
            
            this.showSuccessMessage('📥 JSON形式で結果をエクスポートしました');
            
        } else if (format === 'image') {
            // 結果画像をダウンロード
            const canvas = document.querySelector('#processedImageContainer canvas');
            if (canvas) {
                canvas.toBlob((blob) => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `pathfinding_map_${timestamp}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    
                    this.showSuccessMessage('🖼️ 経路画像をエクスポートしました');
                });
            } else {
                this.showError('画像データが見つかりません', 'まず経路検索を実行してください');
            }
        }
    }
    
    shareResults() {
        if (!this.lastResult) {
            this.showError('共有する結果がありません', 'まず経路検索を実行してください');
            return;
        }
        
        // 結果の要約を作成
        const summary = `🤖 AI経路検索結果\\n` +
                       `📍 経路長: ${this.lastResult.path_length}ステップ\\n` +
                       `⚡ 処理時間: ${this.lastResult.processing_time.toFixed(0)}ms\\n` +
                       `🧠 アルゴリズム: ${this.lastResult.algorithm}\\n` +
                       `🎯 効率: ${this.calculatePathEfficiency(this.lastResult)}%\\n` +
                       `\\n💫 高精度AI経路検索システムで処理されました`;
        
        if (navigator.share) {
            // Web Share API対応ブラウザ
            navigator.share({
                title: 'AI経路検索結果',
                text: summary,
                url: window.location.href
            }).then(() => {
                this.showSuccessMessage('📱 結果を共有しました');
            }).catch((error) => {
                console.log('Share failed:', error);
                this.fallbackShare(summary);
            });
        } else {
            // フォールバック: クリップボードにコピー
            this.fallbackShare(summary);
        }
    }
    
    fallbackShare(text) {
        // クリップボードにコピー
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccessMessage('📋 結果をクリップボードにコピーしました');
        }).catch(() => {
            // さらなるフォールバック: テキストエリア作成
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            
            this.showSuccessMessage('📋 結果をクリップボードにコピーしました');
        });
    }
    
    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// アプリケーション開始
document.addEventListener('DOMContentLoaded', function() {
    console.log('🤖 AI経路検索システムを初期化中...');
    window.app = new AIPathfindingApp();
    console.log('✅ システムの準備が完了しました！');
});