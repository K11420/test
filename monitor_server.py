#!/usr/bin/env python3
"""
東証＆暗号資産 リアルタイム常駐監視＋FastAPI執行サーバー
- 2~3秒間隔で市場を常時監視
- 急騰・急落シグナルを自動検知
- 外部APIエンドポイント（GET /status, GET /market, POST /order）を公開
- Pickle（みるく）からの外部指示を受け付けて即座に執行
"""

import sys
import time
import json
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# --- 設定 ---
PORT = 8000
TICK_INTERVAL_SEC = 3.0  # 監視間隔（秒）

# 監視対象銘柄
WATCHLIST = {
    "6920.T": {"name": "レーザーテック", "market": "JP"},
    "6857.T": {"name": "アドバンテスト", "market": "JP"},
    "6146.T": {"name": "ディスコ", "market": "JP"},
    "3778.T": {"name": "さくらインターネット", "market": "JP"},
    "7014.T": {"name": "名村造船所", "market": "JP"},
    "9984.T": {"name": "ソフトバンクG", "market": "JP"},
    "BTC-JPY": {"name": "ビットコイン (24h)", "market": "CRYPTO"}
}

# --- 共有インメモリ状態 ---
STATE = {
    "server_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "last_check_time": None,
    "check_count": 0,
    "capital": 1500000,          # 初期元本150万円
    "cash": 1500000,
    "leverage": 3.3,
    "positions": {},            # code -> {name, shares, avg_cost, market_value, pnl, pnl_pct}
    "trade_history": [],        # 約定履歴
    "latest_market_data": {},   # code -> {price, change, change_pct, high, low, updated_at}
    "alerts": []                # 急変シグナルキュー
}
STATE_LOCK = threading.Lock()

# --- 株価取得ロジック ---
def fetch_quote(code):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
            prev_close = meta.get("chartPreviousClose") or price
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0.0
            return {
                "price": round(price, 2 if "BTC" in code else 1),
                "prev_close": round(prev_close, 2 if "BTC" in code else 1),
                "change": round(change, 2 if "BTC" in code else 1),
                "change_pct": round(change_pct, 2),
                "updated_at": datetime.now().strftime("%H:%M:%S")
            }
    except Exception as e:
        return None

# --- 常時監視バックグラウンドスレッド ---
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 リアルタイム監視スレッドが起動しました（間隔: {TICK_INTERVAL_SEC}秒）")
    prev_prices = {}
    
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for code, meta in WATCHLIST.items():
                quote = fetch_quote(code)
                if not quote:
                    continue
                
                with STATE_LOCK:
                    STATE["latest_market_data"][code] = {
                        "name": meta["name"],
                        "market": meta["market"],
                        **quote
                    }
                    
                    # 急変検知（直前との価格差・急騰急落シグナル）
                    if code in prev_prices:
                        p_old = prev_prices[code]
                        p_new = quote["price"]
                        diff_pct = ((p_new - p_old) / p_old) * 100 if p_old else 0
                        if abs(diff_pct) >= 0.8:  # 3秒で0.8%以上の急変
                            alert = {
                                "time": now_str,
                                "code": code,
                                "name": meta["name"],
                                "event": "🔥 急騰検知" if diff_pct > 0 else "⚡ 急落検知",
                                "price": p_new,
                                "change_pct": round(diff_pct, 2)
                            }
                            STATE["alerts"].append(alert)
                            if len(STATE["alerts"]) > 50:
                                STATE["alerts"].pop(0)
                            print(f"⚠️ [ALERT] {alert['event']} - {meta['name']}: {p_new}円 ({diff_pct:+.2f}%)")
                    
                    prev_prices[code] = quote["price"]
                    
                    # ポジション評価額・損益の自動再計算
                    if code in STATE["positions"]:
                        pos = STATE["positions"][code]
                        cur_p = quote["price"]
                        pos["current_price"] = cur_p
                        pos["market_value"] = round(cur_p * pos["shares"])
                        pos["pnl"] = round((cur_p - pos["avg_cost"]) * pos["shares"])
                        pos["pnl_pct"] = round(((cur_p - pos["avg_cost"]) / pos["avg_cost"]) * 100, 2)
            
            with STATE_LOCK:
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
            # 信用余力チェック（レバレッジ考慮）
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
                total_pos_val = sum(p["market_value"] for p in STATE["positions"].values())
                total_unrealized = sum(p["pnl"] for p in STATE["positions"].values())
                res = {
                    "status": "online",
                    "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "start_time": STATE["server_start_time"],
                    "checks_completed": STATE["check_count"],
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
                    "market_data": STATE["latest_market_data"],
                    "alerts": STATE["alerts"][-10:]
                })

        elif url_path == "/positions":
            with STATE_LOCK:
                self._send_json(200, {
                    "cash": STATE["cash"],
                    "positions": STATE["positions"],
                    "trade_history": STATE["trade_history"][:20]
                })

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
            # 必須パラメータ: code, action, shares
            code = req_data.get("code")
            action = req_data.get("action")
            shares = req_data.get("shares")
            reason = req_data.get("reason", "Pickle司令官によるAI判断執行")
            
            if not code or not action or not shares:
                return self._send_json(400, {"error": "code, action, shares are required"})
            
            result = execute_order(code, action, int(shares), reason=reason)
            status_code = 200 if result.get("success") else 400
            self._send_json(status_code, result)

        elif url_path == "/alerts/clear":
            with STATE_LOCK:
                STATE["alerts"].clear()
            self._send_json(200, {"success": True, "message": "Alerts cleared"})

        else:
            self._send_json(404, {"error": "Not Found"})

# --- メイン起動 ---
def run_server():
    # 監視ループをデーモンスレッドで開始
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, APIHandler)
    print("=" * 60)
    print(f"🔥 東証＆暗号資産 24時間リアルタイム監視＆執行サーバー起動！")
    print(f"📡 ローカルAPIアドレス: http://localhost:{PORT}")
    print(f"⚡ エンドポイント:")
    print(f"   GET  /status    - サーバー稼働状態・資産サマリー")
    print(f"   GET  /market    - リアルタイム全銘柄気配＆急変アラート")
    print(f"   GET  /positions - 現在保有ポジション＆約定履歴")
    print(f"   POST /order     - 売買執行指示（code, action, shares, reason）")
    print("=" * 60)
    print("💡 Cloudflare Tunnelで外部公開するコマンド:")
    print(f"   cloudflared tunnel --url http://localhost:{PORT}")
    print("=" * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")

if __name__ == "__main__":
    run_server()
