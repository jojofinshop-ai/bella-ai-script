import json
import re
import random


def build_system_prompt(prompt_settings: dict) -> str:
    parts = [
        "# VAI TRÒ",
        "Bạn là chuyên gia sáng tạo nội dung TikTok Shop — am hiểu cách viết hook, lời thoại và CTA tự nhiên, chuyển đổi cao.",
        "Bạn viết kịch bản như người thật đang chia sẻ trải nghiệm: tự nhiên, không văn mẫu, không kiểu MC quảng cáo.",
        "Bạn am hiểu đặc thù từng ngành hàng và điều chỉnh văn phong theo đúng yêu cầu của từng sản phẩm.",
    ]
    shop_context = prompt_settings.get('shopContext', '').strip()
    if shop_context:
        parts += ["", "# THÔNG TIN KÊNH / SHOP", shop_context]
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

# ============================================================
# V6: SUBJECT MODE + PRODUCTION MODE
# ============================================================

SUBJECT_MODE_LABELS = {
    'auto': 'Tự động',
    'face': 'Có người / Lộ mặt',
    'hands': 'Chỉ quay tay / Không lộ mặt',
    'product': 'Chỉ sản phẩm',
}


SUBJECT_MODE_GUIDE = {
    'face': (
        "Có người xuất hiện trong video. Có thể nhìn camera, nói trực tiếp, có biểu cảm, reaction cơ thể.\n"
        "ĐƯỢC DÙNG: nhìn camera, mỉm cười, xoay người, chỉ vào sản phẩm, đưa sản phẩm ra camera, demo trên người, cầm sản phẩm.\n"
        "KHÔNG ĐƯỢC DÙNG: action chỉ phù hợp khi không có người (orbit camera thuần, macro 100% sản phẩm, top-view tay trắng)."
    ),
    'hands': (
        "Không lộ mặt. Chỉ thấy tay hoặc góc POV từ mắt người quay. Không có khuôn mặt.\n"
        "ĐƯỢC DÙNG: cầm, mở, xoay, bóp, thoa, đổ, xịt, cắm, test, top-view, zoom tay thao tác cận cảnh.\n"
        "TUYỆT ĐỐI KHÔNG: nhìn camera (không có mắt để nhìn), mỉm cười, biểu cảm khuôn mặt, bước vào khung hình, xoay người, reaction mặt."
    ),
    'product': (
        "Không người, không tay là chính. Video tập trung vào sản phẩm — như packshot hoặc quảng cáo cinematic.\n"
        "ĐƯỢC DÙNG: macro chi tiết, camera orbit, sản phẩm xoay chậm, ánh sáng lia qua bề mặt, close-up texture, packshot, reveal.\n"
        "TUYỆT ĐỐI KHÔNG: người xuất hiện, tay làm chủ cảnh, biểu cảm, hành động cơ thể."
    ),
    'auto': (
        "AI tự suy luận subject mode phù hợp dựa trên kiểu quay, ngành hàng và mô tả sản phẩm.\n"
        "Phải resolve thành face / hands / product và ghi vào section1.subjectModeResolved."
    ),
}

FACE_ACTIONS = [
    'nhìn thẳng vào camera', 'mỉm cười tự nhiên', 'đưa sản phẩm sát camera',
    'chỉ vào chi tiết sản phẩm', 'mặc thử / dùng thử trên người', 'xoay người nhẹ',
    'bước nhẹ vào khung hình', 'reaction tự nhiên (gật đầu, gương mặt bất ngờ)',
    'đổi biểu cảm theo nội dung', 'cầm sản phẩm ngang ngực', 'demo sản phẩm trên người',
]

HANDS_ACTIONS = [
    'đặt sản phẩm lên bàn (top-view)', 'hai tay mở hộp / mở nắp', 'xoay sản phẩm 45°',
    'lật mặt sau / lật lên thấy rõ', 'bóp thử / nhấn thử bề mặt', 'thoa thử lên cổ tay',
    'đổ ra chén / cốc / đĩa', 'xịt thử / bóp thử', 'kéo khóa / mở nắp / tháo bao',
    'cắm sạc / bật nút / test chức năng', 'quay top-view chi tiết', 'zoom tay thao tác cận cảnh',
]

PRODUCT_ACTIONS = [
    'macro chi tiết texture / chất liệu', 'camera orbit quanh sản phẩm chậm',
    'sản phẩm xoay chậm 360°', 'ánh sáng lia qua bề mặt sản phẩm',
    'close-up texture / logo / chi tiết đặc trưng', 'packshot (hero shot trên nền sạch)',
    'reveal từ bóng tối ra ánh sáng', 'đặt sản phẩm trên nền tối giản (trắng/đen/marble)',
    'slow motion drop / pour / open', 'hero shot với ánh sáng studio nổi bật',
]

INDUSTRY_SUBJECT_ACTIONS = {
    ('fashion', 'face'): 'mặc thử, xoay người 360°, vuốt chất vải, tạo dáng, chỉ vào form/cut, nhìn camera',
    ('fashion', 'hands'): 'cận chất vải, kéo vải kiểm tra độ đàn hồi, zoom đường may, lật mặt trong, flat lay',
    ('fashion', 'product'): 'áo/váy treo trên móc, macro chất vải, ánh sáng lướt qua, flat lay pan 360°',
    ('beauty', 'face'): 'bôi thử lên mặt, phản ứng khi cảm nhận, so sánh da trước/sau, biểu cảm',
    ('beauty', 'hands'): 'swatch lên cổ tay, mở nắp, bóp lấy texture, thoa đều, zoom texture',
    ('beauty', 'product'): 'lọ mỹ phẩm trên nền studio, macro texture khi đổ, ánh sáng nổi bật thiết kế, orbit',
    ('electronics', 'face'): 'cầm sản phẩm, bật thử, nhìn màn hình rồi nhìn camera, reaction',
    ('electronics', 'hands'): 'bấm nút, cắm sạc, test màn hình, mở hộp (unbox), zoom cổng kết nối',
    ('electronics', 'product'): 'orbit camera, macro cổng/nút/chi tiết, ánh sáng viền sản phẩm, reveal từ hộp',
    ('home', 'face'): 'demo sử dụng thật, nhìn camera reaction, so sánh trước/sau, chỉ vào kết quả',
    ('home', 'hands'): 'thao tác từng bước, zoom kết quả, test công năng, lắp ráp cận cảnh',
    ('home', 'product'): 'sản phẩm trong bối cảnh nhà, zoom chi tiết thiết kế, hero shot, orbit',
    ('food', 'face'): 'taste test, biểu cảm khi ăn/uống, cầm sản phẩm, nhìn camera reaction',
    ('food', 'hands'): 'mở gói, đổ ra bát, pha/trộn, taste setup top-view, zoom màu sắc/texture',
    ('food', 'product'): 'packshot, hơi nóng/steam, close-up texture, pouring shot, hero shot',
    ('pet', 'face'): 'cho thú cưng dùng và quay phản ứng, người có thể xuất hiện nhẹ',
    ('pet', 'hands'): 'đặt sản phẩm trước mặt thú cưng, mở gói, zoom phản ứng thú cưng, top-view',
    ('pet', 'product'): 'sản phẩm cận cảnh, thiết kế bao bì, thành phần, macro',
    ('baby', 'face'): 'demo trên bé (nếu có), mẹ cầm sản phẩm và nhìn camera, biểu cảm yêu thương',
    ('baby', 'hands'): 'mở hộp, demo từng bước an toàn, kiểm tra chất liệu, vuốt bề mặt mềm',
    ('baby', 'product'): 'sản phẩm trên nền pastel nhẹ, zoom chất liệu an toàn, close-up chi tiết',
    ('other', 'face'): 'demo sản phẩm trên người, nhìn camera, chỉ vào điểm nổi bật, reaction',
    ('other', 'hands'): 'demo tính năng bằng tay, mở, test, zoom chi tiết quan trọng',
    ('other', 'product'): 'hero shot, macro chi tiết, orbit camera, ánh sáng studio',
}

SUBJECT_TIPS = {
    'face': [
        'Nhìn thẳng vào lens camera — đừng nhìn màn hình preview khi nói',
        'Biểu cảm tự nhiên, mỉm cười nhẹ khi bắt đầu quay',
        'Nói to, rõ ràng — tắt quạt và tiếng ồn nền trước khi quay',
        'Đứng cách camera 50-80cm để thấy cả mặt và sản phẩm',
        'Chiếu sáng từ phía trước hoặc 45° — tránh bóng ngược sáng',
    ],
    'hands': [
        'Móng tay sạch, gọn — đây là "diễn viên" chính của video',
        'Không để ngón tay che logo hoặc tên sản phẩm',
        'Di chuyển tay chậm, mượt — tránh rung giật đột ngột',
        'Dùng top-view (góc từ trên nhìn xuống) để thấy rõ thao tác nhất',
        'Nền sạch: vải trắng, đen hoặc marble — không lộn xộn',
        'Ánh sáng đều từ 2 bên — tránh bóng đổ cứng lên sản phẩm',
    ],
    'product': [
        'Nền tối giản: trắng, đen, pastel nhạt hoặc marble — sản phẩm là trung tâm',
        'Dùng đèn vòng hoặc softbox — tránh bóng đổ cứng',
        'Quay macro để thấy rõ chi tiết texture / chất liệu / logo',
        'Xoay sản phẩm chậm 360° để người xem thấy toàn diện',
        'Tắt auto-focus khi quay close-up để tránh blur đột ngột',
        'Chụp từ nhiều góc: front, 45°, top-down, close-up chi tiết',
    ],
    'auto': [
        'Chọn cách quay phù hợp nhất với sản phẩm',
        'Ổn định camera để video không bị rung',
        'Ánh sáng đủ và đều — tránh quay ngược sáng',
    ],
}


# ============================================================
# V8: REFERENCE LIBRARY — tham khảo mẫu user tự nhập (hook/script/transcript viral)
# ============================================================
# Thay cho V7 (đã gỡ — học theo view/đơn hàng không có tín hiệu khi mọi video đều 0 đơn).
# User tự tay nhập hook/kịch bản/transcript mẫu vào thư viện (localStorage, quản lý ở
# frontend). Khi generate, backend được gửi sẵn 1 danh sách text đã chọn lọc (AI hoặc
# fallback heuristic chọn ở app.py/ai_providers.py) — hàm dưới đây chỉ làm 1 việc: chèn các
# đoạn text đó vào prompt làm ví dụ tham khảo văn phong/cấu trúc, không đụng gì khác.

def get_reference_influence_policy(reference_examples: list, is_koc: bool = False, has_selected_hook: bool = False) -> dict:
    """Xác định mức độ ảnh hưởng của Reference Library dựa trên số lượng mẫu.

    count=0 hoặc is_koc → none (không ảnh hưởng)
    count=1             → light (học DNA/vibe/nhịp câu, KHÔNG override hook type)
    count=2-5           → moderate (blend ≥2 DNA, override hook type nếu không có selectedHook)
    count≥6             → strong (Pattern Blend từ nhiều mẫu, full override)
    """
    count = len([e for e in (reference_examples or []) if e and e.strip()])

    if count == 0 or is_koc:
        return {'level': 'none', 'count': count, 'allow_hook_override': False,
                'hook_blend': False, 'pattern_blend': False, 'max_samples': 0}

    if count == 1:
        return {'level': 'light', 'count': 1, 'allow_hook_override': False,
                'hook_blend': False, 'pattern_blend': False, 'max_samples': 1}

    allow_override = not has_selected_hook
    if count <= 5:
        return {'level': 'moderate', 'count': count, 'allow_hook_override': allow_override,
                'hook_blend': allow_override, 'pattern_blend': False, 'max_samples': min(count, 3)}

    return {'level': 'strong', 'count': count, 'allow_hook_override': allow_override,
            'hook_blend': False, 'pattern_blend': allow_override, 'max_samples': 3}


def _build_reference_examples_block(reference_examples: list, policy: dict = None, avoid_hooks: list = None) -> list:
    """Trả về list dòng prompt tham khảo mẫu từ Thư viện — theo policy ảnh hưởng dựa trên số mẫu."""
    examples = [e.strip()[:600] for e in (reference_examples or []) if e and e.strip()]
    if not examples:
        return []

    if policy is None:
        policy = get_reference_influence_policy(examples)

    level = policy.get('level', 'none')
    if level == 'none':
        return []

    allow_hook_override = policy.get('allow_hook_override', False)
    pattern_blend = policy.get('pattern_blend', False)
    max_samples = policy.get('max_samples', 3)
    count = policy.get('count', len(examples))

    if level == 'light':
        title = f"## ═══ MẪU THAM KHẢO — HỌC PHONG CÁCH ({count} mẫu) ═══"
        mode_note = "1 mẫu → học DNA/vibe/nhịp câu, KHÔNG override kiểu hook ngẫu nhiên."
    elif level == 'moderate':
        title = f"## ═══ MẪU THAM KHẢO — OVERRIDE ENGINE 4 ({count} mẫu) ═══"
        mode_note = f"{count} mẫu → blend DNA từ ≥2 mẫu, hook theo kiểu phổ biến từ mẫu."
    else:
        title = f"## ═══ MẪU THAM KHẢO — PATTERN BLEND ({count} mẫu) ═══"
        mode_note = f"{count} mẫu → Pattern Blend từ nhiều mẫu, tổng hợp thành style mới."

    lines = ["", title, mode_note, "",
             "BƯỚC 1 — PHÂN TÍCH DNA (thực hiện trong đầu trước khi viết):",
             "  • KIỂU HOOK: mẫu mở đầu bằng cách nào?",
             "    — Câu hỏi nghi vấn? / Tiết lộ bí mật / twist? / Kể chuyện 'mình trước đây...'?",
             "    — Reaction bất ngờ 'Ủa / Thú thật...'? / Thách thức nhận thức?",
             "  • NHỊP CÂU: ngắn (<8 từ) hay dài? Có ngắt '...'? Có reaction xen giữa?",
             "  • BỐ CỤC: hook → pain → tính năng → social proof → CTA? hay flow khác?",
             "  • VĂN PHONG: first-person 'mình/em'? Thân mật? Từ ngữ đặc trưng?",
             "", "BƯỚC 2 — ÁP DỤNG:"]

    if level == 'light':
        lines += [
            "  ✓ Học NHỊP CÂU và độ dài câu từ mẫu",
            "  ✓ Học BỐ CỤC nếu phù hợp — không bắt buộc",
            "  ✓ Học VĂN PHONG, cách mở đầu và kết thúc",
            "  ✗ KHÔNG override ENGINE 4 — kiểu hook ngẫu nhiên vẫn dùng như bình thường",
            "  → Nội dung mới hoàn toàn — chỉ học nhịp điệu và văn phong từ mẫu",
        ]
    elif level == 'moderate':
        lines += [
            f"  ✓ BLEND DNA từ ít nhất 2 mẫu — không copy một mẫu duy nhất",
            f"  ✓ Hook phải cùng KIỂU với mẫu (xác định kiểu phổ biến nhất trong {count} mẫu)",
            "     (mẫu dùng câu hỏi → viết câu hỏi; mẫu kể chuyện → kể chuyện; mẫu reaction → reaction)",
            "  ✓ Nhịp câu và độ dài câu blend từ mẫu",
            "  ✓ Bố cục theo flow phổ biến nhất của mẫu",
            "  ✓ Văn phong blend từ mẫu — nội dung phải mới hoàn toàn",
            "  ✗ BỎ QUA ENGINE 4 ngẫu nhiên — hook type từ mẫu QUAN TRỌNG HƠN",
        ]
    else:
        lines += [
            f"  ✓ Pattern Blend từ {min(count, 3)} mẫu — tổng hợp DNA thành style mới, không copy bất kỳ mẫu đơn lẻ nào",
            "  ✓ Lấy kiểu hook từ mẫu nhưng kết hợp sáng tạo, không clone",
            "  ✓ Blend nhịp câu, bố cục, văn phong từ nhiều mẫu",
            "  ✓ Nội dung hoàn toàn mới — chỉ FORMAT được blend",
            "  ✗ BỎ QUA ENGINE 4 ngẫu nhiên — Pattern Blend QUAN TRỌNG HƠN",
        ]

    lines += [
        "",
        "⚠ ANTI-COPY GUARD (bắt buộc mọi trường hợp):",
        "  • Hook mới phải KHÁC mẫu ≥70% về từ ngữ — cùng KIỂU nhưng không clone câu mẫu",
        "  • CTA phải KHÁC mẫu ≥60% về từ ngữ",
        "  • 3 hooks phải thật sự khác nhau (không chỉ đổi từ hoặc hoán vị cùng cấu trúc)",
    ]

    clean_avoid = [h.strip() for h in (avoid_hooks or []) if h and h.strip()][:5]
    if clean_avoid:
        lines += ["", "🔄 TRÁNH LẶP LẠI (regenerate — hook mới phải khác hoàn toàn):"]
        for h in clean_avoid:
            lines.append(f'  ✗ KHÔNG dùng lại: "{h[:100]}"')
        lines.append("  → Hook mới: cách mở đầu khác hoàn toàn về cấu trúc câu và góc tiếp cận")

    lines += ["", "MẪU THAM KHẢO:"]
    for i, ex in enumerate(examples[:max_samples], 1):
        lines.append(f'  [{i}] "{ex}"')

    if allow_hook_override:
        lines += [
            "",
            "→ KIỂM TRA CUỐI: Hook lần này có cùng KIỂU với mẫu không? Nhịp câu có gần mẫu không?",
            "   Hook có KHÁC mẫu ≥70% không? Nếu chưa → viết lại trước khi output.",
            "",
        ]
    else:
        lines += [
            "",
            "→ KIỂM TRA CUỐI: Nhịp câu có gần mẫu không? Văn phong có học từ mẫu không?",
            "   Hook có KHÁC mẫu ≥70% không? Nếu chưa → điều chỉnh trước khi output.",
            "",
        ]
    return lines


def resolve_subject_mode(input_data: dict) -> str:
    """Tự động xác định subject mode nếu user chọn auto.
    Ưu tiên: user choice → shooting style mạnh → product keywords → industry → fallback."""
    mode = input_data.get('subjectMode', 'auto')
    if mode and mode != 'auto':
        return mode

    shooting = input_data.get('shootingStyle', 'one-shot')
    industry = input_data.get('industry', 'auto')
    desc = (input_data.get('productDescription', '') + ' ' + input_data.get('productName', '')).lower()

    # Shooting styles với tín hiệu STRONG face (người xuất hiện, nhìn camera)
    if shooting in ('talking-head', 'koc-review', 'ugc', 'livestream-teaser'):
        return 'face'

    # Shooting styles với tín hiệu STRONG no-face (narrator off-camera hoặc POV)
    if shooting in ('pov', 'voiceover'):
        return 'hands'

    # Product keywords → product-only cinematic (check TRƯỚC industry)
    # Áp dụng khi sản phẩm có tính visual cao, không cần người thao tác
    product_kw = (
        'nước hoa', 'đồng hồ', 'trang sức', 'dây chuyền', 'nhẫn', 'nến thơm',
        'decor', 'lọ hoa', 'bình hoa', 'perfume', 'watch', 'jewelry', 'candle',
        'vase', 'earring', 'bông tai', 'vòng tay', 'bracelet',
        'sofa', 'bàn ghế', 'nội thất', 'furniture', 'đèn led', 'đèn ngủ',
        'máy lọc không khí', 'máy pha cà phê', 'loa bluetooth',
    )
    if any(kw in desc for kw in product_kw):
        return 'product'

    # Industry-based (cho style ambiguous: one-shot, review, tiktok-shop)
    if industry == 'fashion':
        return 'face'
    if industry in ('beauty', 'food', 'home', 'electronics', 'baby', 'pet'):
        return 'hands'

    return 'hands'


def get_subject_action_guide(industry: str, resolved_mode: str) -> str:
    """Trả về action guide phù hợp ngành + subject mode."""
    key = (industry, resolved_mode)
    if key in INDUSTRY_SUBJECT_ACTIONS:
        return INDUSTRY_SUBJECT_ACTIONS[key]
    if resolved_mode == 'face':
        return ', '.join(FACE_ACTIONS[:6])
    if resolved_mode == 'hands':
        return ', '.join(HANDS_ACTIONS[:6])
    if resolved_mode == 'product':
        return ', '.join(PRODUCT_ACTIONS[:6])
    return 'demo sản phẩm tự nhiên, phù hợp với nội dung'


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

    # V6: Subject Mode + Production Mode
    subject_mode = input_data.get('subjectMode', 'auto')
    production_mode = input_data.get('productionMode', 'real')
    resolved_mode = resolve_subject_mode(input_data)
    resolved_label = SUBJECT_MODE_LABELS.get(resolved_mode, resolved_mode)
    subject_guide_vo = SUBJECT_MODE_GUIDE.get(resolved_mode, SUBJECT_MODE_GUIDE['auto'])
    industry_for_action = industry if not _is_auto_industry else 'other'
    subject_action_vo = get_subject_action_guide(industry_for_action, resolved_mode)
    subject_tips_vo = SUBJECT_TIPS.get(resolved_mode, SUBJECT_TIPS['auto'])

    img_line = ("Phân tích ảnh sản phẩm:\n" + image_analysis if image_analysis
                else ("Đã đính kèm ảnh sản phẩm." if has_images else "Không có ảnh."))

    persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật, không quảng cáo cứng.')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    _phone_setup = input_data.get('phoneSetup', 'tripod')
    _phone_setup_ctx = {
        'tripod': 'Điện thoại đặt cố định trên tripod/kẹp — 2 tay rảnh hoàn toàn để demo sản phẩm.',
        'selfie': 'Tự cầm điện thoại bằng 1 tay — chỉ có 1 tay rảnh để demo, hành động phải đơn giản phù hợp.',
        'crew': 'Có người khác cầm camera quay — 2 tay rảnh, camera có thể di chuyển/zoom theo người.',
    }.get(_phone_setup, 'Điện thoại đặt cố định — 2 tay rảnh.')

    # V3: Random engines — varied each request
    _pattern = random.choice(STRUCTURE_PATTERNS)
    _hook_type = random.choice(HOOK_TYPES)
    _caption_styles = random.sample(CAPTION_STYLES, 3)
    # V8/V9: Reference Library — policy-based influence, mẫu user tự nhập
    _ref_policy = get_reference_influence_policy(input_data.get('referenceExamples', []))
    _reference_examples = _build_reference_examples_block(input_data.get('referenceExamples', []), policy=_ref_policy)
    _has_ref = _ref_policy['level'] != 'none'
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

    # V9: override ENGINE 4 check trong _struct_check chỉ khi policy cho phép
    if _ref_policy['allow_hook_override']:
        _e4_header = "## ENGINE 4 — HOOK LẦN NÀY"
        _e4_line = f"Hook phải thuộc kiểu: {_hook_type}"
        _check_line = f"- Hook có đúng kiểu '{_hook_short}' không? → Nếu không, viết lại hook."
        _struct_check = [
            "## ENGINE 4 — HOOK LẦN NÀY (override bởi MẪU THAM KHẢO)"
            if line == _e4_header else
            "Hook lần này: học kiểu hook từ MẪU THAM KHẢO bên dưới — KHÔNG dùng kiểu ngẫu nhiên"
            if line == _e4_line else
            "- Hook có cùng KIỂU/NHỊP CÂU với MẪU THAM KHẢO không? → Nếu không, viết lại hook."
            if line == _check_line else
            line
            for line in _struct_check
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
        "## SUBJECT MODE (V6) — BẮT BUỘC",
        f"Chủ thể quay đã xác định: {resolved_label}",
        subject_guide_vo,
        f"Hành động camera / quay phù hợp: {subject_action_vo}",
        "HARD RULE: Mọi hành động trong section5.timeline PHẢI khớp subject mode trên.",
        "Không được dùng action sai subject mode (VD: 'nhìn camera' khi mode=hands, 'orbit sản phẩm' khi mode=face).",
        "",
        "## PRE-WRITE PROTOCOL — làm TRƯỚC khi viết kịch bản",
        *(["0. Xác định NGÀNH HÀNG từ tên + mô tả sản phẩm (Thời trang / Mỹ phẩm / Điện tử / Gia dụng / Thực phẩm / Thú cưng / Mẹ&Bé / Khác) → dùng để chọn camera action ở bước 3."]
          if _is_auto_industry else [f"0. Ngành hàng: {industry_label} — áp dụng camera action phù hợp ngành này ở bước 3."]),
        "1. Xác định HERO BENEFIT — 1 lợi ích bán hàng mạnh nhất cho khách mục tiêu. Ghi vào section2.heroBenefit.",
        "   Ví dụ: " + industry_data.get('hero_examples', "'Lợi ích mạnh nhất' (TT) / 'Thấm nhanh không nhờn' (MP) / 'Pin trâu 2 ngày' (ĐT)"),
        "2. voScript: 70% xoay quanh Hero Benefit. 30% mới nói lợi ích phụ.",
        f"3. Timeline camera action phục vụ Hero Benefit + Subject Mode [{resolved_label}]:",
        f"   {subject_action_vo}",
        "   KHÔNG dùng action sai subject mode trong timeline. Action phải phục vụ Hero Benefit đang nói.",
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
        *_reference_examples,
        "---",
        "",
        "# ĐẦU RA — Chỉ trả về JSON hợp lệ, không text nào ngoài JSON:",
        "",
        '```json',
        '{',
        f'  "section1": {{"productName":"","targetAudience":"","shootingStyle":"Voice Over (ElevenLabs)","duration":"","tone":"","videoGoal":"","subjectMode":"{subject_mode}","subjectModeResolved":"{resolved_mode}","productionMode":"{production_mode}"}},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":"","heroBenefit":""},',
        '  "section3": {"hooks":[{"text":"câu hook tự nhiên mạnh 0-3s, không tag, không chào hỏi","isRecommended":true},{"text":"hook 2 kiểu khác — phủ định hoặc câu hỏi","isRecommended":false},{"text":"hook 3 kiểu khác — nhận xét bất ngờ","isRecommended":false}]},',
        '  "section7": {"captions":["caption 1 ≤100 ký tự + 1-2 emoji","caption 2 ≤100 ký tự + 1-2 emoji","caption 3 ≤100 ký tự + 1-2 emoji"]},',
        '  "section8": {"hashtags":["#tag1","#tag2","#tiktokshop"]},',
        '  "section4": {',
        '    "duration":"30s",',
        '    "hook":"câu hook ngắn (không tag)",',
        '    "voScript":"HOOK:\\nCâu hook mạnh, tự nhiên, không tag...\\n\\nVOICE OVER:\\nCâu 1 như đang trò chuyện...\\nCâu 2 tự nhiên tiếp theo...\\n\\nCTA:\\nCâu kêu gọi cuối tự nhiên...",',
        f'    "lines":[{{"type":"dialogue","text":"câu thoại 1"}},{{"type":"dialogue","text":"câu thoại 2"}}],',
        '    "rawScript":""',
        '  },',
        '  "section5": {"timeline":[{"timeRange":"0-3s","voice":"câu hook (không tag)","action":"hành động camera tương ứng"}]},',
        f'  "section9": {{"tips":["{subject_tips_vo[0] if subject_tips_vo else "Im lặng hoàn toàn khi quay"}","Im lặng hoàn toàn khi quay — giọng sẽ lồng sau qua ElevenLabs","Sync audio và cắt video theo nhịp giọng khi edit","Ánh sáng đủ và ổn định suốt video"]}}',
        '}',
        '```',
        "",
        "Lưu ý cuối:",
        "- voScript: KHÔNG được chứa bất kỳ [tag] nào. Chỉ lời thoại thuần túy.",
        f"- Viết đủ nội dung cho {duration_label}.",
        f"- Setup quay: {_phone_setup_ctx}",
        "- section5 timeline: 'voice' là lời thoại thuần (không tag), 'action' là hành động cụ thể người thực hiện TỰ LÀM được dựa trên setup quay trên — mô tả tay/thân làm gì, không mô tả camera (VD tốt: 'dùng 2 tay kéo nhẹ phần cạp để show độ co giãn rồi nói hook', 'bóp nhẹ vải phần bụng cho thấy độ mềm'. VD SAI: 'đưa sản phẩm vào khung hình', 'camera zoom vào', 'kéo lên gần camera').",
        "- lines[]: mỗi entry là 1 câu/đoạn thoại trong voScript, type luôn là 'dialogue'.",
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

    # Phone setup context
    _phone_setup = input_data.get('phoneSetup', 'tripod')
    _phone_setup_ctx = {
        'tripod': 'Điện thoại đặt cố định trên tripod/kẹp — 2 tay rảnh hoàn toàn để demo sản phẩm.',
        'selfie': 'Tự cầm điện thoại bằng 1 tay — chỉ có 1 tay rảnh để demo, hành động phải đơn giản phù hợp.',
        'crew': 'Có người khác cầm camera quay — 2 tay rảnh, camera có thể di chuyển/zoom theo người.',
    }.get(_phone_setup, 'Điện thoại đặt cố định — 2 tay rảnh.')

    # V6: Subject Mode + Production Mode
    subject_mode = input_data.get('subjectMode', 'auto')
    production_mode = input_data.get('productionMode', 'real')
    resolved_mode = resolve_subject_mode(input_data)
    resolved_label = SUBJECT_MODE_LABELS.get(resolved_mode, resolved_mode)
    subject_guide_text = SUBJECT_MODE_GUIDE.get(resolved_mode, SUBJECT_MODE_GUIDE['auto'])
    industry_for_action = industry if not _is_auto_industry else 'other'
    subject_action_text = get_subject_action_guide(industry_for_action, resolved_mode)
    subject_tips_list = SUBJECT_TIPS.get(resolved_mode, SUBJECT_TIPS['auto'])

    # V3: Random engines — varied each request
    _pattern = random.choice(STRUCTURE_PATTERNS)
    _hook_type = random.choice(HOOK_TYPES)
    _caption_styles = random.sample(CAPTION_STYLES, 3)

    # KOC Discovery Engine — one-shot / review / koc-review + natural-koc
    _is_koc = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'

    # V8/V9: Reference Library — policy-based influence (KOC không override ENGINE 4)
    _ref_policy = get_reference_influence_policy(input_data.get('referenceExamples', []), is_koc=_is_koc)
    _reference_examples = _build_reference_examples_block(input_data.get('referenceExamples', []), policy=_ref_policy)
    _has_ref = _ref_policy['level'] != 'none'
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
        "- Hook có cùng KIỂU/NHỊP CÂU với MẪU THAM KHẢO không? → Nếu không, viết lại."
        if _ref_policy['allow_hook_override'] else
        f"- Hook có đúng kiểu '{_hook_short_check}' không? → Nếu không, viết lại.",
        f"- Cấu trúc có đúng '{_pattern_short}' không? → Điều chỉnh nếu lệch.",
        "- Có câu nào giống AI/MC/văn quảng cáo không? → Viết lại.",
        "- Có đoạn liệt kê tính năng không? → Chuyển sang lợi ích cụ thể.",
        "- Hero Benefit có xuất hiện ở đa số lời thoại không? → Nếu không, tăng tỷ lệ.",
        "- Lời thoại đọc to lên nghe tự nhiên không? → Nếu không, viết lại.",
        "Nếu chưa đạt → tự chỉnh sửa trước khi xuất JSON.",
        "",
    ]
    # V9: Override ENGINE 4 chỉ khi policy cho phép (count≥2, không KOC, không selectedHook)
    if _ref_policy['allow_hook_override']:
        _engine4_lines = [
            "**ENGINE 4 — HOOK LẦN NÀY:** từ MẪU THAM KHẢO (xem phần cuối) — không dùng kiểu ngẫu nhiên",
            "Hook đi thẳng vào nội dung. Không lời chào, không giới thiệu bản thân.",
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
        "**SUBJECT MODE (V6) — BẮT BUỘC:**",
        f"Chủ thể quay đã xác định: {resolved_label}",
        subject_guide_text,
        f"Action phù hợp ({resolved_label}): {subject_action_text}",
        "HARD RULE: Mọi action trong section5.timeline PHẢI khớp subject mode. Không dùng action sai subject mode.",
        "",
        *_koc_extra,
        *( [""] if _koc_extra else [] ),
        *_selfcheck_lines,
        *_reference_examples,
        "---",
        "",
        "# YÊU CẦU ĐẦU RA",
        "",
        "Chỉ trả về JSON hợp lệ, không có text nào bên ngoài JSON:",
        "",
        '```json',
        '{',
        f'  "section1": {{"productName":"","targetAudience":"","shootingStyle":"","duration":"","tone":"","videoGoal":"","subjectMode":"{subject_mode}","subjectModeResolved":"{resolved_mode}","productionMode":"{production_mode}"}},',
        '  "section2": {"targetCustomer":"","painPoints":"","insight":"","highlights":"","mainBenefits":"","usageSituations":"","heroBenefit":""},',
        '  "section3": {"hooks":[{"text":"hook 1","isRecommended":true},{"text":"hook 2","isRecommended":false},{"text":"hook 3","isRecommended":false}]},',
        '  "section7": {"captions":["1 câu ngắn ≤100 ký tự: tên SP + lợi ích + 1-2 emoji + CTA","caption 2 góc khác cũng ≤100 ký tự","caption 3 góc khác cũng ≤100 ký tự"]},',
        '  "section8": {"hashtags":["#tag_chinh_xac_san_pham","#tag_niche","#tag_rong","#tiktokshop","#reviewsanpham"]},',
        f'  "section4": {{"duration":"","hook":"","lines":[{{"type":"dialogue","text":"câu thoại 1"}},{{"type":"dialogue","text":"câu thoại 2"}}],"rawScript":""}},',
        '  "section5": {"timeline":[{"timeRange":"0-3s","description":"hook + bước vào khung hình"}]},',
        f'  "section9": {{"tips":["{subject_tips_list[0] if subject_tips_list else "Ổn định camera"}","lưu ý 2","lưu ý 3"]}}',
        '}',
        '```',
        "",
        "Lưu ý quan trọng:",
        "- Kịch bản: hoàn toàn mới mỗi lần, lời thoại tự nhiên như đang nói thật. lines[] chỉ chứa dialogue thuần.",
        f"- Setup quay: {_phone_setup_ctx}",
        "- section5 timeline: mô tả hành động cụ thể tay/thân người thực hiện TỰ LÀM được dựa trên setup quay trên (VD tốt: 'dùng 2 tay kéo nhẹ phần cạp để show độ co giãn rồi nói hook', 'bóp nhẹ vải phần bụng cho thấy độ mềm', 'xoay người nhẹ để show form ôm gọn'. VD SAI: 'camera quay cận', 'đưa sản phẩm vào khung hình', 'kéo lên gần camera').",
        f"- section9 tips: viết 4-6 lưu ý phù hợp subject mode '{resolved_label}'. Ví dụ: {' / '.join(subject_tips_list[:2]) if len(subject_tips_list) >= 2 else 'lưu ý quay phù hợp'}.",
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
        # V5 fields — backward compat: section1 V6 fields default to empty strings
        'section1': {'productName': '', 'targetAudience': '', 'shootingStyle': '', 'duration': '', 'tone': '', 'videoGoal': '', 'subjectMode': '', 'subjectModeResolved': '', 'productionMode': ''},
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
        elif key == 'section1':
            # Merge V6 fields into old scripts without overwriting existing values
            for field, val in default.items():
                if field not in parsed[key]:
                    parsed[key][field] = val

    parsed['rawResponse'] = raw
    return parsed


SECTION_SYSTEM = "Bạn là chuyên gia viết kịch bản TikTok Shop. Chỉ trả về JSON hợp lệ, không thêm text nào bên ngoài JSON."


def build_section_prompt(section: str, product_name: str, product_desc: str,
                         input_data: dict, current_script: dict, selected_hook: str = '',
                         avoid_hooks: list = None) -> tuple:
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

    # V6: Subject Mode
    _resolved_mode_sec = resolve_subject_mode(input_data)
    _resolved_label_sec = SUBJECT_MODE_LABELS.get(_resolved_mode_sec, _resolved_mode_sec)
    _subject_action_sec = get_subject_action_guide(industry if industry != 'auto' else 'other', _resolved_mode_sec)
    _subject_tips_sec = SUBJECT_TIPS.get(_resolved_mode_sec, SUBJECT_TIPS['auto'])
    _subject_note = f"\nSUBJECT MODE: {_resolved_label_sec} — action phải khớp: {_subject_action_sec}"

    base = f"Sản phẩm: {product_name}\nMô tả: {product_desc}"
    if audience:
        base += f"\nĐối tượng: {audience}"

    shooting_guide = SHOOTING_GUIDE.get(shooting, '')
    tone_guide = TONE_GUIDE.get(tone, '')
    goal_guide = GOAL_GUIDE.get(input_data.get('videoGoal', ''), '')

    _phone_setup = input_data.get('phoneSetup', 'tripod')
    _phone_setup_ctx = {
        'tripod': 'Điện thoại đặt cố định trên tripod/kẹp — 2 tay rảnh hoàn toàn để demo sản phẩm.',
        'selfie': 'Tự cầm điện thoại bằng 1 tay — chỉ có 1 tay rảnh để demo, hành động phải đơn giản phù hợp.',
        'crew': 'Có người khác cầm camera quay — 2 tay rảnh, camera có thể di chuyển/zoom theo người.',
    }.get(_phone_setup, 'Điện thoại đặt cố định — 2 tay rảnh.')

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
            _sec_policy = get_reference_influence_policy(
                input_data.get('referenceExamples', []), has_selected_hook=bool(selected_hook))
            if _sec_policy['allow_hook_override']:
                _hook_type = 'từ MẪU THAM KHẢO — xem phần dưới, không dùng kiểu ngẫu nhiên'
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
{_subject_note}

Tạo voScript lời thoại thuần túy (ElevenLabs V3 Enhance tự thêm emotion — KHÔNG được viết tag [xxx] nào).{hook_instruction}

Quy tắc viết voScript:
- Viết như người đang NÓI, không phải viết văn
- Không mở đầu kiểu AI/MC: 'Xin chào', 'Hôm nay mình', 'Đây là sản phẩm'
- Không dùng cấu trúc AI: 'Ngoài ra...', 'Đặc biệt...', 'Sản phẩm có...'
- Được dùng reaction độc lập, ngắt nhịp, câu bỏ lửng
- CTA cuối: tự nhiên, không ép mua
- Setup quay: {_phone_setup_ctx}
- timeline 'action': mô tả tay/thân làm gì — người tự làm được dựa trên setup trên. VD SAI: 'đưa sản phẩm vào khung hình', 'camera zoom vào'.

```json
{{"section4":{{"duration":"{duration_label}","hook":"{selected_hook or 'câu hook tự nhiên mạnh, không tag'}","voScript":"HOOK:\\nCâu hook mạnh tự nhiên không có tag...\\n\\nVOICE OVER:\\nCâu 1 như đang nói chuyện thật...\\nCâu 2 tự nhiên...\\n\\nCTA:\\nCâu kêu gọi cuối tự nhiên...","lines":[{{"type":"dialogue","text":"câu thoại 1"}},{{"type":"dialogue","text":"câu thoại 2"}}],"rawScript":""}},"section5":{{"timeline":[{{"timeRange":"0-3s","voice":"câu hook thuần (không tag)","action":"hành động cụ thể người thực hiện tự làm được"}}]}}}}
```"""
        else:
            _pattern = random.choice(STRUCTURE_PATTERNS)
            _hook_type = random.choice(HOOK_TYPES) if not selected_hook else 'theo hook đã chọn'
            _is_koc_sec = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'
            _sec_policy = get_reference_influence_policy(
                input_data.get('referenceExamples', []), is_koc=_is_koc_sec, has_selected_hook=bool(selected_hook))
            if _sec_policy['allow_hook_override']:
                _hook_type = 'từ MẪU THAM KHẢO — xem phần dưới, không dùng kiểu ngẫu nhiên'
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
{_koc_block}{_subject_note}

Tạo kịch bản mới và timeline quay tương ứng. Lời thoại tự nhiên. Setup quay: {_phone_setup_ctx} Timeline viết theo góc nhìn người thực hiện — mô tả tay/thân làm gì, cụ thể, làm được ngay dựa trên setup trên. VD SAI: 'camera zoom vào', 'đưa sản phẩm vào khung hình'.{"" if not selected_hook else " Câu đầu tiên của kịch bản PHẢI là hook đã cho, không được thay đổi."}

```json
{{"section4":{{"duration":"{duration_label}","hook":"{selected_hook or 'câu hook mở đầu'}","lines":[{{"type":"dialogue","text":"câu thoại 1"}},{{"type":"dialogue","text":"câu thoại 2"}}],"rawScript":""}},"section5":{{"timeline":[{{"timeRange":"0-3s","description":"hook + bước vào khung hình"}}]}}}}
```"""

    elif section == 'hooks':
        s2 = current_script.get('section2', {})
        analysis = '\n'.join(filter(None, [
            f"Hero Benefit: {s2.get('heroBenefit','')}" if s2.get('heroBenefit') else '',
            f"Pain point: {s2.get('painPoints','')}" if s2.get('painPoints') else '',
            f"Insight: {s2.get('insight','')}" if s2.get('insight') else '',
            f"Điểm nổi bật: {s2.get('highlights','')}" if s2.get('highlights') else '',
        ]))
        # V3: Pick 3 different hook types; V9: policy-based override when library active
        _hook_types_3 = random.sample(HOOK_TYPES, 3)
        _is_koc_hooks = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'
        _hooks_policy = get_reference_influence_policy(input_data.get('referenceExamples', []), is_koc=_is_koc_hooks)
        if _hooks_policy['allow_hook_override']:
            _hook_req = (
                "  Hook 1 (khuyên dùng): Xác định kiểu hook mẫu dùng (câu hỏi / kể chuyện / reaction / tiết lộ...) "
                "→ viết hook cùng KIỂU ĐÓ, cùng NHỊP CÂU, cùng VĂN PHONG\n"
                "  Hook 2: Biến thể cùng kiểu hook từ mẫu — cùng format câu nhưng góc pain point khác\n"
                f"  Hook 3: {_hook_types_3[2]} (hook tự do để tăng đa dạng)"
            )
        else:
            _hook_req = (
                f"  Hook 1 (khuyên dùng): {_hook_types_3[0]}\n"
                f"  Hook 2: {_hook_types_3[1]}\n"
                f"  Hook 3: {_hook_types_3[2]}"
            )
        if shooting == 'voiceover':
            persona_guide = VO_PERSONA_GUIDE.get(tone, 'Nói tự nhiên như người thật.')
            user = f"""{base}
{analysis}
{context_line}

Persona: {persona_guide}

Tạo 3 hook Voice Over khác nhau (0-3 giây đầu). Hook đầu tiên là hook khuyên dùng.

Yêu cầu 3 kiểu hook:
{_hook_req}

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

Yêu cầu 3 kiểu hook:
{_hook_req}

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
        _subject_tips_hint = f'\nSubject Mode [{_resolved_label_sec}]: {chr(10).join("- " + t for t in _subject_tips_sec)}'
        user = f"""{base}
{context_line}{_tips_industry_hint}{_subject_tips_hint}

Tạo 4-6 lưu ý thực tế khi quay video cho sản phẩm này.
Subject Mode: {_resolved_label_sec}. Tips PHẢI phù hợp với subject mode này.
Gồm: setup góc máy phù hợp subject mode + ngành, cách demo rõ Hero Benefit, ánh sáng, âm thanh, lưu ý đặc thù kiểu quay này.
{"Voiceover: nhấn mạnh tắt micro hoàn toàn, đồng bộ hành động theo script." if shooting == "voiceover" else ""}

```json
{{"section9":{{"tips":["lưu ý 1","lưu ý 2"]}}}}
```"""

    else:
        raise ValueError(f'Section không hợp lệ: {section}')

    # Inject reference library vào hooks và script — policy-aware, với avoid_hooks variation rule
    if section in ('script', 'hooks'):
        _is_koc_inj = shooting in ('one-shot', 'review', 'koc-review') and tone == 'natural-koc'
        _inj_policy = get_reference_influence_policy(
            input_data.get('referenceExamples', []), is_koc=_is_koc_inj,
            has_selected_hook=bool(selected_hook))
        _ref_lines = _build_reference_examples_block(
            input_data.get('referenceExamples', []), policy=_inj_policy, avoid_hooks=avoid_hooks)
        if _ref_lines:
            _ref_block = '\n'.join(_ref_lines)
            user = user.replace('\n```json\n', f'\n{_ref_block}\n```json\n', 1)

    return SECTION_SYSTEM, user


# ============================================================
# V6: AI VISUAL PROMPT MODULE
# ============================================================

# ============================================================
# V6.1: PRODUCT LOCK ENGINE — fix Seedream/Seedance tự vẽ lại sản phẩm
# ============================================================
# Vấn đề: khi AI viết prompt kiểu "make the product look compact, premium,
# and identical...", Seedream vẫn hiểu nhiệm vụ là VẼ LẠI sản phẩm → sai
# hình dáng/cổng/logo. Giải pháp: KHÔNG để AI tự viết phần Product Lock.
# Python lắp ráp các block PRODUCT LOCK/negative prompt CỐ ĐỊNH (nguyên văn),
# AI chỉ được yêu cầu mô tả bối cảnh/ánh sáng/camera/chuyển động xung quanh
# sản phẩm — không bao giờ được mô tả lại chính sản phẩm. Điều này đảm bảo
# Product Lock luôn đúng 100%, không phụ thuộc việc AI có tuân thủ hay không.

PRODUCT_LOCK_IMAGE_TEXT = (
    "PRODUCT LOCK — BẮT BUỘC:\n"
    "Dùng ảnh sản phẩm đã upload làm reference tuyệt đối. Không thiết kế lại, không diễn giải lại, "
    "không đơn giản hóa, không thay thế, không cách điệu hóa, không tạo phiên bản mới của sản phẩm. "
    "Giữ nguyên chính xác hình dạng, tỉ lệ, cổng kết nối, nút bấm, phích cắm, vị trí logo, màu sắc, "
    "chất liệu, chi tiết bề mặt và mọi đặc điểm thiết kế nhìn thấy được từ ảnh gốc."
)

PRODUCT_LOCK_VIDEO_TEXT = (
    "VIDEO PRODUCT LOCK — BẮT BUỘC:\n"
    "Chỉ animate ảnh scene đã cung cấp. Không biến dạng, không thiết kế lại, không thay thế, "
    "không làm chảy nhão, không co giãn thành vật thể khác, không đổi cổng kết nối, không đổi nút bấm, "
    "không đổi logo, không đổi phích cắm, không thay đổi hình học sản phẩm. "
    "Sản phẩm phải giữ nguyên hình dạng xuyên suốt toàn bộ clip."
)

GLOBAL_NEGATIVE_PROMPT_TEXT = (
    "sản phẩm chung chung, sản phẩm thiết kế lại, hình dạng sản phẩm thay đổi, tỉ lệ sản phẩm sai, "
    "cổng kết nối sai, nút bấm sai, phích cắm sai, thiếu phích cắm, thêm phích cắm, logo thay đổi, "
    "logo giả, chữ giả, bao bì thay đổi, màu sắc khác, sản phẩm nhân đôi hoặc thêm sản phẩm, "
    "phụ kiện mới, cáp thêm, cáp giả, hình học sản phẩm méo mó, sản phẩm mờ, "
    "sản phẩm thiếu chi tiết, sản phẩm chảy nhão, sản phẩm cong vênh, sản phẩm biến hình, "
    "phong cách hoạt hình, phong cách CGI, "
    "watermark, watermark TikTok, logo TikTok, logo cửa hàng, logo shop, "
    "chữ đè lên ảnh, phụ đề, chữ giá tiền, badge giảm giá, nhãn khuyến mãi, "
    "chữ sao chép từ ảnh tham chiếu, chữ bắt chước ảnh gốc, chữ tiếng Trung từ ảnh gốc, "
    "nền từ ảnh tham chiếu, background bắt chước ảnh gốc, "
    "người mẫu từ ảnh tham chiếu, quần áo người mẫu từ ảnh gốc, "
    "bàn tay biến dạng, ngón tay thừa, thiếu ngón tay, thêm bàn tay, ba tay trở lên, "
    "bàn tay lơ lửng rời cơ thể, "
    "khuôn mặt lộ ra khi chỉ được phép quay tay, nền lộn xộn"
)

SUBJECT_MODE_NEGATIVE_EXTRA = {
    'hands': "khuôn mặt, mắt, nụ cười, nhìn vào camera, nét mặt, mặt người",
    'product': "tay cầm sản phẩm, khuôn mặt, người, người mẫu",
    'face': "",
}

SUBJECT_MODE_IMAGE_RULE = {
    'hands': (
        "Bố cục chỉ có tay. CHÍNH XÁC một đôi tay (2 bàn tay, thuộc về cùng một người) xuất hiện trong khung — "
        "không bao giờ hiện tay của người thứ hai, không bao giờ có hơn 2 bàn tay, không nhân đôi hay lặp lại bàn tay. "
        "Tay nhẹ nhàng đỡ hoặc tương tác với sản phẩm trong MỘT hành động đơn duy nhất "
        "(ví dụ: chỉ cầm, HOẶC chỉ mở ra, HOẶC chỉ cắm vào — không kết hợp nhiều hành động tay đồng thời trong một khung) "
        "mà không che khuất chi tiết quan trọng ở mặt trước (cổng kết nối, nút bấm, phích cắm, logo). "
        "Không khuôn mặt, không mắt, không nét mặt, không thấy bất kỳ phần nào của người trong khung."
    ),
    'face': (
        "Một người có thể xuất hiện tự nhiên trong khung, cầm hoặc demo sản phẩm. Sản phẩm "
        "phải luôn hiển thị đầy đủ — tay không được che cổng kết nối, nút bấm, phích cắm, hay logo. "
        "Chỉ thấy tay của một người (một đôi, 2 bàn tay)."
    ),
    'product': (
        "Bố cục chỉ có sản phẩm. Không người, không tay, không khuôn mặt ở bất kỳ đâu trong khung. "
        "Phong cách chụp sản phẩm thuần túy / packshot — sản phẩm là chủ thể duy nhất."
    ),
}

INPUT_IMAGES_REFERENCE_STEP = [
    "Ảnh sản phẩm — ảnh sản phẩm cần giữ nguyên chính xác (bắt buộc)",
    "Ảnh người mẫu / thú cưng / em bé — để lock nhân vật nhất quán xuyên suốt (tùy chọn)",
    "Ảnh bối cảnh — phong cách nền/ánh sáng tham khảo (tùy chọn)",
]

INPUT_IMAGES_SCENE_STEP = [
    "Ảnh sản phẩm — reference sản phẩm chính xác, ưu tiên cao nhất (bắt buộc)",
    "Ảnh reference — dùng để giữ nhất quán tay/nền/ánh sáng/bố cục (bắt buộc)",
    "Ảnh người mẫu / thú cưng / em bé — giữ nhất quán nhân vật xuyên suốt các scene (tùy chọn)",
]

INPUT_IMAGES_VIDEO_STEP = [
    "Ảnh scene — ảnh tĩnh cần animate (bắt buộc)",
    "Ảnh reference — giữ nhất quán bối cảnh (bắt buộc)",
    "Ảnh người mẫu / thú cưng / em bé — lock nhân vật khi animate nếu Freepik hỗ trợ (tùy chọn)",
]


INDUSTRY_BACKGROUND_STYLE = {
    'home':        'bối cảnh sử dụng thực tế (phòng khách, bếp, phòng ngủ, không gian gia đình)',
    'food':        'bố cục food styling hấp dẫn, ánh sáng ấm, props phù hợp (đĩa, thớt, khăn bàn)',
    'fashion':     'bối cảnh lifestyle phù hợp phong cách trang phục',
    'beauty':      'nền tối giản hoặc bàn trang điểm, ánh sáng mềm làm nổi kết cấu và màu sắc sản phẩm',
    'pet':         'bối cảnh thân thiện với thú cưng (sàn nhà, thảm, ngoài vườn)',
    'baby':        'bối cảnh ấm áp mềm mại (phòng trẻ em, chăn êm, ánh sáng dịu)',
    'electronics': 'nền tối giản sạch (trắng/xám/đen), bề mặt phẳng chuyên nghiệp',
}

INDUSTRY_EXTRA_GUIDANCE = {
    'home': (
        "GIA DỤNG — BỐI CẢNH LÀ CÂU CHUYỆN:\n"
        "Đặt sản phẩm trong không gian sống thực tế phù hợp — không dùng nền trắng tối giản. "
        "Môi trường xung quanh giúp người xem hình dung sản phẩm trong nhà họ."
    ),
    'food': (
        "THỰC PHẨM — FOOD STYLING:\n"
        "Màu sắc tươi sáng, bắt mắt, ánh sáng ấm làm thực phẩm trông ngon miệng. "
        "Có thể dùng props (đĩa, thớt gỗ, khăn bàn, nguyên liệu tươi xung quanh). "
        "Có thể hiển thị sản phẩm đang được thưởng thức, mở ra để thấy bên trong, "
        "hoặc hiệu ứng tự nhiên hấp dẫn (hơi nước, chảy, đổ, đá tan)."
    ),
    'fashion': (
        "THỜI TRANG — SHOWCASE TRANG PHỤC:\n"
        "Góc quay và ánh sáng làm nổi bật chất liệu, màu sắc, đường may của trang phục/phụ kiện. "
        "Bối cảnh lifestyle tự nhiên phù hợp phong cách item. "
        "Người mẫu chuyển động thoải mái, tự nhiên — không pose cứng nhắc."
    ),
    'beauty': (
        "LÀM ĐẸP — KẾT CẤU VÀ HIỆU QUẢ:\n"
        "Ánh sáng mềm, hướng sáng phù hợp làm nổi kết cấu sản phẩm (kem, lỏng, bột, sáp). "
        "Thể hiện màu sắc thật, độ bóng, độ mịn khi sản phẩm tiếp xúc với da. "
        "Có thể dùng props tối giản (khăn trắng, hoa khô, bình thủy tinh) để tạo không khí chăm sóc bản thân."
    ),
    'pet': (
        "THÚ CƯNG — CHỦ THỂ CÓ THỂ LÀ ĐỘNG VẬT:\n"
        "Nếu thú cưng xuất hiện trong cảnh, chúng là chủ thể chính — "
        "thể hiện phản ứng tự nhiên, vui vẻ, thoải mái khi dùng sản phẩm."
    ),
    'baby': (
        "MẸ & BÉ — NHÂN VẬT VÀ CẢM XÚC:\n"
        "Tone màu ấm áp, ánh sáng mềm mại, an toàn và đáng tin cậy. "
        "Nếu có em bé trong cảnh, thể hiện cảm xúc tự nhiên vui vẻ, thoải mái."
    ),
}

FALLBACK_CAMERA_MOVEMENTS = [
    "Cận cảnh tĩnh, đẩy nhẹ vào sản phẩm",
    "Pan chậm từ trái sang phải, ngang tầm mắt",
    "Góc từ trên xuống tĩnh, zoom nhẹ vào sản phẩm",
    "Chuyển động cầm tay nhẹ, đóng khung gần",
    "Xoay chậm quanh chủ thể, góc cận trung bình",
]

FALLBACK_MOTION_VISUALS = [
    "Chuyển động tự nhiên nhẹ nhàng, tay dịch chuyển nhẹ",
    "Chuyển động liên tục mượt mà theo hướng camera",
    "Chuyển động nhẹ hé lộ góc nhìn mới của scene",
    "Chuyển động đều ổn định với vi chuyển động tự nhiên",
    "Chuyển động nhẹ nhàng kèm dịch chuyển ánh sáng xung quanh",
]


def _fallback_camera_movement(index: int) -> str:
    return FALLBACK_CAMERA_MOVEMENTS[index % len(FALLBACK_CAMERA_MOVEMENTS)]


def _fallback_motion_visual(index: int) -> str:
    return FALLBACK_MOTION_VISUALS[index % len(FALLBACK_MOTION_VISUALS)]


def _align_scenes_to_timeline(ai_scenes: list, timeline: list) -> list:
    """Ép 1:1 giữa timeline gốc (script.section5.timeline) và scenes — không phụ thuộc AI
    trả đúng số lượng/thứ tự. timeRange/description luôn lấy từ timeline gốc làm ground truth;
    AI draft chỉ đóng góp phần creative (sceneVisual/motionVisual/cameraMovement/purpose).
    Nếu AI trả thiếu scene → bổ sung rỗng (dùng fallback ở nơi gọi). Nếu trả dư → cắt bỏ."""
    if not timeline:
        return ai_scenes or [{}]
    aligned = []
    for i, t in enumerate(timeline):
        draft = ai_scenes[i] if i < len(ai_scenes) else {}
        draft = draft or {}
        aligned.append({
            **draft,
            'scene': i + 1,
            'timeRange': t.get('timeRange', '') or draft.get('timeRange', ''),
            'description': draft.get('description') or t.get('description') or t.get('voice', '') or '',
            '_action': t.get('action', ''),
            '_voice': t.get('voice', '') or t.get('description', ''),
        })
    return aligned


def _build_visual_workflow(img_model: str, vid_model: str, aspect_ratio: str) -> dict:
    """Workflow cố định bằng Python (không qua AI) — đúng quy trình Freepik Flow 3 bước."""
    return {
        "title": "Freepik Flow Workflow",
        "imageModel": img_model,
        "videoModel": vid_model,
        "aspectRatio": aspect_ratio,
        "productLockNote": (
            "Luôn upload Ảnh Sản Phẩm làm reference ưu tiên cao nhất. "
            "Không để AI tự vẽ lại sản phẩm."
        ),
        "steps": [
            {
                "step": 1,
                "title": "Tạo Ảnh Reference",
                "inputImages": ["Ảnh sản phẩm"],
                "instruction": "Tạo bối cảnh reference sạch. Ảnh sản phẩm upload là reference sản phẩm chính xác.",
            },
            {
                "step": 2,
                "title": "Tạo Ảnh từng Scene",
                "inputImages": ["Ảnh sản phẩm", "Ảnh reference"],
                "instruction": "Dùng Ảnh Sản Phẩm để giữ đúng sản phẩm. Ảnh Reference chỉ để giữ tay/nền/ánh sáng nhất quán.",
            },
            {
                "step": 3,
                "title": "Tạo Video từng Scene",
                "inputImages": ["Ảnh scene", "Ảnh reference", "Ảnh sản phẩm"],
                "instruction": "Animate Ảnh Scene. Giữ nguyên hình học sản phẩm — không biến dạng.",
            },
        ],
    }


def _build_model_ref_instruction(resolved_mode: str, industry: str) -> str:
    """Instruction dùng ảnh người mẫu / thú cưng / em bé, thay đổi theo ngành."""
    if industry == 'pet':
        return (
            "SỬ DỤNG ẢNH THÚ CƯNG THAM CHIẾU (nếu được upload):\n"
            "Dùng ảnh thú cưng để lock giống, màu lông, vóc dáng — "
            "giữ nguyên ngoại hình thú cưng chính xác xuyên suốt mọi scene. "
            "CHỈ dùng để tham chiếu con vật — KHÔNG lấy đồ vật/nền từ ảnh đó.\n\n"
        )
    if resolved_mode not in ('face', 'hands'):
        return ''
    if industry == 'baby':
        return (
            "SỬ DỤNG ẢNH EM BÉ / NGƯỜI MẪU THAM CHIẾU (nếu được upload):\n"
            "Dùng ảnh em bé hoặc người mẫu để lock khuôn mặt, tóc, vóc dáng — "
            "giữ nguyên ngoại hình chính xác xuyên suốt. "
            "CHỈ dùng để tham chiếu nhân vật — KHÔNG lấy trang phục/phụ kiện từ ảnh đó.\n\n"
        )
    return (
        "SỬ DỤNG ẢNH NGƯỜI MẪU (nếu được upload):\n"
        "Dùng ảnh người mẫu để lock khuôn mặt, tóc, tông da, vóc dáng — "
        "giữ nguyên ngoại hình người mẫu chính xác như ảnh tham chiếu. "
        "KHÔNG thay đổi khuôn mặt, KHÔNG thay đổi màu tóc, KHÔNG thay đổi vóc dáng. "
        "CHỈ dùng để tham chiếu con người — "
        "KHÔNG dùng trang phục/phụ kiện của người mẫu trong ảnh đó.\n\n"
    )


def _build_negative_prompt(resolved_mode: str, industry: str = '') -> str:
    base = GLOBAL_NEGATIVE_PROMPT_TEXT
    if industry == 'food':
        # Thực phẩm: chảy/đổ/tan là hiệu ứng tự nhiên hấp dẫn, không phải lỗi
        for term in ('sản phẩm chảy nhão, ', 'sản phẩm cong vênh, ', 'sản phẩm biến hình, '):
            base = base.replace(term, '')
    parts = [base]
    mode_extra = SUBJECT_MODE_NEGATIVE_EXTRA.get(resolved_mode, '')
    if mode_extra and industry in ('pet', 'baby') and resolved_mode == 'hands':
        # Hands mode cho pet/baby: loại bỏ các term ức chế khuôn mặt —
        # thú cưng và em bé được phép hiện mặt trong cảnh,
        # chỉ giữ "mặt người" để vẫn ức chế khuôn mặt NGƯỜI không mong muốn.
        # Product mode KHÔNG xóa — "khuôn mặt" trong product mode vẫn cần chặn.
        for term in ('khuôn mặt, ', 'mắt, ', 'nụ cười, ', 'nhìn vào camera, ', 'nét mặt, '):
            mode_extra = mode_extra.replace(term, '')
        mode_extra = mode_extra.strip(', ')
    if mode_extra:
        parts.append(mode_extra)
    return ', '.join(p.strip(', ') for p in parts if p)


def _build_continuity_block(environment: str, lighting: str, character_or_hands: str) -> str:
    """Khối NHẤT QUÁN — lặp lại nguyên văn trong reference/image/video prompt để giữ
    bối cảnh/ánh sáng/kiểu tay nhất quán giữa các scene (mỗi lần gọi Seedream/Seedance là
    1 generation độc lập, không có trí nhớ — chỉ có text lặp lại mới giữ được continuity)."""
    lines = []
    if environment:
        lines.append(f"- Nền/bối cảnh: {environment}")
    if lighting:
        lines.append(f"- Ánh sáng: {lighting}")
    if character_or_hands:
        lines.append(f"- Kiểu tay/nhân vật: {character_or_hands}")
    if not lines:
        return ""
    return "TÍNH NHẤT QUÁN (giữ nguyên cho tất cả các scene):\n" + "\n".join(lines) + "\n\n"


def _build_reference_prompt_text(resolved_mode: str, reference_scene: str, aspect_ratio: str,
                                  environment: str = '', lighting: str = '', character_or_hands: str = '',
                                  industry: str = '') -> str:
    """Template cố định — PRODUCT LOCK nguyên văn. AI chỉ điền phần 'Bối cảnh' (scene).
    NHẤT QUÁN block thiết lập bối cảnh/ánh sáng/tay làm chuẩn cho các scene sau dùng lại."""
    style_line = {
        'hands': "Bố cục cận cảnh ưu tiên sản phẩm",
        'face': "Bố cục lifestyle tự nhiên với người và sản phẩm đều hiển thị",
        'product': "Bố cục studio packshot, sản phẩm là chủ thể duy nhất",
    }.get(resolved_mode, "Bố cục cận cảnh ưu tiên sản phẩm")
    continuity = _build_continuity_block(environment, lighting, character_or_hands)
    bg_style = INDUSTRY_BACKGROUND_STYLE.get(industry, 'nền tối giản sạch')
    extra_guidance = INDUSTRY_EXTRA_GUIDANCE.get(industry, '')
    extra_section = f"{extra_guidance}\n\n" if extra_guidance else ''
    model_ref_instruction = _build_model_ref_instruction(resolved_mode, industry)

    return (
        f"Tạo ảnh reference dọc {aspect_ratio} phong cách UGC thực tế TikTok Shop, "
        f"dùng ảnh sản phẩm đã upload làm sản phẩm chính xác.\n\n"
        f"{PRODUCT_LOCK_IMAGE_TEXT}\n\n"
        "LỌC ẢNH SẢN PHẨM THAM CHIẾU (ảnh upload có thể là ảnh TikTok/e-commerce chứa nhiễu):\n"
        "Từ ảnh sản phẩm, chỉ trích xuất HÌNH THỂ VẬT LÝ sản phẩm chính: "
        "hình dạng, màu sắc, chất liệu bề mặt, chi tiết thiết kế. "
        "Bỏ qua và KHÔNG tái tạo: người mẫu, nền ảnh gốc, chữ/watermark/giá tiền/badge, "
        "logo cửa hàng, phụ kiện không phải sản phẩm chính.\n\n"
        f"{model_ref_instruction}"
        "NẾU CÓ ẢNH BỐI CẢNH (tùy chọn):\n"
        "Dùng làm reference phong cách nền/ánh sáng/không khí — học tông màu, độ sáng, không gian. "
        "KHÔNG copy nguyên xi, chỉ học phong cách. "
        "KHÔNG đưa đồ vật, người, chi tiết cụ thể từ ảnh bối cảnh vào output.\n\n"
        f"{continuity}"
        f"{extra_section}"
        f"Bối cảnh:\n{reference_scene}\n\n"
        f"Camera:\n{style_line}, dọc {aspect_ratio}, ánh sáng tự nhiên mềm, nét rõ trên sản phẩm, "
        f"{bg_style}, phong cách review TikTok Shop UGC.\n\n"
        f"Số tay (nếu có tay): đúng một đôi tay (2 bàn tay, một người) — không được nhiều hơn.\n\n"
        f"Không thêm chữ, phụ đề, nhãn, icon, cáp thêm, cổng thêm, phụ kiện thêm, "
        f"thương hiệu mới, chi tiết sản phẩm mới, tay thêm, hoặc nhân đôi bàn tay."
    )


def _build_image_prompt_text(resolved_mode: str, scene_visual: str,
                              environment: str = '', lighting: str = '', character_or_hands: str = '',
                              voice_hint: str = '', industry: str = '') -> str:
    """Template cố định — PRODUCT LOCK nguyên văn. AI chỉ điền phần 'CẢNH' (bối cảnh/hành động).
    NHẤT QUÁN block lặp lại environment/lighting/hands-style từ visualDirector ở mọi scene
    để Seedream giữ bối cảnh nhất quán xuyên suốt video (mỗi scene là 1 generation độc lập)."""
    subject_rule = SUBJECT_MODE_IMAGE_RULE.get(resolved_mode, SUBJECT_MODE_IMAGE_RULE['hands'])
    continuity = _build_continuity_block(environment, lighting, character_or_hands)
    bg_style = INDUSTRY_BACKGROUND_STYLE.get(industry, 'nền sạch')
    extra_guidance = INDUSTRY_EXTRA_GUIDANCE.get(industry, '')
    extra_section = f"{extra_guidance}\n\n" if extra_guidance else ''
    voice_section = (
        f"THÔNG ĐIỆP CẦN HỖ TRỢ:\n\"{voice_hint}\"\n"
        "→ Chọn góc chụp và bố cục để hình ảnh bổ trợ thông điệp này "
        "(ví dụ: thấy nhãn thông số, thấy hiệu quả, thấy tính năng đang được đề cập)\n\n"
    ) if voice_hint and voice_hint.strip() else ''
    model_ref_instruction = _build_model_ref_instruction(resolved_mode, industry)
    model_ref_short = (
        "- Ảnh người mẫu / thú cưng / em bé (nếu có): lock nhân vật — KHÔNG lấy trang phục/phụ kiện từ ảnh này.\n"
    ) if model_ref_instruction else ''

    return (
        "ẢNH ĐẦU VÀO:\n"
        "- Ảnh sản phẩm: reference sản phẩm chính xác, ưu tiên cao nhất.\n"
        "- Ảnh reference: chỉ dùng để giữ nhất quán tay/nền/ánh sáng/bố cục.\n"
        f"{model_ref_short}"
        "- Ảnh bối cảnh (nếu có): chỉ học phong cách nền/ánh sáng/không khí — KHÔNG copy chi tiết cụ thể.\n"
        "\n"
        f"{PRODUCT_LOCK_IMAGE_TEXT}\n\n"
        "LỌC ẢNH SẢN PHẨM THAM CHIẾU (ảnh có thể là ảnh TikTok/e-commerce chứa nhiễu):\n"
        "Từ ảnh sản phẩm, chỉ trích xuất HÌNH THỂ VẬT LÝ sản phẩm chính. "
        "KHÔNG tái tạo từ ảnh gốc: người mẫu, nền ảnh gốc, "
        "chữ/watermark/giá tiền/badge, logo cửa hàng, phụ kiện không phải sản phẩm chính.\n\n"
        "NẾU CÓ ẢNH BỐI CẢNH:\n"
        "Dùng làm reference phong cách nền/ánh sáng/không khí — học tông màu, độ sáng, không gian. "
        "KHÔNG copy nguyên xi, chỉ học phong cách. "
        "KHÔNG đưa đồ vật, người, chi tiết cụ thể từ ảnh bối cảnh vào output.\n\n"
        f"{model_ref_instruction}"
        f"{continuity}"
        f"{extra_section}"
        f"{voice_section}"
        f"CẢNH:\n{scene_visual}\n\n"
        f"CHỦ THỂ:\n{subject_rule}\n\n"
        "BỐ CỤC:\n"
        "Ưu tiên sản phẩm. Sản phẩm phải hiển thị đầy đủ và nhận dạng được. Không che khuất "
        "chi tiết quan trọng. Nếu có tay, hiện đúng một đôi tay (2 bàn tay, một người) "
        "thực hiện một hành động duy nhất — không nhân đôi tay, không tay thừa hoặc tay lơ lửng.\n\n"
        "PHONG CÁCH:\n"
        f"Dọc 9:16, phong cách thực tế TikTok Shop UGC/thương mại, ánh sáng mềm, nét rõ, {bg_style}.\n\n"
        "TRÁNH:\n"
        "Không chữ đè lên ảnh, không phụ đề, không watermark, không thương hiệu thêm, "
        "không giao diện giả, không thiết kế lại sản phẩm, không tay thêm, không nhân đôi bàn tay."
    )


def _build_video_prompt_text(motion_visual: str, camera_movement: str, clip_dur: str, aspect_ratio: str,
                              environment: str = '', lighting: str = '', character_or_hands: str = '',
                              original_action: str = '') -> str:
    """Template cố định — VIDEO PRODUCT LOCK nguyên văn. AI chỉ điền CHUYỂN ĐỘNG/CAMERA.
    NHẤT QUÁN block giữ bối cảnh/ánh sáng/tay nhất quán với ảnh tĩnh gốc khi animate."""
    continuity = _build_continuity_block(environment, lighting, character_or_hands)
    action_section = (
        f"HÀNH ĐỘNG GỐC TỪ KỊCH BẢN (ưu tiên thực hiện đúng hành động này):\n\"{original_action}\"\n\n"
    ) if original_action and original_action.strip() else ''
    return (
        "ẢNH ĐẦU VÀO:\n"
        "- Ảnh scene: ảnh chính cần animate.\n"
        "- Ảnh reference: giữ nhất quán bối cảnh.\n"
        "- Ảnh người mẫu: lock khuôn mặt/tóc khi animate — ngoại hình không được thay đổi giữa các frame (tùy chọn).\n\n"
        f"{PRODUCT_LOCK_VIDEO_TEXT}\n\n"
        f"{continuity}"
        f"{action_section}"
        f"CHUYỂN ĐỘNG:\n{motion_visual}\n\n"
        f"CAMERA:\n{camera_movement}\n\n"
        f"THỜI LƯỢNG:\n{clip_dur}, dọc {aspect_ratio}.\n\n"
        "KHÓA SỐ TAY:\n"
        "Nếu có tay, giữ đúng một đôi tay (2 bàn tay, một người) hiển thị xuyên suốt toàn bộ clip. "
        "Không thêm tay của người thứ hai, không nhân đôi bàn tay, không để tay xuất hiện/biến mất "
        "không nhất quán giữa các frame.\n\n"
        "PHONG CÁCH:\n"
        "Video thực tế TikTok Shop UGC/thương mại, chuyển động tự nhiên, sản phẩm luôn hiển thị ổn định.\n\n"
        "TRÁNH:\n"
        "Không chữ đè lên ảnh, không phụ đề, không watermark, không biến đổi sản phẩm, "
        "không phụ kiện mới, không tay biến dạng, không tay thêm, không nhân đôi bàn tay."
    )


VISUAL_SYSTEM_PROMPT = """Bạn là AI Visual Director cho Freepik Flow (Seedream tạo ảnh, Seedance tạo video).

QUAN TRỌNG NHẤT — ĐỌC KỸ TRƯỚC KHI VIẾT:
Sản phẩm trong video LÀ ẢNH THẬT do người dùng tải lên (Product Image). Bạn KHÔNG được mô tả lại
hình dáng, màu sắc, logo, cổng kết nối, nút bấm, hay bất kỳ chi tiết thiết kế nào của sản phẩm.
Sản phẩm đã có sẵn trong ảnh upload — không cần và không được sáng tạo lại hay tưởng tượng thêm.

Nhiệm vụ của bạn CHỈ là mô tả những gì XUNG QUANH sản phẩm:
- Bối cảnh / background / setting / bề mặt
- Ánh sáng
- Góc máy / camera / chuyển động
- Tay hoặc người (nếu subject mode cho phép) — chỉ mô tả HÀNH ĐỘNG của tay/người, KHÔNG mô tả lại
  sản phẩm họ đang cầm hay tương tác

TUYỆT ĐỐI KHÔNG dùng các cụm mô tả/sáng tạo lại sản phẩm như: "a compact charger", "a premium-looking
device", "a product similar to...", "make the product look...", "create a sleek gadget that...",
"identical to a...". Sản phẩm không cần bạn miêu tả vì nó đã có sẵn trong ảnh upload — nếu cần nhắc tới,
chỉ dùng "the product" hoặc "the exact product from the uploaded image".

QUY TẮC KHÁC:
- Không viết lại kịch bản bán hàng, không viết lời thoại.
- 1 timeline item = 1 scene.
- Tất cả mô tả bằng tiếng Việt.
- Output JSON hợp lệ duy nhất. Không markdown. Không giải thích ngoài JSON."""


def build_visual_prompt(script: dict, product_name: str, product_desc: str,
                        image_analysis: str, input_data: dict, visual_settings: dict) -> tuple:
    """Tạo (system_prompt, user_prompt) để AI sinh DRAFT mô tả bối cảnh/ánh sáng/camera/chuyển động.

    AI KHÔNG được mô tả lại sản phẩm. assemble_visual_section10() sẽ lắp ráp PRODUCT LOCK +
    section10 đầy đủ từ draft này. Lựa chọn kỹ thuật này (Python lắp khung cố định, AI chỉ điền
    phần bối cảnh) đảm bảo Product Lock luôn đúng 100%, không phụ thuộc AI có tuân thủ instruction
    hay không — fix lỗi Seedream tự vẽ lại sản phẩm (sai hình dáng/cổng/logo)."""
    resolved_mode = resolve_subject_mode(input_data)
    shooting = input_data.get('shootingStyle', 'one-shot')
    shooting_label = input_data.get('shootingStyleCustom', '') if shooting == 'custom' else SHOOTING_LABELS.get(shooting, shooting)
    duration = input_data.get('duration', '30s')
    duration_label = input_data.get('durationCustom', '') if duration == 'custom' else DURATION_LABELS.get(duration, duration)
    tone = input_data.get('tone', 'natural-koc')
    tone_label = input_data.get('toneCustom', '') if tone == 'custom' else TONE_LABELS.get(tone, tone)
    industry = input_data.get('industry', 'auto')
    industry_label = INDUSTRY_LABELS.get(industry, 'Tự động nhận diện')
    video_goal = GOAL_LABELS.get(input_data.get('videoGoal', ''), input_data.get('videoGoal', ''))

    s2 = script.get('section2', {})
    s4 = script.get('section4', {})
    s5 = script.get('section5', {})
    hero_benefit = s2.get('heroBenefit', '')

    timeline = s5.get('timeline', [])
    timeline_text = '\n'.join(
        f"  Scene {i+1} [{t.get('timeRange','?')}]: {t.get('description', '') or t.get('voice','') or ''} | Action: {t.get('action','')}"
        for i, t in enumerate(timeline)
    ) if timeline else '  (Chưa có timeline — tự đề xuất scene dựa trên kịch bản)'

    lines_data = s4.get('lines', [])
    vo_script = s4.get('voScript', '')
    script_summary = vo_script[:500] if vo_script else ' '.join(
        l.get('text', '') for l in lines_data if l.get('type') == 'dialogue'
    )[:500]

    subject_rule = SUBJECT_MODE_IMAGE_RULE.get(resolved_mode, SUBJECT_MODE_IMAGE_RULE['hands'])
    n_scenes = len(timeline) or 5

    character_field_hint = (
        'mô tả ngoại hình nhân vật nhất quán (trang phục, phong cách) — không mô tả sản phẩm họ cầm'
        if resolved_mode == 'face' else
        'mô tả kiểu tay (tông màu da, móng tay) — không mô tả khuôn mặt'
        if resolved_mode == 'hands' else
        'không có người trong mode này — để chuỗi rỗng'
    )

    image_analysis_block = (
        f'\n# PHÂN TÍCH ẢNH SẢN PHẨM (mô tả từ ảnh thực — dùng làm reference màu sắc/chất liệu/chi tiết; '
        f'KHÔNG copy nguyên vào output, chỉ dùng để viết bối cảnh/ánh sáng phù hợp)\n'
        f'{image_analysis[:800]}\n'
    ) if image_analysis and image_analysis.strip() else ''

    user_prompt = f"""# BỐI CẢNH SẢN PHẨM (chỉ để hiểu — KHÔNG mô tả lại sản phẩm trong output)
Tên: {product_name}
Mô tả: {product_desc[:400]}
Ngành: {industry_label}
Lợi ích chính: {hero_benefit}{image_analysis_block}
# TÓM TẮT KỊCH BẢN
Kiểu quay: {shooting_label}
Thời lượng: {duration_label}
Giọng điệu: {tone_label}
Mục tiêu video: {video_goal}
Trích kịch bản: {script_summary[:300]}

# TIMELINE (mỗi item = 1 scene, tạo đúng {n_scenes} scene theo thứ tự)
{timeline_text}

# CHỦ THỂ VIDEO: {resolved_mode}
{subject_rule}

# YÊU CẦU OUTPUT — JSON DRAFT (chỉ bối cảnh/camera/chuyển động, KHÔNG một chữ nào mô tả sản phẩm):
{{
  "visualDirector": {{
    "visualStyle": "phong cách tổng thể (ví dụ: TikTok Shop UGC sạch, ánh sáng tự nhiên mềm)",
    "environment": "mô tả nền/bối cảnh/bề mặt — KHÔNG mô tả sản phẩm",
    "lighting": "mô tả ánh sáng",
    "cameraStyle": "phong cách góc máy và chuyển động camera",
    "characterOrHands": "{character_field_hint}"
  }},
  "referenceScene": "mô tả cảnh xung quanh sản phẩm (bề mặt, nền, props, vị trí tay/người) — KHÔNG mô tả bản thân sản phẩm",
  "scenes": [
    {{
      "scene": 1,
      "timeRange": "0-4s",
      "description": "Mô tả việc gì xảy ra trong cảnh này",
      "purpose": "Mục đích bán hàng của cảnh này",
      "sceneVisual": "mô tả bố cục/bối cảnh/hành động xung quanh sản phẩm cho keyframe tĩnh — KHÔNG mô tả hình dạng/màu sắc/cổng/logo sản phẩm",
      "cameraMovement": "mô tả chuyển động camera",
      "motionVisual": "mô tả những gì chuyển động trong video (tay, camera, môi trường) — KHÔNG mô tả sản phẩm biến đổi",
      "motionNotes": "chi tiết chuyển động bổ sung"
    }}
  ]
}}

Tạo đúng {n_scenes} scene, mỗi scene tương ứng 1 timeline item theo thứ tự ở trên.
Chỉ output JSON hợp lệ. Không markdown. Không giải thích ngoài JSON."""

    return VISUAL_SYSTEM_PROMPT, user_prompt


def assemble_visual_section10(ai_draft: dict, product_name: str, input_data: dict, visual_settings: dict,
                               script: dict = None) -> dict:
    """Lắp ráp section10 đầy đủ từ AI draft (chỉ bối cảnh/camera/chuyển động) + PRODUCT LOCK
    templates cố định bằng Python (xem các hàm _build_*_prompt_text ở trên). Đảm bảo
    CRITICAL PRODUCT LOCK / negative prompt luôn đúng 100% trong mọi imagePrompt/videoPrompt/
    referencePrompt, không phụ thuộc việc AI có tuân thủ instruction hay không.

    script (optional): nếu truyền vào, dùng script['section5']['timeline'] làm ground truth để
    ép 1:1 số lượng/timeRange scene — không phụ thuộc AI trả đúng số lượng (Fix #2)."""
    resolved_mode = resolve_subject_mode(input_data)
    industry = input_data.get('industry', 'auto')
    aspect_ratio = visual_settings.get('aspectRatio', '9:16')
    clip_dur = visual_settings.get('clipDuration', '4s')
    img_model = visual_settings.get('targetImageModel', 'Seedream 3.0')
    vid_model = visual_settings.get('targetVideoModel', 'Seedance 1.0')

    ai_draft = ai_draft or {}
    vd = ai_draft.get('visualDirector', {}) or {}
    environment = vd.get('environment', '')
    lighting = vd.get('lighting', '')
    character_or_hands = vd.get('characterOrHands', '')
    reference_scene = ai_draft.get('referenceScene') or 'Bối cảnh bàn sạch, ánh sáng tự nhiên mềm, nền tối giản.'
    ai_scenes = ai_draft.get('scenes', []) or []

    # Fix #2: ép 1:1 với timeline gốc nếu có (không phụ thuộc AI trả đúng số lượng/thứ tự)
    timeline = ((script or {}).get('section5', {}) or {}).get('timeline', [])
    if timeline:
        ai_scenes = _align_scenes_to_timeline(ai_scenes, timeline)

    workflow = _build_visual_workflow(img_model, vid_model, aspect_ratio)

    visual_director = {
        "subjectMode": input_data.get('subjectMode', 'auto'),
        "resolvedSubjectMode": resolved_mode,
        "visualStyle": vd.get('visualStyle', ''),
        "environment": environment,
        "lighting": lighting,
        "cameraStyle": vd.get('cameraStyle', ''),
        "characterOrHands": character_or_hands,
        "productLock": PRODUCT_LOCK_IMAGE_TEXT,
    }

    # Fix #1: CONTINUITY (environment/lighting/characterOrHands) cũng được gắn vào Reference Prompt
    # vì Reference Image chính là cái xác lập bối cảnh cho mọi scene sau đó
    reference_prompt = {
        "inputImagesNeeded": list(INPUT_IMAGES_REFERENCE_STEP),
        "prompt": _build_reference_prompt_text(resolved_mode, reference_scene, aspect_ratio,
                                                 environment, lighting, character_or_hands,
                                                 industry=industry),
        "negativePrompt": _build_negative_prompt(resolved_mode, industry),
    }

    global_negative = _build_negative_prompt(resolved_mode, industry)

    scenes = []
    for i, sc in enumerate(ai_scenes):
        sc = sc or {}
        scene_no = sc.get('scene', i + 1)
        time_range = sc.get('timeRange', '')
        description = sc.get('description', '')
        purpose = sc.get('purpose', '')
        scene_visual = sc.get('sceneVisual') or description or 'Bố cục sản phẩm sạch, ánh sáng mềm.'
        # Fix #4: fallback đa dạng theo index thay vì lặp lại 1 câu cho mọi scene
        camera_movement = sc.get('cameraMovement', '') or _fallback_camera_movement(i)
        motion_visual = sc.get('motionVisual') or _fallback_motion_visual(i)
        motion_notes = sc.get('motionNotes', '')
        original_action = sc.get('_action', '')
        original_voice = sc.get('_voice', '')

        scenes.append({
            "scene": scene_no,
            "timeRange": time_range,
            "description": description,
            "purpose": purpose,
            "inputImagesForImageGeneration": list(INPUT_IMAGES_SCENE_STEP),
            "imagePrompt": _build_image_prompt_text(resolved_mode, scene_visual,
                                                      environment, lighting, character_or_hands,
                                                      voice_hint=original_voice, industry=industry),
            "inputImagesForVideoGeneration": list(INPUT_IMAGES_VIDEO_STEP),
            "videoPrompt": _build_video_prompt_text(motion_visual, camera_movement, clip_dur, aspect_ratio,
                                                      environment, lighting, character_or_hands,
                                                      original_action=original_action),
            "duration": clip_dur,
            "cameraMovement": camera_movement,
            "motionNotes": motion_notes,
            "negativePrompt": _build_negative_prompt(resolved_mode, industry),
        })

    all_image_prompts = '\n\n'.join(
        f"=== SCENE {s['scene']} ({s['timeRange']}) ===\n{s['imagePrompt']}\n\nNegative prompt: {s['negativePrompt']}"
        for s in scenes
    )
    all_video_prompts = '\n\n'.join(
        f"=== SCENE {s['scene']} ({s['timeRange']}) ===\n{s['videoPrompt']}\n\nNegative prompt: {s['negativePrompt']}"
        for s in scenes
    )
    freepik_workflow_text = (
        "1. Tạo Reference Image: upload Product Image, dùng Reference Prompt.\n"
        "2. Tạo Scene Image cho từng cảnh: upload Product Image + Reference Image, dùng Image Prompt tương ứng.\n"
        "3. Tạo Video cho từng cảnh: upload Scene Image (+ Reference Image, + Product Image nếu Freepik hỗ trợ), dùng Video Prompt tương ứng.\n"
        "4. Luôn ưu tiên Product Image để giữ đúng sản phẩm thật — không để AI tự vẽ lại sản phẩm."
    )

    return {
        "workflow": workflow,
        "visualDirector": visual_director,
        "referencePrompt": reference_prompt,
        "globalNegativePrompt": global_negative,
        "scenes": scenes,
        "copyBlocks": {
            "referencePromptFull": reference_prompt["prompt"] + "\n\nNegative prompt: " + reference_prompt["negativePrompt"],
            "allImagePrompts": all_image_prompts,
            "allVideoPrompts": all_video_prompts,
            "freepikWorkflow": freepik_workflow_text,
        },
    }
