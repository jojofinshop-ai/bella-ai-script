import time
import base64


def get_base64_from_data_url(data_url: str) -> tuple[str, str]:
    """Extract base64 data and mime type from data URL."""
    if ',' in data_url:
        header, data = data_url.split(',', 1)
        mime = header.split(':')[1].split(';')[0] if ':' in header else 'image/jpeg'
        return data, mime
    return data_url, 'image/jpeg'


def call_openai_compatible(settings: dict, system_prompt: str, user_prompt: str, images: list) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=settings.get('apiKey', 'no-key'),
        base_url=settings.get('baseUrl', 'https://api.openai.com/v1'),
        timeout=90,
    )
    messages = [{'role': 'system', 'content': system_prompt}]

    if images:
        content = [{'type': 'text', 'text': user_prompt}]
        for img in images:
            b64_data, mime = get_base64_from_data_url(img.get('dataUrl', ''))
            content.append({
                'type': 'image_url',
                'image_url': {'url': f'data:{mime};base64,{b64_data}', 'detail': 'high'}
            })
        messages.append({'role': 'user', 'content': content})
    else:
        messages.append({'role': 'user', 'content': user_prompt})

    model_name = settings.get('modelName', 'gpt-4o')
    max_tok = int(settings.get('maxTokens') or 0)
    temp = float(settings.get('temperature') or 0.8)
    # DeepSeek JSON output bị lỗi khi temperature > 1.5 dù API cho phép đến 2.0
    if settings.get('provider') == 'deepseek':
        temp = min(temp, 1.5)

    # o1/o3/o4 chỉ hỗ trợ temperature=1 (mặc định) → không truyền tham số này
    use_new_param = any(model_name.startswith(p) for p in ('gpt-5', 'o1', 'o3', 'o4'))
    token_param = {}
    if max_tok > 0:
        param_key = 'max_completion_tokens' if use_new_param else 'max_tokens'
        token_param = {param_key: max_tok}

    create_kwargs = {'model': model_name, 'messages': messages, **token_param}
    if not use_new_param:
        create_kwargs['temperature'] = temp

    response = client.chat.completions.create(**create_kwargs)
    content = response.choices[0].message.content
    if not content:
        raise ValueError('AI trả về nội dung rỗng')
    # Strip <think>...</think> blocks (DeepSeek V3/V4/reasoner extended thinking)
    import re as _re
    content = _re.sub(r'<think>[\s\S]*?</think>\s*', '', content, flags=_re.IGNORECASE).strip()
    if not content:
        raise ValueError('AI trả về nội dung rỗng sau khi xử lý thinking block')
    return content


def call_gemini(settings: dict, system_prompt: str, user_prompt: str, images: list) -> str:
    import urllib.request
    import json as _json

    # Lấy key đầu tiên nếu user nhập nhiều key trên nhiều dòng
    raw_key = settings.get('apiKey', '')
    api_key = raw_key.replace(',', '\n').split('\n')[0].strip()
    model_name = settings.get('modelName', 'gemini-1.5-flash-latest')
    temperature = float(settings.get('temperature') or 0.8)
    max_tokens = int(settings.get('maxTokens') or 0)

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}'

    parts = [{'text': user_prompt}]
    for img in images:
        b64_data, mime = get_base64_from_data_url(img.get('dataUrl', ''))
        parts.append({'inline_data': {'mime_type': mime, 'data': b64_data}})

    gen_config = {'temperature': temperature}
    if max_tokens > 0:
        gen_config['maxOutputTokens'] = max_tokens

    body = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': gen_config,
        'safetySettings': [
            {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'},
        ],
    }
    if system_prompt:
        body['systemInstruction'] = {'parts': [{'text': system_prompt}]}
    payload = _json.dumps(body).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = _json.loads(resp.read())

    candidate = data['candidates'][0]
    content = candidate.get('content')
    if not content:
        reason = candidate.get('finishReason', 'UNKNOWN')
        raise ValueError(f'Gemini chặn nội dung (finishReason: {reason})')
    text = content['parts'][0]['text']
    if not text:
        raise ValueError('Gemini trả về nội dung rỗng')
    return text


_VISION_SYSTEM = (
    'Bạn là chuyên gia phân tích sản phẩm từ ảnh TikTok Shop / e-commerce. '
    'Ảnh thường chứa model mặc/dùng sản phẩm, background, phụ kiện không liên quan — '
    'nhiệm vụ của bạn là tách thông tin SẢN PHẨM CHÍNH ra khỏi nhiễu bối cảnh.'
)

def _vision_user_prompt(n: int, product_name: str = '') -> str:
    product_line = f'Sản phẩm cần phân tích: "{product_name}"\n' if product_name else ''
    return (
        f'{product_line}'
        f'Tôi gửi {n} ảnh (ảnh TikTok/e-commerce — có thể chứa model, background, watermark). '
        f'Hãy tập trung vào sản phẩm trên và phân tích TẤT CẢ {n} ảnh theo thứ tự ưu tiên:\n\n'
        'ƯU TIÊN 1 — ĐẶC ĐIỂM VẬT LÝ SẢN PHẨM CHÍNH:\n'
        '- Loại sản phẩm: nhận dạng chính xác\n'
        '- Màu sắc cụ thể, họa tiết, form dáng/kiểu dáng\n'
        '- Chất liệu nhìn thấy được (bóng/mờ, mềm/cứng, dày/mỏng, vải/nhựa/kim loại...)\n'
        '- Chi tiết thiết kế: đường may, logo, khóa, cúc, cổ, tay, họa tiết in, label\n'
        '- Thông tin đọc được trên sản phẩm: brand, size, thành phần, dung tích, model\n'
        '- Các màu/size/biến thể thấy được trong ảnh\n\n'
        'ƯU TIÊN 2 — THÔNG TIN SẢN PHẨM SUY RA TỪ CÁCH DÙNG:\n'
        '- Nếu model mặc quần áo → form ôm người thế nào, độ co giãn, độ dài, cách mặc\n'
        '- Nếu model dùng mỹ phẩm/thiết bị → cách dùng, vùng áp dụng, hiệu quả thấy được\n'
        '- Nếu sản phẩm đang hoạt động → trạng thái, output, hiệu quả quan sát được\n\n'
        'ƯU TIÊN 3 — BẰNG CHỨNG PAIN POINT NHÌN THẤY ĐƯỢC (quan trọng cho TikTok script):\n'
        '- Vấn đề của model/người dùng thấy rõ trong ảnh mà sản phẩm này đang giải quyết\n'
        '  VD: "model có bụng rõ → SP tạo cảm giác thon bụng", "da không đều tone → SP che khuyết điểm",\n'
        '  "tóc khô xơ → SP làm tóc mượt mà", "bụng bầu lớn → SP thiết kế riêng cho bầu"\n'
        '- Chỉ nêu nếu thực sự nhìn thấy bằng chứng trong ảnh. Không bịa.\n\n'
        'ƯU TIÊN 4 — ĐIỂM KHÁC BIỆT NHÌN THẤY ĐƯỢC so với sản phẩm thông thường:\n'
        '- Chi tiết thiết kế đặc biệt không phổ biến: dây đai điều chỉnh, 2 lớp, khóa đặc biệt,\n'
        '  vùng lưng/bụng/vai được xử lý riêng, cấu trúc đặc thù, phụ kiện đi kèm thấy được\n'
        '- Nếu thấy thông tin so sánh trước/sau trong ảnh → mô tả hiệu quả quan sát được\n'
        '- Chỉ nêu điểm khác biệt thực sự thấy được, không đoán mò.\n\n'
        'BỎ QUA (không đề cập): background, nền ảnh, watermark TikTok, '
        'phụ kiện/quần áo khác của model không phải sản phẩm đang bán.\n\n'
        'Chỉ mô tả những gì thực sự nhìn thấy. Không bịa đặt tính năng.'
    )


def analyze_images_with_openai(openai_settings: dict, images: list, product_name: str = '') -> str:
    """Dùng OpenAI-compatible (GPT-4o, GPT-4o-mini...) để phân tích ảnh sản phẩm, trả về text mô tả."""
    if not images or not openai_settings.get('apiKey', ''):
        return ''
    settings = {**openai_settings, 'temperature': 0.2, 'maxTokens': 0}
    try:
        return call_openai_compatible(settings, _VISION_SYSTEM, _vision_user_prompt(len(images), product_name), images)
    except Exception:
        return ''


def analyze_images_with_gemini(gemini_api_keys, images: list, product_name: str = '') -> str:
    """Dùng Gemini Flash (rẻ) để phân tích toàn bộ ảnh sản phẩm, trả về text mô tả.
    Hỗ trợ nhiều API key — tự động chuyển key khi gặp 429."""
    keys = [k for k in _parse_gemini_keys(gemini_api_keys) if k]
    if not keys or not images:
        return ''
    models = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite-preview-06-17',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]
    _up = _vision_user_prompt(len(images), product_name)
    for key in keys:
        for model in models:
            settings = {'apiKey': key, 'modelName': model, 'temperature': 0.2, 'maxTokens': 0}
            try:
                return call_gemini(settings, _VISION_SYSTEM, _up, images)
            except Exception as e:
                err_s = str(e)
                if '429' in err_s:
                    break  # key bị rate-limit → sang key tiếp ngay
                if '404' in err_s or '503' in err_s:
                    continue  # model không có/unavailable → thử model tiếp
                break  # lỗi khác (auth...) → sang key tiếp
    return ''


def _parse_gemini_keys(keys_input) -> list:
    """Chuyển string hoặc list thành danh sách API key sạch."""
    if isinstance(keys_input, list):
        return [k.strip() for k in keys_input if k and k.strip()]
    if isinstance(keys_input, str):
        return [k.strip() for k in keys_input.replace(',', '\n').split('\n') if k.strip()]
    return []


def scan_product_from_screenshot(gemini_api_keys, image_data_urls: list, main_settings: dict = None) -> dict:
    """Scan ảnh màn hình sản phẩm → {productDescription}.
    Thứ tự ưu tiên: Gemini (rẻ) → ChatGPT/provider chính (nếu Gemini fail)."""
    import json as _json, re
    n = len(image_data_urls)
    if not image_data_urls:
        raise ValueError('Không có ảnh để scan')
    system_prompt = 'Bạn là công cụ đọc thông tin sản phẩm từ ảnh chụp màn hình. Trả về JSON chính xác.'
    user_prompt = (
        f'Đây là {n} ảnh chụp màn hình trang sản phẩm (TikTok Shop, Shopee, hoặc website bán hàng).\n'
        'Hãy đọc TẤT CẢ ảnh và trích xuất toàn bộ nội dung mô tả sản phẩm:\n'
        '- Chất liệu, kích thước, màu sắc, tính năng, ưu điểm\n'
        '- Mọi thông tin hữu ích cho người bán hàng\n\n'
        'Trả về JSON (chỉ JSON, không giải thích thêm):\n'
        '{"productDescription": "..."}'
    )
    images = [{'dataUrl': u} for u in image_data_urls]

    def _parse_json(raw):
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return _json.loads(m.group(0))
        raise ValueError('AI không trả về JSON hợp lệ')

    # ── Thử Gemini trước (rẻ hơn) ───────────────────────────────────────────
    keys = [k for k in _parse_gemini_keys(gemini_api_keys) if k]
    if keys:
        gemini_models = [
            'gemini-2.5-flash',
            'gemini-2.5-flash-lite-preview-06-17',
            'gemini-2.0-flash',
            'gemini-1.5-flash',
        ]
        for key in keys:
            for model in gemini_models:
                try:
                    raw = call_gemini(
                        {'apiKey': key, 'modelName': model, 'temperature': 0.1, 'maxTokens': 0},
                        system_prompt, user_prompt, images
                    )
                    try:
                        return _parse_json(raw)
                    except ValueError:
                        continue  # AI trả text không phải JSON → thử model tiếp
                except Exception as e:
                    err_s = str(e)
                    if '429' in err_s:
                        break  # key bị rate-limit → sang key tiếp ngay
                    if '404' in err_s or '503' in err_s:
                        continue  # model không có/unavailable → thử model tiếp
                    break  # lỗi khác (key sai) → sang key tiếp

    # ── Fallback: dùng provider chính (ChatGPT/OpenAI/custom) ───────────────
    if main_settings:
        provider = main_settings.get('provider', 'openai')
        model_name = main_settings.get('modelName', '')
        api_keys = main_settings.get('apiKeys') or {}
        api_key = api_keys.get(provider, '') or main_settings.get('apiKey', '')

        if provider == 'gemini':
            if not api_key:
                api_key = api_keys.get('gemini', '')
            if api_key:
                raw = call_gemini(
                    {'apiKey': api_key, 'modelName': model_name or 'gemini-2.5-flash', 'temperature': 0.1, 'maxTokens': 0},
                    system_prompt, user_prompt, images
                )
                try:
                    return _parse_json(raw)
                except ValueError:
                    raise ValueError('AI phân tích ảnh trả về định dạng không hợp lệ. Thử lại.')
        elif api_key:
            # OpenAI / DeepSeek / custom — thử gửi ảnh trực tiếp
            scan_settings = {
                'apiKey': api_key,
                'baseUrl': main_settings.get('baseUrl', 'https://api.openai.com/v1'),
                'modelName': model_name,
                'temperature': 0.1,
                'maxTokens': 0,
            }
            raw = call_openai_compatible(scan_settings, system_prompt, user_prompt, images)
            try:
                return _parse_json(raw)
            except ValueError:
                raise ValueError('AI phân tích ảnh trả về định dạng không hợp lệ. Thử lại.')

    raise ValueError('Không scan được ảnh. Vui lòng kiểm tra API key trong Cài đặt.')


def select_relevant_examples(settings: dict, product_name: str, product_desc: str, industry: str, candidates: list) -> dict:
    """V8 Reference Library: dùng AI chọn tối đa 3 mẫu (hook/script/transcript) phù hợp nhất
    từ candidates (frontend đã pre-filter theo ngành hàng trước khi gửi lên).
    Lỗi ở bước chọn lọc này KHÔNG được làm fail lần generate chính — luôn fallback an toàn
    về vài candidate đầu tiên (frontend đã sắp theo mới nhất) nếu AI lỗi/parse hỏng.
    Trả dict: {'contents': list[str], 'used': list[dict]} để frontend hiển thị mẫu đã dùng."""
    if not candidates:
        return {'contents': [], 'used': []}

    def _make_result(items):
        items = [c for c in items if c.get('content')][:3]
        return {
            'contents': [c.get('content', '') for c in items],
            'used': [{'type': c.get('type', ''), 'productTag': c.get('productTag', ''),
                      'industry': c.get('industry', ''), 'preview': (c.get('content', '') or '')[:120]}
                     for c in items],
        }

    fallback = _make_result(candidates[:3])

    try:
        import json as _json, re as _re

        listing = '\n'.join(
            f"[{i}] loại={c.get('type', '')} ngành={c.get('industry', '')} tag={c.get('productTag', '')}: "
            f"{(c.get('content', '') or '')[:300]}"
            for i, c in enumerate(candidates)
        )
        system_prompt = 'Bạn là bộ lọc chọn mẫu tham khảo cho copywriter. Chỉ trả JSON, không giải thích gì thêm.'
        user_prompt = (
            f"Sản phẩm cần viết kịch bản: {product_name}\n"
            f"Mô tả: {(product_desc or '')[:300]}\n"
            f"Ngành hàng: {industry}\n\n"
            f"Danh sách mẫu trong thư viện:\n{listing}\n\n"
            'Chọn tối đa 3 mẫu PHÙ HỢP NHẤT để tham khảo văn phong/cấu trúc cho sản phẩm này '
            '(ngành tương tự, hoặc cách viết đáng học hỏi dù ngành khác). '
            'Trả về JSON: {"selected": [index, ...]} — index là số trong dấu [] ở trên. '
            'Nếu không mẫu nào phù hợp, trả {"selected": []}.'
        )
        # Ưu tiên Gemini Flash (rẻ hơn) để chọn mẫu; fallback về model chính nếu không có key
        _ref_gemini_raw = (
            settings.get('visionGeminiKeys', '')
            or (settings.get('apiKeys') or {}).get('gemini', '')
            or (settings.get('apiKey', '') if settings.get('provider') == 'gemini' else '')
        )
        _ref_gemini_keys = [k.strip() for k in _ref_gemini_raw.replace(',', '\n').split('\n') if k.strip()]
        raw = None
        if _ref_gemini_keys:
            for _rgk in _ref_gemini_keys:
                for _rgm in ('gemini-2.0-flash', 'gemini-1.5-flash'):
                    try:
                        raw = call_gemini(
                            {'apiKey': _rgk, 'modelName': _rgm, 'temperature': 0.2, 'maxTokens': 300},
                            system_prompt, user_prompt, []
                        )
                        break
                    except Exception:
                        continue
                if raw:
                    break
        if not raw:
            scan_settings = dict(settings)
            scan_settings['maxTokens'] = 300
            scan_settings['temperature'] = 0.2
            raw = call_ai(scan_settings, system_prompt, user_prompt, [])

        m = _re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return fallback
        parsed = _json.loads(m.group(0))
        selected_idx = parsed.get('selected', [])
        selected_items = [candidates[i] for i in selected_idx
                          if isinstance(i, int) and 0 <= i < len(candidates)]
        return _make_result(selected_items) if selected_items else fallback
    except Exception:
        return fallback


def detect_industry_with_groq(groq_api_key: str, text: str) -> str:
    """Dùng Groq LLM (llama-3.1-8b-instant) phân loại ngành hàng từ transcript.
    Trả về 1 trong: fashion/beauty/electronics/home/food/pet/baby/other/auto (nếu lỗi)."""
    import requests as _req
    headers = {'Authorization': f'Bearer {groq_api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': 'llama-3.1-8b-instant',
        'messages': [
            {'role': 'system', 'content': 'Bạn phân loại ngành hàng TikTok Shop. Chỉ trả về đúng 1 từ khóa tiếng Anh, không giải thích.'},
            {'role': 'user', 'content': (
                f'Đọc đoạn script/transcript video TikTok Shop này:\n\n"{text[:800]}"\n\n'
                'Chọn đúng 1 trong các từ khóa sau: fashion, beauty, electronics, home, food, pet, baby, other'
            )},
        ],
        'temperature': 0.1,
        'max_tokens': 20,
    }
    try:
        resp = _req.post('https://api.groq.com/openai/v1/chat/completions', headers=headers, json=payload, timeout=15)
        if not resp.ok:
            return 'auto'
        content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip().lower()
        for kw in ('fashion', 'beauty', 'electronics', 'home', 'food', 'pet', 'baby', 'other'):
            if kw in content:
                return kw
    except Exception:
        pass
    return 'auto'


def transcribe_with_groq(groq_api_key: str, file_bytes: bytes, filename: str, language: str = 'vi') -> str:
    """Gọi Groq Whisper API để chuyển audio/video thành text."""
    import requests as _req
    url = 'https://api.groq.com/openai/v1/audio/transcriptions'
    headers = {'Authorization': f'Bearer {groq_api_key}'}
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'mp4'
    mime_map = {
        'mp3': 'audio/mpeg', 'mp4': 'video/mp4', 'mpeg': 'audio/mpeg',
        'mpga': 'audio/mpeg', 'm4a': 'audio/mp4', 'wav': 'audio/wav',
        'webm': 'audio/webm', 'flac': 'audio/flac', 'ogg': 'audio/ogg', 'opus': 'audio/opus',
    }
    mime = mime_map.get(ext, 'audio/mpeg')
    files = {'file': (filename, file_bytes, mime)}
    data = {'model': 'whisper-large-v3-turbo', 'response_format': 'text'}
    if language and language != 'auto':
        data['language'] = language
    resp = _req.post(url, headers=headers, files=files, data=data, timeout=180)
    if resp.status_code == 401:
        raise ValueError('Groq API key không hợp lệ hoặc đã hết hạn')
    if resp.status_code == 413:
        raise ValueError('File quá lớn. Groq giới hạn 25MB — hãy nén video trước')
    if not resp.ok:
        try:
            err = resp.json().get('error', {}).get('message', resp.text[:200])
        except Exception:
            err = resp.text[:200]
        raise ValueError(f'Groq API lỗi: {err}')
    text = resp.text.strip()
    if not text:
        raise ValueError('Groq trả về kết quả rỗng — file có thể không có âm thanh')
    return text


def call_ai(settings: dict, system_prompt: str, user_prompt: str, images: list) -> str:
    provider = settings.get('provider', 'openai')
    if provider == 'gemini':
        return call_gemini(settings, system_prompt, user_prompt, images)
    else:
        return call_openai_compatible(settings, system_prompt, user_prompt, images)


def test_ai_connection(settings: dict) -> dict:
    start = time.time()
    provider = settings.get('provider', 'openai')
    try:
        if provider == 'gemini':
            import urllib.request, json as _json
            api_key = settings.get('apiKey', '').replace(',', '\n').split('\n')[0].strip()
            model_name = settings.get('modelName', 'gemini-1.5-flash-latest')
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}'
            payload = _json.dumps({'contents':[{'role':'user','parts':[{'text':'Hi'}]}]}).encode()
            req = urllib.request.Request(url, data=payload, headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req, timeout=10)
        else:
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.get('apiKey', 'no-key'),
                base_url=settings.get('baseUrl', 'https://api.openai.com/v1'),
            )
            model_name = settings.get('modelName', '')
            use_new_param = any(model_name.startswith(p) for p in ('gpt-5', 'o1', 'o3', 'o4'))
            token_param = {'max_completion_tokens': 5} if use_new_param else {'max_tokens': 5}
            client.chat.completions.create(
                model=model_name,
                messages=[{'role': 'user', 'content': 'Hi'}],
                **token_param,
            )
        latency = int((time.time() - start) * 1000)
        return {'success': True, 'message': f'Kết nối thành công ({latency}ms)', 'latency': latency}
    except Exception as e:
        msg = str(e)
        if '401' in msg or 'api key' in msg.lower():
            msg = 'API key không hợp lệ hoặc đã hết hạn'
        elif '404' in msg or 'not found' in msg.lower():
            msg = 'Model không tồn tại hoặc Base URL sai'
        elif '429' in msg:
            msg = 'Vượt quá rate limit, thử lại sau'
        return {'success': False, 'message': msg}
