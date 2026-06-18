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
    """yfinance를 이용해 당일 실시간 수치(현재가, 변동금액, 등락률)를 계산합니다."""
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
    """[후보군 없음] 야후 파이낸스 전체 시장에서 실시간 상위 급등주를 통째로 긁어옵니다."""
    try:
        if market_type == "morning":
            # 미국 전체 시장에서 당일 가장 거래량이 많고 급등한 탑 무버 실시간 트래킹
            screener = yf.Screener()
            # 야후 파이낸스 내장 미국 실시간 상승 상위 스크리너 호출
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
            # 한국 전체 시장 종목 중 당일 상위 상승 종목 긁어오기 (네이버/야후 인덱스 결합)
            # 한국 시장은 스크리너가 불안정할 수 있으므로 시총 상위 및 당일 활성 인덱스를 동적 풀링합니다.
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
                text += f"- {m['name']} [{m['price']:,.0f}원, 🔴 {m['amount']:+,0.0f}원 ({m['percent']:.2f}%)]\n"
            return text
    except Exception as e:
        print(f"⚠️ 실시간 급등주 스크리닝 실패: {e}")
        return "- 실시간 급등주 데이터를 불러오는 중 오류가 발생했습니다.\n"

def ask_gemini_for_recommendations(market_type):
    """[1단계] 제미나이가 웹 검색을 통해 '아무런 제한 없이' 유망 종목과 근거를 발굴합니다."""
    market_name = "미국 주식 시장" if market_type == "morning" else "대한민국 주식 시장"
    currency = "티커(예: NVDA, TSLA, AAPL 등)" if market_type == "morning" else "6자리 종목코드(예: 005930, 000660 등)"
    
    prompt = f"""
    너는 최고의 금융 분석 에이전트야. 실시간 웹 검색을 결합해서 오늘 자 기준으로 {market_name}에서 가장 유망한 추천 주식 3개를 너의 기준대로 자유롭게 선정해줘. 너의 종목 선정에는 아무런 제한이 없어.
    그리고 각 종목의 선정 이유와 구체적인 투자 근거를 전문적으로 서술해줘.
    
    단, 파이썬 코드가 수치를 뒤이어 결합할 수 있도록 각 종목의 타이틀 부분에 반드시 해당 종목의 {currency}를 정확히 포함해줘.
    양식 예시:
    ■ 종목명: 기업이름 (티커: TICKER)
    - 추천 근거: ...
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        print(f"Gemini 추천 로드 실패: {e}")
        return "추천 데이터를 가져오지 못했습니다."

def inject_yfinance_to_recommendations(gemini_recommendations, market_type):
    """[2단계] 제미나이가 자유롭게 뽑은 종목 본문에서 티커를 파싱해 실시간 수치를 동적으로 붙입니다."""
    # 글 속에서 알파벳 티커나 숫자 6자리 종목코드를 추출
    pattern = r'([A-Z]{2,5})' if market_type == "morning" else r'(\d{6})'
    found_tickers = list(set(re.findall(pattern, gemini_recommendations)))
    
    stock_fact_map = {}
    for ticker in found_tickers:
        full_ticker = ticker if market_type == "morning" else f"{ticker}.KS"
        info = get_realtime_stock_info(full_ticker)
        if not info and market_type != "morning": # 코스닥 체크 방어
            info = get_realtime_stock_info(f"{ticker}.KQ")
            
        if info:
            emoji = "🔴" if info['percent'] >= 0 else "🔵"
            if market_type == "morning":
                stock_fact_map[ticker] = f"[{info['price']:,.2f}달러, {emoji} {info['amount']:+.2f}달러 ({info['percent']:.2f}%)]"
            else:
                stock_fact_map[ticker] = f"[{info['price']:,.0f}원, {emoji} {info['amount']:+,0.0f}원 ({info['percent']:.2f}%)]"

    # 제미나이가 작성한 텍스트 라인 중 종목 타이틀(■ 포함된 줄) 옆에 yfinance 수치를 실시간 결합
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
    
    # 1. 지수 정보 수집
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
        base_info = f"코스피: {k_price:,.2f} ({k_diff:+.2f}, {(k_diff/kospi['Open'].iloc[-1])*100:+.2f}%), 코스닥: {kq_price:,.2f} ({kq_diff:+.2f}, {(kq_diff/kosdaq['Open'].iloc[-1])*100:+.2f}%)"
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 장 마감 종합 보고서"

    print("🚀 [1단계] 시장 전체 실시간 급등주 스크리닝 진행 중...")
    top_movers_section = get_pure_top_movers(market_type)

    print("🚀 [2단계] Gemini 모델에 추천 종목 및 자유 분석 요청 중...")
    raw_recommendations = ask_gemini_for_recommendations(market_type)
    
    print("🚀 [3단계] Gemini 추천 종목의 티커를 추출하여 yfinance 수치 주입 중...")
    final_recommendations_section = inject_yfinance_to_recommendations(raw_recommendations, market_type)

    # 최종 보고서 조립
    final_prompt = f"""
    너는 금융 분석가야. 아래 재료들을 깔끔하게 조립해서 최종 이메일 보고서 본문을 완성해줘.
    
    분석 기준 날짜: {date_str}
    [시장 지수 데이터]
    {base_info}
    
    [오늘의 실제 실시간 급등주 목록]
    {top_movers_section}
    
    [AI 분석 추천 주식 및 수치 결합본]
    {final_recommendations_section}
    
    [최종 지침]
    - 제공된 원본 수치를 변조하지 말고 그대로 리포트에 녹여줘.
    - 1번 항목에는 너의 실시간 웹 검색을 결합하여 '오늘 하루 글로벌 주요 시황 이슈 3가지'를 추가해줘.
    - 2번 항목에는 시장의 전체적인 흐름 요약을 적어줘.
    - 3번 항목에는 제공된 [오늘의 실제 실시간 급등주 목록]을 그대로 가독성 좋게 배치해줘.
    - 4번 항목에는 제공된 [AI 분석 추천 주식 및 수치 결합본]을 활용해 종목명, 정확한 수치, 그리고 추천 근거(이유)를 전문성 있게 배치해줘.
    """
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=final_prompt)
        return subject, response.text
    except Exception as e:
        return subject, f"최종 보고서 빌드 실패: {e}"

def send_email(subject, body):
    global GMAIL_USER, GMAIL_APP_PASSWORD, RECEIVER_EMAIL
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECEIVER_EMAIL: return
    try:
        targets = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
        msg = EmailMessage()
        msg.set_content(body, charset='utf-8') 
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = ", ".join(targets)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("🎉 이메일 발송 최종 성공!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    subject, report_text = generate_report()
    send_email(subject, report_text)
