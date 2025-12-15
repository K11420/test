import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/cloudflare-workers'

const app = new Hono()

// CORS設定（API用）
app.use('/api/*', cors())

// 静的ファイル配信（/static/*）
app.use('/static/*', serveStatic({ root: './public' }))

// API: 画像の二値化処理
app.post('/api/process-image', async (c) => {
  try {
    const { imageData, binarizationMode, threshold, adaptiveMethod } = await c.req.json()
    
    // Base64画像データをデコード
    const base64Data = imageData.replace(/^data:image\/(png|jpg|jpeg);base64,/, '')
    
    // ブラウザの Canvas を使用した処理を返す（フロントエンドで処理）
    return c.json({
      success: true,
      processedImageData: imageData, // フロントエンドで実際の処理を行う
      binarizationMode,
      threshold,
      adaptiveMethod
    })
  } catch (error) {
    return c.json({ error: 'Image processing failed' }, 500)
  }
})

// API: パス検索（フロントエンドで処理）
app.post('/api/find-path', async (c) => {
  try {
    const { grid, startPoint, endPoint, algorithm } = await c.req.json()
    
    // フロントエンドで処理されるため、パラメータのみ返す
    return c.json({
      success: true,
      grid,
      startPoint,
      endPoint,
      algorithm
    })
  } catch (error) {
    return c.json({ error: 'Path finding failed' }, 500)
  }
})

// メインページ
app.get('/', (c) => {
  return c.html(`
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚀 高速CV経路検出システム - 高度な二値化処理対応版</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet">
        <link href="/static/style.css" rel="stylesheet">
    </head>
    <body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen">
        <div class="container mx-auto px-4 py-8">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-gray-800 mb-4">
                    <i class="fas fa-route mr-3 text-blue-600"></i>
                    高速CV経路検出システム
                </h1>
                <p class="text-lg text-gray-600 mb-2">高度な二値化処理とリアルタイム経路探索</p>
                <div class="inline-flex items-center px-4 py-2 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                    <i class="fas fa-bolt mr-2"></i>
                    A* • BFS • Dijkstra アルゴリズム対応
                </div>
            </div>
            
            <div id="app">
                <!-- Reactアプリケーションがマウントされる -->
                <div class="text-center py-12">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p class="text-gray-600">アプリケーションを読み込み中...</p>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/axios@1.6.0/dist/axios.min.js"></script>
        <script src="/static/app.js"></script>
    </body>
    </html>
  `)
})

export default app
