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
    'one-shot': 'One Shot', 'review': 'Review sản phẩm',
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
    'tiktok-nhay': (
        "Nhây nhây, tăng động, khùng tự nhiên — như đang livestream tám chuyện với hội bạn. "
        "Reaction trước, review sau. Nói chưa hết câu cũng được. Hay cười ngắt giữa chừng. "
        "Hook có twist hoặc sarcasm nhẹ. Gọi người xem: 'tụi bay' 'mấy bà' 'các vợ' 'chúng mày'."
    ),
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
        "Bạn là TikToker Việt thật — đang tám chuyện hoặc livestream cùng hội bạn.\n"
        "Review sản phẩm chỉ là cái cớ để vui miệng nói chuyện.\n"
        "Mục tiêu: người xem nghĩ 'Con này khùng thật.' — không phải 'Con này đang bán hàng.'\n"
        "\n"
        "EMOTION RHYTHM — LUẬT SỐ 1\n"
        "KHÔNG được viết: Review → Review → Review → Review liên tiếp.\n"
        "SAU MỖI 1-2 Ý REVIEW → BẮT BUỘC có ít nhất 1 nhịp cảm xúc.\n"
        "Nhịp cảm xúc CÓ THỂ là: reaction độc lập / đoạn cười / lẩm bẩm / đổi ý / bẻ lái.\n"
        "Mạch nói phải giống TikToker thật — không phải AI điền template.\n"
        "\n"
        "REACTION = CÂU ĐỨNG RIÊNG BIỆT. Không phải filler word nhét vào câu review.\n"
        "  ĐÚNG: 'Ủa khoan.' [câu riêng] / 'Mặc lên cái thấy khác liền.' [câu review]\n"
        "  SAI:  'Ủa mặc lên cái thấy khác liền.' [reaction bị nhét vào review]\n"
        "\n"
        "SỐ REACTION TỐI THIỂU (câu đứng riêng):\n"
        "  15s-20s → 3 reaction\n"
        "  30s     → 4-5 reaction\n"
        "  45s-60s → 6-8 reaction\n"
        "\n"
        "REACTION BANK — dùng theo cảm xúc câu chuyện, KHÔNG spam, KHÔNG lặp:\n"
        "\n"
        "  NHÓM CƯỜI:\n"
        "    Hahahaaaaa... / Há há há... / Hê hê hê... / Hihi... / Hohoho...\n"
        "    Cười chết. / Xỉu ngang.\n"
        "\n"
        "  NHÓM SỐC / KHÓ TIN:\n"
        "    Chời má... / Chời má ơiiii... / Má ơi cứu. / Ôi thôiiiiii...\n"
        "    Trời quơi. / Hú hồn. / Thôi chết. / Thôi xong.\n"
        "    Ủa gì vậy trời? / Ủa alo alo? / Hả??? / Đùa hả?\n"
        "    Mắc gì kỳ vậy? / Trời đất quỷ thần ơi.\n"
        "\n"
        "  NHÓM GỌI HỘI:\n"
        "    Ê tụi bay. / Ê mấy bà. / Ê các vợ. / Ê chúng mày ơi.\n"
        "\n"
        "  NHÓM PHỦ ĐỊNH / BẺ LÁI:\n"
        "    Không không không. / Khoan khoan khoan. / Wait wait wait.\n"
        "    Hello? / Nooooo. / Hả???\n"
        "\n"
        "  NHÓM XÁC NHẬN / THÁN PHỤC:\n"
        "    Okaaaay. / Wowwwww. / Chịu luôn á. / Rồi xong luôn.\n"
        "    Ủa... / Trời đất. / Thiệt luôn? / Ghê vậy. / Bro... / OMG...\n"
        "\n"
        "  NHÓM TỰ BÌNH LUẬN:\n"
        "    Thôi chết, cái này nguy hiểm nha. / Nguy hiểm nha tụi bay.\n"
        "    Em không đùa đâu. / Đừng nhìn cái đó. / Bình tĩnh bình tĩnh.\n"
        "    Ủa sao kỳ vậy. / Không hiểu luôn.\n"
        "\n"
        "ĐƯỢC PHÉP:\n"
        "  Tự cười. Tự phủ định. Tự bẻ lái giữa câu. Đổi ý.\n"
        "  Chọc người xem. Chọc chính mình. Lẩm bẩm ngắn.\n"
        "  Câu không hoàn chỉnh. Bỏ dở câu. Nói sai rồi tự sửa.\n"
        "  Nói chen — xen reaction bất chợt vào giữa ý review.\n"
        "  Kéo dài âm khi cảm xúc: Đẹpppp / Ghêeeee / Mềmmmm / Nooooo / Wowwwww\n"
        "    / ơiiiii / thôiiiiii / Okaaaay / Hả????\n"
        "\n"
        "CHUYỂN Ý: 'Mà nè...' / 'Ê nhưng mà...' / 'À khoan...' / 'Chưa hết đâu.' / 'Đỉnh nhất là...'\n"
        "FILLER: Rồi luôn. / Xong luôn. / Chịu luôn á. / Nói thiệt chứ. / Không giỡn đâu. / Nhìn phát mê luôn.\n"
        "\n"
        "GỌI NGƯỜI XEM: 'tụi bay' / 'mấy bà' / 'các vợ' / 'chúng mày' — xen tự nhiên, không mỗi câu.\n"
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
        'pattern': 'Đặt kỳ vọng nghi ngờ về một điểm → Thử thật / trải nghiệm trực tiếp → Bất ngờ vì kết quả tốt hơn tưởng',
        'example': 'TT: "Em tưởng mặc lên sẽ hơi rộng..." → thử → "ai ngờ lại gọn hơn nghĩ." / MP: "Em tưởng bôi lên sẽ nhờn..." → bôi → "ai ngờ thấm nhanh, không bóng."',
    },
    {
        'name': 'Flow B — Lúc đầu để ý một điểm → Phát hiện điểm khác',
        'pattern': 'Chú ý điểm A bình thường → Trải nghiệm thực tế → Vô tình phát hiện điểm B hay hơn',
        'example': 'TT: "Lúc đầu chỉ để ý màu..." → thử → "mới thấy cái phần eo này mới là điểm chính." / ĐT: "Lúc đầu chỉ chú ý thiết kế..." → dùng → "mới thấy tiếng máy cực nhỏ."',
    },
    {
        'name': 'Flow C — Vừa thử vừa nhận xét',
        'pattern': 'Mời người xem → Thực hiện demo trực tiếp → Nhận xét ngay khi làm',
        'example': 'TT: "Để em xoay cho mọi người xem nha..." → xoay → "form rủ tự nhiên, không dính." / ĐT: "Để em bật thử nha..." → bật → "khởi động nhanh, không lag gì hết."',
    },
    {
        'name': 'Flow D — Một điểm nghi ngờ → Được giải quyết',
        'pattern': 'Nêu nỗi lo / nghi ngờ cụ thể về sản phẩm → Thử thật → Lo ngại được giải quyết',
        'example': 'TT: "Em sợ kiểu tay bồng này làm người to hơn..." → mặc → "nhưng lên người lại ổn, không bị phồng." / MP: "Em sợ bôi xong bị bít lỗ chân lông..." → thoa → "nhưng thấm nhanh, không nhờn."',
    },
    {
        'name': 'Flow E — Cảm nhận thật sau khi dùng',
        'pattern': 'Nói kỳ vọng / nỗi sợ ban đầu thật → Trải nghiệm trực tiếp → Đánh giá thật lòng',
        'example': 'TT: "Nói thật em sợ nhất là mặc không thoải mái..." → mặc đi lại → "nhưng cái này nhẹ, không vướng." / TP: "Em tưởng cà phê này sẽ đắng gắt..." → nếm → "nhưng uống được, không đắng kiểu thô."',
    },
]

def _get_mini_hooks(tone: str) -> str:
    """Trả về mini hook phù hợp giọng điệu. Trả '' cho tiktok-nhay (REACTION BANK đã cover)."""
    if tone == 'tiktok-nhay':
        return ''
    return {
        'natural-koc': "'Khoan đã...' / 'Cái này mới hay nè.' / 'Ủa chưa hết nha.' / 'Mọi người nhìn nè.' / 'Phần này nè...'",
        'cute': "'Ủa mà nè!' / 'Nhìn chỗ này nè~' / 'Còn cái này nữa nha!' / 'Thích ghê á.'",
        'light-elegant': "'Thật ra...' / 'Điều mình thấy hay là...' / 'Phải nói thêm...' / 'Và điểm này nữa...'",
        'friendly': "'Ê mà này nha.' / 'Quan trọng là...' / 'Chưa hết nha.' / 'À khoan.' / 'Cái này nè.'",
        'light-humor': "'Nhưng mà đợi đã.' / 'Cái này mới hay nè.' / 'Chưa kể...' / 'À mà buồn cười là...'",
        'soft-close': "'Quan trọng hơn là...' / 'Và điều này nữa...' / 'Cái này mới là điểm chính...'",
        'real-review': "'Nói thật thêm...' / 'Và điểm mình lưu ý...' / 'Thật ra còn...' / 'Chưa kể...'",
    }.get(tone, "'Quan trọng là...' / 'Chưa kể...' / 'Nhìn nè.' / 'Cái này nữa nha.'")

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

INDUSTRY_LABELS = {
    'auto': 'Tự động nhận diện',
    'fashion': 'Thời trang',
    'beauty': 'Mỹ phẩm & Skincare',
    'electronics': 'Điện tử & Công nghệ',
    'home': 'Gia dụng',
    'food': 'Thực phẩm & Đồ uống',
    'pet': 'Thú cưng',
    'baby': 'Mẹ & Bé',
    'other': 'Ngành hàng khác',
}

INDUSTRY_GUIDE = {
    'fashion': {
        'hero_examples': "'Che bụng cực khéo' / 'Co giãn cực thoải mái' / 'Gọn dáng rõ' / 'Mặc mát cả ngày'",
        'demo': 'mặc thử, xoay người, zoom chi tiết chất vải, quay nghiêng, tạo dáng',
        'camera': 'quay nghiêng, zoom chất vải/chi tiết, pan full body, close-up điểm nổi bật',
        'koc_hook': 'câu nói thật khi vừa mặc: "Em tưởng mặc lên sẽ..." / "Lên người mới thấy..." / "Nhìn form này nè..."',
        'koc_action': 'chỉ/vuốt phần nổi bật, xoay người, kéo vải cho thấy form/chất, quay nghiêng 45°',
        'cta': '"ai thích [lợi ích Hero Benefit] thì thử mẫu này nha" / "link ở bio" / "ai cần thì vào xem thử"',
    },
    'beauty': {
        'hero_examples': "'Dưỡng ẩm 24h' / 'Không bóng nhờn' / 'Tone up rõ' / 'Da căng mịn sau 2 tuần'",
        'demo': 'mở nắp, lấy texture, bôi thử lên da, zoom chất kem/serum, cảm nhận ngay sau bôi',
        'camera': 'close-up texture sản phẩm, zoom da/màu trước-sau, cận mặt khi bôi, reveal màu sắc',
        'koc_hook': 'câu nói thật khi thử: "Em tưởng bôi lên sẽ nhờn..." / "Da mình hay nhạy cảm nhưng..." / "Thấm nhanh hơn nghĩ..."',
        'koc_action': 'bôi lên da tay/mặt, zoom texture khi lấy ra, vuốt nhẹ, biểu cảm khi cảm nhận kết quả',
        'cta': '"ai da [loại da] như em thì thử" / "mình để link bên dưới"',
    },
    'electronics': {
        'hero_examples': "'Pin trâu cả ngày' / 'Kết nối ổn định' / 'Màn hình siêu sắc nét' / 'Âm thanh sống động'",
        'demo': 'mở hộp (unbox), cắm điện/bật máy, test chức năng chính, zoom màn hình/âm thanh, demo thực tế',
        'camera': 'zoom màn hình/nút bấm, góc rộng khi demo toàn sản phẩm, close-up chi tiết thiết kế, unbox reveal',
        'koc_hook': 'câu nói thật khi dùng lần đầu: "Em tưởng pin sẽ yếu..." / "Bật lên thấy màn hình đẹp hơn ảnh nhiều..." / "Tưởng setup phức tạp..."',
        'koc_action': 'bật/tắt, test feature chính, zoom kết quả thực tế, so sánh với kỳ vọng ban đầu',
        'cta': '"ai đang cần [chức năng chính] thì xem thử" / "link ở bio"',
    },
    'home': {
        'hero_examples': "'Sạch nhanh không tốn sức' / 'Tiết kiệm điện đáng kể' / 'Kết quả thấy ngay' / 'Dùng cực dễ'",
        'demo': 'lắp ráp/chuẩn bị, sử dụng thực tế, demo kết quả, so sánh trước/sau',
        'camera': 'góc rộng demo toàn cảnh, zoom kết quả sau khi dùng, before/after cạnh nhau, close-up chi tiết hoạt động',
        'koc_hook': 'câu nói thật khi dùng: "Hồi trước làm cách này mất bao lâu..." / "Dùng thử mới thấy tiện thật..." / "Tưởng phức tạp hơn..."',
        'koc_action': 'demo sử dụng thực tế bước bước, zoom kết quả, reaction khi thấy kết quả tốt',
        'cta': '"ai hay gặp [vấn đề] như mình thì thử cái này" / "link ở bio"',
    },
    'food': {
        'hero_examples': "'Vị đậm đà tự nhiên' / 'Không chất bảo quản' / 'Pha nhanh 2 phút' / 'Cả nhà đều thích'",
        'demo': 'mở bao bì, pha/nấu/chuẩn bị, taste test, biểu cảm khi ăn/uống, cận cảnh thành phẩm',
        'camera': 'close-up màu sắc/texture sản phẩm, hơi steam, reveal thành phẩm hoàn chỉnh, zoom biểu cảm taste test',
        'koc_hook': 'câu nói thật khi nếm: "Em tưởng sẽ ngọt/đắng quá..." / "Mùi thơm hơn nghĩ nhiều..." / "Nhìn thì bình thường nhưng thử thì..."',
        'koc_action': 'mở nắp/bao bì, pha thử, nếm, biểu cảm tự nhiên, zoom sản phẩm cận cảnh',
        'cta': '"ai thích [hương vị/loại] thì thử" / "mình để link bên dưới"',
    },
    'pet': {
        'hero_examples': "'Thú kén ăn cũng thích' / 'Không phụ gia độc hại' / 'An toàn 100%' / 'Lông bóng rõ sau 1 tháng'",
        'demo': 'mở sản phẩm, cho thú cưng dùng/ăn/chơi, ghi lại phản ứng thú cưng, zoom sản phẩm',
        'camera': 'zoom thú cưng phản ứng, sản phẩm cận cảnh, góc rộng cảnh thú cưng đang dùng',
        'koc_hook': 'câu nói thật: "Con nhà mình khó ăn lắm, thử đủ loại rồi..." / "Tưởng nó không thích loại này đâu..."',
        'koc_action': 'đặt sản phẩm trước mặt thú cưng, quay phản ứng, zoom cận mặt thú khi dùng',
        'cta': '"bé nhà ai cũng [vấn đề] như mình thì thử" / "link ở bio"',
    },
    'baby': {
        'hero_examples': "'Chất liệu an toàn cho da bé' / 'Không kích ứng' / 'Dùng từ sơ sinh được' / 'Mẹ an tâm tuyệt đối'",
        'demo': 'mở sản phẩm, demo trên bé/búp bê, test độ an toàn, zoom chất liệu/chi tiết',
        'camera': 'zoom chi tiết an toàn (khóa/nút/chất liệu), close-up chất liệu mềm, demo trên bé (nếu có), cận cảnh sản phẩm',
        'koc_hook': 'câu nói thật của mẹ: "Hồi tìm sản phẩm cho con mình lo nhất là..." / "Dùng thử mới an tâm thật..." / "Tưởng khó dùng..."',
        'koc_action': 'demo trên bé/búp bê, kiểm tra chi tiết an toàn từng bước, vuốt chất liệu',
        'cta': '"mẹ nào đang tìm [loại sản phẩm] cho bé thì xem thử" / "link ở bio"',
    },
    'other': {
        'hero_examples': "lợi ích bán hàng mạnh nhất, phù hợp nhất với khách hàng mục tiêu của sản phẩm này",
        'demo': 'demo tính năng/lợi ích chính một cách trực quan, so sánh trước/sau, trải nghiệm thực tế',
        'camera': 'focus camera vào điểm thể hiện Hero Benefit tốt nhất, demo từng bước rõ ràng',
        'koc_hook': 'câu nói thật về trải nghiệm ban đầu: "Em tưởng [điểm nghi ngờ]..." / "Dùng thử mới thấy [kết quả tốt hơn]..."',
        'koc_action': 'demo trực tiếp lợi ích chính, zoom điểm nổi bật, reaction tự nhiên khi phát hiện điều thú vị',
        'cta': '"ai đang cần [giải pháp Hero Benefit] thì xem thử" / "link ở bio"',
    },
}


def build_voiceover_prompt(input_data: dict, has_images: bool, image_analysis: str = '') -> str:
    """Prompt V3 cho Voice Over (ElevenLabs V3 Enhance) — pure voice script, không emotion tag."""
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    goal_label = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    audience = input_data.get('targetAudience', '').strip()
    industry = input_data.get('industry', 'auto')
    industry_label = INDUSTRY_LABELS.get(industry, 'Tự động nhận diện')
    industry_data = INDUSTRY_GUIDE.get(industry, {})
    _is_auto_industry = industry == 'auto'

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
    _mini_hooks = _get_mini_hooks(tone)

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
            "KHÔNG được: Review → Review → Review → Review liên tiếp.",
            "SAU MỖI 1-2 Ý REVIEW → BẮT BUỘC có ít nhất 1 nhịp cảm xúc.",
            "Nhịp cảm xúc = reaction độc lập / cười ngắn / lẩm bẩm / đổi ý / bẻ lái — KHÔNG phải filler nhét vào câu review.",
            f"Reaction độc lập tối thiểu: {_reaction_min} câu (câu đứng riêng).",
            "Mạch nói phải giống TikToker thật đang tám chuyện — không phải AI điền template.",
            "",
            "## ENGINE 3 — EMOTION CURVE",
            "Năng lượng KHÔNG được đều từ đầu đến cuối.",
            "Hook mạnh → body xen kẽ cao/thấp → CTA bật lên.",
            "Câu reaction ngắn = giảm tốc, tạo nhịp. Câu bất ngờ = tăng đột ngột.",
            "",
            "## ĐA DẠNG CẤU TRÚC CÂU",
            "Kết hợp: câu cực ngắn (1-3 từ), câu trung, câu bỏ dở, câu cảm thán, câu hỏi tự hỏi.",
            "Cho phép: nói sai rồi tự sửa giữa câu. Cười chen giữa ý. Bẻ lái bất chợt.",
            "",
            "## TỰ KIỂM TRA TRƯỚC KHI OUTPUT",
            "Trước khi trả JSON, kiểm tra voScript:",
            "- Có tag dạng [xxx] không? → Xóa hết.",
            "- Nghe giống AI / MC / reviewer không? → Viết lại toàn bộ.",
            f"- Đếm reaction độc lập: đủ {_reaction_min} chưa? → Nếu thiếu, thêm vào.",
            "- Có đoạn Review → Review → Review liên tiếp (2+ ý không xen nhịp cảm xúc) không? → Chèn reaction/cười/lẩm bẩm vào giữa.",
            f"- Hook có đúng kiểu '{_hook_short}' không? → Nếu không, viết lại hook.",
            f"- Cấu trúc có đúng '{_pattern_short}' không? → Nếu lệch, điều chỉnh.",
            "- Đọc to lên: nghe buồn cười không? Giống đang tám chuyện không? Hay vẫn giống review?",
            "Chỉ output khi nghe giống TikToker thật đang vui miệng nói — không phải đang review sản phẩm.",
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
        "## PRE-WRITE PROTOCOL — làm TRƯỚC khi viết kịch bản",
        *(["0. Xác định NGÀNH HÀNG từ tên + mô tả sản phẩm (Thời trang / Mỹ phẩm / Điện tử / Gia dụng / Thực phẩm / Thú cưng / Mẹ&Bé / Khác) → dùng để chọn camera action ở bước 3."]
          if _is_auto_industry else [f"0. Ngành hàng: {industry_label} — áp dụng camera action phù hợp ngành này ở bước 3."]),
        "1. Xác định HERO BENEFIT — 1 lợi ích bán hàng mạnh nhất cho khách mục tiêu. Ghi vào section2.heroBenefit.",
        "   Ví dụ: " + industry_data.get('hero_examples', "'Lợi ích mạnh nhất' (TT) / 'Thấm nhanh không nhờn' (MP) / 'Pin trâu 2 ngày' (ĐT)"),
        "2. voScript: 70% xoay quanh Hero Benefit. 30% mới nói lợi ích phụ.",
        "3. Camera action trong lines[] phục vụ Hero Benefit (người quay im lặng — chỉ di chuyển camera):",
        *([ f"   {industry_data.get('camera', '')}" ] if not _is_auto_industry and industry_data.get('camera') else [
            "   Thời trang → quay nghiêng, zoom chất vải/chi tiết, pan full body",
            "   Mỹ phẩm → close-up texture, zoom da trước-sau, cận mặt khi bôi",
            "   Điện tử → zoom màn hình/nút bấm, demo chức năng, unbox reveal",
            "   Gia dụng → góc rộng demo, zoom kết quả, before/after",
            "   Thực phẩm → close-up màu/texture, steam, reveal thành phẩm",
            "   Thú cưng / Mẹ&Bé → zoom phản ứng/chi tiết an toàn, sản phẩm cận cảnh",
            "   Khác → focus camera vào điểm thể hiện Hero Benefit tốt nhất",
        ]),
        *([
            "4. Thân voScript: tự nhiên thêm 1-2 Mini Hook ngắt nhịp giữ người nghe (khớp giọng điệu):",
            f"   {_mini_hooks}",
            "   Mỗi video khác nhau — không cố định câu nào.",
        ] if _mini_hooks else [
            "4. Nhịp điệu voScript: xen kẽ câu ngắn/dài, reaction/review — không đều đơn điệu.",
        ]),
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
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":"","heroBenefit":""},',
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
    industry = input_data.get('industry', 'auto')
    industry_label = INDUSTRY_LABELS.get(industry, 'Tự động nhận diện')
    industry_data = INDUSTRY_GUIDE.get(industry, {})
    _is_auto_industry = industry == 'auto'

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
        _ind_hook = industry_data.get('koc_hook', 'câu nói thật khi vừa trải nghiệm sản phẩm lần đầu, không quảng cáo')
        _ind_action = industry_data.get('koc_action', 'demo trực tiếp điểm nổi bật, zoom phần thể hiện Hero Benefit, reaction khi phát hiện điều thú vị')
        _ind_cta = industry_data.get('cta', '"ai đang cần [giải pháp] thì xem thử nha" / "link ở bio"')
        _engine4_lines = [
            "**HOOK KOC:** Câu nói thật khi vừa trải nghiệm sản phẩm. Không quảng cáo. Không trau chuốt.",
            f"Ví dụ ({industry_label}): {_ind_hook}",
            "TRÁNH: 'Sản phẩm này...' / 'Hôm nay em giới thiệu...' / 'Đây là...' / Liệt kê thông số.",
        ]
        _koc_extra = [
            "**KOC DIALOGUE ENGINE — CÁCH VIẾT LỜI THOẠI**",
            "Không review như liệt kê. Không trơn tru. Ưu tiên ngôn ngữ nói, được phép bỏ dở câu, sửa ý giữa chừng.",
            "Dùng (chọn phù hợp, không lặp, không nhồi):",
            "  'Em tưởng...' / 'Ai ngờ...' / 'Thử rồi mới thấy...' / 'Lúc đầu em nghĩ...' / 'Em mới để ý...'",
            "  'Ủa...' / 'À...' / 'Công nhận...' / 'Nói thật...' / 'Em bất ngờ luôn.' / 'Cái này hay nè.'",
            "  'Mọi người nhìn nè.' / 'Phần này nè...' / 'Nhìn chỗ này nè...' / 'Đúng kiểu...' / 'Kiểu như...'",
            f"Một video {duration_label}: {_koc_reaction_count} phản ứng nhỏ tự nhiên.",
            "",
            "**HÀNH ĐỘNG PHẢI KHỚP LỜI THOẠI**",
            "Rule: Nói gì → làm cái đó. Không tạo hành động chung chung không liên quan lời.",
            "  Nói về 1 điểm cụ thể → chỉ / zoom / focus vào đúng điểm đó.",
            "  Nói 'thử xem' / 'để em thử' → thực hiện demo tương ứng ngay lúc đó.",
            "  Phát hiện điều bất ngờ → cười nhẹ / reaction ngắn phù hợp.",
            f"Action phù hợp ngành {industry_label}: {_ind_action}",
            "",
            f"**CTA KOC:** Nhẹ nhàng, không ép mua. Ví dụ: {_ind_cta}",
            "",
            "**TỰ KIỂM TRA KOC TRƯỚC KHI OUTPUT**",
            "- Lời thoại có giống người thật đang trải nghiệm sản phẩm không? → Nếu không, viết lại.",
            "- Có bị liệt kê tính năng như bài review không? → Nếu có, phá cấu trúc đó.",
            f"- Có ít nhất {_koc_reaction_count} phản ứng nhỏ tự nhiên không? → Nếu thiếu, thêm vào.",
            "- Hành động có khớp từng câu thoại không? → Nếu không, sửa cho khớp.",
            "- Có câu nào giống MC / quảng cáo / ChatGPT không? → Viết lại câu đó.",
            "- Có cảm giác 'vừa dùng vừa phát hiện' không? → Áp dụng đúng flow đã chọn.",
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

    _mini_hooks = _get_mini_hooks(tone)
    _pattern_short = _pattern['name'].split(' —')[0].strip()
    _hook_short_check = _hook_type.split(' —')[0].strip()
    _selfcheck_lines = [] if _is_koc else [
        "**TỰ KIỂM TRA TRƯỚC KHI OUTPUT**",
        f"- Hook có đúng kiểu '{_hook_short_check}' không? → Nếu không, viết lại.",
        f"- Cấu trúc có đúng '{_pattern_short}' không? → Điều chỉnh nếu lệch.",
        "- Có câu nào giống AI/MC/văn quảng cáo không? → Viết lại.",
        "- Có đoạn liệt kê tính năng không? → Chuyển sang lợi ích cụ thể.",
        "- Hero Benefit có xuất hiện ở đa số lời thoại không? → Nếu không, tăng tỷ lệ.",
        "- Lời thoại đọc to lên nghe tự nhiên không? → Nếu không, viết lại.",
        "Nếu chưa đạt → tự chỉnh sửa trước khi xuất JSON.",
        "",
    ]

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
        "## PRE-WRITE PROTOCOL — làm TRƯỚC khi viết kịch bản",
        *(["0. Xác định NGÀNH HÀNG từ tên + mô tả sản phẩm (Thời trang / Mỹ phẩm / Điện tử / Gia dụng / Thực phẩm / Thú cưng / Mẹ&Bé / Khác) → dùng để chọn action phù hợp ở bước 3."]
          if _is_auto_industry else [f"0. Ngành hàng: {industry_label} — áp dụng action phù hợp ngành này ở bước 3."]),
        "1. Xác định HERO BENEFIT — 1 lợi ích bán hàng mạnh nhất cho khách mục tiêu. Ghi vào section2.heroBenefit.",
        f"   Ví dụ ({industry_label}): " + industry_data.get('hero_examples', "'Lợi ích mạnh nhất' / 'Giải pháp chính' / 'Kết quả thấy rõ'"),
        "2. Kịch bản: 70% lời thoại xoay quanh Hero Benefit. 30% mới nói lợi ích phụ.",
        *([
            "3. Hành động phục vụ Hero Benefit — xem chi tiết trong HÀNH ĐỘNG PHẢI KHỚP bên dưới.",
        ] if _is_koc else (
            [
                "3. Hành động (Action) phục vụ Hero Benefit (không random):",
                f"   {industry_data.get('demo', '')}",
                "   Action phải khớp với Hero Benefit đang nói. Không dùng action chung chung.",
            ] if not _is_auto_industry and industry_data.get('demo') else [
                "3. Hành động (Action) phục vụ Hero Benefit (không random):",
                "   Thời trang → mặc thử, xoay người, zoom chất vải/chi tiết, tạo dáng, quay nghiêng",
                "   Mỹ phẩm → bôi thử lên da, zoom texture, cảm nhận ngay sau bôi, reveal kết quả",
                "   Điện tử → mở hộp, bật máy, test chức năng, demo thực tế, zoom màn hình",
                "   Gia dụng → lắp ráp, sử dụng thực tế, zoom kết quả, before/after cạnh nhau",
                "   Thực phẩm → mở bao bì, pha/nấu, taste test, biểu cảm khi thử",
                "   Thú cưng / Mẹ&Bé → zoom phản ứng/chi tiết an toàn, sản phẩm cận cảnh",
                "   Khác → chọn action tự nhiên nhất thể hiện Hero Benefit tốt nhất",
            ]
        )),
        *([
            "4. Thân video: tự nhiên thêm 1-2 Mini Hook giữ người xem (khớp giọng điệu):",
            f"   {_mini_hooks}",
            "   Mỗi video khác nhau — không cố định câu nào.",
        ] if _mini_hooks else [
            "4. Nhịp điệu video: xen kẽ reaction/review, câu ngắn/dài — không đều đơn điệu.",
        ]),
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
        *_selfcheck_lines,
        "---",
        "",
        "# YÊU CẦU ĐẦU RA",
        "",
        "Chỉ trả về JSON hợp lệ, không có text nào bên ngoài JSON:",
        "",
        '```json',
        '{',
        '  "section1": {"productName":"","targetAudience":"","shootingStyle":"","duration":"","tone":"","videoGoal":""},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":"","heroBenefit":""},',
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
        'section2': {'targetCustomer': '', 'painPoints': '', 'insight': '', 'highlights': '', 'mainBenefits': '', 'usageSituations': '', 'heroBenefit': ''},
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
    industry = input_data.get('industry', 'auto')
    industry_label = INDUSTRY_LABELS.get(industry, 'Tự động nhận diện')
    industry_data = INDUSTRY_GUIDE.get(industry, {})

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
        hero_benefit = s2.get('heroBenefit', '').strip()
        analysis_parts = list(filter(None, [
            f"Hero Benefit: {hero_benefit}" if hero_benefit else '',
            f"Pain point: {s2.get('painPoints','')}" if s2.get('painPoints') else '',
            f"Insight khách hàng: {s2.get('insight','')}" if s2.get('insight') else '',
            f"Điểm nổi bật sản phẩm: {s2.get('highlights','')}" if s2.get('highlights') else '',
            f"Lợi ích chính: {s2.get('mainBenefits','')}" if s2.get('mainBenefits') else '',
            f"Tình huống dùng: {s2.get('usageSituations','')}" if s2.get('usageSituations') else '',
        ]))
        analysis_block = ('\n' + '\n'.join(analysis_parts)) if analysis_parts else ''
        hook_line = f'\nHook mở đầu bắt buộc dùng: "{selected_hook}"' if selected_hook else ''
        hero_line = f'\nHero Benefit: {hero_benefit} → 70% lời thoại xoay quanh điểm này. Hành động ưu tiên phục vụ Hero Benefit. Thân video thêm 1-2 Mini Hook tự nhiên.' if hero_benefit else ''

        if shooting == 'voiceover':
            persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật.')
            _pattern = random.choice(STRUCTURE_PATTERNS)
            _hook_type = random.choice(HOOK_TYPES) if not selected_hook else 'theo hook đã chọn'
            _reaction_min = '3' if duration in ('15s', '20s') else '4-5' if duration == '30s' else '6-8'
            _nhay_law = (
                "\nEMOTION RHYTHM — LUẬT BẮT BUỘC:\n"
                "KHÔNG được: Review → Review → Review → Review liên tiếp.\n"
                "SAU MỖI 1-2 Ý REVIEW → BẮT BUỘC có ít nhất 1 nhịp cảm xúc.\n"
                "Nhịp cảm xúc = reaction độc lập / cười ngắn / lẩm bẩm / đổi ý / bẻ lái.\n"
                "Reaction = câu đứng riêng biệt, không nhét vào câu review.\n"
                "Nếu có đoạn Review → Review → Review liên tiếp → chèn nhịp cảm xúc vào giữa."
            ) if tone == 'tiktok-nhay' else ''
            hook_instruction = f' Câu đầu tiên PHẢI là hook đã cho, không được thay đổi: "{selected_hook}"' if selected_hook else ''
            user = f"""{base}{analysis_block}
{context_line}{hook_line}{hero_line}

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
            _ind_hook_sec = industry_data.get('koc_hook', 'câu nói thật khi vừa trải nghiệm sản phẩm lần đầu')
            _ind_action_sec = industry_data.get('koc_action', 'demo trực tiếp điểm nổi bật, zoom phần thể hiện Hero Benefit, reaction khi phát hiện điều thú vị')
            if _is_koc_sec:
                _koc_block = f"""
KOC DISCOVERY ENGINE — {_koc_flow_sec['name']}
Flow: {_koc_flow_sec['pattern']}
Ví dụ: {_koc_flow_sec['example']}

HOOK KOC ({industry_label}): {_ind_hook_sec}
TRÁNH: 'Sản phẩm này...' / 'Hôm nay em giới thiệu...' / 'Đây là...' / Liệt kê thông số.

KOC DIALOGUE: Ưu tiên ngôn ngữ nói. Không liệt kê tính năng.
Dùng: 'Em tưởng...' / 'Thử rồi mới thấy...' / 'Mọi người nhìn nè.' / 'Công nhận...' / 'Cái này hay nè.'
Một video {duration_label}: {_koc_reaction_sec} phản ứng nhỏ tự nhiên.

HÀNH ĐỘNG PHẢI KHỚP LỜI THOẠI:
Rule: Nói gì → làm cái đó. Nói về 1 điểm cụ thể → zoom/chỉ/focus đúng điểm đó.
Action phù hợp ngành {industry_label}: {_ind_action_sec}
Bổ sung: (cười nhẹ vì bất ngờ) / (reaction ngắn khi phát hiện điều hay)

TỰ KIỂM TRA KOC: Lời thoại có giống người thật đang trải nghiệm sản phẩm không? Có bị liệt kê không? Hành động có khớp không? Có cảm giác 'vừa dùng vừa phát hiện' không?"""
            else:
                _koc_block = ""
            user = f"""{base}{analysis_block}
{context_line}{hook_line}{hero_line}

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
            f"Hero Benefit: {s2.get('heroBenefit','')}" if s2.get('heroBenefit') else '',
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

TỰ KIỂM TRA: Đếm ký tự từng caption trước khi output. Nếu > 100 ký tự → rút ngắn ngay.

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
1. Brand (1-2 tag): thương hiệu cửa hàng. Ví dụ: #shopname #thuonghieu
2. Product (3 tag): loại sản phẩm cụ thể, đa dạng từ ngữ, không lặp từ gốc.
   Ví dụ (thời trang): #aobau #babydoll #voansuong  (KHÔNG: #aobau #aobauxinh #aobaudep)
   Ví dụ (mỹ phẩm): #serum #duongda #kemduongam
   Ví dụ (thực phẩm): #caphe #caphesuada #nuocuong
3. Audience (2 tag): đối tượng khách hàng phù hợp sản phẩm.
   Ví dụ: #mebau #thoitrangbau / #dagot #skincare / #congnghe #gadget
4. Usage (2 tag): tình huống sử dụng thật.
   Ví dụ: #macnha #dichoicho / #trangdiem #makeup / #uongsang #caphesang
5. TikTok Shop (2 tag): ví dụ #tiktokshop #reviewthat #reviewsanpham
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
        _ind_hero_ex = industry_data.get('hero_examples', "'Lợi ích mạnh nhất' / 'Giải pháp chính' / 'Kết quả thấy rõ'")
        user = f"""{base}
{context_line}

Phân tích nhanh sản phẩm để tạo kịch bản TikTok Shop.
Xác định luôn Hero Benefit — 1 lợi ích bán hàng mạnh nhất cho khách mục tiêu cụ thể này.
Ví dụ Hero Benefit ({industry_label}): {_ind_hero_ex}

```json
{{"section2":{{"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":"","heroBenefit":""}}}}
```"""

    elif section == 'tips':
        _demo_tip = industry_data.get('demo', '')
        _camera_tip = industry_data.get('camera', '')
        _tips_industry_hint = f'\nNgành hàng ({industry_label}): demo = {_demo_tip}. Camera = {_camera_tip}.' if _demo_tip else ''
        user = f"""{base}
{context_line}{_tips_industry_hint}

Tạo 4-6 lưu ý thực tế khi quay video cho sản phẩm này.
Gồm: setup góc máy phù hợp ngành, cách demo rõ Hero Benefit, ánh sáng, âm thanh, lưu ý đặc thù kiểu quay này.
{"Voiceover: nhấn mạnh tắt micro hoàn toàn, đồng bộ hành động theo script." if shooting == "voiceover" else ""}

```json
{{"section9":{{"tips":["lưu ý 1","lưu ý 2"]}}}}
```"""

    else:
        raise ValueError(f'Section không hợp lệ: {section}')

    return SECTION_SYSTEM, user
