import json
import re


def build_system_prompt(prompt_settings: dict) -> str:
    parts = [
        "# VAI TRÒ",
        prompt_settings.get('rolePrompt', '').strip(),
        "",
        "# BỐI CẢNH BELLA",
        prompt_settings.get('bellaContext', '').strip(),
        "",
        "# QUY TẮC PHÂN TÍCH SẢN PHẨM",
        prompt_settings.get('productAnalysisRules', '').strip(),
        "",
        "# QUY TẮC HOOK",
        prompt_settings.get('hookRules', '').strip(),
        "",
        "# QUY TẮC LỜI THOẠI",
        prompt_settings.get('dialogueRules', '').strip(),
        "",
        "# QUY TẮC CHUYỂN TÍNH NĂNG THÀNH LỢI ÍCH",
        prompt_settings.get('benefitRules', '').strip(),
        "",
        "# QUY TẮC HÀNH ĐỘNG TRONG VIDEO",
        prompt_settings.get('actionRules', '').strip(),
        "",
        "# QUY TẮC KẾT THÚC",
        prompt_settings.get('endingRules', '').strip(),
    ]
    additional = prompt_settings.get('additionalPrompt', '').strip()
    if additional:
        parts += ["", "# YÊU CẦU BỔ SUNG", additional]
    return "\n".join(parts)


SHOOTING_LABELS = {
    'one-shot': 'One Shot', 'review': 'Review mặc sản phẩm',
    'koc-review': 'KOC Review', 'tiktok-shop': 'TikTok Shop',
    'ugc': 'UGC', 'talking-head': 'Talking Head', 'pov': 'POV',
    'livestream-teaser': 'Livestream teaser',
    'voiceover': 'Voice Over (ElevenLabs)',
}

SHOOTING_GUIDE = {
    'one-shot': 'Quay một cảnh liên tục không cắt. Người quay tự nhiên cầm/mặc/dùng sản phẩm trong khi nói.',
    'review': 'Thử mặc/dùng sản phẩm trực tiếp. Chỉ ra điểm hay và lưu ý thật lòng, không quá PR.',
    'koc-review': 'Cấu trúc KOC: pain point → giải pháp → trải nghiệm thật → khuyến nghị rõ ràng.',
    'tiktok-shop': 'Format TikTok Shop: hook mạnh → điểm nổi bật ngắn gọn → CTA rõ ràng kéo click giỏ hàng.',
    'ugc': 'Cảm giác người dùng thật chia sẻ, không phải quảng cáo. Thô nhưng chân thực, gần gũi.',
    'talking-head': 'Ngồi/đứng nói thẳng vào camera. Không cần cầm sản phẩm suốt, tập trung vào lời thoại.',
    'pov': 'Góc nhìn người xem (POV: bạn đang thử...). Dùng ngôi "bạn/mình", kéo người xem vào trải nghiệm.',
    'livestream-teaser': 'Đoạn teaser giới thiệu sản phẩm cho livestream. Kết thúc kêu gọi vào live xem thêm.',
}

TONE_GUIDE = {
    'natural-koc': 'Tự nhiên như đang chia sẻ với bạn bè, không có cảm giác đọc script.',
    'friendly': 'Ấm áp, gần gũi, như người thân giới thiệu. Không formal, không cứng.',
    'cute': 'Dễ thương, nhẹ nhàng, dùng từ ngữ cute. Giọng tươi vui, không quá mạnh.',
    'light-elegant': 'Sang nhẹ, tinh tế. Không dùng từ thô hay slang. Câu chữ chỉn chu nhưng không cứng nhắc.',
    'tiktok-nhay': "Nhây nhây, hài hước, bắt trend. Dùng: 'mấy má' 'các vợ' 'thiệt luôn á' 'dữ thần' 'đứt lẹ'. Hook có twist, sarcasm nhẹ.",
    'light-humor': 'Hài hước vừa phải, dễ chịu. Có thể pha chút hài nhưng không quá nhây.',
    'soft-close': 'Tập trung vào giá trị và lợi ích thật. Chốt sale nhẹ nhàng, không gây áp lực.',
    'real-review': 'Thật thà, có cả mặt tốt lẫn điểm cần lưu ý. Nghe đáng tin, không quá quảng cáo.',
}

GOAL_GUIDE = {
    'increase-conversion': 'CTA mạnh cuối video. Nhấn mạnh giá trị, deal, hoặc lý do mua ngay hôm nay.',
    'build-trust': 'Tập trung chất lượng, độ bền, trải nghiệm thật. Tránh ngôn ngữ quảng cáo.',
    'introduce-new': 'Nêu bật điểm mới lạ, khác biệt so với sản phẩm thường. Tạo tò mò.',
    'push-bestseller': 'Nhấn mạnh nhiều người đã mua, phổ biến, bestseller. Social proof mạnh.',
    'solve-pain': 'Hook vào nỗi đau cụ thể, sản phẩm là giải pháp. Pain → Agitate → Solution.',
    'increase-comments': 'Cuối video đặt câu hỏi để kéo bình luận. Ví dụ: "Mấy chị hay bị vấn đề này không?"',
    'click-to-cart': 'CTA "nhấn giỏ hàng" / "link bio" / "bình luận hỏi giá" rõ ràng, lặp lại cuối.',
}
DURATION_LABELS = {
    '15s': '15 giây', '20s': '20 giây', '30s': '30 giây',
    '45s': '45 giây', '60s': '60 giây', '90s': '90 giây',
}
TONE_LABELS = {
    'natural-koc': 'Tự nhiên như KOC', 'friendly': 'Gần gũi',
    'cute': 'Dễ thương', 'light-elegant': 'Sang nhẹ',
    'tiktok-nhay': 'Nhây nhây bắt trend TikTok',
    'light-humor': 'Hài hước nhẹ', 'soft-close': 'Chốt sale mềm',
    'real-review': 'Review trải nghiệm thật',
}
GOAL_LABELS = {
    'increase-conversion': 'Tăng chuyển đổi', 'build-trust': 'Tạo niềm tin',
    'introduce-new': 'Giới thiệu sản phẩm mới', 'push-bestseller': 'Đẩy sản phẩm bán chạy',
    'solve-pain': 'Xử lý nỗi đau khách hàng', 'increase-comments': 'Tăng bình luận',
    'click-to-cart': 'Kéo click vào giỏ hàng',
}


def build_voiceover_prompt(input_data: dict, has_images: bool, image_analysis: str = '') -> str:
    """Prompt cho Voice Over (ElevenLabs Adam V3) — script giọng riêng, hành động camera riêng."""
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    goal_label = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    audience = input_data.get('targetAudience', '').strip()

    img_line = ("Phân tích ảnh (Gemini):\n" + image_analysis if image_analysis
                else ("Đã đính kèm ảnh sản phẩm." if has_images else "Không có ảnh."))

    tone_guide = TONE_GUIDE.get(tone, 'Tự nhiên, không quảng cáo cứng.')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    lines = [
        "Bạn là TikToker chuyên làm content giọng Adam trên ElevenLabs V3.",
        f"Phong cách giọng: {tone_label} — {tone_guide}",
        "Hook cực mạnh 3 giây đầu, có twist, nhịp nhanh. KHÔNG viết kiểu MC hay quảng cáo cứng.",
        f"Mục tiêu video: {goal_label}" + (f" — {goal_guide}" if goal_guide else '') + ".",
        "BẮT BUỘC chèn Audio Tag ElevenLabs vào đúng chỗ thể hiện cảm xúc — đây là yêu cầu quan trọng nhất.",
        "",
        "Audio Tags hợp lệ (chỉ dùng những tag này, KHÔNG tự đặt tag khác):",
        "[giggles] [playful] [sarcastic] [whispering] [laughs] [sighs] [clears throat] [excited] [sad]",
        "",
        "Ví dụ voScript ĐÚNG:",
        "[playful] Ê mấy má, cái quần này mà không mua là hối hận đó nha. [giggles]",
        "[sarcastic] Ừ thôi cứ mặc quần chật đi, bụng to thêm chút rồi tính.",
        "[whispering] Thiệt luôn á, em mặc vào là không muốn cởi ra luôn.",
        "",
        "Ví dụ voScript SAI (KHÔNG làm thế này):",
        "[cười nhẹ] Cái quần này... — SAI vì [cười nhẹ] không phải ElevenLabs tag",
        "[vuốt bụng] Em thấy... — SAI vì đây là hành động camera, không phải audio tag",
        "",
        "---",
        "",
        "# THÔNG TIN SẢN PHẨM",
        f"Tên sản phẩm: {input_data.get('productName', '')}",
        f"Mô tả: {input_data.get('productDescription', '')}",
    ]
    if audience:
        lines.append(f"Đối tượng: {audience}")
    lines += [
        f"Thời lượng: {duration_label} | Phong cách: {tone_label} | Mục tiêu: {goal_label}",
        f"Ảnh: {img_line}",
        "",
        "Bối cảnh: video OneShot quay liên tục, người quay KHÔNG NÓI — miệng im hoàn toàn.",
        "Giọng Adam lồng vào sau khi edit. Người quay chỉ làm hành động khớp với giọng Adam.",
        "",
        "---",
        "",
        "# ĐẦU RA — Chỉ trả về JSON hợp lệ, không text nào ngoài JSON:",
        "",
        '```json',
        '{',
        '  "section1": {"productName":"","targetAudience":"","shootingStyle":"Voice Over (ElevenLabs)","duration":"","tone":"","videoGoal":""},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":""},',
        '  "section3": {"hooks":[{"text":"[playful] câu hook nhây nhây Adam đọc","isRecommended":true},{"text":"hook 2 có audio tag","isRecommended":false},{"text":"hook 3 có audio tag","isRecommended":false}]},',
        '  "section7": {"captions":["caption ≤100 ký tự + 1-2 emoji","caption 2","caption 3"]},',
        '  "section8": {"hashtags":["#tag1","#tag2","#tiktokshop"]},',
        '  "section4": {',
        '    "duration":"30s",',
        '    "hook":"câu hook ngắn không có tag",',
        '    "voScript":"HOOK:\\n[playful] Câu hook cực mạnh có twist... [giggles]\\n\\nVOICE OVER:\\n[sarcastic] Câu 1 nhây nhây...\\n[whispering] Câu 2 bí mật...\\n[excited] Câu 3 hào hứng...\\n\\nCTA:\\n[playful] Câu kêu gọi tự nhiên...",',
        '    "lines":[{"type":"action","text":"hành động camera cụ thể khi Adam đọc câu 1"},{"type":"action","text":"hành động camera khi Adam đọc câu 2"}],',
        '    "rawScript":""',
        '  },',
        '  "section5": {"timeline":[{"timeRange":"0-3s","voice":"[playful] Câu Adam đọc...","action":"hành động camera tương ứng"}]},',
        '  "section9": {"tips":["tip quay (im lặng, tắt micro, ánh sáng)","tip edit lồng tiếng (sync audio, cut nhịp)"]}',
        '}',
        '```',
        "",
        "Lưu ý cuối:",
        f"- Viết đủ nội dung cho {duration_label}, không được thiếu.",
        "- section5 timeline: mỗi entry có 'voice' (câu Adam đọc kèm audio tag) và 'action' (hành động camera) riêng biệt.",
        "- lines[]: số entry bằng số câu trong voScript. Hành động mô tả cụ thể: cầm gì, góc máy, di chuyển.",
    ]
    return "\n".join(lines)


def build_user_prompt(input_data: dict, has_images: bool, image_analysis: str = '') -> str:
    shooting = input_data.get('shootingStyle', 'one-shot')

    # Voice Over dùng prompt riêng
    if shooting == 'voiceover':
        return build_voiceover_prompt(input_data, has_images, image_analysis)

    shooting_label = input_data.get('shootingStyleCustom', '') if shooting == 'custom' else SHOOTING_LABELS.get(shooting, shooting)
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    goal_label = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))

    lines = [
        "# THÔNG TIN SẢN PHẨM CẦN TẠO KỊCH BẢN",
        "",
        f"**Tên sản phẩm:** {input_data.get('productName', '')}",
        "",
        "**Mô tả sản phẩm:**",
        input_data.get('productDescription', ''),
        "",
    ]
    audience = input_data.get('targetAudience', '').strip()
    if audience:
        lines += [f"**Đối tượng khách hàng:** {audience}", ""]

    shooting_guide = SHOOTING_GUIDE.get(shooting, '')
    tone_guide = TONE_GUIDE.get(tone, '')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    lines += [
        f"**Kiểu quay:** {shooting_label}" + (f" — {shooting_guide}" if shooting_guide else ''),
        f"**Thời lượng:** {duration_label}",
        f"**Giọng điệu:** {tone_label}" + (f" — {tone_guide}" if tone_guide else ''),
        f"**Mục tiêu video:** {goal_label}" + (f" — {goal_guide}" if goal_guide else ''),
        "",
        "**Ảnh sản phẩm:** " + ("Phân tích ảnh (Gemini):\n" + image_analysis if image_analysis else ("Đã đính kèm - hãy phân tích màu sắc, form dáng, chất liệu, chi tiết từ ảnh." if has_images else "Không có ảnh - tạo kịch bản dựa trên tên và mô tả.")),
        "",
        "---",
        "",
        "# YÊU CẦU ĐẦU RA",
        "",
        "Chỉ trả về JSON hợp lệ, không có text nào bên ngoài JSON:",
        "",
        '```json',
        '{',
        '  "section1": {"productName":"","targetAudience":"","shootingStyle":"","duration":"","tone":"","videoGoal":""},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":""},',
        '  "section3": {"hooks":[{"text":"hook 1","isRecommended":true},{"text":"hook 2","isRecommended":false},{"text":"hook 3","isRecommended":false}]},',
        '  "section7": {"captions":["1 câu ngắn ≤100 ký tự: tên SP + lợi ích + 1-2 emoji + CTA","caption 2 góc khác cũng ≤100 ký tự","caption 3 góc khác cũng ≤100 ký tự"]},',
        '  "section8": {"hashtags":["#tag_chinh_xac_san_pham","#tag_niche","#tag_rong","#tiktokshop","#reviewsanpham"]},',
        '  "section4": {"duration":"","hook":"","lines":[{"type":"action","text":"hành động"},{"type":"dialogue","text":"lời thoại"}],"rawScript":""},',
        '  "section5": {"timeline":[{"timeRange":"0-3s","description":"hook + bước vào khung hình"}]},',
        '  "section9": {"tips":["lưu ý 1","lưu ý 2"]}',
        '}',
        '```',
        "",
        "Lưu ý quan trọng:",
        "- Kịch bản: hoàn toàn mới mỗi lần, lời thoại tự nhiên như đang nói thật, hành động đan xen sau mỗi 1-2 câu.",
        "- Caption TikTok: Tối đa 100 ký tự (TikTok cắt sau ~100 ký tự). Phải đề cập tên/loại sản phẩm, có 1-2 emoji. Chỉ 1 câu duy nhất — đừng giải thích dài.",
        "- Hashtag: mix đa dạng — 2-3 tag đặc trưng sản phẩm (niche/cụ thể), 3-4 tag danh mục rộng, 2 tag TikTok Shop chuẩn. Tổng 8-12 tag.",
    ]
    return "\n".join(lines)


def _try_parse_json(text: str):
    """Thử parse JSON, nếu lỗi thì tự clean rồi thử lại."""
    # Lần 1: parse thẳng
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Lần 2: xóa trailing commas (AI hay thêm) rồi parse
    cleaned = re.sub(r',\s*([\]}])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Lần 3: JSON bị cắt giữa chừng (AI hết token) — thử tại mỗi vị trí có '}'
    # chỉ scan những vị trí có ý nghĩa, không scan từng ký tự
    brace_positions = [i for i, c in enumerate(cleaned) if c == '}']
    for pos in reversed(brace_positions):
        chunk = cleaned[:pos + 1]
        opens = chunk.count('{') - chunk.count('}')
        if opens > 0:
            chunk += '}' * opens
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    raise ValueError('Không thể parse JSON từ response của AI')


def parse_ai_response(raw: str) -> dict:
    text = raw.strip()
    # Ưu tiên lấy JSON trong code block
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        text = match.group(1).strip()
    else:
        # Tìm từ { đầu tiên đến } cuối cùng
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]

    parsed = _try_parse_json(text)

    # Ensure all sections exist
    defaults = {
        'section1': {'productName': '', 'targetAudience': '', 'shootingStyle': '', 'duration': '', 'tone': '', 'videoGoal': ''},
        'section2': {'targetCustomer': '', 'painPoints': '', 'insight': '', 'highlights': '', 'mainBenefits': '', 'usageSituations': ''},
        'section3': {'hooks': []},
        'section4': {'duration': '', 'hook': '', 'lines': [], 'rawScript': '', 'voScript': ''},
        'section5': {'timeline': []},
        'section7': {'captions': []},
        'section8': {'hashtags': []},
        'section9': {'tips': []},
    }
    for key, default in defaults.items():
        if key not in parsed:
            parsed[key] = default

    parsed['rawResponse'] = raw
    return parsed


SECTION_SYSTEM = "Bạn là chuyên gia viết kịch bản TikTok Shop cho BELLA. Chỉ trả về JSON hợp lệ, không thêm text nào bên ngoài JSON."


def build_section_prompt(section: str, product_name: str, product_desc: str,
                         input_data: dict, current_script: dict, selected_hook: str = '') -> tuple:
    """Trả về (system_prompt, user_prompt) để tạo lại 1 section cụ thể."""
    shooting = input_data.get('shootingStyle', 'one-shot')
    shooting_label = input_data.get('shootingStyleCustom', '') if shooting == 'custom' else SHOOTING_LABELS.get(shooting, shooting)
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    goal_label = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))
    audience = input_data.get('targetAudience', '').strip()

    base = f"Sản phẩm: {product_name}\nMô tả: {product_desc}"
    if audience:
        base += f"\nĐối tượng: {audience}"

    shooting_guide = SHOOTING_GUIDE.get(shooting, '')
    tone_guide = TONE_GUIDE.get(tone, '')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    context_line = (
        f"Kiểu quay: {shooting_label}" + (f" ({shooting_guide})" if shooting_guide else '') + " | "
        f"Thời lượng: {duration_label} | "
        f"Giọng điệu: {tone_label}" + (f" ({tone_guide})" if tone_guide else '') + " | "
        f"Mục tiêu: {goal_label}" + (f" ({goal_guide})" if goal_guide else '')
    )

    if section == 'script':
        s2 = current_script.get('section2', {})
        analysis_parts = list(filter(None, [
            f"Pain point: {s2.get('painPoints','')}" if s2.get('painPoints') else '',
            f"Insight khách hàng: {s2.get('insight','')}" if s2.get('insight') else '',
            f"Điểm nổi bật sản phẩm: {s2.get('highlights','')}" if s2.get('highlights') else '',
            f"Lợi ích chính: {s2.get('mainBenefits','')}" if s2.get('mainBenefits') else '',
            f"Tình huống dùng: {s2.get('usageSituations','')}" if s2.get('usageSituations') else '',
        ]))
        analysis_block = ('\n' + '\n'.join(analysis_parts)) if analysis_parts else ''
        hook_line = f'\nHook mở đầu bắt buộc dùng: "{selected_hook}"' if selected_hook else ''
        user = f"""{base}{analysis_block}
{context_line}{hook_line}

Tạo kịch bản mới và timeline quay tương ứng. Lời thoại tự nhiên, hành động đan xen sau mỗi 1-2 câu.{"" if not selected_hook else " Câu đầu tiên của kịch bản PHẢI là hook đã cho, không được thay đổi."}

```json
{{"section4":{{"duration":"{duration_label}","hook":"{selected_hook or 'câu hook mở đầu'}","lines":[{{"type":"action","text":"hành động"}},{{"type":"dialogue","text":"lời thoại"}}],"rawScript":""}},"section5":{{"timeline":[{{"timeRange":"0-3s","description":"hook + bước vào khung hình"}}]}}}}
```"""

    elif section == 'hooks':
        s2 = current_script.get('section2', {})
        analysis = '\n'.join(filter(None, [
            f"Pain point: {s2.get('painPoints','')}" if s2.get('painPoints') else '',
            f"Insight: {s2.get('insight','')}" if s2.get('insight') else '',
            f"Điểm nổi bật: {s2.get('highlights','')}" if s2.get('highlights') else '',
        ]))
        user = f"""{base}
{analysis}
{context_line}

Tạo 3 hook mở đầu khác nhau, hook đầu tiên là hook khuyên dùng. Hook phải ngắn gọn, gây tò mò hoặc đánh vào nỗi đau.

```json
{{"section3":{{"hooks":[{{"text":"hook 1","isRecommended":true}},{{"text":"hook 2","isRecommended":false}},{{"text":"hook 3","isRecommended":false}}]}}}}
```"""

    elif section == 'caption':
        s4 = current_script.get('section4', {})
        lines_data = s4.get('lines', [])
        dialogue = ' '.join(l.get('text', '') for l in lines_data if l.get('type') == 'dialogue')
        vo_script = s4.get('voScript', '')
        script_text = (s4.get('rawScript', '') or vo_script or dialogue)[:600]
        user = f"""{base}
Kịch bản video: {script_text}
{context_line}

Tạo 3 caption TikTok Shop khác nhau. Quy tắc bắt buộc:
- Tối đa 100 ký tự mỗi caption (TikTok cắt sau ~100 ký tự)
- Chỉ 1 câu duy nhất — không giải thích dài, không liệt kê tính năng
- Đề cập tên hoặc loại sản phẩm cụ thể ngay đầu câu
- 1-2 emoji phù hợp
- Mỗi caption 1 góc khác nhau: pain point / lợi ích chính / social proof

```json
{{"section7":{{"captions":["caption 1","caption 2","caption 3"]}}}}
```"""

    elif section == 'hashtag':
        captions = current_script.get('section7', {}).get('captions', [])
        caption_hint = ' '.join(captions[:2])[:300] if captions else ''
        user = f"""{base}
Caption: {caption_hint}
{context_line}

Tạo 8-12 hashtag TikTok. Mix theo công thức:
- 2-3 tag đặc trưng sản phẩm (niche, cụ thể, ít cạnh tranh)
- 3-4 tag danh mục rộng (nhiều người tìm)
- 2 tag TikTok Shop chuẩn (#tiktokshop #reviewsanpham hoặc tương tự)
- Tag bằng tiếng Việt không dấu hoặc có dấu đều được

```json
{{"section8":{{"hashtags":["#tag1","#tag2","#tag3"]}}}}
```"""

    elif section == 'analysis':
        user = f"""{base}
{context_line}

Phân tích nhanh sản phẩm để tạo kịch bản TikTok Shop.

```json
{{"section2":{{"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":""}}}}
```"""

    elif section == 'tips':
        user = f"""{base}
{context_line}

Tạo 4-6 lưu ý khi quay video cho sản phẩm này, phù hợp với kiểu quay và mục tiêu video.

```json
{{"section9":{{"tips":["lưu ý 1","lưu ý 2"]}}}}
```"""

    else:
        raise ValueError(f'Section không hợp lệ: {section}')

    return SECTION_SYSTEM, user
