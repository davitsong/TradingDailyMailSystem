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
    """yfinance를 이용해 전일 마감 종가 대비 오늘 실시간 현재가의 정확한 수치를 계산합니다."""
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
        chg_percent = (chg_amount / prev_close) * 100 if prev_close != 0 else 0
        
        return {"price": current_price, "amount": chg_amount, "percent": chg_percent}
    except:
        return None

def get_pure_top_movers(market_type):
    """각 시장별로 30개의 핵심 주도주 백업 풀을 구축하여 안정성을 극대화한 스크리닝 엔진"""
    try:
        if market_type == "morning":
            # 🇺🇸 미국 시장: AI/빅테크, 반도체, 시가총액 최상위 및 고유동성 핵심 30대 주도주 백업 풀
            us_backup = [
                "TSLA", "NVDA", "AAPL", "AMD", "AMZN", "MSFT", "META", "GOOGL", 
                "AVGO", "NFLX", "PLTR", "SMCI", "MU", "INTC", "QCOM", "ARM", 
                "COIN", "MARA", "COSM", "NKE", "BRK-B", "LLY", "UNH", "JPM",
                "V", "XOM", "MA", "COST", "HD", "PG"
            ]
            results = []
            
            try:
                screener = yf.Screener()
                scr_data = screener.get_screeners('day_gainers', count=10)
                for quote in scr_data['day_gainers']['quotes']:
                    t = quote['symbol']
                    info = get_realtime_stock_info(t)
                    if info:
                        results.append({"name": t, "ticker": t, **info})
            except Exception as e:
                print(f"⚠️ 미국 스크리너 연동 지연, 30대 백업 엔진 가동: {e}")
                
            if len(results) < 3:
                for t in us_backup:
                    if not any(r['ticker'] == t for r in results):
                        info = get_realtime_stock_info(t)
                        if info: results.append({"name": t, "ticker": t, **info})
                        
            results.sort(key=lambda x: x["percent"], reverse=True)
            text = ""
            for m in results[:3]:
                text += f"- {m['name']} [{m['price']:,.2f}달러, 🔴 {m['amount']:+.2f}달러 ({m['percent']:.2f}%)]\n"
            return text
            
        else:
            # 🇰🇷 대한민국 코스피 시장: 주요 섹터별 시가총액 최상위 30대 대장주 백업 풀
            print("🔍 코스피 전체 시장 동적 탐색 시도 중...")
            results = []
            
            try:
                search_results = yf.Search(".KS", max_results=50).quotes
                for q in search_results:
                    t = q['symbol']
                    if t.endswith(".KS") and not t.startswith("^"):
                        info = get_realtime_stock_info(t)
                        if info and info['percent'] > 0:
                            results.append({"name": q.get('shortname', t), "ticker": t, **info})
            except Exception as e:
                print(f"⚠️ 코스피 전체 동적 검색 지연, 30대 백업 엔진 가동: {e}")

            if len(results) < 3:
                print("🚨 코스피 초유동성 30대 대장주 엔진으로 전환하여 실시간 최고 급등주를 선별합니다.")
                core_kospi = {
                    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", 
                    "000270.KS": "기아", "005490.KS": "POSCO홀딩스", "035420.KS": "NAVER", 
                    "051910.KS": "LG화학", "068270.KS": "셀트리온", "373220.KS": "LG에너지솔루션",
                    "042700.KS": "한미반도체", "000100.KS": "유한양행", "011200.KS": "HMM",
                    "010140.KS": "삼성중공업", "028260.KS": "삼성물산", "034220.KS": "LG디스플레이",
                    "000810.KS": "삼성화재", "012330.KS": "현대모비스", "015760.KS": "한국전력",
                    "017670.KS": "SK텔레콤", "323410.KS": "카카오뱅크",
                    "055550.KS": "신한지주", "105560.KS": "KB금융", "003670.KS": "포스코푸처엠",
                    "012450.KS": "한화에어로스페이스", "271560.KS": "오리온", "032830.KS": "삼성생명",
                    "000720.KS": "현대건설", "009150.KS": "삼성전기", "033780.KS": "KT&G", "004020.KS": "현대제철"
                }
                for ticker, name in core_kospi.items():
                    if not any(r['ticker'] == ticker for r in results):
                        info = get_realtime_stock_info(ticker)
                        if info and info['percent'] > 0:
                            results.append({"name": name, "ticker": ticker, **info})

            results.sort(key=lambda x: x["percent"], reverse=True)
            
            if not results:
                return "- 오늘 상승 마감한 코스피 주요 종목 데이터가 없습니다.\n"
                
            text = ""
            for m in results[:3]:
                text += f"- {m['name']} ({m['ticker'].replace('.KS','')}) [{m['price']:,.0f}원, 🔴 {int(m['amount']):+,}원 ({m['percent']:.2f}%)]\n"
            return text
            
    except Exception as e:
        print(f"⚠️ 실시간 급등주 스크리닝 치명적 실패: {e}")
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
    market_name = "미국 주식 시장" if market_type == "morning" else "대한민국 코스피(KOSPI) 시장"
    currency = "티커(예: NVDA, TSLA 등)" if market_type == "morning" else "6자리 코스피 종목코드(예: 005930, 000660 등)"
    
    prompt = f"""
    너는 최고의 금융 분석 에이전트야. 실시간 웹 검색을 결합해서 오늘 자 기준으로 {market_name}에서 가장 유망한 추천 주식 3개를 너의 기준대로 자유롭게 선정해줘. 너의 종목 선정에는 아무런 제한이 없어.
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
    m_name = "미국 증시" if market_type == "morning" else "코스피 시장"
    
    if market_type == "morning":
        nasdaq = yf.Ticker("^IXIC").history(period="1d")
        sp500 = yf.Ticker("^GSPC").history(period="1d")
        n_price, s_price = nasdaq['Close'].iloc[-1], sp500['Close'].iloc[-1]
        n_diff, s_diff = n_price - nasdaq['Open'].iloc[-1], s_price - sp500['Open'].iloc[-1]
        
        n_emoji = "🔴" if n_diff >= 0 else "🔵"
        s_emoji = "🔴" if s_diff >= 0 else "🔵"
        
        base_info = f"나스닥: {n_price:,.2f} ({n_emoji} {n_diff:+.2f}, {(n_diff/nasdaq['Open'].iloc[-1])*100:+.2f}%), S&P 500: {s_price:,.2f} ({s_emoji} {s_diff:+.2f}, {(s_diff/sp500['Open'].iloc[-1])*100:+.2f}%)"
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 아침 미국 증시 리포트"
    else:
        kospi = yf.Ticker("^KS11").history(period="1d")
        kosdaq = yf.Ticker("^KQ11").history(period="1d")
        k_price, kq_price = kospi['Close'].iloc[-1], kosdaq['Close'].iloc[-1]
        k_diff, kq_diff = k_price - kospi['Open'].iloc[-1], kq_price - kosdaq['Open'].iloc[-1]
        
        k_emoji = "🔴" if k_diff >= 0 else "🔵"
        kq_emoji = "🔴" if kq_diff >= 0 else "🔵"
        
        base_info = f"코스피: {k_price:,.2f} ({k_emoji} {k_diff:+.2f}, {(k_diff/kospi['Open'].iloc[-1])*100:+.2f}%), 코스닥: {kq_price:,.2f} ({kq_emoji} {kq_diff:+.2f}, {(kq_diff/kosdaq['Open'].iloc[-1])*100:+.2f}%)"
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 장 마감 코스피 종합 보고서"

    print(f"🚀 [1단계] {m_name} 전체 실시간 당일 최고 급등주 동적 검색 중...")
    top_movers_section = get_pure_top_movers(market_type)

    print(f"🚀 [2단계] Gemini 모델에 유동적 {m_name} 추천 종목 및 분석 근거 요청 중...")
    raw_recommendations = ask_gemini_for_recommendations(market_type)
    
    print("🚀 [3단계] Gemini 추천 종목의 티커를 추출하여 yfinance 수치 주입 중...")
    final_recommendations_section = inject_yfinance_to_recommendations(raw_recommendations, market_type)

    final_prompt = f"""
    너는 금융 분석가야. 아래 재료들을 깔끔하게 조립해서 최종 이메일 보고서 본문을 완성해줘.
    
    분석 기준 날짜: {date_str}
    [시장 지수 데이터]
    {base_info}
    
    [오늘의 {m_name} 실제 실시간 급등주 목록]
    {top_movers_section}
    
    [AI 분석 추천 주식 및 수치 결합본]
    {final_recommendations_section}
    
    [최종 지침]
    - 제공된 원본 수치와 지수의 빨강(🔴)/파랑(🔵) 양식을 절대 변조하지 말고 그대로 리포트에 녹여줘.
    - 1번 항목에는 너의 실시간 웹 검색을 결합하여 '오늘 하루 글로벌 주요 시황 이슈 3가지'를 추가해줘.
    - 2번 항목에는 {m_name} 중심의 전체적인 흐름 요약을 적어줘. 지수 데이터 수치는 제공된 것을 그대로 적어줘.
    - 3번 항목에는 제공된 [오늘의 {m_name} 실제 실시간 급등주 목록]을 원본 양식 그대로 가독성 좋게 배치하고 상세 분석을 적어줘.
    - 4번 항목에는 제공된 [AI 분석 추천 주식 및 수치 결합본]을 활용해 추천 종목명, 정확한 수치, 그리고 추천 근거(이유)를 전문성 있게 배치해줘.
    """
    
    try:
        return subject, ask_gemini_with_retry(final_prompt)
    except Exception as e:
        return subject, f"최종 보고서 빌드 실패: {e}"

def send_email(subject, body):
    global GMAIL_USER, GMAIL_APP_PASSWORD, RECEIVER_EMAIL
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECEIVER_EMAIL: return
    try:
        GMAIL_USER = GMAIL_USER.replace('\xa0', ' ').strip()
        GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD.replace('\xa0', ' ').strip()
        RECEIVER_EMAIL = RECEIVER_EMAIL.replace('\xa0', ' ').strip()

        targets = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
        
        msg = EmailMessage()
        msg.set_content(body, charset='utf-8') 
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = ", ".join(targets)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("🎉 30대 대장주 안전 백업 시스템 적용 메일 발송 최종 성공!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

if __name__ == "__main__":
    subject, report_text = generate_report()
    send_email(subject, report_text)
