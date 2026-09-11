import os
import requests
import json
import google.generativeai as genai
import time
import re
from bs4 import BeautifulSoup

def generate_with_retry(prompt, is_json=False):
    api_keys_str = os.environ.get('GEMINI_API_KEY', '')
    if not api_keys_str:
        raise ValueError('GEMINI_API_KEY is not set.')
    API_KEYS = [k.strip() for k in api_keys_str.split(',') if k.strip()]
    MODELS = ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
    generation_config = {"response_mime_type": "application/json"} if is_json else None
    
    for key in API_KEYS:
        genai.configure(api_key=key)
        for model_name in MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=generation_config)
                if response.text and response.text.strip():
                    return response.text.strip()
            except Exception as e:
                time.sleep(1)
                continue
    raise Exception("Critical: All API keys and models exhausted in keyword_miner!")

def get_naver_news_articles():
    url = "https://news.naver.com/breakingnews/section/105/230"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    articles = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.sa_text, .section_article')
        for it in items[:40]:
            title_tag = it.select_one('.sa_text_title, .title, a strong')
            desc_tag = it.select_one('.sa_text_lede, .lede, .desc')
            title = title_tag.get_text().strip() if title_tag else ""
            desc = desc_tag.get_text().strip() if desc_tag else ""
            if title:
                articles.append({"title": title, "description": desc, "date": "최신"})
    except Exception as e:
        print(f"네이버 뉴스 수집 에러: {e}")

    if not articles:
        articles = [
            {"title": "IT 기술 및 스마트 라이프 주요 제도 변경 및 혜택 안내", "description": "올해 새롭게 시행되는 기준과 필수 신청 자격 조건 총정리", "date": "2026"}
        ]
    return articles

def get_golden_keyword_and_source():
    history_file = 'posted_history.txt'
    history = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = [line.strip().lower() for line in f if line.strip()]

    articles = get_naver_news_articles()
    headlines = [a["title"] for a in articles]

    prompt = f"""
    다음은 [IT 기술 및 스마트 라이프] 분야의 최신 뉴스 및 정책 헤드라인 목록입니다:
    {json.dumps(headlines[:35], ensure_ascii=False)}
    
    이전에 이미 다룬 주제 (중복 금지):
    {json.dumps(history[-30:], ensure_ascii=False)}
    
    일반 서민과 독자들이 검색창에서 가장 간절히 찾는 '실용적이고 구체적인 핵심 황금 키워드' 1개(예: 2026 부모급여 신청방법, 디딤돌대출 금리조건 등)를 선별하세요.
    반드시 다음 JSON 형식으로만 반환하세요:
    {"golden_keyword": "선정된 키워드"}
    """
    try:
        res = generate_with_retry(prompt, is_json=True)
        data = json.loads(res)
        kw = data.get("golden_keyword", "IT 기술 및 스마트 라이프 핵심 가이드")
    except Exception as e:
        kw = "IT 기술 및 스마트 라이프 필수 정보"

    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(kw + "\n")

    kw_words = set(re.findall(r'[가-힣a-zA-Z0-9]+', kw.lower()))
    relevant_snippets = []
    for a in articles:
        article_words = set(re.findall(r'[가-힣a-zA-Z0-9]+', (a["title"] + " " + a["description"]).lower()))
        if kw_words.intersection(article_words) or len(relevant_snippets) < 3:
            snippet = f"- 헤드라인: {a['title']}\n  주요 내용: {a['description']}"
            relevant_snippets.append(snippet)
            if len(relevant_snippets) >= 5:
                break

    source_text = "\n\n".join(relevant_snippets)
    return kw, source_text
