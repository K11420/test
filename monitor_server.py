#!/usr/bin/env python3
"""
東証＆暗号資産 24時間リアルタイム常駐監視＋FastAPI執行サーバー（マルチ銘柄＆動的追加対応版）
- 並行フェッチ（ThreadPoolExecutor）で数十銘柄を数秒で高速巡回
- 半導体、AI、防衛、海運、メガバンク、暗号資産など25銘柄を標準搭載
- API経由での銘柄動的追加（POST /watchlist/add）に対応
- 急騰・急落シグナル自動検知
- 外部APIエンドポイント（GET /status, GET /market, POST /order）完備
"""

import sys
import time
import json
import threading
import concurrent.futures
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# --- 設定 ---
PORT = 8000
TICK_INTERVAL_SEC = 3.0  # 監視間隔（秒）
MAX_WORKERS = 10        # 並行フェッチスレッド数

# 監視対象銘柄（初期25銘柄）
WATCHLIST = {
    # --- 半導体・AIインフラ（激動・ボラティリティモンスター） ---
    "6920.T": {"name": "レーザーテック", "market": "JP", "category": "半導体"},
    "6857.T": {"name": "アドバンテスト", "market": "JP", "category": "半導体"},
    "6146.T": {"name": "ディスコ", "market": "JP", "category": "半導体"},
    "8035.T": {"name": "東京エレクトロン", "market": "JP", "category": "半導体"},
    "6526.T": {"name": "ソシオネクスト", "market": "JP", "category": "半導体"},
    "6723.T": {"name": "ルネサス", "market": "JP", "category": "半導体"},
    "3778.T": {"name": "さくらインターネット", "market": "JP", "category": "AIデータセンター"},
    
    # --- 防衛・重工・造船（国策・テーマ急騰株） ---
    "7011.T": {"name": "三菱重工業", "market": "JP", "category": "防衛・宇宙"},
    "7012.T": {"name": "川崎重工業", "market": "JP", "category": "防衛・航空"},
    "7014.T": {"name": "名村造船所", "market": "JP", "category": "造船・海運"},
    "7003.T": {"name": "三井E&S", "market": "JP", "category": "造船・港湾"},

    # --- メガテック・ゲーム・主力株 ---
    "9984.T": {"name": "ソフトバンクG", "market": "JP", "category": "AI投資・テック"},
    "6758.T": {"name": "ソニーグループ", "market": "JP", "category": "エンタメ・電機"},
    "7203.T": {"name": "トヨタ自動車", "market": "JP", "category": "自動車"},
    "6501.T": {"name": "日立製作所", "market": "JP", "category": "社会イノベーション"},
    "7974.T": {"name": "任天堂", "market": "JP", "category": "ゲーム"},
    "9432.T": {"name": "NTT", "market": "JP", "category": "通信・インフラ"},

    # --- メガバンク・海運・商社 ---
    "8306.T": {"name": "三菱UFJフィナンシャルG", "market": "JP", "category": "銀行"},
    "8316.T": {"name": "三井住友フィナンシャルG", "market": "JP", "category": "銀行"},
    "8058.T": {"name": "三菱商事", "market": "JP", "category": "総合商社"},
    "9101.T": {"name": "日本郵船", "market": "JP", "category": "海運"},
    "9104.T": {"name": "商船三井", "market": "JP", "category": "海運"},

    # --- 新興・グロース・VTuber ---
    "5253.T": {"name": "カバー", "market": "JP", "category": "VTuber・IP"},
    "5032.T": {"name": "ANYCOLOR", "market": "JP", "category": "VTuber・IP"},

    # --- 暗号資産（24時間365日常時激動） ---
    "BTC-JPY": {"name": "ビットコイン (24h)", "market": "CRYPTO", "category": "暗号資産"},
    "ETH-JPY": {"name": "イーサリアム (24h)", "market": "CRYPTO", "category": "暗号資産"},
    "SOL-JPY": {"name": "ソラナ (24h)", "market": "CRYPTO", "category": "暗号資産"}
}

# --- 共有インメモリ状態 ---
STATE = {
    "server_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "last_check_time": None,
    "check_count": 0,
    "capital": 1500000,
    "cash": 1500000,
    "leverage": 3.3,
    "positions": {},
    "trade_history": [],
    "latest_market_data": {},
    "alerts": []
}
STATE_LOCK = threading.Lock()

# --- 株価取得ロジック ---
def fetch_single_quote(code, meta):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode("utf-8"))
            meta_data = data["chart"]["result"][0]["meta"]
            price = meta_data.get("regularMarketPrice") or meta_data.get("chartPreviousClose")
            prev_close = meta_data.get("chartPreviousClose") or price
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0.0
            is_crypto = "CRYPTO" in meta.get("market", "")
            return code, {
                "name": meta["name"],
                "market": meta["market"],
                "category": meta.get("category", "一般"),
                "price": round(price, 2 if is_crypto else 1),
                "prev_close": round(prev_close, 2 if is_crypto else 1),
                "change": round(change, 2 if is_crypto else 1),
                "change_pct": round(change_pct, 2),
                "updated_at": datetime.now().strftime("%H:%M:%S")
            }
    except Exception:
        return code, None

# --- 常時監視バックグラウンドスレッド（並行フェッチ） ---
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 高速並行監視スレッド起動（監視銘柄数: {len(WATCHLIST)}件, 間隔: {TICK_INTERVAL_SEC}秒）")
    prev_prices = {}
    
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with STATE_LOCK:
                current_watchlist = dict(WATCHLIST)

            # 並行フェッチで一斉取得
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(fetch_single_quote, c, m) for c, m in current_watchlist.items()]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            with STATE_LOCK:
                for code, quote in results:
                    if not quote:
                        continue
                    
                    STATE["latest_market_data"][code] = quote
                    
                    # 急変検知（直前との価格差・急騰急落シグナル）
                    if code in prev_prices:
                        p_old = prev_prices[code]
                        p_new = quote["price"]
                        diff_pct = ((p_new - p_old) / p_old) * 100 if p_old else 0
                        if abs(diff_pct) >= 0.7:  # 0.7%以上の急変動
                            alert = {
                                "time": now_str,
                                "code": code,
                                "name": quote["name"],
                                "event": "🔥 急騰検知" if diff_pct > 0 else "⚡ 急落検知",
                                "price": p_new,
                                "change_pct": round(diff_pct, 2)
                            }
                            STATE["alerts"].append(alert)
                            if len(STATE["alerts"]) > 50:
                                STATE["alerts"].pop(0)
                            print(f"⚠️ [ALERT] {alert['event']} - {quote['name']}: {p_new} ({diff_pct:+.2f}%)")
                    
                    prev_prices[code] = quote["price"]
                    
                    # 保有ポジション損益のリアルタイム更新
                    if code in STATE["positions"]:
                        pos = STATE["positions"][code]
                        cur_p = quote["price"]
                        pos["current_price"] = cur_p
                        pos["market_value"] = round(cur_p * pos["shares"])
                        pos["pnl"] = round((cur_p - pos["avg_cost"]) * pos["shares"])
                        pos["pnl_pct"] = round(((cur_p - pos["avg_cost"]) / pos["avg_cost"]) * 100, 2)
                
                STATE["last_check_time"] = now_str
                STATE["check_count"] += 1

        except Exception as e:
            print(f"Error in monitor loop: {e}")
            
        time.sleep(TICK_INTERVAL_SEC)

# --- 注文執行ロジック ---
def execute_order(code, action, shares, price=None, reason="AI指令執行"):
    action = action.upper()
    with STATE_LOCK:
        if code not in STATE["latest_market_data"]:
            return {"success": False, "error": f"銘柄 {code} の価格データがありません"}
        
        cur_price = price or STATE["latest_market_data"][code]["price"]
        amount = round(cur_price * shares)
        name = WATCHLIST.get(code, {}).get("name", code)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "BUY":
            margin_cap = (STATE["cash"] * STATE["leverage"])
            current_exposure = sum(p["market_value"] for p in STATE["positions"].values())
            if current_exposure + amount > margin_cap:
                return {"success": False, "error": f"信用余力不足です（上限: {margin_cap:,.0f}円, 現在建玉: {current_exposure:,.0f}円）"}
            
            if code in STATE["positions"]:
                old_pos = STATE["positions"][code]
                total_shares = old_pos["shares"] + shares
                total_cost = (old_pos["avg_cost"] * old_pos["shares"]) + amount
                old_pos["avg_cost"] = round(total_cost / total_shares, 1)
                old_pos["shares"] = total_shares
                old_pos["current_price"] = cur_price
                old_pos["market_value"] = round(cur_price * total_shares)
                old_pos["pnl"] = round((cur_price - old_pos["avg_cost"]) * total_shares)
                old_pos["pnl_pct"] = round(((cur_price - old_pos["avg_cost"]) / old_pos["avg_cost"]) * 100, 2)
            else:
                STATE["positions"][code] = {
                    "name": name,
                    "shares": shares,
                    "avg_cost": cur_price,
                    "current_price": cur_price,
                    "market_value": amount,
                    "pnl": 0,
                    "pnl_pct": 0.0,
                    "entry_time": now_str
                }
            
            log_item = {
                "time": now_str,
                "action": "BUY",
                "code": code,
                "name": name,
                "shares": shares,
                "price": cur_price,
                "amount": amount,
                "reason": reason
            }
            STATE["trade_history"].insert(0, log_item)
            print(f"🟢 [EXECUTE] BUY {name} {shares}株 @ {cur_price}円 - 理由: {reason}")
            return {"success": True, "trade": log_item}

        elif action == "SELL":
            if code not in STATE["positions"] or STATE["positions"][code]["shares"] < shares:
                return {"success": False, "error": f"保有株数が不足しています"}
            
            pos = STATE["positions"][code]
            realized_pnl = round((cur_price - pos["avg_cost"]) * shares)
            realized_pnl_pct = round(((cur_price - pos["avg_cost"]) / pos["avg_cost"]) * 100, 2)
            STATE["cash"] += realized_pnl
            
            if pos["shares"] == shares:
                del STATE["positions"][code]
            else:
                pos["shares"] -= shares
                pos["market_value"] = round(cur_price * pos["shares"])
                pos["pnl"] = round((cur_price - pos["avg_cost"]) * pos["shares"])
                pos["pnl_pct"] = round(((cur_price - pos["avg_cost"]) / pos["avg_cost"]) * 100, 2)
            
            log_item = {
                "time": now_str,
                "action": "SELL",
                "code": code,
                "name": name,
                "shares": shares,
                "price": cur_price,
                "pnl": realized_pnl,
                "pnl_pct": realized_pnl_pct,
                "reason": reason
            }
            STATE["trade_history"].insert(0, log_item)
            print(f"🔴 [EXECUTE] SELL {name} {shares}株 @ {cur_price}円 (損益: {realized_pnl:+}円 / {realized_pnl_pct:+}%) - 理由: {reason}")
            return {"success": True, "trade": log_item}

        else:
            return {"success": False, "error": f"不明なアクション: {action}"}

# --- HTTP API ハンドラ ---
class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self):
        self._send_json(200, {"status": "ok"})

    def do_GET(self):
        url_path = urllib.parse.urlparse(self.path).path
        
        if url_path == "/" or url_path == "/status":
            with STATE_LOCK:
                total_unrealized = sum(p["pnl"] for p in STATE["positions"].values())
                res = {
                    "status": "online",
                    "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "start_time": STATE["server_start_time"],
                    "checks_completed": STATE["check_count"],
                    "watchlist_count": len(WATCHLIST),
                    "last_check": STATE["last_check_time"],
                    "total_equity": STATE["cash"] + total_unrealized,
                    "cash": STATE["cash"],
                    "positions_count": len(STATE["positions"]),
                    "unrealized_pnl": total_unrealized
                }
            self._send_json(200, res)

        elif url_path == "/market":
            with STATE_LOCK:
                self._send_json(200, {
                    "count": len(STATE["latest_market_data"]),
                    "market_data": STATE["latest_market_data"],
                    "alerts": STATE["alerts"][-15:]
                })

        elif url_path == "/positions":
            with STATE_LOCK:
                self._send_json(200, {
                    "cash": STATE["cash"],
                    "positions": STATE["positions"],
                    "trade_history": STATE["trade_history"][:25]
                })

        elif url_path == "/watchlist":
            with STATE_LOCK:
                self._send_json(200, {"watchlist": WATCHLIST})

        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        url_path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        
        try:
            req_data = json.loads(body)
        except Exception:
            return self._send_json(400, {"error": "Invalid JSON format"})

        if url_path == "/order":
            code = req_data.get("code")
            action = req_data.get("action")
            shares = req_data.get("shares")
            reason = req_data.get("reason", "Pickle司令官によるAI判断執行")
            
            if not code or not action or not shares:
                return self._send_json(400, {"error": "code, action, shares are required"})
            
            result = execute_order(code, action, int(shares), reason=reason)
            status_code = 200 if result.get("success") else 400
            self._send_json(status_code, result)

        elif url_path == "/watchlist/add":
            code = req_data.get("code")
            name = req_data.get("name", code)
            market = req_data.get("market", "JP")
            category = req_data.get("category", "カスタム")
            if not code:
                return self._send_json(400, {"error": "code is required"})
            with STATE_LOCK:
                WATCHLIST[code] = {"name": name, "market": market, "category": category}
            print(f"➕ [WATCHLIST] 銘柄追加: {name} ({code})")
            self._send_json(200, {"success": True, "message": f"{name} ({code}) を監視リストに追加しました", "total_watchlist": len(WATCHLIST)})

        elif url_path == "/watchlist/remove":
            code = req_data.get("code")
            if not code:
                return self._send_json(400, {"error": "code is required"})
            with STATE_LOCK:
                if code in WATCHLIST:
                    del WATCHLIST[code]
                    if code in STATE["latest_market_data"]:
                        del STATE["latest_market_data"][code]
            self._send_json(200, {"success": True, "message": f"{code} を監視リストから削除しました", "total_watchlist": len(WATCHLIST)})

        elif url_path == "/alerts/clear":
            with STATE_LOCK:
                STATE["alerts"].clear()
            self._send_json(200, {"success": True, "message": "Alerts cleared"})

        else:
            self._send_json(404, {"error": "Not Found"})

# --- メイン起動 ---
def run_server():
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, APIHandler)
    print("=" * 65)
    print(f"🔥 東証＆暗号資産 24時間リアルタイム監視＆執行サーバー（25銘柄版）起動！")
    print(f"📡 ローカルAPIアドレス: http://localhost:{PORT}")
    print(f"📊 監視銘柄数: {len(WATCHLIST)}銘柄（並行フェッチ）")
    print(f"⚡ エンドポイント:")
    print(f"   GET  /status          - サーバー稼働状態・資産サマリー")
    print(f"   GET  /market          - リアルタイム全銘柄気配＆急変アラート")
    print(f"   GET  /positions       - 現在保有ポジション＆約定履歴")
    print(f"   POST /order           - 売買執行指示（code, action, shares, reason）")
    print(f"   POST /watchlist/add   - 銘柄動的追加（code, name, category）")
    print(f"   POST /watchlist/remove - 銘柄削除（code）")
    print("=" * 65)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")

if __name__ == "__main__":
    run_server()
