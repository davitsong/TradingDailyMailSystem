import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz
import yfinance as yf
# 최신 구글 제미나이 라이브러리 불러오기
from google import genai
from email.header import Header

# 1. 환경 변수로부터 비밀 정보 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

if not GEMINI_API_KEY:
    raise ValueError("GitHub Secrets에 GEMINI_API_KEY가 등록되지 않았거나 불러올 수 없습니다.")

# 최신 방식으로 클라이언트 초기화
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_data(market_type):
    try:
        if market_type == "morning":
            nasdaq = yf.Ticker("^IXIC").history(period="1d")
            sp500 = yf.Ticker("^GSPC").history(period="1d")
            n_chg = ((nasdaq['Close'].iloc[-1] - nasdaq['Open'].iloc[-1]) / nasdaq['Open'].iloc[-1]) * 100
            s_chg = ((sp500['Close'].iloc[-1] - sp500['Open'].iloc[-1]) / sp500['Open'].iloc[-1]) * 100
            return f"[미국 증시 기본 데이터] 나스닥 등락률: {n_chg:.2f}%, S&P 500 등락률: {s_chg:.2f}%"
        else:
            kospi = yf.Ticker("^KS11").history(period="1d")
            kosdaq = yf.Ticker("^KQ11").history(period="1d")
            k_chg = ((kospi['Close'].iloc[-1] - kospi['Open'].iloc[-1]) / kospi['Open'].iloc[-1]) * 100
            kq_chg = ((kosdaq['Close'].iloc[-1] - kosdaq['Open'].iloc[-1]) / kosdaq['Open'].iloc[-1]) * 100
            return f"[한국 증시 기본 데이터] 코스피 등락률: {k_chg:.2f}%, 코스닥 등락률: {kq_chg:.2f}%"
    except Exception as e:
        return f"기본 지수 데이터 수집 실패(AI가 자체 지식으로 분석 필요): {str(e)}"

def generate_report():
    tz_seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_seoul)
    hour = now.hour

    if hour < 12:
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
    else:
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

    # 최신 규격 모델 및 호출 방식 적용
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return subject, response.text

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECEIVER_EMAIL:
        print("이메일 설정 정보(Secrets)가 누락되어 발송을 건너뜁니다.")
        return

    try:
        targets = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
        
        # [⚠️ 핵심 수정] 이메일 제목과 본문 모두 UTF-8 한글 설정 적용
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8') # 제목이 한글이어도 깨지지 않게 보정
        msg['From'] = GMAIL_USER
        msg['To'] = ", ".join(targets)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, targets, msg.as_string())
        print(f"이메일 발송 성공! (수신처: {targets})")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    subject, report_text = generate_report()
    send_email(subject, report_text)
