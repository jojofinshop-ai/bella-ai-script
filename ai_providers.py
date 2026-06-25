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
    max_tok = int(settings.get('maxTokens', 0))
    temp = float(settings.get('temperature', 0.8))

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
    return content


def call_gemini(settings: dict, system_prompt: str, user_prompt: str, images: list) -> str:
    import urllib.request
    import json as _json

    api_key = settings.get('apiKey', '')
    model_name = settings.get('modelName', 'gemini-1.5-flash-latest')
    temperature = float(settings.get('temperature', 0.8))
    max_tokens = int(settings.get('maxTokens', 0))

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}'

    parts = [{'text': f"{system_prompt}\n\n{user_prompt}"}]
    for img in images:
        b64_data, mime = get_base64_from_data_url(img.get('dataUrl', ''))
        parts.append({'inline_data': {'mime_type': mime, 'data': b64_data}})

    gen_config = {'temperature': temperature}
    if max_tokens > 0:
        gen_config['maxOutputTokens'] = max_tokens

    payload = _json.dumps({
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': gen_config,
        'safetySettings': [
            {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'},
        ]
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = _json.loads(resp.read())

    text = data['candidates'][0]['content']['parts'][0]['text']
    if not text:
        raise ValueError('Gemini trả về nội dung rỗng')
    return text


def analyze_images_with_gemini(gemini_api_keys, images: list) -> str:
    """Dùng Gemini Flash (rẻ) để phân tích toàn bộ ảnh sản phẩm, trả về text mô tả.
    Hỗ trợ nhiều API key — tự động chuyển key khi gặp 429."""
    keys = _parse_gemini_keys(gemini_api_keys)
    if not keys or not images:
        return ''
    n = len(images)
    system_prompt = 'Bạn là chuyên gia phân tích sản phẩm thời trang. Mô tả chính xác, chi tiết những gì thấy trong ảnh.'
    user_prompt = (
        f'Tôi gửi {n} ảnh sản phẩm. Hãy phân tích TẤT CẢ {n} ảnh và tổng hợp thành 1 mô tả đầy đủ:\n'
        '- Màu sắc: tên màu cụ thể (đen tuyền, be sữa, xanh navy...), có bao nhiêu màu/biến thể\n'
        '- Chất liệu: nhận dạng nếu nhìn thấy (cotton, vải lụa, denim...)\n'
        '- Kiểu dáng & form: rộng/ôm/suông, dáng quần/áo/váy cụ thể\n'
        '- Chi tiết thiết kế nổi bật: cổ áo, tay áo, đường may, họa tiết, logo, phụ kiện đính kèm\n'
        '- Cách mặc & phối đồ thấy trong ảnh (nếu có model mặc)\n'
        'Chỉ mô tả những gì thực sự nhìn thấy. Không bịa đặt.'
    )
    for key in keys:
        settings = {'apiKey': key, 'modelName': 'gemini-2.0-flash', 'temperature': 0.2, 'maxTokens': 0}
        try:
            return call_gemini(settings, system_prompt, user_prompt, images)
        except Exception as e:
            if '429' in str(e) and key != keys[-1]:
                continue
    return ''


def _parse_gemini_keys(keys_input) -> list:
    """Chuyển string hoặc list thành danh sách API key sạch."""
    if isinstance(keys_input, list):
        return [k.strip() for k in keys_input if k and k.strip()]
    if isinstance(keys_input, str):
        return [k.strip() for k in keys_input.replace(',', '\n').split('\n') if k.strip()]
    return []


def scan_product_from_screenshot(gemini_api_keys, image_data_urls: list) -> dict:
    """Dùng Gemini Vision đọc 1 hoặc nhiều ảnh chụp màn hình sản phẩm, trả về {productName, productDescription}.
    Hỗ trợ nhiều API key — tự động chuyển key khi gặp 429 rate limit."""
    keys = _parse_gemini_keys(gemini_api_keys)
    if not keys or not image_data_urls:
        raise ValueError('Cần Gemini API key và ảnh')
    n = len(image_data_urls)
    system_prompt = 'Bạn là công cụ đọc thông tin sản phẩm từ ảnh chụp màn hình. Trả về JSON chính xác.'
    user_prompt = (
        f'Đây là {n} ảnh chụp màn hình trang sản phẩm (TikTok Shop, Shopee, hoặc website bán hàng).\n'
        'Hãy đọc TẤT CẢ ảnh và trích xuất:\n'
        '1. Tên sản phẩm (tiêu đề/heading chính)\n'
        '2. Toàn bộ nội dung mô tả sản phẩm từ tất cả ảnh (chất liệu, kích thước, tính năng, ưu điểm...)\n\n'
        'Trả về JSON (chỉ JSON, không giải thích thêm):\n'
        '{"productName": "...", "productDescription": "..."}'
    )
    import json as _json, re
    images = [{'dataUrl': u} for u in image_data_urls]
    last_err = None
    for key in keys:
        settings = {'apiKey': key, 'modelName': 'gemini-2.0-flash', 'temperature': 0.1, 'maxTokens': 0}
        try:
            raw = call_gemini(settings, system_prompt, user_prompt, images)
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                return _json.loads(m.group(0))
            raise ValueError('Gemini không trả về JSON hợp lệ')
        except Exception as e:
            last_err = e
            if '429' in str(e) and key != keys[-1]:
                continue  # thử key tiếp theo ngay lập tức
            raise last_err
    raise last_err


def call_ai(settings: dict, system_prompt: str, user_prompt: str, images: list) -> str:
    provider = settings.get('provider', 'openai')
    if provider == 'gemini':
        return call_gemini(settings, system_prompt, user_prompt, images)
    else:
        return call_openai_compatible(settings, system_prompt, user_prompt, images)


def model_supports_vision(provider: str, model_name: str) -> bool:
    if provider == 'deepseek':
        return False
    if provider == 'gemini':
        return True
    if provider == 'openai':
        name = model_name.lower()
        return any(x in name for x in ['gpt-4', 'gpt-4o', 'vision', '4.1', '4-turbo'])
    return True  # assume custom supports vision


def test_ai_connection(settings: dict) -> dict:
    start = time.time()
    provider = settings.get('provider', 'openai')
    try:
        if provider == 'gemini':
            import urllib.request, json as _json
            api_key = settings.get('apiKey', '')
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
