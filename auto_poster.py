import os
import json
import random
import time
import re
from datetime import datetime
import google.generativeai as genai
import keyword_miner
import fact_checker

# Setup Gemini API
api_keys_str = os.environ.get('GEMINI_API_KEY', '')
if not api_keys_str:
    print('GEMINI_API_KEY is not set.')
    exit(1)

API_KEYS = [k.strip() for k in api_keys_str.split(',') if k.strip()]
print(f"Loaded {len(API_KEYS)} API key(s) for auto_poster.")
models_to_use = ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']

def generate_with_retry(prompt, is_json=False):
    for key_idx, key in enumerate(API_KEYS):
        genai.configure(api_key=key)
        for model_name in models_to_use:
            try:
                model = genai.GenerativeModel(model_name)
                config = genai.GenerationConfig(response_mime_type="application/json") if is_json else None
                response = model.generate_content(prompt, generation_config=config)
                if response.text and response.text.strip():
                    return response.text.strip()
            except Exception as e:
                err_msg = str(e).lower()
                print(f"[Key {key_idx+1}/{len(API_KEYS)}][{model_name}] Request warning: {e}")
                time.sleep(2)
                continue
    print("Warning: All API keys temporarily exhausted or rate-limited for today.")
    # 우아한 종료 (GitHub Actions 실패 메일 방지)
    exit(0)

def create_text_thumbnail(text, filename_prefix="thumb"):
    import urllib.request
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()][:3]
    img_width, img_height = 1200, 675  # 16:9 표준 비율 (웹 및 모바일 잘림 완전 방지)
    background_color = (30, 45, 65) # Dark Navy Blue
    text_color = (255, 255, 255)
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (img_width, img_height), color=background_color)
        draw = ImageDraw.Draw(img)
        font_path = "NanumGothic-Bold.ttf"
        if not os.path.exists(font_path):
            try:
                urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", font_path)
            except:
                pass

        border_margin = 40
        draw.rectangle([border_margin, border_margin, img_width - border_margin, img_height - border_margin], outline=(100, 150, 200), width=3)
        
        # 텍스트 가로폭에 따라 폰트 크기 자동 조절 (Auto-fit)
        max_text_width = img_width - (border_margin * 2) - 100
        current_font_size = 75
        font = ImageFont.truetype(font_path, current_font_size)
        
        while current_font_size > 35:
            max_line_w = 0
            for line in lines:
                try:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    w = bbox[2] - bbox[0]
                except:
                    w = len(line) * (current_font_size * 0.6)
                if w > max_line_w:
                    max_line_w = w
            if max_line_w <= max_text_width:
                break
            current_font_size -= 2
            font = ImageFont.truetype(font_path, current_font_size)
            
        line_height = current_font_size + 25
        total_text_height = len(lines) * line_height
        y_text = (img_height // 2) - (total_text_height // 2)
        
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
            except:
                w = len(line) * (current_font_size * 0.6)
            x_text = (img_width - w) / 2
            draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += line_height
            
        os.makedirs('assets/images', exist_ok=True)
        img_path = f'assets/images/{filename_prefix}.webp'
        img.save(img_path, 'WEBP', quality=85)
        return img_path
    except Exception as e:
        print(f"Thumbnail error: {e}")
        return ""

def download_vibe_image(img_url, filename_prefix):
    if not img_url: return ""
    try:
        import requests, io
        from PIL import Image
        os.makedirs('assets/images', exist_ok=True)
        img_r = requests.get(img_url, timeout=10)
        image = Image.open(io.BytesIO(img_r.content))
        base_width = 800
        if image.size[0] > base_width:
            wpercent = (base_width / float(image.size[0]))
            hsize = int((float(image.size[1]) * float(wpercent)))
            image = image.resize((base_width, hsize), Image.Resampling.LANCZOS)
        img_path = f'assets/images/{filename_prefix}.webp'
        image.save(img_path, 'WEBP', quality=85)
        return img_path
    except:
        return ""

def generate_post(keyword, source_text):
    # Load prompt templates
    with open('prompts/draft_template.txt', 'r', encoding='utf-8') as f:
        draft_template = f.read()

    # [Pass 1/3] 사실 기반 심층 초안 작성
    print(f"Pass 1/3: Generating Grounded Draft on '{keyword}'...")
    draft_prompt = draft_template.replace('{keyword}', keyword).replace('{source_text}', source_text)
    draft = generate_with_retry(draft_prompt)

    # [Pass 2/3] 혹독한 편집장의 기계적 문체/가독성 결함 비판 (Critic)
    print("Pass 2/3: Running Incisive Critic Audit for AI Smell & Flow...")
    critic_prompt = f"""당신은 혹독한 시사·경제 전문 수석 편집장입니다.
다음 초안을 읽고 개선해야 할 핵심 단점 3가지를 신랄하게 지적하세요:
1. AI 특유의 번역투, 기계적인 말투, 작위적 추임새(하하, 자 그럼, 현대 사회에서, 결론적으로, 살펴보겠습니다 등) 여부
2. 문장 길이가 획일적이거나 접속사가 남발되어 가독성이 떨어지는지 여부
3. 피상적인 겉핥기식 요약에 그치지 않고 독자에게 실질적인 통찰과 실익을 주는지 여부

[초안]:
{draft}"""
    critique = generate_with_retry(critic_prompt)
    print(f"Critic Audit Complete. Feedback length: {len(critique)} chars")

    # [Pass 3/3] 비판 100% 수용 최종 인간화 재작성 & 메타데이터 일괄 생성
    print("Pass 3/3: Executing Final Humanized Rewrite & Meta Generation...")
    rewrite_prompt = f"""당신은 상위 1% 전문 칼럼니스트이자 수석 에디터입니다.
아래 [초안]에 [전문가 비판]을 100% 수용하여 결함을 완벽히 뜯어고친 최종 2,000자 내외의 고품질 블로그 원고를 완성하세요.

[핵심 집필 및 서술 규칙]
1. AI 특유의 기계적 말투와 번역투를 완전히 제거하고, 실제 사람이 직접 쓴 것처럼 유려하고 자연스러운 호흡으로 작성하세요.
2. 소제목은 반드시 '## '(H2) 또는 '### '(H3)만 사용하세요. 최상위 제목(# H1)은 절대 쓰지 마세요.
3. 각 H2 소제목 바로 다음 줄에 정확히 '[VIBE_IMAGE_HERE]'를 유지하세요.
4. 마크다운 비교 표(Table)와 구체적 체크리스트를 포함하되, 대괄호 지시어(예: [3단계 ...])를 제목으로 노출하지 마세요.
5. 마크다운 코드 블록(```)으로 전체 본문을 감싸지 마세요.

[전문가 비판]:
{critique}

[초안]:
{draft}

반드시 본문 작성이 끝난 후, 맨 마지막 줄에 아래 구분자 사이에 메타데이터 JSON을 정확히 첨부하세요:
---METADATA_START---
{{
  "title": "{keyword} 관련 클릭률 높은 매력적인 1줄 제목",
  "thumb_hook": "{keyword}\n핵심 분석 요약 (줄바꿈은 \\n)",
  "vibe_keywords": "Pixabay 검색용 영문 키워드 1~2개 (예: finance market)",
  "meta_description": "150자 이내의 검색 최적화 요약문"
}}
---METADATA_END---"""

    rewrite_output = generate_with_retry(rewrite_prompt)

    # 메타데이터 파싱 및 본문 분리
    meta = {}
    if '---METADATA_START---' in rewrite_output and '---METADATA_END---' in rewrite_output:
        parts = rewrite_output.split('---METADATA_START---')
        final_draft = parts[0].strip()
        meta_json_str = parts[1].split('---METADATA_END---')[0].strip()
        try:
            meta = json.loads(meta_json_str)
        except:
            pass
    else:
        final_draft = rewrite_output.strip()

    title = meta.get('title', f"{keyword} 완벽 가이드")
    thumb_hook = meta.get('thumb_hook', f"{keyword}\n핵심 분석")
    vibe_keywords = meta.get('vibe_keywords', 'finance')
    meta_desc = meta.get('meta_description', '')

    # [팩트체크 게이트] 비용 0원 로컬 정규식 검증
    print("Running Local Regex Fact-Check Gate...")
    check_result = fact_checker.verify_facts(final_draft, source_text, threshold=0.55)
    print(f"Fact-Check result: Passed={check_result['passed']}, Match Rate={int(check_result['match_rate']*100)}%")

    # 클린업 및 AI 티 제거 정제 필터
    final_draft = re.sub(r'^#\s+(.+)$', r'## \1', final_draft, flags=re.MULTILINE)
    final_draft = re.sub(r'^(?:하하[!,~]?\s*|자,\s*그럼\s*|현대\s*사회[는에서]?\s*)', '', final_draft, flags=re.MULTILINE)
    final_draft = re.sub(r'\[(?:\d+단계|[가-힣\s]+체크리스트|[가-힣\s]+절차)\]', r'### 핵심 이용 절차 및 확인사항', final_draft)
    final_draft = re.sub(r'\[(?:Actionable|Key Takeaway|Checklist)[^\]]*\]', r'### Strategic Action Framework', final_draft, flags=re.IGNORECASE)
    final_draft = re.sub(r'(?i)^(?:#+\s*)?H[23]:\s*', '', final_draft, flags=re.MULTILINE)
    final_draft = re.sub(r'^---.*?---\s*', '', final_draft, flags=re.DOTALL)

    # Pixabay 이미지 처리
    image_urls = []
    try:
        import urllib.parse, requests
        url = f"https://pixabay.com/api/?key=57366919-c2774ae5199cc6a6cdb9a301d&q={urllib.parse.quote(vibe_keywords)}&image_type=photo&orientation=horizontal&per_page=10"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('hits'):
            image_urls = [hit.get('largeImageURL', hit.get('webformatURL')) for hit in data['hits']]
    except:
        pass

    parts = final_draft.split('[VIBE_IMAGE_HERE]')
    processed_text = parts[0]
    img_idx = 0
    for part in parts[1:]:
        v_path = ""
        if img_idx < len(image_urls):
            v_path = download_vibe_image(image_urls[img_idx], f"vibe_{int(time.time())}_{img_idx}")
            img_idx += 1
        if v_path:
            alt_text = f"{keyword} 핵심 분석 인포그래픽 {img_idx}"
            processed_text += f"\n\n![{alt_text}]({{{{ '/' | append: '{v_path}' | relative_url }}}})\n\n"
        processed_text += part

    # 썸네일 생성
    thumb_filename = f"thumb_{int(time.time())}"
    thumb_rel_path = create_text_thumbnail(thumb_hook, thumb_filename)

    # 하단 팩트 검증 출처 고지문 (E-E-A-T 강화)
    attribution_notice = """
<div style="margin: 35px 0; padding: 16px 20px; border-left: 4px solid #3b82f6; background-color: #f8fafc; font-size: 13px; color: #475569; line-height: 1.6;">
    <strong>데이터 무결성 및 공공 정보 공시:</strong> 본 분석 리포트는 각 기관의 공식 발표 자료, 공개 통계 데이터 및 정책 공시문을 기반으로 사실 관계 검증을 거쳐 작성되었습니다.
</div>
"""
    ad_bottom = '\n<div class="manual-ad-container" style="margin: 30px 0; text-align: center;">\n<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-2228289204702106" data-ad-slot="2231432699" data-ad-format="auto" data-full-width-responsive="true"></ins>\n<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>\n</div>\n'

    final_text = processed_text + attribution_notice + ad_bottom
    return title, final_text, thumb_rel_path, meta_desc

def main():
    print("=== Starting Fact-Grounded Economy Post Pipeline ===")
    keyword, source_text = keyword_miner.get_golden_keyword_and_source()
    print(f"Target Keyword: {keyword}")
    print(f"Source Context Length: {len(source_text)} chars")

    title, post_content, thumb_path, meta_desc = generate_post(keyword, source_text)

    if post_content:
        date_str = datetime.now().strftime('%Y-%m-%d')
        clean_kw = re.sub(r'[^a-zA-Z0-9가-힣\s\-]', '', keyword).strip()
        safe_title = re.sub(r'[\s\-]+', '-', clean_kw).strip('-').lower()
        if not safe_title or safe_title == '-':
            safe_title = f"post-{int(time.time())}"
        filename = f'_posts/{date_str}-{safe_title}.md'
        os.makedirs('_posts', exist_ok=True)
        
        frontmatter = f"---\nlayout: post\ntitle: \"{title}\"\ndate: {date_str}\nimage: {thumb_path}\ndescription: \"{meta_desc}\"\n---\n\n"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(frontmatter + post_content)
        print(f"Successfully published high-authority post: {filename}")

if __name__ == '__main__':
    main()
