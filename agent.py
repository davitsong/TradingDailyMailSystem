import os
import smtplib
import time
import re
from email.message import EmailMessage
from datetime import datetime
import pytz
import yfinance as yf
from google import genai

# 환경 변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 등록되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

def get_realtime_stock_info(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="2d")
        if len(hist) < 2:
            hist = stock.history(period="1d")
            prev_close = hist['Open'].iloc[-1]      
            current_price = hist['Close'].iloc[-1]  
        else:
            prev_close = hist['Close'].iloc[-2]     
            current_price = hist['Close'].iloc[-1]  
            
        chg_amount = current_price - prev_close     
        chg_percent = (chg_amount / prev_close) * 100 
        
        return {"price": current_price, "amount": chg_amount, "percent": chg_percent}
    except:
        return None

def get_pure_top_movers(market_type):
    try:
        if market_type == "morning":
            screener = yf.Screener()
            scr_data = screener.get_screeners('day_gainers', count=3)
            
            text = ""
            for quote in scr_data['day_gainers']['quotes']:
                t = quote['symbol']
                price = quote['regularMarketPrice']
                chg_amount = quote['regularMarketChange']
                chg_percent = quote['regularMarketChangePercent']
                text += f"- {t} [{price:,.2f}달러, 🔴 {chg_amount:+.2f}달러 ({chg_percent:+.2f}%)]\n"
            return text
        else:
            kr_trending = yf.Search("KRX", max_results=20).quotes
            results = []
            for q in kr_trending:
                t = q['symbol']
                if t.endswith(".KS") or t.endswith(".KQ"):
                    info = get_realtime_stock_info(t)
                    if info and info['percent'] > 0:
                        results.append({"name": q.get('shortname', t), **info})
            
            results.sort(key=lambda x: x["percent"], reverse=True)
            text = ""
            for m in results[:3]:
                # ⭕ 완벽 교정: 마침표 하나(,+0f)로 변경하여 콤마 표기 보장
                text += f"- {m['name']} [{m['price']:,.0f}원, 🔴 {int(m['amount']):+,}원 ({m['percent']:.2f}%)]\n"
            return text
    except Exception as e:
        print(f"⚠️ 실시간 급등주 스크리닝 실패: {e}")
        return "- 실시간 급등주 데이터를 불러오는 중 오류가 발생했습니다.\n"

def ask_gemini_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ 구글 AI 서버 혼잡(503). {5 * (attempt + 1)}초 후 재시도합니다...")
                time.sleep(5 * (attempt + 1))
            else:
                raise e

def ask_gemini_for_recommendations(market_type):
    market_name = "미국 주식 시장" if market_type == "morning" else "대한민국 주식 시장"
    currency = "티커(예: NVDA, TSLA 등)" if market_type == "morning" else "6자리 종목코드(예: 005930, 000660 등)"
    
    prompt = f"""
    너는 최고의 금융 분석 에이전트야. 실시간 웹 검색을 결합해서 오늘 자 기준으로 {market_name}에서 가장 유망한 추천 주식 3개를 너의 기준대로 자유롭게 선정해줘.
    그리고 각 종목의 선정 이유와 구체적인 투자 근거를 전문적으로 서술해줘.
    
    단, 파이썬 코드가 수치를 뒤이어 결합할 수 있도록 각 종목의 타이틀 부분에 반드시 해당 종목의 {currency}를 정확히 포함해줘.
    양식 예시:
    ■ 종목명: 기업이름 (티커: TICKER)
    - 추천 근거: ...
    """
    try:
        return ask_gemini_with_retry(prompt)
    except Exception as e:
        print(f"Gemini 추천 로드 실패: {e}")
        return "추천 데이터를 가져오지 못했습니다."

def inject_yfinance_to_recommendations(gemini_recommendations, market_type):
    pattern = r'([A-Z]{2,5})' if market_type == "morning" else r'(\d{6})'
    found_tickers = list(set(re.findall(pattern, gemini_recommendations)))
    
    stock_fact_map = {}
    for ticker in found_tickers:
        full_ticker = ticker if market_type == "morning" else f"{ticker}.KS"
        info = get_realtime_stock_info(full_ticker)
        if not info and market_type != "morning": 
            info = get_realtime_stock_info(f"{ticker}.KQ")
            
        if info:
            emoji = "🔴" if info['percent'] >= 0 else "🔵"
            if market_type == "morning":
                stock_fact_map[ticker] = f"[{info['price']:,.2f}달러, {emoji} {info['amount']:+.2f}달러 ({info['percent']:.2f}%)]"
            else:
                # ⭕ 완벽 교정: 안전하게 정수형 처리 후 콤마(,) 포맷 주입
                stock_fact_map[ticker] = f"[{info['price']:,.0f}원, {emoji} {int(info['amount']):+,}원 ({info['percent']:.2f}%)]"

    lines = gemini_recommendations.split('\n')
    for i, line in enumerate(lines):
        for ticker, fact_str in stock_fact_map.items():
            if ticker in line and fact_str not in line and "■" in line:
                lines[i] = f"{line} {fact_str}"
                break
                
    return '\n'.join(lines)

def generate_report():
    tz_seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_seoul)
    hour = now.hour
    date_str = now.strftime('%Y년 %m월 %d일')

    market_type = "morning" if hour < 12 else "evening"
    
    if market_type == "morning":
        nasdaq = yf.Ticker("^IXIC").history(period="1d")
        sp500 = yf.Ticker("^GSPC").history(period="1d")
        n_price, s_price = nasdaq['Close'].iloc[-1], sp500['Close'].iloc[-1]
        n_diff, s_diff = n_price - nasdaq['Open'].iloc[-1], s_price - sp500['Open'].iloc[-1]
        base_info = f"나스닥: {n_price:,.2f} ({n_diff:+.2f}, {(n_diff/nasdaq['Open'].iloc[-1])*100:+.2f}%), S&P 500: {s_price:,.2f} ({s_diff:+.2f}, {(s_diff/sp500['Open'].iloc[-1])*100:+.2f}%)"
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 아침 미국 증시 리포트"
    else:
        kospi = yf.Ticker("^KS11").history(period="1d")
        kosdaq = yf.Ticker("^KQ11").history(period="1d")
        k_price, kq_price = kospi['Close'].iloc[-1], kosdaq['Close'].iloc[-1]
        k_diff, kq_diff = k_price - kospi['Open'].iloc[-1], kq_price - kosdaq['Open'].iloc[-1]
        base_info =
