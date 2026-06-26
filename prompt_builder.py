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

VO_PERSONA_GUIDE = {
    'natural-koc': (
        "Persona: Người vừa trải nghiệm sản phẩm — đang kể lại cho bạn bè nghe.\n"
        "Chân thật, không cường điệu. Dùng: 'mọi người', 'các mẹ', 'các chị', 'theo mình', 'công nhận', 'nói thật'.\n"
        "Không hype, không quảng cáo cứng. Như đang nhận xét thật sau khi dùng."
    ),
    'friendly': (
        "Persona: Người bạn thân đang gợi ý món đồ hay.\n"
        "Ấm áp, gần gũi. Dùng: 'nè', 'nha', 'á', 'đó', 'chị em', 'mọi người'.\n"
        "Không formal, không cứng nhắc. Nghe như đang nhắn tin cho bạn, không phải đọc quảng cáo."
    ),
    'cute': (
        "Persona: Cô gái dễ thương đang chia sẻ món đồ yêu thích của mình.\n"
        "Nhẹ nhàng, tươi vui. Có thể dùng: 'hihi', 'hehe', 'ui', 'cưng ghê', 'trời ơi'.\n"
        "Dịu dàng nhưng vẫn tự nhiên. Không gượng ép, không quá lố."
    ),
    'light-elegant': (
        "Persona: Người thanh lịch, tinh tế đang chia sẻ quan điểm cá nhân.\n"
        "Không dùng từ lóng, không slang thô. Câu chữ chỉn chu nhưng không cứng nhắc.\n"
        "Phải nghe như người đang nói chuyện — không phải đọc bài hay đọc quảng cáo."
    ),
    'tiktok-nhay': (
        "Persona: TikToker Gen Z năng lượng cao — nhập vai hoàn toàn, không phải AI đang viết.\n"
        "Xưng hô linh hoạt theo ngữ cảnh: 'ê', 'ê mọi người', 'mấy bà', 'các vợ', 'chị em', 'bro', 'alo'.\n"
        "Phản ứng tự nhiên (không spam, chọn dùng 1-2 cái phù hợp): 'Ủa?', 'Thiệt luôn?', 'Má ơi.', "
        "'Công nhận.', 'Đỉnh ghê.', 'Xịn dữ.', 'Mượt dữ.', 'Hết nước chấm.', 'Đúng kiểu luôn.'.\n"
        "Kéo dài âm khi nhấn mạnh: 'Đẹpppp', 'Mềmmmm', 'Ghêeeee', 'Nooooo'.\n"
        "Tiếng Anh đơn giản khi phù hợp: 'Wait...', 'OMG...', 'Bro...', 'Okay...'.\n"
        "Câu chuyển ý đa dạng: 'Mà nè...', 'Chưa hết đâu.', 'Còn cái này nữa.', 'Quan trọng nè.'.\n"
        "Câu hỏi kéo người xem: 'Thấy chưa?', 'Tin nổi không?', 'Mấy bà thấy sao?'.\n"
        "Phủ định để tạo twist: 'Không không không...', 'Khoan...', 'Đừng vội...'.\n"
        "QUAN TRỌNG: Mỗi video phải có cảm giác như một TikToker khác nhau. Tự sáng tạo, không lặp công thức."
    ),
    'light-humor': (
        "Persona: Người hài hước vừa phải — dí dỏm nhưng không lố.\n"
        "Hài có chừng mực, có thể pha châm biếm nhẹ nhàng hoặc nhận xét buồn cười.\n"
        "Vẫn tự nhiên, không ép hài, không cố quá."
    ),
    'soft-close': (
        "Persona: Người bạn chân thành đang giới thiệu món đồ thật sự tốt.\n"
        "Tập trung vào giá trị thật. Không dùng: 'mua ngay kẻo hết', 'sale cuối', 'không mua là tiếc'.\n"
        "Ưu tiên: 'nếu bạn đang cần...', 'mình thấy đáng...', 'thật ra cái này...'. Chốt nhẹ, không áp lực."
    ),
    'real-review': (
        "Persona: Người vừa dùng sản phẩm xong — đang nói thật, không PR.\n"
        "Có cả ưu và điểm cần lưu ý. Nghe đáng tin vì không hoàn hảo 100%.\n"
        "Có thể dùng: 'thật ra', 'nói thật', 'mình dùng rồi nên biết', 'điểm này mình thích / chưa thích lắm'."
    ),
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
    """Prompt cho Voice Over (ElevenLabs V3 Enhance) — pure voice script, không emotion tag."""
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    goal_label = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    audience = input_data.get('targetAudience', '').strip()

    img_line = ("Phân tích ảnh sản phẩm:\n" + image_analysis if image_analysis
                else ("Đã đính kèm ảnh sản phẩm." if has_images else "Không có ảnh."))

    persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật, không quảng cáo cứng.')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    lines = [
        "# VAI TRÒ",
        "Bạn là một Creator TikTok thật — đang nói chuyện trực tiếp với người xem.",
        "Kiểu quay: Voice Over (ElevenLabs V3 Enhance).",
        "ElevenLabs V3 Enhance tự nhận diện cảm xúc từ cách viết và tự thêm emotion vào giọng.",
        "Nhiệm vụ của bạn: CHỈ viết lời thoại thuần túy. Không cần tag gì cả.",
        "",
        "# PERSONA",
        f"Giọng điệu: {tone_label}",
        persona_guide,
        "",
        f"Mục tiêu video: {goal_label}" + (f" — {goal_guide}" if goal_guide else '') + ".",
        "",
        "# QUY TẮC BẮT BUỘC",
        "",
        "## TUYỆT ĐỐI KHÔNG được viết emotion tag",
        "Không được có [playful], [giggles], [laughs], [excited], [whisper], [sarcastic], [whispering],",
        "[sighs], [clears throat], [sad] hay bất kỳ dấu ngoặc vuông nào dạng tag cảm xúc.",
        "ElevenLabs V3 Enhance tự xử lý. Nếu output có tag → sai hoàn toàn.",
        "",
        "## KHÔNG viết như AI, MC, văn viết, quảng cáo",
        "Không mở đầu bằng: 'Xin chào mọi người', 'Hôm nay mình sẽ', 'Mình xin giới thiệu',",
        "'Trong video này', 'Đây là sản phẩm', 'Sản phẩm này được thiết kế để'.",
        "Không dùng cấu trúc AI: 'Ngoài ra...', 'Đặc biệt...', 'Sản phẩm có...', 'Sản phẩm được...'.",
        "",
        "## Viết như người đang NÓI, không phải VIẾT",
        "Được dùng câu đệm, phản ứng tự nhiên, ngắt nghỉ, câu bỏ lửng.",
        "Ví dụ (chỉ là ví dụ, AI phải sáng tạo thêm, không lặp lại những cái này):",
        "'Ủa...', 'À mà...', 'Khoan...', 'Wow...', 'Haha...', 'Công nhận...', 'Ghê vậy.', 'Thiệt luôn.'",
        "Nếu viết 100 video cho cùng 1 sản phẩm, người nghe phải cảm giác như 100 Creator khác nhau.",
        "",
        "## CẤU TRÚC VIDEO",
        "HOOK (0-3s): Câu mạnh nhất. Gây tò mò / bất ngờ / phủ định / câu hỏi / nhận xét thú vị.",
        "Đi thẳng vào vấn đề. Không có lời chào, không giới thiệu bản thân.",
        "BODY: Lời thoại tự nhiên như đang trò chuyện. Không cố tạo cảm xúc liên tục.",
        "CTA: Tăng năng lượng cuối, tự nhiên, không ép mua.",
        "",
        "## ĐA DẠNG CẤU TRÚC CÂU",
        "Kết hợp: câu ngắn, câu dài, câu hỏi, câu kể, câu bỏ lửng, câu cảm thán.",
        "Không để tất cả câu giống nhau về độ dài hay nhịp điệu.",
        "",
        "## TỰ KIỂM TRA TRƯỚC KHI OUTPUT",
        "Trước khi trả JSON, kiểm tra voScript:",
        "- Có tag dạng [xxx] không? → Xóa hết.",
        "- Có giống văn viết / MC / ChatGPT không? → Viết lại.",
        "- Có câu mở đầu kiểu AI ('Xin chào', 'Hôm nay mình') không? → Thay hook khác.",
        "- Có lặp từ / lặp cấu trúc câu không? → Đa dạng hóa.",
        "- Có đúng Persona và Giọng điệu đã chọn không?",
        "- Người nghe có cảm giác 'đây là Creator thật' không?",
        "Nếu chưa đạt → tự chỉnh sửa trước khi xuất JSON.",
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
        "Bối cảnh quay: video liên tục, người quay KHÔNG NÓI — miệng im hoàn toàn.",
        "Giọng lồng vào sau khi edit qua ElevenLabs. Người quay chỉ làm hành động khớp với giọng.",
        "",
        "---",
        "",
        "# ĐẦU RA — Chỉ trả về JSON hợp lệ, không text nào ngoài JSON:",
        "",
        '```json',
        '{',
        '  "section1": {"productName":"","targetAudience":"","shootingStyle":"Voice Over (ElevenLabs)","duration":"","tone":"","videoGoal":""},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":""},',
        '  "section3": {"hooks":[{"text":"câu hook tự nhiên mạnh 0-3s, không tag, không chào hỏi","isRecommended":true},{"text":"hook 2 kiểu khác — phủ định hoặc câu hỏi","isRecommended":false},{"text":"hook 3 kiểu khác — nhận xét bất ngờ","isRecommended":false}]},',
        '  "section7": {"captions":["caption ≤100 ký tự + 1-2 emoji","caption 2","caption 3"]},',
        '  "section8": {"hashtags":["#tag1","#tag2","#tiktokshop"]},',
        '  "section4": {',
        '    "duration":"30s",',
        '    "hook":"câu hook ngắn (không tag)",',
        '    "voScript":"HOOK:\\nCâu hook mạnh, tự nhiên, không tag...\\n\\nVOICE OVER:\\nCâu 1 như đang trò chuyện...\\nCâu 2 tự nhiên tiếp theo...\\n\\nCTA:\\nCâu kêu gọi cuối tự nhiên...",',
        '    "lines":[{"type":"action","text":"hành động camera cụ thể khi voiceover câu 1"},{"type":"action","text":"hành động camera câu 2"}],',
        '    "rawScript":""',
        '  },',
        '  "section5": {"timeline":[{"timeRange":"0-3s","voice":"câu hook (không tag)","action":"hành động camera tương ứng"}]},',
        '  "section9": {"tips":["tip quay (im lặng hoàn toàn, tắt micro, ánh sáng)","tip edit lồng tiếng (sync audio, cut theo nhịp giọng)"]}',
        '}',
        '```',
        "",
        "Lưu ý cuối:",
        f"- voScript: KHÔNG được chứa bất kỳ [tag] nào. Chỉ lời thoại thuần túy.",
        f"- Viết đủ nội dung cho {duration_label}.",
        "- section5 timeline: 'voice' là lời thoại thuần (không tag), 'action' là hành động camera riêng biệt.",
        "- lines[]: số entry bằng số câu/đoạn trong voScript. Mô tả hành động cụ thể: cầm gì, góc máy, di chuyển.",
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
        "**Ảnh sản phẩm:** " + ("Phân tích ảnh sản phẩm:\n" + image_analysis if image_analysis else ("Đã đính kèm - hãy phân tích màu sắc, form dáng, chất liệu, chi tiết từ ảnh." if has_images else "Không có ảnh - tạo kịch bản dựa trên tên và mô tả.")),
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

        if shooting == 'voiceover':
            persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật.')
            hook_instruction = f' Câu đầu tiên PHẢI là hook đã cho, không được thay đổi: "{selected_hook}"' if selected_hook else ''
            user = f"""{base}{analysis_block}
{context_line}{hook_line}

Persona: {persona_guide}

Tạo voScript lời thoại thuần túy (ElevenLabs V3 Enhance tự thêm emotion — KHÔNG được viết tag [xxx] nào).{hook_instruction}

Quy tắc viết voScript:
- Viết như người đang NÓI, không phải viết văn
- Không mở đầu kiểu AI/MC: 'Xin chào', 'Hôm nay mình', 'Đây là sản phẩm', 'Sản phẩm này được...'
- Không dùng cấu trúc AI: 'Ngoài ra...', 'Đặc biệt...', 'Sản phẩm có...'
- Được dùng câu đệm, phản ứng, ngắt nghỉ, câu bỏ lửng
- Kết hợp câu ngắn, câu dài, câu hỏi, câu cảm thán
- HOOK 0-3s: câu mạnh nhất, đi thẳng vào vấn đề
- CTA cuối: tự nhiên, không ép mua

```json
{{"section4":{{"duration":"{duration_label}","hook":"{selected_hook or 'câu hook tự nhiên mạnh, không tag'}","voScript":"HOOK:\\nCâu hook mạnh tự nhiên không có tag...\\n\\nVOICE OVER:\\nCâu 1 như đang nói chuyện thật...\\nCâu 2 tự nhiên...\\n\\nCTA:\\nCâu kêu gọi cuối tự nhiên...","lines":[{{"type":"action","text":"hành động camera cụ thể câu 1"}},{{"type":"action","text":"hành động camera câu 2"}}],"rawScript":""}},"section5":{{"timeline":[{{"timeRange":"0-3s","voice":"câu hook thuần (không tag)","action":"hành động camera tương ứng"}}]}}}}
```"""
        else:
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
        if shooting == 'voiceover':
            persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật.')
            user = f"""{base}
{analysis}
{context_line}

Persona: {persona_guide}

Tạo 3 hook Voice Over khác nhau (0-3 giây đầu). Hook đầu tiên là hook khuyên dùng.

Quy tắc hook Voice Over:
- KHÔNG được có tag [xxx] nào — ElevenLabs V3 Enhance tự xử lý cảm xúc
- Không mở đầu kiểu AI/MC: 'Xin chào', 'Hôm nay mình', 'Đây là sản phẩm'
- Đi thẳng vào nội dung: gây tò mò / phủ định / câu hỏi / nhận xét bất ngờ
- Viết như người đang nói chuyện thật, không phải viết văn
- 3 hook phải 3 kiểu khác nhau hoàn toàn (tò mò / twist / pain point)

```json
{{"section3":{{"hooks":[{{"text":"hook 1 tự nhiên mạnh, không tag","isRecommended":true}},{{"text":"hook 2 kiểu khác, không tag","isRecommended":false}},{{"text":"hook 3 kiểu khác, không tag","isRecommended":false}}]}}}}
```"""
        else:
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
