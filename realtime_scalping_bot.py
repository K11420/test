#!/usr/bin/env python3
"""
⚡ 東証リアルタイム・スキャルピング & デイトレード監視Bot
作成: 久保田様専属AI みるく
動作環境: Python 3.8+ (標準ライブラリのみで動作、外部依存なし)

使い方:
  python3 realtime_scalping_bot.py
  
  # Discord通知を使いたい場合:
  python3 realtime_scalping_bot.py --webhook https://discord.com/api/webhooks/...
  # または環境変数
  export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error
from datetime import datetime

# ==================== 設定エリア ====================
POLL_INTERVAL_SEC = 3.0       # 株価取得の間隔（秒）
INITIAL_CAPITAL = 1500000     # 初期資金（円）
LEVERAGE = 3.3                # 信用取引レバレッジ倍率
MAX_POSITIONS = 2             # 同時保有ポジション上限数

WATCHLIST = [
    {"code": "6920.T", "name": "レーザーテック", "unit": 100, "take_profit": 1.5, "stop_loss": 1.0},
    {"code": "6857.T", "name": "アドバンテスト", "unit": 100, "take_profit": 1.5, "stop_loss": 1.0},
    {"code": "3778.T", "name": "さくらインターネット", "unit": 400, "take_profit": 2.0, "stop_loss": 1.2},
    {"code": "9984.T", "name": "ソフトバンクG", "unit": 300, "take_profit": 1.8, "stop_loss": 1.0},
    {"code": "6146.T", "name": "ディスコ", "unit": 100, "take_profit": 1.2, "stop_loss": 0.8},
    {"code": "7014.T", "name": "名村造船所", "unit": 300, "take_profit": 2.0, "stop_loss": 1.2},
]

# ANSI カラーコード
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_BG_BLUE = "\033[44m"

# ==================== Discord Webhook 通知 ====================
def send_discord_notification(webhook_url, title, description, color=0x38BDF8, fields=None):
    if not webhook_url:
        return
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields or [],
            "footer": {"text": "東証リアルタイム・スキャルピングBot · 久保田様専属"},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "ScalpBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception as e:
        # 通知エラーで監視を止めない
        pass

# ==================== 株価取得 (Yahoo Finance API) ====================
def fetch_quote(code):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev_close = meta.get("previousClose") or price
            high = meta.get("regularMarketDayHigh") or price
            low = meta.get("regularMarketDayLow") or price
            open_p = meta.get("regularMarketDayOpen") or prev_close
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0

            return {
                "price": round(price, 1),
                "change": round(change, 1),
                "change_pct": round(change_pct, 2),
                "high": round(high, 1),
                "low": round(low, 1),
                "open": round(open_p, 1),
                "prev_close": round(prev_close, 1)
            }
    except Exception:
        return None

# ==================== メインロジック ====================
class ScalpingDesk:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url
        self.cash = INITIAL_CAPITAL
        self.initial_capital = INITIAL_CAPITAL
        self.positions = {}  # code -> pos_dict
        self.history = []
        self.price_history = {item["code"]: [] for item in WATCHLIST}
        self.win_count = 0
        self.loss_count = 0
        self.trade_count = 0
        self.realized_pnl = 0

    def run(self):
        print(f"{C_BOLD}{C_GREEN}🚀 リアルタイム・スキャルピングBotを起動しました...{C_RESET}")
        time.sleep(1)
        
        while True:
            now_str = datetime.now().strftime("%H:%M:%S")
            market_quotes = {}

            # 銘柄を巡回して株価取得
            for item in WATCHLIST:
                code = item["code"]
                quote = fetch_quote(code)
                if quote:
                    market_quotes[code] = quote
                    hist = self.price_history[code]
                    hist.append(quote["price"])
                    if len(hist) > 20:
                        hist.pop(0)

            # ポジションの決済判定（利確／損切）
            self.check_positions(market_quotes)

            # 新規エントリー判定
            self.check_entries(market_quotes)

            # 画面描画
            self.render_dashboard(now_str, market_quotes)

            time.sleep(POLL_INTERVAL_SEC)

    def check_positions(self, market_quotes):
        closed_codes = []
        for code, pos in self.positions.items():
            quote = market_quotes.get(code)
            if not quote:
                continue
            curr_p = quote["price"]
            entry_p = pos["entry_price"]
            shares = pos["shares"]
            pnl = (curr_p - entry_p) * shares
            pnl_pct = ((curr_p - entry_p) / entry_p) * 100

            duration = int(time.time() - pos["entry_time"])

            # 利確判定
            if pnl_pct >= pos["take_profit"]:
                self.close_trade(code, curr_p, pnl, pnl_pct, duration, "利確ターゲット到達 (TAKE PROFIT)")
                closed_codes.append(code)
            # 損切判定
            elif pnl_pct <= -pos["stop_loss"]:
                self.close_trade(code, curr_p, pnl, pnl_pct, duration, "ロスカット執行 (STOP LOSS)")
                closed_codes.append(code)

        for c in closed_codes:
            del self.positions[c]

    def close_trade(self, code, exit_price, pnl, pnl_pct, duration_sec, reason):
        pos = self.positions[code]
        pnl_round = round(pnl)
        self.cash += pnl_round
        self.realized_pnl += pnl_round
        self.trade_count += 1
        if pnl >= 0:
            self.win_count += 1
        else:
            self.loss_count += 1

        record = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "SELL (利確)" if pnl >= 0 else "SELL (損切)",
            "code": code,
            "name": pos["name"],
            "shares": pos["shares"],
            "entry_p": pos["entry_price"],
            "exit_p": exit_price,
            "pnl": pnl_round,
            "pnl_pct": round(pnl_pct, 2),
            "duration": f"{duration_sec}秒",
            "reason": reason
        }
        self.history.insert(0, record)

        # Discord通知
        color = 0x22C55E if pnl >= 0 else 0xEF4444
        sign = "+" if pnl >= 0 else ""
        title = f"{'🟢 利確約定' if pnl >= 0 else '🔴 損切約定'}: {pos['name']} ({sign}{pnl_round:,}円)"
        desc = f"**{record['action']}** {pos['shares']}株 @ {exit_price:,}円 (保有: {duration_sec}秒)\n{reason}"
        fields = [
            {"name": "損益", "value": f"**{sign}{pnl_round:,} 円 ({sign}{round(pnl_pct,2)}%)**", "inline": True},
            {"name": "本日累計実現損益", "value": f"{self.realized_pnl:,} 円", "inline": True},
            {"name": "勝率", "value": f"{self.win_count}勝{self.loss_count}敗 ({round(self.win_count/self.trade_count*100, 1)}%)", "inline": True}
        ]
        send_discord_notification(self.webhook_url, title, desc, color, fields)

    def check_entries(self, market_quotes):
        if len(self.positions) >= MAX_POSITIONS:
            return

        for item in WATCHLIST:
            code = item["code"]
            if code in self.positions:
                continue
            hist = self.price_history[code]
            if len(hist) < 3:
                continue

            quote = market_quotes.get(code)
            if not quote:
                continue

            # スキャルピング・シグナル検知
            # 1. 急反発リバウンド (直前2回連続下落から今回プラスへ反転)
            rebound = (hist[-3] > hist[-2] and hist[-1] > hist[-2] and quote["price"] > quote["low"])
            # 2. ブレイクアウト (高値近辺で勢いよく上伸)
            breakout = (quote["price"] >= quote["high"] * 0.998 and quote["change_pct"] > 1.0)

            if rebound or breakout:
                shares = item["unit"]
                cost = shares * quote["price"]
                entry_reason = "急反発リバウンドシグナル点灯" if rebound else "高値ブレイクアウト順張り"
                
                self.positions[code] = {
                    "name": item["name"],
                    "shares": shares,
                    "entry_price": quote["price"],
                    "entry_time": time.time(),
                    "take_profit": item["take_profit"],
                    "stop_loss": item["stop_loss"],
                    "reason": entry_reason
                }

                # 履歴
                self.history.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "BUY (エントリー)",
                    "code": code,
                    "name": item["name"],
                    "shares": shares,
                    "entry_p": quote["price"],
                    "reason": entry_reason
                })

                # Discord通知
                title = f"⚡ エントリー約定: {item['name']} ({shares}株 @ {quote['price']:,}円)"
                desc = f"**BUY** {shares}株 買付総額: {cost:,}円\n根拠: {entry_reason} (利確目標: +{item['take_profit']}%, 損切: -{item['stop_loss']}%)"
                send_discord_notification(self.webhook_url, title, desc, 0xF59E0B)

                if len(self.positions) >= MAX_POSITIONS:
                    break

    def render_dashboard(self, now_str, market_quotes):
        # 画面クリア（ANSI）
        sys.stdout.write("\033[2J\033[H")

        # 未実現損益
        unrealized = 0
        for code, pos in self.positions.items():
            curr_p = market_quotes.get(code, {}).get("price", pos["entry_price"])
            unrealized += (curr_p - pos["entry_price"]) * pos["shares"]

        total_equity = self.cash + round(unrealized)
        total_pnl = total_equity - self.initial_capital
        pnl_pct = round((total_pnl / self.initial_capital) * 100, 2)
        win_rate = round((self.win_count / self.trade_count * 100), 1) if self.trade_count > 0 else 0

        pnl_color = C_GREEN if total_pnl >= 0 else C_RED
        pnl_sign = "+" if total_pnl >= 0 else ""

        print(f"{C_BOLD}{C_BG_BLUE} ⚡ 東証リアルタイム・スキャルピングDesk | 久保田様専属 {C_RESET}  時刻: {C_CYAN}{now_str}{C_RESET}")
        print("=" * 72)
        print(f" 総資産: {C_BOLD}{total_equity:,} 円{C_RESET} ({pnl_color}{pnl_sign}{total_pnl:,} 円 / {pnl_sign}{pnl_pct}%{C_RESET}) | 現金余力: {self.cash:,} 円")
        print(f" 本日確定損益: {pnl_color}{pnl_sign}{self.realized_pnl:,} 円{C_RESET} | 戦績: {self.win_count}勝 {self.loss_count}敗 (勝率 {win_rate}%)")
        print("-" * 72)

        # 監視銘柄一覧
        print(f"{C_BOLD}[監視板 - リアルタイム株価]{C_RESET}")
        for item in WATCHLIST:
            code = item["code"]
            q = market_quotes.get(code)
            if q:
                chg_c = C_GREEN if q["change"] >= 0 else C_RED
                chg_s = "+" if q["change"] >= 0 else ""
                in_pos = f"{C_YELLOW}[保有中]{C_RESET}" if code in self.positions else "       "
                print(f" {in_pos} {item['name']:<12} {q['price']:>9,f}円  {chg_c}{chg_s}{q['change']:>7,f} ({chg_s}{q['change_pct']}率){C_RESET}  高:{q['high']:,} 低:{q['low']:,}")

        # 保有ポジション
        print("-" * 72)
        print(f"{C_BOLD}[戦闘中ポジション ({len(self.positions)}/{MAX_POSITIONS})]{C_RESET}")
        if not self.positions:
            print("  現在エントリー待機中...")
        else:
            for code, pos in self.positions.items():
                curr_p = market_quotes.get(code, {}).get("price", pos["entry_price"])
                pnl = (curr_p - pos["entry_price"]) * pos["shares"]
                p_pct = round(((curr_p - pos["entry_price"]) / pos["entry_price"]) * 100, 2)
                p_col = C_GREEN if pnl >= 0 else C_RED
                p_sig = "+" if pnl >= 0 else ""
                dur = int(time.time() - pos["entry_time"])
                print(f"  ⚔️ {pos['name']} {pos['shares']}株  買値:{pos['entry_price']:,} -> 現在:{curr_p:,}  {p_col}{p_sig}{round(pnl):,}円 ({p_sig}{p_pct}%){C_RESET}  保有:{dur}秒")

        # 直近約定ログ
        print("-" * 72)
        print(f"{C_BOLD}[直近の約定ログ]{C_RESET}")
        if not self.history:
            print("  約定履歴なし")
        else:
            for rec in self.history[:4]:
                if "pnl" in rec:
                    col = C_GREEN if rec["pnl"] >= 0 else C_RED
                    sig = "+" if rec["pnl"] >= 0 else ""
                    print(f"  {rec['time']} {rec['action']} {rec['name']} {rec['shares']}株  {col}{sig}{rec['pnl']:,}円 ({sig}{rec['pnl_pct']}率){C_RESET} - {rec['reason']}")
                else:
                    print(f"  {rec['time']} {rec['action']} {rec['name']} {rec['shares']}株 @ {rec['entry_p']:,}円 - {rec['reason']}")
        print("=" * 72)
        print(f" {C_YELLOW}※ Ctrl+C で停止できます。3秒ごとに自動更新中...{C_RESET}")
        sys.stdout.flush()

if __name__ == "__main__":
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if len(sys.argv) > 1 and sys.argv[1] == "--webhook":
        if len(sys.argv) > 2:
            webhook = sys.argv[2]

    desk = ScalpingDesk(webhook_url=webhook)
    try:
        desk.run()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}監視Botを停止しました。{C_RESET}")
