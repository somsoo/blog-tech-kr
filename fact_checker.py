import re

def extract_facts(text: str) -> dict:
    """본문에서 검증 대상이 되는 핵심 팩트(수치, 퍼센트, 화폐, 날짜)를 정규식으로 추출"""
    facts = {
        "percentages": list(set(re.findall(r'\b\d+(?:\.\d+)?%', text))),
        "currencies": list(set(re.findall(r'\$\d+(?:,\d+)*(?:\.\d+)?|\b\d+(?:,\d+)*\s*(?:달러|원|억원|조원|billions?|trillions?)', text, re.IGNORECASE))),
        "dates": list(set(re.findall(r'\b202\d(?:년|[-/.])\s*(?:\d{1,2}(?:월|[-/.])\s*(?:\d{1,2}일?)?)?|\b\d{1,2}월\s*\d{1,2}일', text))),
        "pure_numbers": list(set(re.findall(r'\b\d{2,}(?:,\d{3})*(?:\.\d+)?\b', text)))
    }
    return facts

def verify_facts(generated_text: str, source_text: str, threshold: float = 0.70) -> dict:
    """
    생성된 글 속의 수치가 원문 기사(source_text)에 실제로 존재하는지 대조.
    threshold: 최소 일치율 (기본 70%)
    """
    if not source_text or not source_text.strip():
        return {
            "passed": True,
            "match_rate": 1.0,
            "total_facts": 0,
            "matched_facts": 0,
            "unmatched": [],
            "note": "No source text provided for comparison."
        }

    gen_facts = extract_facts(generated_text)
    critical_items = gen_facts["percentages"] + gen_facts["currencies"]
    all_items = critical_items + gen_facts["dates"]
    
    for num in gen_facts["pure_numbers"]:
        clean_num = num.replace(",", "")
        try:
            if float(clean_num) >= 50 and num not in all_items:
                all_items.append(num)
        except ValueError:
            pass

    if not all_items:
        return {
            "passed": True,
            "match_rate": 1.0,
            "total_facts": 0,
            "matched_facts": 0,
            "unmatched": [],
            "note": "No specific numeric facts found to verify."
        }

    matched = []
    unmatched = []
    clean_source = re.sub(r'\s+', ' ', source_text).lower()

    for item in all_items:
        clean_item = item.strip().lower()
        raw_digits = re.sub(r'[^\d.]', '', clean_item)
        if clean_item in clean_source or (raw_digits and raw_digits in clean_source):
            matched.append(item)
        else:
            unmatched.append(item)

    total_count = len(all_items)
    matched_count = len(matched)
    match_rate = matched_count / total_count if total_count > 0 else 1.0
    passed = (match_rate >= threshold) and (len(unmatched) <= 4)

    return {
        "passed": passed,
        "match_rate": round(match_rate, 2),
        "total_facts": total_count,
        "matched_facts": matched_count,
        "unmatched": unmatched[:10],
        "note": "Fact-check passed successfully." if passed else f"Fact-check failed: Match rate {round(match_rate*100)}% is below {int(threshold*100)}%."
    }

if __name__ == "__main__":
    sample_source = "The Federal Reserve held the interest rate steady at 5.25% in 2026. Inflation dropped to 2.8%, while tech investments reached $12 billion."
    sample_valid_gen = "In 2026, the Federal Reserve maintained interest rates at 5.25%. Inflation eased to 2.8%, driving $12 billion into tech."
    sample_fake_gen = "In 2026, the Fed cut rates to 1.5% as inflation skyrocketed to 9.4%, causing a $85 billion market crash."

    print("Test Valid:", verify_facts(sample_valid_gen, sample_source))
    print("Test Fake:", verify_facts(sample_fake_gen, sample_source))
