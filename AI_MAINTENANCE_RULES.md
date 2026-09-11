# 🚨 [CRITICAL] AI_MAINTENANCE_RULES 🚨
이 문서는 블로그 자동화 파이프라인의 생명줄입니다. 향후 코드를 수정하는 어떤 AI도 아래의 핵심 시스템을 임의로 생략, 최적화, 또는 훼손해서는 안 됩니다.

## 1. 🛡️ API 무적 순환 (Active Failover) 시스템 보존
- generate_with_retry 함수의 API 호출 에러(ResourceExhausted 등) 발생 시 무조건 작동해야 합니다.
- **2중 루프 로직 절대 보존:** 1차로 단일 API 키 내에서 모델(gemini-3.5-flash-lite -> 3.1-flash-lite)을 전환하고, 2차로 다음 GEMINI_API_KEY로 교체하여 재시도하는 로직을 지우지 마세요.

## 2. ✍️ True 3-Pass 글쓰기 파이프라인 (AEO/SEO 최적화)
API 비용을 아끼겠다고 글쓰기 단계를 1~2개로 단축하지 마세요. 반드시 아래 3단계를 독립적으로 호출해야 합니다.
- **Pass 1 (Write):** 검색어 기반의 정보성 초안 생성
- **Pass 2 (Check):** AEO(AI 최적화), SEO, GEO 관점에서 초안의 약점을 날카롭게 비판
- **Pass 3 (Revise):** 비판을 수용하여 AI 특유의 기계적 말투를 제거한 사람다운 전문가 최종 원고 작성

## 3. 🖼️ 썸네일 이미지 기획 (다중 사물 조합 허용 & 심플 프롬프트)
- **대상 제한:** 인물, 동물은 절대 금지합니다.
- **조합 허용:** 반드시 1개의 사물일 필요는 없습니다. 대상은 '상징적인 무생물 사물'이되, 문맥에 맞는 **적절한 사물들의 자연스러운 조합(예: 황금 동전과 계산기)**을 허용합니다.
- **심플 프롬프트 고정:** 찰흙 질감을 방지하기 위해 과도한 수식어(Photorealistic, 8k, ultra 등)를 배제하고 무조건 아래 포맷을 고정 사용하세요.
  A realistic photograph of {obj_name} on a clean desk, bright natural lighting, simple and clear

## 4. 💰 영문 경제 블로그 필수 규칙 (Golden Keyword Miner)
- **100% 데이터 드리븐 황금 키워드 아키텍처 적용:**
  1. **Google News RSS (US):** 미국 경제/금융 실시간 뉴스 헤드라인을 수집하여 팩트를 확보합니다.
  2. **AI Seed Extraction:** 가십을 배제하고 핵심 영문 명사(Seed) 5개를 추출합니다.
  3. **Google Autocomplete API:** 씨앗 명사를 확장하여 실제 유저가 검색하는 롱테일 키워드를 발굴합니다.
  4. **History Validation:** posted_history.txt를 대조하여 완벽히 일치하는 중복 키워드를 원천 차단합니다.
- **US 타겟 영문 작성:** 모든 원고는 영어(English)로 작성되며 미국 시장을 타겟팅해야 합니다.
- **애드센스 블록 보존:** d_top, d_middle, d_bottom 위치에 치환되는 고단가 애드센스 광고 블록을 훼손하지 마세요.
