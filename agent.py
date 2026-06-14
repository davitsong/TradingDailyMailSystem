import os
import smtplib
import time  # 🔴 재시도 대기 시간을 쓰기 위해 반드시 필요합니다!
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

def get_stock_data(market_type):
    try:
        if market_type == "morning":
            nasdaq = yf.Ticker("^IXIC").history(period="1d")
            sp500 = yf.Ticker("^GSPC").history(period="1d")
            n_chg = ((nasdaq['Close'].iloc[-1] - nasdaq['Open'].iloc[-1]) / nasdaq['Open'].iloc[-1]) * 100
            s_chg = ((sp500['Close'].iloc[-1] - sp500['Open'].iloc[-1]) / sp500['Open'].iloc[-1]) * 100
            
            # 야후파이낸스 기초 데이터부터 이모지 적용
            n_emoji = "🔴 +" if n_chg >= 0 else "🔵 "
            s_emoji = "🔴 +" if s_chg >= 0 else "🔵 "
            return f"[미국 증시 기본 데이터] 나스닥 등락률: {n_emoji}{n_chg:.2f}%, S&P 500 등락률: {s_emoji}{s_chg:.2f}%"
        else:
            kospi = yf.Ticker("^KS11").history(period="1d")
            kosdaq = yf.Ticker("^KQ11").history(period="1d")
            k_chg = ((kospi['Close'].iloc[-1] - kospi['Open'].iloc[-1]) / kospi['Open'].iloc[-1]) * 100
            kq_chg = ((kosdaq['Close'].iloc[-1] - kosdaq['Open'].iloc[-1]) / kosdaq['Open'].iloc[-1]) * 100
            
            # 야후파이낸스 기초 데이터부터 이모지 적용
            k_emoji = "🔴 +" if k_chg >= 0 else "🔵 "
            kq_emoji = "🔴 +" if kq_chg >= 0 else "🔵 "
            return f"[한국 증시 기본 데이터] 코스피 등락률: {k_emoji}{k_chg:.2f}%, 코스닥 등락률: {kq_emoji}{kq_chg:.2f}%"
    except Exception as e:
        return f"기본 지수 데이터 수집 실패(AI가 자체 지식으로 분석 필요): {str(e)}"

def generate_report():
    tz_seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_seoul)
    hour = now.hour
    
    date_str = now.strftime('%Y년 %m월 %d일')

    if hour < 12:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ☀️ 아침 미국 증시 리포트 생성 시작...")
        market_info = get_stock_data("morning")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 아침 미국 증시 및 글로벌 이슈 보고서"
        
        prompt = f"""
        너는 최고의 금융 분석 에이전트야. 제공된 데이터({market_info})와 너의 최신 웹 검색/지식을 활용해서 아래 조건에 맞는 아침 리포트를 작성해줘.
        
        [🚨 가장 중요한 초강력 절대 규칙]
        - 보고서에 등장하는 '모든 수치(시장 지수, 개별 주식 종목)'의 등락률 뒤에는 무조건 색상 이모지를 붙여야 해.
        - 가격이나 전일 대비 수치가 올랐거나 상승한 주식이면 무조건 빨간색 원형 이모지와 플러스 기호인 '🔴 +0.00%' 형태로 적어줘.
        - 가격이나 전일 대비 수치가 내렸거나 하락한 주식이면 무조건 파란색 원형 이모지와 마이너스 기호인 '🔵 -0.00%' 형태로 적어줘.
        - 특히 3번(급등 종목)과 4번(추천/주목 종목)에 작성하는 모든 주식은 이름 옆 괄호 안에 등락률을 '종목명(티커) [🔴 +5.40%]' 혹은 '종목명(티커) [🔵 -1.20%]' 형태로 100% 명시해야 해. 무슨 일이 있어도 예외는 없어!

        [🚨 절대 준수 규칙 - 위반 시 페널티]
        - 무슨 일이 있어도 아래 [작성 내용]의 1번부터 4번까지의 모든 항목을 '단 하나도 누락하지 말고 전체 작성'해야 해. 중간에 글을 끊거나 요약하지 마.
        - 리포트 본문 맨 첫 줄에 반드시 "분석 기준 날짜: {date_str}"를 명시해줘.
        
        [작성 내용 - 반드시 4개 항목 모두 작성]
        1. 밤 사이에 있었던 글로벌 주요 이슈 3가지 (핵심 내용 정리)
        2. 새벽 마감된 미국 시장의 전체적인 흐름과 변동 요인 분석 (지수 언급 시 🔴/🔵 필수 적용)
        3. 오늘 새벽 미국 시장에서 많이 오른 급등 종목 3가지를 선정하고, 반드시 해당 기업의 '공식 이름(종목명)'과 '티커'를 명시하고 상승률(🔴 +0.00%)과 명확한 상승 이유를 적어줘.
        4. 오늘 밤 장에서 주목할 만한 미국 주식 3개를 추천하되, 반드시 해당 기업의 '공식 이름(종목명)'과 '티커'를 명확히 표기하고 예상 등락률(🔴 또는 🔵 필수 표기)과 구체적인 이유를 제시해줘.
        
        격식 있고 전문적인 언어로 작성하고, 가독성이 좋게 줄바꿈과 기호(■, -, 💡)를 적절히 섞어줘.
        """
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌙 오후 장 마감 리포트 생성 시작...")
        market_info = get_stock_data("evening")
        subject = f"[AI 주식 에이전트] {now.strftime('%Y-%m-%d')} 장 마감 한국 증시 종합 보고서"
        
        prompt = f"""
        너는 최고의 금융 분석 에이전트야. 제공된 데이터({market_info})와 너의 최신 웹 검색/지식을 활용해서 아래 조건에 맞는 마감 리포트를 작성해줘.
        
        [🚨 가장 중요한 초강력 절대 규칙]
        - 보고서에 등장하는 '모든 수치(시장 지수, 개별 주식 종목)'의 등락률 뒤에는 무조건 색상 이모지를 붙여야 해.
        - 가격이나 전일 대비 수치가 올랐거나 상승한 주식이면 무조건 빨간색 원형 이모지와 플러스 기호인 '🔴 +0.00%' 형태로 적어줘.
        - 가격이나 전일 대비 수치가 내렸거나 하락한 주식이면 무조건 파란색 원형 이모지와 마이너스 기호인 '🔵 -0.00%' 형태로 적어줘.
        - 특히 3번(급등 종목)과 4번(추천/주목 종목)에 작성하는 모든 주식은 이름 바로 옆에 등락률을 '종목명 [🔴 +5.40%]' 혹은 '종목명 [🔵 -1.20%]' 형태로 100% 명시해야 해. 무슨 일이 있어도 예외는 없어!

        [🚨 절대 준수 규칙 - 위반 시 페널티]
        - 무슨 일이 있어도 아래 [작성 내용]의 1번부터 4번까지의 모든 항목을 '단 하나도 누락하지 말고 전체 작성'해야 해. 중간에 글을 끊거나 요약하지 마.
        - 리포트 본문 맨 첫 줄에 반드시 "분석 기준 날짜: {date_str}"를 명시해줘.
        
        [작성 내용 - 반드시 4개 항목 모두 작성]
        1. 오늘 대한민국 주식시장 관련 주요 이슈 3가지
        2. 오늘 한국 시장의 전체적인 흐름과 변동 요인 분석 (지수 언급 시 🔴/🔵 필수 적용)
        3. 오늘 코스피/코스닥 시장에서 많이 오른 급등 종목 3가지를 선정하고, 반드시 해당 '기업 이름(종목명)'을 명시하고 상승률(🔴 +0.00%)과 명확한 상승 이유를 적어줘.
        4. 내일 장에서 주목할 만한 한국 주식 3개를 추천하되, 반드시 해당 '기업 이름(종목명)'을 명시하고 예상 등락률(🔴 또는 🔵 필수 표기)과 구체적인 이유를 제시해줘.
        
        격식 있고 전문적인 언어로 작성하고, 가독성이 좋게 줄바꿈과 기호(■, -, 💡)를 적절히 섞어줘.
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
    print(f"- 보내는 사람(GMAIL_USER) 로드 여부: {'⭕ 성공' if GMAIL_USER else '❌ 누락'}")
    print(f"- 앱 비밀번호(GMAIL_APP_PASSWORD) 로드 여부: {'⭕ 성공' if GMAIL_APP_PASSWORD else '❌ 누락'}")
    print(f"- 받는 사람(RECEIVER_EMAIL) 로드 여부: {'⭕ 성공' if RECEIVER_EMAIL else '❌ 누락'}")

    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECEIVER_EMAIL:
        print("⚠️ [경고] 이메일 필수 설정 정보가 누락되어 발송을 취소하고 건너뜁니다! GitHub Secrets를 다시 확인하세요.")
        return

    try:
        GMAIL_USER = GMAIL_USER.replace('\xa0', ' ').strip()
        GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD.replace('\xa0', ' ').strip()
        RECEIVER_EMAIL = RECEIVER_EMAIL.replace('\xa0', ' ').strip()
        subject = subject.replace('\xa0', ' ')
        body = body.replace('\xa0', ' ')

        targets = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✉️ 이메일 메시지 객체 생성 중...")
        msg = EmailMessage()
        msg.set_content(body, charset='utf-8') 
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = ", ".join(targets)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 구글 SMTP 서버(smtp.gmail.com:465) 연결 시도 중...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔑 구글 SMTP 로그인 시도 중...")
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 이메일 실제 전송 중... (수신처: {targets})")
            server.send_message(msg)
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 이메일 발송 최종 성공!")
    except smtplib.SMTPAuthenticationError:
        print("❌ [이메일 에러] 구글 로그인 인증 실패! GMAIL_USER 혹은 16자리 앱 비밀번호가 정확한지 확인하세요.")
    except Exception as e:
        print(f"❌ [이메일 에러] 발송 중 예기치 못한 치명적 오류 발생: {e}")

if __name__ == "__main__":
    print(f"================ [주식 에이전트 시스템 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ================")
    try:
        subject, report_text = generate_report()
        send_email(subject, report_text)
    except Exception as main_err:
        print(f"❌ 메인 시스템 실행 실패 원인: {main_err}")
    print("================ [주식 에이전트 시스템 종료] ================")
