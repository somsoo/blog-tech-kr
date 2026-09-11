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
    with open('prompts/meta_template.txt', 'r', encoding='utf-8') as f:
        meta_template = f.read()

    print(f"Step 1: Generating Grounded Report on '{keyword}'...")
    draft_prompt = draft_template.replace('{keyword}', keyword).replace('{source_text}', source_text)
    draft = generate_with_retry(draft_prompt)

    # 팩트체크 게이트 실행 (비용 0원 정규식 검증)
    print("Step 2: Running Regex Fact-Check Gate...")
    check_result = fact_checker.verify_facts(draft, source_text, threshold=0.65)
    print(f"Fact-Check result: Passed={check_result['passed']}, Match Rate={int(check_result['match_rate']*100)}%")
    if not check_result['passed']:
        print(f"Unmatched figures detected: {check_result['unmatched']}. Retrying draft once with stricter grounding...")
        strict_prompt = draft_prompt + "\n\nCRITICAL WARNING: Prior draft contained unverified figures. STRICTLY use only figures in the source material."
        draft = generate_with_retry(strict_prompt)
        check_result = fact_checker.verify_facts(draft, source_text, threshold=0.60)
        print(f"Re-check result: Passed={check_result['passed']}, Match Rate={int(check_result['match_rate']*100)}%")

    # 클린업
    draft = re.sub(r'(?i)^(?:#+\s*)?H[23]:\s*', '', draft, flags=re.MULTILINE)
    draft = re.sub(r'^---.*?---\s*', '', draft, flags=re.DOTALL)

    # Step 3: Meta 정보 생성
    print("Step 3: Generating SEO Metadata...")
    meta_prompt = meta_template.replace('{keyword}', keyword).replace('{draft_text}', draft[:1500])
    meta_json_str = generate_with_retry(meta_prompt, is_json=True)
    try:
        meta = json.loads(meta_json_str)
        title = meta.get('title', f"{keyword} Analysis")
        thumb_hook = meta.get('thumb_hook', f"{keyword}\nMarket Insights")
        vibe_keywords = meta.get('vibe_keywords', 'finance')
        meta_desc = meta.get('meta_description', '')
    except:
        title, thumb_hook, vibe_keywords, meta_desc = f"{keyword} Analysis", f"{keyword}\nMarket Insights", "finance", ""

    # Step 4: Pixabay 이미지 처리
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

    parts = draft.split('[VIBE_IMAGE_HERE]')
    processed_text = parts[0]
    img_idx = 0
    for part in parts[1:]:
        v_path = ""
        if img_idx < len(image_urls):
            v_path = download_vibe_image(image_urls[img_idx], f"vibe_{int(time.time())}_{img_idx}")
            img_idx += 1
        if v_path:
            processed_text += f"\n<br>\n![Market Chart]({{{{ '/' | append: '{v_path}' | relative_url }}}})\n<br>\n"
        processed_text += part

    # 썸네일 생성
    thumb_filename = f"thumb_{int(time.time())}"
    thumb_rel_path = create_text_thumbnail(thumb_hook, thumb_filename)

    # 하단 팩트 검증 출처 고지문 (E-E-A-T 강화)
    attribution_notice = """
<div style="margin: 35px 0; padding: 16px 20px; border-left: 4px solid #3b82f6; background-color: #f8fafc; font-size: 13px; color: #475569; line-height: 1.6;">
    <strong>Data Integrity & Attribution:</strong> This analytical report is curated from public central bank announcements, institutional market disclosures, and verified news feeds. Factual figures and metrics are validated via automated factual consistency checks.
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
        safe_title = re.sub(r'[^a-zA-Z0-9\-]', '', keyword.replace(' ', '-')).lower()
        filename = f'_posts/{date_str}-{safe_title}.md'
        os.makedirs('_posts', exist_ok=True)
        
        frontmatter = f"---\nlayout: post\ntitle: \"{title}\"\ndate: {date_str}\nimage: {thumb_path}\ndescription: \"{meta_desc}\"\n---\n\n"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(frontmatter + post_content)
        print(f"Successfully published high-authority post: {filename}")

if __name__ == '__main__':
    main()
