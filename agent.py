import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz
import yfinance as yf
import google.generativeai as genai

# 1. 환경 변수로부터 비밀 정보 로드 (GitHub Secrets와 연동됨)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# AI 설정
genai.configure(api_key=GEMINI_API_KEY)

def get_stock_data(market_type):
    """간단한 지수 데이터를 긁어와 AI 프롬프트에 힌트로 제공"""
    try:
        if market_type == "morning":
            # 미국 나스닥, S&P500
            nasdaq = yf.Ticker("^IXIC").history(period="1d")
            sp500 = yf.Ticker("^GSPC").history(period="1d")
            n_chg = ((nasdaq['Close'].iloc[-1] - nasdaq['Open'].iloc[-1]) / nasdaq['Open'].iloc[-1]) * 100
            s_chg = ((sp500['Close'].iloc[-1] - sp500['Open'].iloc[-1]) / sp500['Open'].iloc[-1]) * 100
            return f"[미국 증시 기본 데이터] 나스닥 등락률: {n_chg:.2f}%, S&P 500 등락률: {s_chg:.2f}%"
        else:
            # 한국 코스피, 코스닥
            kospi = yf.Ticker("^KS11").history(period="1d")
            kosdaq = yf.Ticker("^KQ11").history(period="1d")
            k_chg = ((kospi['Close'].iloc[-1] - kospi['Open'].iloc[-1]) / kospi['Open'].iloc[-1]) * 100
            kq_chg = ((kosdaq['Close'].iloc[-1] - kosdaq['Open'].iloc[-1]) / kosdaq['Open'].iloc[-1]) * 100
            return f"[한국 증시 기본 데이터] 코스피 등락률: {k_chg:.2f}%, 코스닥 등락률: {kq_chg:.2f}%"
    except Exception as e:
        return f"기본 지수 데이터 수집 실패(AI가 자체 지식으로 분석 필요): {str(e)}"

def generate_report():
    # 한국 시간 기준 현재 시각 확인
    tz_seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_seoul)
    hour = now.hour

    model = genai.GenerativeModel('gemini-1.5-flash') # 속도가 빠르고 텍스트 분석에 뛰어난 모델

    if hour < 12:  # 아침 6시 타임
        print("아침 미국 증시 리포트 생성 중...")
        market_info = get_stock_data("morning")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 아침 미국 증시 및 글로벌 이슈 보고서"
        prompt = f"""
        너는 최고의 금융 분석 에이전트야. 제공된 데이터({market_info})와 너의 최신 웹 검색/지식을 활용해서 아래 조건에 맞는 아침 리포트를 작성해줘.
        
        [작성 내용]
        1. 밤 사이에 있었던 글로벌 주요 이슈 3가지 (핵심 내용 정리)
        2. 새벽 마감된 미국 시장의 변동 및 그렇게 변동한 원인을 명확한 근거(금리, 지표, 이벤트 등)를 들어서 3가지 제시
        3. 오늘 밤 주목해야 할 미국 주식 3개 추천 및 구체적인 이유와 근거 제시
        
        격식 있고 전문적인 언어로 작성하고, 가독성이 좋게 줄바꿈과 기호(■, -, 💡)를 적절히 섞어줘.
        """
    else:  # 오후 장 마감 타임
        print("오후 장 마감 리포트 생성 중...")
        market_info = get_stock_data("evening")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 장 마감 한국 증시 종합 보고서"
        prompt = f"""
        너는 최고의 금융 분석 에이전트야. 제공된 데이터({market_info})와 너의 최신 웹 검색/지식을 활용해서 아래 조건에 맞는 마감 리포트를 작성해줘.
        
        [작성 내용]
        1. 오늘 대한민국 주식시장 관련 주요 이슈 3가지
        2. 오늘 한국 시장의 전체적인 흐름과 변동 요인 분석
        3. 오늘 코스피/코스닥 시장에서 많이 오른 급등 종목 3가지와 그 종목이 상승한 명확한 이유와 근거
        4. 내일 장에서 주목할 만한 한국 주식 3개 추천 및 구체적인 이유와 근거 제시
        
        격식 있고 전문적인 언어로 작성하고, 가독성이 좋게 줄바꿈과 기호(■, -, 💡)를 적절히 섞어줘.
        """

    response = model.generate_content(prompt)
    return subject, response.text

def send_email(subject, body):
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = RECEIVER_EMAIL

        # Gmail SMTP 서버 연결
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [RECEIVER_EMAIL], msg.as_string())
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    subject, report_text = generate_report()
    send_email(subject, report_text)
