import os
import smtplib
import time
from email.message import EmailMessage
from datetime import datetime
import pytz
import yfinance as yf
from google import genai

# 1. 환경 변수로부터 비밀 정보 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

if not GEMINI_API_KEY:
    raise ValueError("GitHub Secrets에 GEMINI_API_KEY가 등록되지 않았거나 불러올 수 없습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

def get_realtime_stock_info(ticker_symbol):
    """
    특정 종목의 '전일 마감 종가' 대비 '오늘 실시간 현재가'의 정확한 당일 등락률을 계산합니다.
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        # 전일 종가와 오늘 현재가를 대조하기 위해 최근 2일 데이터를 가져옵니다.
        hist = stock.history(period="2d")
        
        if len(hist) < 2:
            # 장 시작 직후라 데이터가 부족하면 당일 시가(Open) 대비 현재가(Close)로 방어 계산
            hist = stock.history(period="1d")
            prev_close = hist['Open'].iloc[-1]      
            current_price = hist['Close'].iloc[-1]  
        else:
            prev_close = hist['Close'].iloc[-2]     # 1일 전 최종 마감 가격
            current_price = hist['Close'].iloc[-1]  # 현재 움직이는 실시간 가격
            
        chg_percent = ((current_price - prev_close) / prev_close) * 100
        return {"price": current_price, "chg": chg_percent}
    except Exception as e:
        print(f"⚠️ {ticker_symbol} 실시간 데이터 수집 실패: {e}")
        return None

def get_market_and_top_movers(market_type):
    """지수 데이터와 함께 실시간 개별 종목의 정확한 당일 변동 수치를 주입용 데이터로 가공합니다."""
    try:
        if market_type == "morning":
            # 1. 미국 주요 시장 지수 데이터 추출
            nasdaq = yf.Ticker("^IXIC").history(period="1d")
            sp500 = yf.Ticker("^GSPC").history(period="1d")
            n_price, s_price = nasdaq['Close'].iloc[-1], sp500['Close'].iloc[-1]
            n_chg = ((n_price - nasdaq['Open'].iloc[-1]) / nasdaq['Open'].iloc[-1]) * 100
            s_chg = ((s_price - sp500['Open'].iloc[-1]) / sp500['Open'].iloc[-1]) * 100
            
            base_info = f"나스닥: {n_price:,.2f} ({n_chg:+.2f}%), S&P 500: {s_price:,.2f} ({s_chg:+.2f}%)"
            
            # 2. 미국 실시간 관심 종목 데이터 수집 (당일 팩트 전달용)
            watchlist = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL"]
            movers_list = []
            for ticker in watchlist:
                info = get_realtime_stock_info(ticker)
                if info:
                    movers_list.append({"ticker": ticker, "price": info["price"], "chg": info["chg"]})
            
            # 오늘 가장 많이 오른(혹은 덜 떨어진) 순으로 정렬
            movers_list.sort(key=lambda x: x["chg"], reverse=True)
            
            fact_movers = " [미국 시장 실시간 당일 종목 팩트 데이터]\n"
            for m in movers_list:
                fact_movers += f"- {m['ticker']}: 실시간 현재가 {m['price']:,.2f}달러, 전일대비 등락률 {m['chg']:+.2f}%\n"
                
            return base_info, fact_movers

        else:
            # 1. 한국 주요 시장 지수 데이터 추출
            kospi = yf.Ticker("^KS11").history(period="1d")
            kosdaq = yf.Ticker("^KQ11").history(period="1d")
            k_price, kq_price = kospi['Close'].iloc[-1], kosdaq['Close'].iloc[-1]
            k_chg = ((k_price - kospi['Open'].iloc[-1]) / kospi['Open'].iloc[-1]) * 100
            kq_chg = ((kq_price - kosdaq['Open'].iloc[-1]) / kosdaq['Open'].iloc[-1]) * 100
            
            base_info = f"코스피: {k_price:,.2f} ({k_chg:+.2f}%), 코스닥: {kq_price:,.2f} ({kq_chg:+.2f}%)"
            
            # 2. 한국 실시간 주요 종목 데이터 수집
            watchlist = ["005930.KS", "000660.KS", "005380.KS", "247540.KQ", "086520.KQ"]
            names = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로"}
            movers_list = []
            for ticker in watchlist:
                info = get_realtime_stock_info(ticker)
                if info:
                    movers_list.append({"name": names[ticker], "price": info["price"], "chg": info["chg"]})
            
            movers_list.sort(key=lambda x: x["chg"], reverse=True)
            
            fact_movers = " [한국 시장 실시간 당일 종목 팩트 데이터]\n"
            for m in movers_list:
                fact_movers += f"- {m['name']}: 실시간 현재가 {m['price']:,.0f}원, 전일대비 등락률 {m['chg']:+.2f}%\n"
                
            return base_info, fact_movers
            
    except Exception as e:
        return f"데이터 수집 실패: {str(e)}", ""

def generate_report():
    tz_seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_seoul)
    hour = now.hour
    date_str = now.strftime('%Y년 %m월 %d일')

    if hour < 12:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ☀️ 아침 미국 증시 리포트 생성 시작...")
        market_info, fact_data = get_market_and_top_movers("morning")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 아침 미국 증시 및 글로벌 이슈 보고서"
        
        prompt = f"""
        너는 최고의 금융 분석 송방원 에이전트야. 제공된 지수 지표({market_info})와 아래의 정확한 [개별 종목 실시간 당일 데이터]를 바탕으로, 너의 최신 웹 검색 지식을 결합해서 아침 리포트를 작성해줘.
        
        [🚨 중요: 당일 수치 데이터 제공 - 절대 변조 금지]
        {fact_data}
        
        [🚨 가장 중요한 초강력 절대 규칙]
        - 절대로 위에 적힌 주식들의 실시간 가격이나 당일 등락률 퍼센트 수치를 다른 숫자로 지어내거나 변조하지 마. 100% 똑같이 받아적어야 해.
        - 보고서에 등장하는 모든 수치 뒤에는 조건에 맞는 색상 원형 이모지를 강제 적용해줘.
        - 당일 변동이 상승(+)이거나 동일하면 무조건 '0,000.00 달러 (🔴 +0.00%)' 형태로 표기해줘.
        - 당일 변동이 하락(-)이면 무조건 '0,000.00 달러 (🔵 -0.00%)' 형태로 표기해줘.
        - 3번(급등 종목)과 4번(추천/주목 종목)에 들어갈 주식은 위 데이터 목록에서 선정하며, 이름 옆에 정확한 가격과 등락률을 '종목명(티커) [000.00달러, 🔴 +5.40%]' 혹은 '종목명(티커) [000.00달러, 🔵 -1.20%]' 양식으로 100% 명시해줘.

        [작성 내용 - 반드시 4개 항목 모두 작성]
        분석 기준 날짜: {date_str}
        1. 밤 사이에 있었던 글로벌 주요 이슈 3가지 (핵심 내용 정리)
        2. 새벽 마감된 미국 시장의 전체적인 흐름과 변동 요인 분석 (지수 언급 시 🔴/🔵 필수 적용)
        3. 제공된 데이터 중 당일 등락률 상위 종목을 기반으로 급등 종목을 매칭하여 구체적인 상승 이유 작성.
        4. 제공된 데이터 중 향후 흐름이 중요하게 기대되는 종목을 선정하여 합리적인 추천 이유 제시.
        """
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌙 오후 장 마감 리포트 생성 시작...")
        market_info, fact_data = get_market_and_top_movers("evening")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 장 마감 한국 증시 종합 보고서"
        
        prompt = f"""
        너는 최고의 금융 분석 에이전트야. 제공된 지수 지표({market_info})와 아래의 정확한 [개별 종목 실시간 당일 데이터]를 바탕으로, 너의 최신 웹 검색 지식을 결합해서 마감 리포트를 작성해줘.
        
        [🚨 중요: 당일 수치 데이터 제공 - 절대 변조 금지]
        {fact_data}
        
        [🚨 가장 중요한 초강력 절대 규칙]
        - 절대로 위에 적힌 주식들의 실시간 가격이나 당일 등락률 퍼센트 수치를 다른 숫자로 지어내거나 변조하지 마. 100% 똑같이 받아적어야 해.
        - 보고서에 등장하는 모든 수치 뒤에는 조건에 맞는 색상 원형 이모지를 강제 적용해줘.
        - 당일 변동이 상승(+)이거나 동일하면 무조건 '0,000원 (🔴 +0.00%)' 형태로 표기해줘.
        - 당일 변동이 하락(-)이면 무조건 '0,000원 (🔵 -0.00%)' 형태로 표기해줘.
        - 3번(급등 종목)과 4번(추천/주목 종목)에 들어갈 주식은 위 데이터 목록에서 선정하며, 이름 바로 옆에 가격과 등락률을 '종목명 [00,000원, 🔴 +5.40%]' 혹은 '종목명 [00,000원, 🔵 -1.20%]' 양식으로 100% 명시해줘.

        [작성 내용 - 반드시 4개 항목 모두 작성]
        분석 기준 날짜: {date_str}
        1. 오늘 대한민국 주식시장 관련 주요 이슈 3가지
        2. 오늘 한국 시장의 전체적인 흐름과 변동 요인 분석 (지수 언급 시 🔴/🔵 필수 적용)
        3. 제공된 데이터 중 당일 등락률 상위 종목을 기반으로 급등 종목을 매칭하여 명확한 상승 이유 작성.
        4. 제공된 데이터 중 내일 장에서 주목할 만한 종목을 선정하여 구체적인 추천 이유 제시.
        """

    max_retries = 5
    delays = [5, 15, 30, 60, 0] 
    
    for attempt in range(max_retries):
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Gemini AI 모델에 리포트 요청 중... (시도 {attempt + 1}/{max_retries})")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Gemini AI 리포트 생성 완료!")
            return subject, response.text
        except Exception as e:
            wait_time = delays[attempt]
            print(f"❌ Gemini 에러 발생: {str(e)}")
            if attempt < max_retries - 1:
                print(f"➡️ {wait_time}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                print("❌ 모든 재시도 실패. 프로그램 종료.")
                raise e
                
def send_email(subject, body):
    global GMAIL_USER, GMAIL_APP_PASSWORD, RECEIVER_EMAIL
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 이메일 발송 준비 및 Secrets 데이터 검증 중...")
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECEIVER_EMAIL:
        print("⚠️ [경고] 이메일 필수 설정 정보가 누락되어 발송을 취소합니다.")
        return

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
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 이메일 발송 최종 성공!")
    except Exception as e:
        print(f"❌ [이메일 에러] 발송 실패: {e}")

if __name__ == "__main__":
    print(f"================ [주식 에이전트 시스템 시작] ================")
    try:
        subject, report_text = generate_report()
        send_email(subject, report_text)
    except Exception as main_err:
        print(f"❌ 메인 시스템 실행 실패 원인: {main_err}")
    print("================ [주식 에이전트 시스템 종료] ================")
