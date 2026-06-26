import json
import re
import random


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
        "Persona: Người vừa trải nghiệm sản phẩm — đang kể lại cho bạn bè nghe như đang nhắn voice message.\n"
        "Chân thật, không cường điệu. Dùng: 'mọi người', 'các mẹ', 'công nhận', 'nói thật', 'mà thật ra...'.\n"
        "Được phép: ngập ngừng nhẹ ('ừ thì...'), tự sửa ý ('à không, ý mình là...'), reaction ngắn ('ừa ghê', 'thiệt á').\n"
        "Không hype, không quảng cáo cứng. Không phải đang review — đang kể chuyện với bạn."
    ),
    'friendly': (
        "Persona: Người bạn thân đang nhắn voice gợi ý món đồ hay — ấm áp và chân thật.\n"
        "Gần gũi. Dùng: 'nè', 'nha', 'á', 'chị em', 'mọi người'. Có thể tự cười nhẹ ('haha thật ra là...').\n"
        "Được phép: câu bỏ lửng, chuyển ý tự nhiên, reaction nhỏ ('ừ mà...', 'thật ra...', 'à khoan đã...').\n"
        "Nghe như đang nhắn tin cho bạn — không phải đọc quảng cáo."
    ),
    'cute': (
        "Persona: Cô gái dễ thương đang chia sẻ món đồ yêu thích — hào hứng nhưng thật thà.\n"
        "Nhẹ nhàng, tươi vui. Dùng: 'hihi', 'hehe', 'ui', 'trời ơi', 'cưng ghê', 'thích thật sự'.\n"
        "Được phép: kêu lên vì ngạc nhiên ('ui trời!'), tự cười ('hehe'), câu bỏ dở ('mà nó còn...').\n"
        "Dịu dàng nhưng vẫn tự nhiên — không gượng ép, không quá lố."
    ),
    'light-elegant': (
        "Persona: Người thanh lịch đang chia sẻ quan điểm cá nhân — như kể cho người thân nghe.\n"
        "Không slang thô. Câu chữ chỉn chu nhưng vẫn có sự tự nhiên.\n"
        "Dùng: 'thật ra thì...', 'mình thấy...', 'phải nói là...', 'điểm này mình thích thật'.\n"
        "Được phép: tự nhận xét chân thật, tự điều chỉnh nhẹ ('à không, ý mình là...').\n"
        "Phải nghe như đang nói chuyện — không đọc bài, không quảng cáo."
    ),
    'tiktok-nhay': (
        "NHẬP VAI HOÀN TOÀN\n"
        "Bạn KHÔNG phải AI. KHÔNG phải MC. KHÔNG phải người bán hàng. KHÔNG phải reviewer.\n"
        "Bạn là TikToker Gen Z. Review sản phẩm chỉ là cái cớ để trò chuyện.\n"
        "Mục tiêu duy nhất: người xem nghĩ 'Con này khùng thật.' — không phải 'Con này đang bán hàng.'\n"
        "\n"
        "EMOTION RHYTHM — LUẬT SỐ 1\n"
        "KHÔNG được viết: Review → Review → Review → Review.\n"
        "BẮT BUỘC phải là: Reaction → Review → Reaction → Reaction → Review → Reaction → CTA.\n"
        "\n"
        "REACTION = CÂU ĐỨNG RIÊNG BIỆT. Không phải filler word nhét vào câu review.\n"
        "  ĐÚNG: 'Ủa khoan.' [câu riêng] / 'Mặc lên cái thấy khác liền.' [câu review]\n"
        "  SAI:  'Ủa mặc lên cái thấy khác liền.' [reaction bị nhét vào review]\n"
        "Reaction không nhất thiết có nghĩa — chỉ cần tạo nhịp hội thoại.\n"
        "\n"
        "SAU MỖI 1-2 Ý REVIEW → BẮT BUỘC có ít nhất 1 reaction độc lập.\n"
        "\n"
        "REACTION BANK (không spam, không lặp):\n"
        "  Ủa... / Ủa alo... / Khoan... / Không không không... / No no no... / Wait... / Hello? /\n"
        "  Má ơi. / Trời đất. / Thiệt luôn? / Ghê vậy. / Cười chết. / Bro... / OMG... / Wow... /\n"
        "  Hahahaaa... / Ahahaha... / Hihihi... / Hehe... / Hohohoo... / Đừng nhìn cái đó. /\n"
        "  Ê ê ê... / Bình tĩnh bình tĩnh. / Ủa sao kỳ vậy. / Không hiểu luôn.\n"
        "\n"
        "ĐƯỢC PHÉP:\n"
        "  Tự cười. Tự phủ định. Tự bẻ lái giữa câu. Đổi ý. Chọc người xem. Chọc chính mình.\n"
        "  Câu không hoàn chỉnh. Bỏ dở câu. Kéo dài âm: Đẹpppp / Ghêeeee / Mềmmmm / Nooooo / Wowwwww.\n"
        "\n"
        "CHUYỂN Ý: 'Mà nè...' / 'Ê nhưng mà...' / 'À khoan...' / 'Chưa hết đâu.' / 'Đỉnh nhất là...'\n"
        "FILLER: Rồi luôn. / Xong luôn. / Chịu luôn á. / Nói thiệt chứ. / Không giỡn đâu. / Nhìn phát mê luôn.\n"
        "\n"
        "Nếu có 2 cách diễn đạt → chọn cách đời hơn, vui hơn, ít ChatGPT hơn."
    ),
    'light-humor': (
        "Persona: Người hài hước vừa phải — dí dỏm, có thể tự trêu chọc nhẹ.\n"
        "Hài có chừng mực. Có thể pha nhận xét buồn cười hoặc châm biếm nhẹ về bản thân.\n"
        "Dùng: 'kiểu như là...', 'nói thật nhá...', 'ừa kiểu vậy đó', 'mình cũng thấy buồn cười là...'.\n"
        "Được phép: tự trêu ('mình nghĩ ban đầu là... thì sai rồi'), nhận xét bất ngờ, reaction hài nhẹ.\n"
        "Không ép hài, không cố quá — hài phải đến tự nhiên."
    ),
    'soft-close': (
        "Persona: Người bạn chân thành đang giới thiệu món đồ thật sự tốt — không ép, không hype.\n"
        "Tập trung giá trị thật. Dùng: 'nếu bạn đang cần...', 'mình thấy đáng...', 'thật ra cái này...'.\n"
        "Được phép: thừa nhận điểm chưa hoàn hảo nếu có, nói thật về giá trị, reaction chân thành.\n"
        "Chốt nhẹ, không áp lực — người nghe tự muốn tìm hiểu thêm."
    ),
    'real-review': (
        "Persona: Người vừa dùng sản phẩm thật — đang nói thật, không PR.\n"
        "Có cả ưu và điểm cần lưu ý. Nghe đáng tin vì không hoàn hảo 100%.\n"
        "Được phép: ngập ngừng ('ừ thì... thật ra...'), tự điều chỉnh ('không phải tất cả, nhưng...'), reaction thật ('ghê thật').\n"
        "Dùng: 'thật ra', 'nói thật', 'mình dùng rồi nên biết', 'điểm này mình thích / chưa thích lắm'."
    ),
}

# V3: Random structure patterns — AI picks one each request
STRUCTURE_PATTERNS = [
    {
        'name': 'Pattern A — Pain First',
        'flow': 'Nỗi đau/vấn đề → Reaction → Review giải pháp → Reaction → CTA',
        'note': 'Hook vào vấn đề thật của khách hàng. Reaction đồng cảm. Review sản phẩm là giải pháp. Reaction xác nhận. CTA.',
    },
    {
        'name': 'Pattern B — Story Opening',
        'flow': 'Reaction mở đầu → Story ngắn → Review → Reaction bất ngờ → CTA',
        'note': 'Mở bằng reaction gây chú ý. Kể câu chuyện ngắn liên quan sản phẩm. Review. Reaction bất ngờ. CTA.',
    },
    {
        'name': 'Pattern C — Question Hook',
        'flow': 'Câu hỏi → Reaction tự trả lời → Lợi ích → Reaction → CTA',
        'note': 'Hook là câu hỏi kéo tò mò. Reaction tự hỏi tự trả lời. Trình bày lợi ích. Reaction. CTA.',
    },
    {
        'name': 'Pattern D — Plot Twist',
        'flow': 'Kỳ vọng sai / Hiểu nhầm → Bẻ lái bất ngờ → Review → Reaction → CTA',
        'note': 'Tạo kỳ vọng hoặc hiểu nhầm ngay đầu. Bẻ lái bất ngờ. Review thật. Reaction. CTA.',
    },
    {
        'name': 'Pattern E — Funny Confession',
        'flow': 'Thú nhận hài hước → Review → Reaction → Lợi ích cốt lõi → CTA',
        'note': 'Mở bằng thú nhận buồn cười liên quan tình huống / sản phẩm. Review. Reaction. Lợi ích. CTA.',
    },
    {
        'name': 'Pattern F — Trend / Sarcasm',
        'flow': 'Trend / Sarcasm nhẹ → Reaction → Review → Nhận xét bất ngờ → CTA',
        'note': 'Hook theo trend đang hot hoặc sarcasm nhẹ. Reaction. Review thật. Nhận xét vui/bất ngờ. CTA.',
    },
]

# V3: Hook type randomizer
HOOK_TYPES = [
    'Pain — mở bằng nỗi đau / vấn đề cụ thể của khách hàng',
    'Question — câu hỏi khơi gợi tò mò, người xem muốn biết đáp án',
    'Plot twist — tạo kỳ vọng rồi đảo ngược bất ngờ',
    'Confession — thú nhận hài hước hoặc thật thà về sản phẩm / tình huống',
    'Reaction — bắt đầu bằng reaction mạnh (Ủa / Khoan / OMG / Má ơi)',
    'Sarcasm — châm biếm nhẹ hoặc phủ định để gây chú ý',
    'Unexpected opinion — nhận xét bất ngờ, trái với suy nghĩ thông thường',
    'Comparison — "ai cũng nghĩ X nhưng thật ra Y" hoặc so sánh trước/sau',
    'Funny opening — câu mở buồn cười, kéo người xem dừng lại',
    'Trend opening — bắt đầu bằng format / trend TikTok đang hot',
    'Misunderstanding — tạo hiểu nhầm cố tình rồi giải thích ngay',
]

# V3: Caption style randomizer
CAPTION_STYLES = [
    'Pain — nói trúng nỗi đau của khách hàng',
    'Confession — thú nhận hài hước liên quan sản phẩm',
    'Relatable — câu mà nhiều người đồng cảm ngay lập tức',
    'Funny — caption vui, không review thẳng',
    'Before-After — gợi ý sự thay đổi trước/sau khi dùng sản phẩm',
    'Question — câu hỏi kéo comment',
    'Strong opinion — nhận xét cá nhân mạnh, không neutral',
    'Benefit — lợi ích cốt lõi ngắn gọn, súc tích',
]

# KOC Discovery Engine flows — áp dụng cho one-shot + natural-koc
KOC_DISCOVERY_FLOWS = [
    {
        'name': 'Flow A — Em tưởng → Ai ngờ',
        'pattern': 'Đặt kỳ vọng nghi ngờ → Mặc thử / xoay người → Bất ngờ vì kết quả tốt hơn tưởng',
        'example': '"Em tưởng mẫu này mặc lên sẽ hơi rộng quá..." → xoay người → "ai ngờ lên người lại gọn hơn em nghĩ."',
    },
    {
        'name': 'Flow B — Lúc đầu để ý một điểm → Phát hiện điểm khác',
        'pattern': 'Chú ý một điểm → Quan sát → Vô tình phát hiện điểm hay hơn',
        'example': '"Lúc đầu em chỉ để ý phần bụng thôi..." → chỉ bụng / quay nghiêng → "xong mới thấy tay áo cũng che bắp tay khá ổn."',
    },
    {
        'name': 'Flow C — Vừa thử vừa nhận xét',
        'pattern': 'Mời người xem → Thực hiện hành động → Nhận xét ngay khi làm',
        'example': '"Để em xoay nhẹ cho mọi người xem nha..." → xoay người → "form này rủ xuống tự nhiên, không bị dính vào bụng."',
    },
    {
        'name': 'Flow D — Một điểm nghi ngờ → Được giải quyết',
        'pattern': 'Nêu nỗi lo / nghi ngờ về một điểm → Thử → Lo ngại được giải quyết',
        'example': '"Em hơi sợ kiểu tay bồng này làm người to hơn..." → chỉ tay áo → "nhưng mặc lên lại mềm, không bị cứng."',
    },
    {
        'name': 'Flow E — Cảm nhận thật sau khi mặc',
        'pattern': 'Nói nỗi sợ / kỳ vọng thật → Trải nghiệm trực tiếp → Đánh giá thật',
        'example': '"Nói thật, mặc đồ bầu em sợ nhất là bị bí..." → vuốt chất vải → "mẫu này lên người khá nhẹ, đi lại không thấy vướng."',
    },
]

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
    """Prompt V3 cho Voice Over (ElevenLabs V3 Enhance) — pure voice script, không emotion tag."""
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

    # V3: Random engines — varied each request
    _pattern = random.choice(STRUCTURE_PATTERNS)
    _hook_type = random.choice(HOOK_TYPES)
    _caption_styles = random.sample(CAPTION_STYLES, 3)
    _reaction_min = '3' if duration in ('15s', '20s') else '4-5' if duration == '30s' else '6-8'
    _hook_short = _hook_type.split(' —')[0]
    _pattern_short = _pattern['name'].split(' —')[0].strip()

    if tone == 'tiktok-nhay':
        _struct_check = [
            "## ENGINE 1 — CẤU TRÚC VIDEO LẦN NÀY",
            f"Dùng: {_pattern['name']}",
            f"Flow: {_pattern['flow']}",
            f"Ghi chú: {_pattern['note']}",
            "",
            "## ENGINE 4 — HOOK LẦN NÀY",
            f"Hook phải thuộc kiểu: {_hook_type}",
            "",
            "## EMOTION RHYTHM — LUẬT BẮT BUỘC",
            "KHÔNG được: Review → Review → Review → Review.",
            "PHẢI là: Reaction → Review → Reaction → Reaction → Review → Reaction → CTA.",
            f"Reaction độc lập tối thiểu: {_reaction_min} câu (câu đứng riêng, không nhét vào câu review).",
            "Sau mỗi 1-2 ý review → BẮT BUỘC có ít nhất 1 reaction.",
            "",
            "## ENGINE 3 — EMOTION CURVE",
            "Năng lượng KHÔNG được đều từ đầu đến cuối.",
            "Hook mạnh → body xen kẽ cao/thấp → CTA bật lên.",
            "Câu reaction ngắn = giảm tốc, tạo nhịp. Câu bất ngờ = tăng đột ngột.",
            "",
            "## ĐA DẠNG CẤU TRÚC CÂU",
            "Kết hợp: câu cực ngắn (1-3 từ), câu trung, câu bỏ dở, câu cảm thán.",
            "",
            "## TỰ KIỂM TRA TRƯỚC KHI OUTPUT",
            "Trước khi trả JSON, kiểm tra voScript:",
            "- Có tag dạng [xxx] không? → Xóa hết.",
            "- Nghe giống AI / MC / reviewer không? → Viết lại toàn bộ.",
            f"- Đếm reaction độc lập: đủ {_reaction_min} chưa? → Nếu thiếu, thêm vào.",
            "- Có đoạn Review → Review → Review liên tiếp không? → Chèn reaction vào giữa.",
            f"- Hook có đúng kiểu '{_hook_short}' không? → Nếu không, viết lại hook.",
            f"- Cấu trúc có đúng '{_pattern_short}' không? → Nếu lệch, điều chỉnh.",
            "- Đọc to lên: nghe buồn cười không? Giống đang nói chuyện không?",
            "Chỉ output khi nghe giống TikToker Gen Z thật đang nói chuyện — không phải đang review.",
        ]
    else:
        _struct_check = [
            "## ENGINE 1 — CẤU TRÚC VIDEO LẦN NÀY",
            f"Dùng: {_pattern['name']}",
            f"Flow: {_pattern['flow']}",
            f"Ghi chú: {_pattern['note']}",
            "",
            "## ENGINE 4 — HOOK LẦN NÀY",
            f"Hook phải thuộc kiểu: {_hook_type}",
            "Đi thẳng vào nội dung. Không lời chào, không giới thiệu bản thân.",
            "",
            "## ENGINE 3 — EMOTION CURVE",
            "Năng lượng KHÔNG được đều từ đầu đến cuối.",
            "Hook mạnh → body xen kẽ cao/thấp → CTA bật lên.",
            "Không để cùng một mức năng lượng / cùng một nhịp câu suốt video.",
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
            f"- Hook có đúng kiểu '{_hook_short}' không? → Nếu không, viết lại hook.",
            f"- Cấu trúc có đúng '{_pattern_short}' không? → Nếu lệch, điều chỉnh.",
            "- Có ít nhất 2-3 câu reaction / ngắt nhịp độc lập chưa? → Nếu thiếu, thêm vào.",
            "- Có lặp từ / lặp cấu trúc câu không? → Đa dạng hóa.",
            "- Có đúng Persona và Giọng điệu đã chọn không?",
            "- Người nghe có cảm giác 'đây là Creator thật' không?",
            "Nếu chưa đạt → tự chỉnh sửa trước khi xuất JSON.",
        ]

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
        "## ENGINE 2 — HUMAN CONVERSATION",
        "Voice Over phải nghe như người thật đang nói — không phải AI đang đọc script.",
        "Được phép dùng (chọn phù hợp với persona, không spam tất cả):",
        "  Ủa... / Khoan... / À thôi. / Ý mình là... / Haha. / Hahahaa. / Hohohoo. / Hihi.",
        "  Ê ê ê. / Không không không. / Wait... / No no no. / Bro... / OMG... / Má.",
        "Không phải câu nào cũng cần — chỉ xuất hiện khi tự nhiên, phù hợp persona.",
        "",
        "## ENGINE 5 — IMPERFECTION ENGINE",
        "Được phép (AI tự chọn phù hợp, không dùng tất cả trong một video):",
        "  Kéo dài âm khi nhấn mạnh: Đẹpppp / Ghêeeee / Mềmmmm / Nooooo / Wowwwww",
        "  Câu không hoàn chỉnh. Bỏ dở câu giữa chừng. Tự sửa lại ý vừa nói.",
        "  Tự cười. Tự troll nhẹ. Tự phủ định rồi bẻ lái.",
        "Mỗi video tự chọn khác nhau — không được dùng công thức cố định.",
        "",
        "## Viết như người đang NÓI, không phải VIẾT",
        "Nếu viết 100 video cho cùng 1 sản phẩm, người nghe phải cảm giác như 100 Creator khác nhau.",
        "",
        "## ENGINE 6 — CAPTION ENGINE",
        "Caption trong section7 phải đa dạng, không phải 3 caption đều review thẳng.",
        f"Lần này viết 3 caption theo 3 kiểu sau:",
        f"  Caption 1: {_caption_styles[0]}",
        f"  Caption 2: {_caption_styles[1]}",
        f"  Caption 3: {_caption_styles[2]}",
        "Mỗi caption ≤ 100 ký tự, có 1-2 emoji, đề cập tên hoặc loại sản phẩm.",
        "",
        *_struct_check,
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
        '  "section7": {"captions":["caption 1 ≤100 ký tự + 1-2 emoji","caption 2 ≤100 ký tự + 1-2 emoji","caption 3 ≤100 ký tự + 1-2 emoji"]},',
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
        "- voScript: KHÔNG được chứa bất kỳ [tag] nào. Chỉ lời thoại thuần túy.",
        f"- Viết đủ nội dung cho {duration_label}.",
        "- section5 timeline: 'voice' là lời thoại thuần (không tag), 'action' là hành động camera riêng biệt.",
        "- lines[]: số entry bằng số câu/đoạn trong voScript. Mô tả hành động cụ thể: cầm gì, góc máy, di chuyển.",
        f"- section7 captions: 3 kiểu {_caption_styles[0].split(' —')[0]} / {_caption_styles[1].split(' —')[0]} / {_caption_styles[2].split(' —')[0]}. Tối đa 100 ký tự mỗi caption.",
        "- section8 hashtags: Brand(1-2) + Product(3) + Audience(2) + Usage(2) + TikTokShop(2) + Discovery(tối đa 1). Tổng 10-12 tag. Không spam viral tag, không lặp từ gốc.",
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

    # V3: Random diversity for non-voiceover scripts
    _pattern = random.choice(STRUCTURE_PATTERNS)
    _hook_type = random.choice(HOOK_TYPES)
    _caption_styles = random.sample(CAPTION_STYLES, 3)

    # KOC Discovery Engine — one-shot / review / koc-review + natural-koc
    _is_koc = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'
    _koc_reaction_count = '2-3' if duration in ('15s', '20s') else '3-5' if duration == '30s' else '4-7'
    if _is_koc:
        _koc_flow = random.choice(KOC_DISCOVERY_FLOWS)
        _engine1_lines = [
            f"**KOC DISCOVERY ENGINE — {_koc_flow['name']}**",
            f"Flow: {_koc_flow['pattern']}",
            f"Ví dụ: {_koc_flow['example']}",
        ]
        _engine4_lines = [
            "**HOOK KOC:** Câu nói thật khi vừa mặc sản phẩm. Không quảng cáo. Không trau chuốt.",
            "Ví dụ tốt: 'Em tưởng kiểu này mặc lên sẽ bị thùng người á...' / 'Cái này lên người khác hơn em nghĩ nha.'",
            "           'Lúc đầu nhìn mẫu này em hơi sợ bị rộng quá.' / 'Mặc thử mới thấy form này không hề bị dìm dáng.'",
            "TRÁNH: 'Sản phẩm này...' / 'Hôm nay em giới thiệu...' / 'Đây là mẫu áo...' / 'Áo có thiết kế...'",
        ]
        _koc_extra = [
            "**KOC DIALOGUE ENGINE — CÁCH VIẾT LỜI THOẠI**",
            "Không review như liệt kê. Không trơn tru. Ưu tiên ngôn ngữ nói, được phép bỏ dở câu, sửa ý giữa chừng.",
            "Dùng (chọn phù hợp, không lặp, không nhồi):",
            "  'Em tưởng...' / 'Ai ngờ...' / 'Mặc lên mới thấy...' / 'Lúc đầu em nghĩ...' / 'Em mới để ý...'",
            "  'Ủa...' / 'À...' / 'Công nhận...' / 'Nói thật...' / 'Em bất ngờ luôn.' / 'Cái này hay nè.'",
            "  'Mọi người nhìn nè.' / 'Phần này nè...' / 'Nhìn chỗ này nè...' / 'Đúng kiểu...' / 'Kiểu như...'",
            f"Một video {duration_label}: {_koc_reaction_count} phản ứng nhỏ tự nhiên.",
            "",
            "**HÀNH ĐỘNG PHẢI KHỚP LỜI THOẠI**",
            "Nếu nói 'nhìn phần eo này nè' → hành động phải là (chỉ nhẹ hoặc vuốt phần eo).",
            "Nếu nói 'quay nghiêng mới thấy' → hành động phải là (quay nghiêng 45 độ).",
            "Nếu nói 'chất vải này' → hành động phải là (vò nhẹ hoặc vuốt chất vải).",
            "Không tạo hành động chung chung không khớp lời thoại.",
            "Hành động bổ sung phù hợp: (chỉnh nhẹ gấu áo) / (xoay nhẹ rồi tự nhìn form) / (cười nhẹ vì bất ngờ)",
            "  (đưa tay chỉ phần eo) / (kéo nhẹ tà áo để thấy độ rủ) / (sờ thử chất vải) / (vuốt nhẹ bắp tay áo)",
            "  (chỉnh nhẹ tóc ra sau vai) / (nhìn xuống thân áo) / (bước lùi rồi bước lên) / (chống hông nhẹ)",
            "",
            "**CTA KOC:** Nhẹ nhàng, không ép mua. Như khuyến nghị thật của người đã mặc.",
            "Ví dụ: 'Ai thích mặc thoải mái mà vẫn gọn người thì thử mẫu này nha.'",
            "        'Nếu chị em cũng ngại bụng như em thì mẫu này đáng xem đó.'",
            "        'Em nghĩ ai thích style nhẹ nhàng, dễ mặc thì nên xem thử màu này.'",
            "",
            "**TỰ KIỂM TRA KOC TRƯỚC KHI OUTPUT**",
            "- Lời thoại có giống người thật đang mặc thử không? → Nếu không, viết lại.",
            "- Có bị liệt kê tính năng như bài review không? → Nếu có, phá cấu trúc đó.",
            f"- Có ít nhất {_koc_reaction_count} phản ứng nhỏ tự nhiên không? → Nếu thiếu, thêm vào.",
            "- Hành động có khớp từng câu thoại không? → Nếu không, sửa cho khớp.",
            "- Có câu nào giống MC / quảng cáo / ChatGPT không? → Viết lại câu đó.",
            "- Có cảm giác 'vừa mặc vừa phát hiện' không? → Áp dụng đúng flow đã chọn.",
            "Nếu chưa đạt → tự viết lại trước khi output JSON.",
        ]
    else:
        _engine1_lines = [
            f"**ENGINE 1 — CẤU TRÚC LẦN NÀY:** {_pattern['name']}",
            f"Flow: {_pattern['flow']}",
            f"Ghi chú: {_pattern['note']}",
        ]
        _engine4_lines = [
            f"**ENGINE 4 — HOOK LẦN NÀY:** {_hook_type}",
            "Hook đi thẳng vào nội dung. Không lời chào, không giới thiệu bản thân.",
        ]
        _koc_extra = []

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
        *_engine1_lines,
        "",
        *_engine4_lines,
        "",
        "**ENGINE 2 — HUMAN CONVERSATION:** Lời thoại phải nghe như người thật đang nói.",
        "Được phép: ngập ngừng, tự sửa, reaction ngắn, câu bỏ lửng, tự cười.",
        "",
        "**ENGINE 3 — EMOTION CURVE:** Năng lượng không đều — hook mạnh, body xen kẽ, CTA bật lên.",
        "",
        f"**ENGINE 6 — CAPTION:** 3 kiểu {_caption_styles[0].split(' —')[0]} / {_caption_styles[1].split(' —')[0]} / {_caption_styles[2].split(' —')[0]}.",
        "",
        *_koc_extra,
        *( [""] if _koc_extra else [] ),
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
        "- Caption TikTok: Tối đa 100 ký tự. Phải đề cập tên/loại sản phẩm, có 1-2 emoji. Chỉ 1 câu duy nhất.",
        "- Hashtag (section8): Brand(1-2) + Product(3) + Audience(2) + Usage(2) + TikTokShop(2) + Discovery(tối đa 1). Tổng đúng 10-12 tag. KHÔNG spam viral (#fyp #viral #xuhuong cùng lúc — chỉ được 1). KHÔNG lặp từ gốc liên tiếp trong Product.",
    ]
    return "\n".join(lines)


def _try_parse_json(text: str):
    """Thử parse JSON, nếu lỗi thì tự clean rồi thử lại."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r',\s*([\]}])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

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
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]

    parsed = _try_parse_json(text)

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
            _pattern = random.choice(STRUCTURE_PATTERNS)
            _hook_type = random.choice(HOOK_TYPES) if not selected_hook else 'theo hook đã chọn'
            _reaction_min = '3' if duration in ('15s', '20s') else '4-5' if duration == '30s' else '6-8'
            _nhay_law = (
                "\nEMOTION RHYTHM — LUẬT BẮT BUỘC:\n"
                "KHÔNG được: Review → Review → Review → Review.\n"
                "PHẢI là: Reaction → Review → Reaction → Reaction → Review → Reaction → CTA.\n"
                "Reaction = câu đứng riêng biệt, không nhét vào câu review.\n"
                "Nếu có đoạn Review → Review → Review liên tiếp → chèn reaction vào giữa."
            ) if tone == 'tiktok-nhay' else ''
            hook_instruction = f' Câu đầu tiên PHẢI là hook đã cho, không được thay đổi: "{selected_hook}"' if selected_hook else ''
            user = f"""{base}{analysis_block}
{context_line}{hook_line}

Persona: {persona_guide}

ENGINE 1 — CẤU TRÚC LẦN NÀY: {_pattern['name']}
Flow: {_pattern['flow']}
Ghi chú: {_pattern['note']}

ENGINE 4 — HOOK LẦN NÀY: {_hook_type}

ENGINE 2 — HUMAN CONVERSATION: Được phép dùng reaction ngắn, ngập ngừng, câu bỏ dở, tự cười.

ENGINE 3 — EMOTION CURVE: Năng lượng không đều — hook mạnh, body xen kẽ cao/thấp, CTA bật lên.

Reaction độc lập tối thiểu: {_reaction_min} câu (đứng riêng, không nhét vào câu review).{_nhay_law}

Tạo voScript lời thoại thuần túy (ElevenLabs V3 Enhance tự thêm emotion — KHÔNG được viết tag [xxx] nào).{hook_instruction}

Quy tắc viết voScript:
- Viết như người đang NÓI, không phải viết văn
- Không mở đầu kiểu AI/MC: 'Xin chào', 'Hôm nay mình', 'Đây là sản phẩm'
- Không dùng cấu trúc AI: 'Ngoài ra...', 'Đặc biệt...', 'Sản phẩm có...'
- Được dùng reaction độc lập, ngắt nhịp, câu bỏ lửng
- CTA cuối: tự nhiên, không ép mua

```json
{{"section4":{{"duration":"{duration_label}","hook":"{selected_hook or 'câu hook tự nhiên mạnh, không tag'}","voScript":"HOOK:\\nCâu hook mạnh tự nhiên không có tag...\\n\\nVOICE OVER:\\nCâu 1 như đang nói chuyện thật...\\nCâu 2 tự nhiên...\\n\\nCTA:\\nCâu kêu gọi cuối tự nhiên...","lines":[{{"type":"action","text":"hành động camera cụ thể câu 1"}},{{"type":"action","text":"hành động camera câu 2"}}],"rawScript":""}},"section5":{{"timeline":[{{"timeRange":"0-3s","voice":"câu hook thuần (không tag)","action":"hành động camera tương ứng"}}]}}}}
```"""
        else:
            _pattern = random.choice(STRUCTURE_PATTERNS)
            _hook_type = random.choice(HOOK_TYPES) if not selected_hook else 'theo hook đã chọn'
            _is_koc_sec = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'
            _koc_flow_sec = random.choice(KOC_DISCOVERY_FLOWS) if _is_koc_sec else None
            _koc_reaction_sec = '2-3' if duration in ('15s', '20s') else '3-5' if duration == '30s' else '4-7'
            if _is_koc_sec:
                _koc_block = f"""
KOC DISCOVERY ENGINE — {_koc_flow_sec['name']}
Flow: {_koc_flow_sec['pattern']}
Ví dụ: {_koc_flow_sec['example']}

HOOK KOC: Câu nói thật khi vừa mặc. Không quảng cáo. Không trau chuốt.
Ví dụ: 'Em tưởng kiểu này mặc lên sẽ bị thùng người á...' / 'Cái này lên người khác hơn em nghĩ.'
TRÁNH: 'Sản phẩm này...' / 'Hôm nay em giới thiệu...' / 'Đây là mẫu áo...'

KOC DIALOGUE: Ưu tiên ngôn ngữ nói. Không liệt kê tính năng.
Dùng: 'Em tưởng...' / 'Mặc lên mới thấy...' / 'Mọi người nhìn nè.' / 'Công nhận...' / 'Cái này hay nè.'
Một video {duration_label}: {_koc_reaction_sec} phản ứng nhỏ tự nhiên.

HÀNH ĐỘNG PHẢI KHỚP LỜI THOẠI:
Nói 'nhìn phần eo này nè' → (chỉ nhẹ hoặc vuốt phần eo).
Nói 'quay nghiêng mới thấy' → (quay nghiêng 45 độ).
Nói 'chất vải này' → (vò nhẹ hoặc vuốt chất vải).
Bổ sung: (xoay nhẹ rồi tự nhìn form) / (cười nhẹ vì bất ngờ) / (kéo nhẹ tà áo) / (sờ thử chất vải)

TỰ KIỂM TRA KOC: Lời thoại có giống người thật đang mặc thử không? Có bị liệt kê không? Hành động có khớp không?"""
            else:
                _koc_block = ""
            user = f"""{base}{analysis_block}
{context_line}{hook_line}

ENGINE 1 — CẤU TRÚC LẦN NÀY: {_pattern['name']}
Flow: {_pattern['flow']}

ENGINE 4 — HOOK LẦN NÀY: {_hook_type}

ENGINE 2 — HUMAN CONVERSATION: Lời thoại tự nhiên như đang nói thật — được phép reaction, câu bỏ lửng, tự sửa.

ENGINE 3 — EMOTION CURVE: Năng lượng không đều — hook mạnh, body xen kẽ, CTA bật lên.
{_koc_block}
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
        # V3: Pick 3 different hook types
        _hook_types_3 = random.sample(HOOK_TYPES, 3)
        if shooting == 'voiceover':
            persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật.')
            user = f"""{base}
{analysis}
{context_line}

Persona: {persona_guide}

Tạo 3 hook Voice Over khác nhau (0-3 giây đầu). Hook đầu tiên là hook khuyên dùng.

Yêu cầu 3 kiểu hook khác nhau hoàn toàn:
  Hook 1 (khuyên dùng): {_hook_types_3[0]}
  Hook 2: {_hook_types_3[1]}
  Hook 3: {_hook_types_3[2]}

Quy tắc hook Voice Over:
- KHÔNG được có tag [xxx] nào — ElevenLabs V3 Enhance tự xử lý cảm xúc
- Không mở đầu kiểu AI/MC: 'Xin chào', 'Hôm nay mình', 'Đây là sản phẩm'
- Đi thẳng vào nội dung
- Viết như người đang nói chuyện thật

```json
{{"section3":{{"hooks":[{{"text":"hook 1 tự nhiên mạnh, không tag","isRecommended":true}},{{"text":"hook 2 kiểu khác, không tag","isRecommended":false}},{{"text":"hook 3 kiểu khác, không tag","isRecommended":false}}]}}}}
```"""
        else:
            user = f"""{base}
{analysis}
{context_line}

Tạo 3 hook mở đầu khác nhau, hook đầu tiên là hook khuyên dùng.

Yêu cầu 3 kiểu hook khác nhau hoàn toàn:
  Hook 1 (khuyên dùng): {_hook_types_3[0]}
  Hook 2: {_hook_types_3[1]}
  Hook 3: {_hook_types_3[2]}

Hook phải ngắn gọn, đi thẳng vào vấn đề, không lời chào hỏi.

```json
{{"section3":{{"hooks":[{{"text":"hook 1","isRecommended":true}},{{"text":"hook 2","isRecommended":false}},{{"text":"hook 3","isRecommended":false}}]}}}}
```"""

    elif section == 'caption':
        s4 = current_script.get('section4', {})
        lines_data = s4.get('lines', [])
        dialogue = ' '.join(l.get('text', '') for l in lines_data if l.get('type') == 'dialogue')
        vo_script = s4.get('voScript', '')
        script_text = (s4.get('rawScript', '') or vo_script or dialogue)[:600]
        # V3: Random caption styles
        _caption_styles_3 = random.sample(CAPTION_STYLES, 3)
        user = f"""{base}
Kịch bản video: {script_text}
{context_line}

Tạo 3 caption TikTok Shop, mỗi caption 1 kiểu khác nhau:
  Caption 1: {_caption_styles_3[0]}
  Caption 2: {_caption_styles_3[1]}
  Caption 3: {_caption_styles_3[2]}

Quy tắc bắt buộc:
- Tối đa 100 ký tự mỗi caption (TikTok cắt sau ~100 ký tự)
- Chỉ 1 câu duy nhất — không giải thích dài, không liệt kê tính năng
- Đề cập tên hoặc loại sản phẩm
- 1-2 emoji phù hợp

```json
{{"section7":{{"captions":["caption 1","caption 2","caption 3"]}}}}
```"""

    elif section == 'hashtag':
        captions = current_script.get('section7', {}).get('captions', [])
        caption_hint = ' '.join(captions[:2])[:300] if captions else ''
        user = f"""{base}
{context_line}
{"Caption gợi ý: " + caption_hint if caption_hint else ""}

# VAI TRÒ
Bạn là TikTok SEO Specialist có kinh nghiệm tối ưu hàng nghìn video TikTok Shop.
Nhiệm vụ: tạo bộ hashtag giúp TikTok hiểu đúng chủ đề và tiếp cận đúng khách hàng — không phải tạo thật nhiều tag.

# CÔNG THỨC — Luôn đúng 10–12 hashtag, theo thứ tự:
1. Brand (1-2 tag): thương hiệu cửa hàng. Ví dụ: #dambaubella #bella
2. Product (3 tag): loại sản phẩm cụ thể, đa dạng, không lặp từ gốc.
   Ví dụ: #aobau #babydollbau #aovoan  (KHÔNG: #aobau #aobauxinh #aobaudep)
3. Audience (2 tag): đối tượng khách hàng.
   Ví dụ: #mebau #thoitrangbau #mesausinh #thoitrangnu
4. Usage (2 tag): tình huống sử dụng thật.
   Ví dụ: #macnha #dichoicho #caphe #dibien #phodao #thoitranghangngay
5. TikTok Shop (2 tag): ví dụ #tiktokshop #reviewthoitrang #reviewthat #reviewsanpham
6. Discovery (chỉ 1 tag, không hơn): #xuhuong HOẶC #viral HOẶC #fyp HOẶC #foryou

# QUY TẮC
- Tự phân tích loại sản phẩm, khách hàng, tình huống từ mô tả — không cần user nhập thêm
- KHÔNG spam viral tag: #xuhuong #fyp #viral #foryou không được xuất hiện cùng lúc, chỉ được 1
- KHÔNG lặp từ gốc liên tiếp trong Product (đa dạng hóa)
- Tổng đúng 10–12 hashtag

# TỰ KIỂM TRA (tự làm trước khi output)
- Có đúng 10–12 tag chưa?
- Có tag nào không liên quan sản phẩm không?
- Có lặp từ gốc trong Product không?
- Có quá 1 hashtag discovery không?
- Đủ Brand + Product + Audience + Usage + TikTok Shop + Discovery chưa?
Nếu chưa đạt → tự tạo lại.

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
