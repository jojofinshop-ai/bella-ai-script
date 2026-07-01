import sys
import os
import threading
import json
import base64
import struct
import zlib
from flask import Flask, render_template, request, jsonify, Response

IS_CLOUD = bool(os.environ.get('PORT') or os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'))

# PyInstaller path handling
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS          # bundled assets (templates, icons)
    EXE_DIR  = os.path.dirname(sys.executable)  # folder where exe is installed
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR  = BASE_DIR

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json() or {}
        product_name = data.get('productName', '').strip()
        product_desc = data.get('productDescription', '').strip()
        images = data.get('images', [])
        settings = data.get('settings', {})
        prompt_settings = data.get('promptSettings', {})
        input_data = data.get('input', {})
        reference_candidates = data.get('referenceLibraryCandidates', [])  # V8: Reference Library

        if not product_name:
            return jsonify({'success': False, 'error': 'Thiếu tên sản phẩm'}), 400
        if not product_desc:
            return jsonify({'success': False, 'error': 'Thiếu mô tả sản phẩm'}), 400

        provider = settings.get('provider', 'openai')
        api_key = settings.get('apiKey', '')
        if not api_key and provider != 'custom':
            return jsonify({'success': False, 'error': 'Chưa nhập API key. Vào tab Cài đặt để nhập.'}), 400

        # Không giới hạn token output — để model tự dùng max của nó
        settings = dict(settings)
        settings['maxTokens'] = 0  # 0 = không giới hạn (bỏ tham số max_tokens)

        from prompt_builder import build_system_prompt, build_user_prompt, parse_ai_response
        from ai_providers import call_ai, analyze_images_with_gemini, analyze_images_with_openai

        system_prompt = build_system_prompt(prompt_settings)
        has_images = len(images) > 0

        # Phân tích ảnh theo cấu hình Vision AI
        image_analysis = ''
        images_to_send = []
        analysis_status = 'no_image'  # no_image | skipped | gemini | openai | same_ai
        if has_images:
            vision_provider = settings.get('visionProvider', 'gemini')
            max_imgs = max(1, int(settings.get('maxAnalysisImages', 1)))
            images_for_analysis = images[:max_imgs]
            if vision_provider == 'gemini':
                raw_vision = settings.get('visionGeminiKeys', '') or (settings.get('apiKeys') or {}).get('gemini', '')
                gemini_keys = [k.strip() for k in raw_vision.replace(',', '\n').split('\n') if k.strip()]
                if gemini_keys:
                    image_analysis = analyze_images_with_gemini(gemini_keys, images_for_analysis, product_name)
                    analysis_status = 'gemini' if image_analysis else 'skipped'
                else:
                    analysis_status = 'skipped'
            elif vision_provider == 'openai':
                vision_key = settings.get('visionOpenaiKey', '').strip()
                vision_base_url = (settings.get('visionOpenaiBaseUrl', '') or 'https://api.openai.com/v1').strip()
                vision_model = (settings.get('visionOpenaiModel', '') or 'gpt-4o-mini').strip()
                if vision_key:
                    openai_vision_settings = {'apiKey': vision_key, 'baseUrl': vision_base_url, 'modelName': vision_model}
                    image_analysis = analyze_images_with_openai(openai_vision_settings, images_for_analysis, product_name)
                    analysis_status = 'openai' if image_analysis else 'skipped'
                else:
                    analysis_status = 'skipped'
            elif vision_provider == 'same':
                if provider != 'deepseek':
                    images_to_send = images_for_analysis
                    analysis_status = 'same_ai'
                else:
                    analysis_status = 'skipped'

        # has_images_effective: True chỉ khi AI thực sự nhận được ảnh (qua analysis text hoặc trực tiếp)
        has_images_effective = bool(image_analysis) or bool(images_to_send)

        # V8: Reference Library — AI chọn lọc mẫu phù hợp nhất từ candidates (frontend đã
        # pre-filter theo ngành hàng). Lỗi ở bước này KHÔNG được làm fail cả lần generate chính.
        _ref_result = {'contents': [], 'used': []}
        if reference_candidates:
            from ai_providers import select_relevant_examples
            _ref_result = select_relevant_examples(
                settings, product_name, product_desc, input_data.get('industry', 'auto'), reference_candidates
            )
        input_data['referenceExamples'] = _ref_result['contents']
        _referenced_samples = _ref_result['used']

        user_prompt = build_user_prompt(input_data, has_images_effective, image_analysis)
        raw_response = call_ai(settings, system_prompt, user_prompt, images_to_send)

        try:
            script = parse_ai_response(raw_response)
            from validators import validate_script_schema
            script, _val_issues = validate_script_schema(script)
            return jsonify({'success': True, 'script': script, 'imageAnalysis': image_analysis, 'imageAnalysisStatus': analysis_status, 'schemaIssues': _val_issues if _val_issues else None, 'referencedSamples': _referenced_samples})
        except Exception as parse_err:
            return jsonify({
                'success': False,
                'error': 'AI trả về định dạng không hợp lệ. Thử lại hoặc điều chỉnh prompt.',
                'rawResponse': raw_response
            }), 422

    except Exception as e:
        msg = str(e)
        if 'api key' in msg.lower() or '401' in msg:
            msg = 'API key không hợp lệ hoặc đã hết hạn'
        elif '404' in msg or 'not found' in msg.lower():
            msg = 'Model không tồn tại. Kiểm tra lại tên model'
        elif '429' in msg or 'rate limit' in msg.lower():
            msg = 'Vượt quá rate limit. Thử lại sau vài giây'
        elif 'connection' in msg.lower() or 'timeout' in msg.lower():
            msg = 'Không thể kết nối API. Kiểm tra internet và Base URL'
        return jsonify({'success': False, 'error': msg}), 500


def _get_chrome_cookies(domain):
    """Đọc cookies từ Chrome (Windows) cho domain cụ thể."""
    import ctypes, ctypes.wintypes, sqlite3, shutil, tempfile

    try:
        # 1. Lấy master key từ Local State
        local_state_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Local State')
        with open(local_state_path, 'r', encoding='utf-8') as f:
            ls = json.loads(f.read())
        encrypted_key = base64.b64decode(ls['os_crypt']['encrypted_key'])[5:]  # bỏ prefix "DPAPI"

        # 2. Giải mã master key bằng Windows DPAPI
        class _BLOB(ctypes.Structure):
            _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
        buf = ctypes.create_string_buffer(encrypted_key)
        inp = _BLOB(len(encrypted_key), buf)
        out = _BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
            return {}
        master_key = ctypes.string_at(out.pbData, out.cbData)
        ctypes.windll.kernel32.LocalFree(out.pbData)

        # 3. Đọc cookies DB (copy ra temp vì Chrome lock file)
        cookies_src = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies')
        tmp = tempfile.mktemp(suffix='.db')
        shutil.copy2(cookies_src, tmp)

        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?", (f'%{domain}%',))
        rows = cur.fetchall()
        conn.close()
        os.unlink(tmp)

        # 4. Giải mã từng cookie
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cookies = {}
        for name, enc_val in rows:
            try:
                if enc_val[:3] == b'v10':
                    iv, payload = enc_val[3:15], enc_val[15:]
                    value = AESGCM(master_key).decrypt(iv, payload, None).decode('utf-8', errors='ignore')
                    cookies[name] = value
            except Exception:
                pass
        return cookies
    except Exception:
        return {}

_PLAYWRIGHT_PROFILE = os.path.join(EXE_DIR, 'bella_browser_profile')

def _find_chrome_executable():
    """Tìm Chrome hoặc Edge có sẵn trên máy để dùng với Playwright."""
    candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None

_READ_DOM_JS = """() => {
    const m = (s) => document.querySelector(s)?.content || '';
    const title = document.querySelector('h1')?.innerText?.trim()
        || m('meta[property="og:title"]') || m('meta[name="twitter:title"]')
        || document.title || '';

    let desc = '';

    // Strategy 1A: TikTok sectionHeader -> sectionContent (confirmed from DevTools)
    for (const header of document.querySelectorAll('[class*="sectionHeader"]')) {
        const ht = (header.innerText || '').trim().toLowerCase();
        if (ht.includes('product description') || ht.includes('mo ta san pham')
            || ht.includes('m\\u00f4 t\\u1ea3 s\\u1ea3n ph\\u1ea9m')) {
            const content = header.nextElementSibling;
            if (content) { desc = (content.innerText || '').trim(); }
            break;
        }
    }

    // Strategy 1B: Find heading text, walk to sibling content
    if (!desc) {
        for (const el of document.querySelectorAll('p, span, div, h2, h3, h4, button')) {
            const t = (el.innerText || '').trim().toLowerCase();
            if (t === 'product description' || (t.length < 35 && t.startsWith('product description'))) {
                const sibs = [
                    el.nextElementSibling,
                    el.parentElement && el.parentElement.nextElementSibling,
                    el.parentElement && el.parentElement.parentElement && el.parentElement.parentElement.nextElementSibling,
                    el.parentElement && el.parentElement.parentElement && el.parentElement.parentElement.parentElement && el.parentElement.parentElement.parentElement.nextElementSibling,
                ];
                for (const sib of sibs) {
                    if (!sib) continue;
                    const txt = (sib.innerText || sib.textContent || '').trim();
                    if (txt.length > 50 && txt.toLowerCase() !== t) { desc = txt; break; }
                }
                if (desc) break;
            }
        }
    }

    // Strategy 2: TikTok SmallText1-Regular spans (confirmed class from DevTools)
    if (!desc) {
        const spans = document.querySelectorAll('[class*="SmallText1"]');
        if (spans.length > 2) {
            desc = Array.from(spans).map(function(s) { return (s.innerText || '').trim(); }).filter(function(t) { return t.length > 0; }).join('\\n');
        }
    }

    // Strategy 3: Broad candidate search
    if (!desc) {
        const BLOCKED = ['get the full app', 'security check', 'open tiktok', 'not now',
                         'make your day', 'sign up', 'log in', 'create account'];
        const candidates = Array.from(document.querySelectorAll('p, li, div, [class*="desc"], [class*="detail"]'))
            .map(function(el) { return el.innerText ? el.innerText.trim() : ''; })
            .filter(function(t) { return t.length > 80 && t.length < 10000; })
            .filter(function(t) { const tl = t.toLowerCase(); return !BLOCKED.some(function(b) { return tl.startsWith(b) || tl === b; }); })
            .filter(function(t) { return !t.includes('TikTok Shop') || t.length > 300; })
            .sort(function(a, b) { return b.length - a.length; });
        desc = candidates[0] || '';
    }

    if (!desc) desc = m('meta[property="og:description"]') || '';

    const productImgs = Array.from(document.querySelectorAll('img'))
        .map(i => i.src || i.dataset.src || i.dataset.original || '')
        .filter(s => s && (s.includes('ibyteimg.com') || s.includes('seaimg.com')))
        .filter(s => !s.includes('logo') && !s.includes('icon') && !s.includes('avatar'))
        .filter((v, i, a) => a.indexOf(v) === i).slice(0, 5);
    const ogImg = m('meta[property="og:image"]') || '';
    if (ogImg && !productImgs.length) productImgs.push(ogImg);
    return { title, desc, productImgs };
}"""

def _is_blocked_page(page):
    """Trả về True nếu trang đang hiện security check / login."""
    try:
        url = page.url
        title = page.title()
    except Exception:
        return True
    auth_url = any(k in url for k in ('login', 'passport', 'auth', 'signin', 'account', 'risk-check', 'verify'))
    blocked_title = any(k in title.lower() for k in ('security check', 'verify', 'captcha', 'robot', 'checking'))
    return auth_url or blocked_title

def _fetch_with_playwright(url, injected_cookies=None, cookie_domain=None):
    """Mở Chromium persistent (giữ session), chờ user xác thực nếu cần, đọc DOM."""
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    import time

    os.makedirs(_PLAYWRIGHT_PROFILE, exist_ok=True)

    _chrome_exe = _find_chrome_executable()
    with sync_playwright() as p:
        _pw_kwargs = dict(
            user_data_dir=_PLAYWRIGHT_PROFILE,
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-first-run'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='vi-VN',
            viewport={'width': 1280, 'height': 800},
        )
        if _chrome_exe:
            _pw_kwargs['executable_path'] = _chrome_exe
        ctx = p.chromium.launch_persistent_context(**_pw_kwargs)

        # Inject Chrome cookies vào persistent profile (hữu ích lần đầu chưa có session)
        if injected_cookies and cookie_domain:
            pw_cookies = [
                {'name': k, 'value': v, 'domain': cookie_domain, 'path': '/',
                 'sameSite': 'None', 'secure': True}
                for k, v in injected_cookies.items()
            ]
            try:
                ctx.add_cookies(pw_cookies)
            except Exception:
                pass

        page = ctx.new_page()
        try:
            page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # Phase 1: Chờ user vượt xác thực lần đầu (tối đa 3 phút)
            deadline = time.time() + 180
            while time.time() < deadline:
                if not _is_blocked_page(page):
                    break
                time.sleep(1.5)
            else:
                ctx.close()
                return None, 'Hết thời gian chờ xác thực (3 phút). Thử lại.'

            # Phase 2: Stabilization — TikTok có thể chuyển sang security check khác ngay sau
            # Chờ trang ổn định (không bị chặn) liên tục 3 lần check (~4.5s) mới tiến hành đọc
            stable_count = 0
            stab_deadline = time.time() + 60  # tối đa 60s để stabilize
            while time.time() < stab_deadline:
                if _is_blocked_page(page):
                    stable_count = 0  # xuất hiện check mới — chờ user vượt tiếp
                    inner = time.time() + 120
                    while time.time() < inner:
                        if not _is_blocked_page(page):
                            break
                        time.sleep(1.5)
                else:
                    stable_count += 1
                    if stable_count >= 3:
                        break
                time.sleep(1.5)

            # Phase 3: Chờ JS render & API xong
            try:
                page.wait_for_load_state('networkidle', timeout=15000)
            except PwTimeout:
                pass
            time.sleep(2)

            # Nếu short link redirect sang shop.tiktok.com/pdp/ → điều hướng sang view/product/ (DOM tốt hơn)
            import re as _re_pw
            _cur_url = page.url
            _m_pdp = _re_pw.search(r'shop\.tiktok\.com/[a-z]+/pdp/(\d{10,})', _cur_url)
            if _m_pdp:
                _target = f'https://www.tiktok.com/view/product/{_m_pdp.group(1)}'
                try:
                    page.goto(_target, timeout=20000, wait_until='domcontentloaded')
                    try:
                        page.wait_for_load_state('networkidle', timeout=12000)
                    except PwTimeout:
                        pass
                    time.sleep(2)
                except Exception:
                    pass  # Giữ nguyên trang hiện tại nếu không chuyển được

            # Dismiss "Get the full app experience" modal nếu xuất hiện
            try:
                page.click('text="Not now"', timeout=1500)
                time.sleep(0.5)
            except Exception:
                pass

            # Scroll để trigger lazy-load + hiện "Product description" content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
            time.sleep(1.5)

            dom = page.evaluate(_READ_DOM_JS)
            name = dom.get('title', '').strip()
            desc = dom.get('desc', '').strip()
            img_urls = dom.get('productImgs', [])

            # Tải ảnh qua page.request (dùng session đang mở)
            images = []
            for i, iurl in enumerate(img_urls[:4]):
                try:
                    resp = page.request.get(iurl, timeout=10000)
                    if resp.ok:
                        mime = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
                        b64 = base64.b64encode(resp.body()).decode()
                        images.append({'id': f'pw-{i}', 'dataUrl': f'data:{mime};base64,{b64}'})
                except Exception:
                    pass

            ctx.close()

            if name and not any(k in name for k in ('Security Check', 'Verify', 'Captcha')) and len(name) > 3:
                return {'productName': name, 'productDescription': desc, 'images': images}, None
            return None, 'Không đọc được thông tin sản phẩm — thử lại hoặc kiểm tra trang trong cửa sổ vừa mở'

        except Exception as e:
            try:
                ctx.close()
            except Exception:
                pass
            return None, str(e)


def _fetch_with_playwright_headless(url):
    """Headless Playwright — chạy trên cloud server, không cần GUI, render JavaScript đầy đủ."""
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    _chrome_exe2 = _find_chrome_executable()
    with sync_playwright() as p:
        _launch_kwargs = dict(
            headless=True,
            args=[
                '--no-sandbox', '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', '--disable-gpu',
                '--single-process', '--no-zygote',
                '--disable-extensions', '--disable-background-networking',
            ],
        )
        if _chrome_exe2:
            _launch_kwargs['executable_path'] = _chrome_exe2
        browser = p.chromium.launch(**_launch_kwargs)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='vi-VN',
            viewport={'width': 1280, 'height': 800},
        )
        page = ctx.new_page()
        try:
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state('networkidle', timeout=12000)
            except PwTimeout:
                pass
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
            page.wait_for_timeout(1500)

            dom = page.evaluate(_READ_DOM_JS)
            name = dom.get('title', '').strip()
            desc = dom.get('desc', '').strip()
            img_urls = dom.get('productImgs', [])

            images = []
            for i, iurl in enumerate(img_urls[:4]):
                try:
                    resp = page.request.get(iurl, timeout=10000)
                    if resp.ok:
                        mime = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
                        b64 = base64.b64encode(resp.body()).decode()
                        images.append({'id': f'cl-{i}', 'dataUrl': f'data:{mime};base64,{b64}'})
                except Exception:
                    pass

            browser.close()

            if name and len(name) > 3 and not any(k in name for k in ('Security Check', 'Verify', 'Captcha')):
                return {'productName': name, 'productDescription': desc, 'images': images}, None
            return None, 'Không đọc được thông tin sản phẩm'
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return None, str(e)


def _fetch_shopee_data(url, opener=None):
    import re, urllib.request as _req, json as _json, http.cookiejar as _cj
    # Format 1: /product-name-i.SHOPID.ITEMID
    m = re.search(r'-i\.(\d+)\.(\d+)', url)
    if m:
        shopid, itemid = m.group(1), m.group(2)
    else:
        # Format 2: shopee.vn/shopname/SHOPID/ITEMID (từ short link)
        m2 = re.search(r'shopee\.vn/[^/?#]+/(\d+)/(\d+)', url)
        if m2:
            shopid, itemid = m2.group(1), m2.group(2)
        else:
            return None, 'Không nhận dạng được URL Shopee. Hãy dùng link trực tiếp đến sản phẩm.'

    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

    # Nếu chưa có opener (cookie session), tạo mới và ghé trang chủ lấy cookie
    if opener is None:
        cj = _cj.CookieJar()
        opener = _req.build_opener(_req.HTTPCookieProcessor(cj))
        try:
            seed_req = _req.Request(
                f'https://shopee.vn/product-i.{shopid}.{itemid}',
                headers={'User-Agent': UA, 'Accept': 'text/html', 'Accept-Language': 'vi-VN,vi;q=0.9'}
            )
            with opener.open(seed_req, timeout=10):
                pass
        except Exception:
            pass

    # Thử nhiều endpoint API
    apis = [
        f'https://shopee.vn/api/v4/item/get?itemid={itemid}&shopid={shopid}',
        f'https://shopee.vn/api/v4/pdp/get_pc?item_id={itemid}&shop_id={shopid}',
    ]
    last_err = None
    for api in apis:
        try:
            api_req = _req.Request(api, headers={
                'User-Agent': UA,
                'Referer': f'https://shopee.vn/product-i.{shopid}.{itemid}',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'vi-VN,vi;q=0.9',
            })
            with opener.open(api_req, timeout=15) as resp:
                data = _json.loads(resp.read())
            item = (data.get('data') or data.get('item') or {})
            if item:
                return item, None
        except Exception as e:
            last_err = e

    # Fallback: parse HTML meta tags (og:title / og:description / JSON-LD)
    try:
        page_url = f'https://shopee.vn/product-i.{shopid}.{itemid}'
        page_req = _req.Request(page_url, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'vi-VN,vi;q=0.9',
            'Referer': 'https://www.google.com/',
        })
        with opener.open(page_req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        name, desc, imgs = '', '', []
        og_t = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html)
        og_d = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{10,})["\']', html)
        og_i = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og_t:
            name = re.sub(r'\s*[\|\-–]\s*Shopee.*$', '', og_t.group(1)).strip()
        if og_d:
            desc = og_d.group(1).strip()

        # JSON-LD
        ld = re.search(r'<script type=["\']application/ld\+json["\']>(.*?)</script>', html, re.DOTALL)
        if ld:
            try:
                ld_data = _json.loads(ld.group(1))
                if isinstance(ld_data, list):
                    ld_data = next((d for d in ld_data if d.get('@type') == 'Product'), {})
                if not name:
                    name = ld_data.get('name', '')
                if not desc:
                    desc = ld_data.get('description', '')
            except Exception:
                pass

        if name:
            return {'name': name, 'description': desc, 'images': []}, None
    except Exception:
        pass

    err_str = str(last_err) if last_err else ''
    if '403' in err_str or 'Forbidden' in err_str:
        return None, 'Shopee chặn truy cập từ server (403). Hãy chụp màn hình sản phẩm và dùng nút "Scan ảnh mô tả sản phẩm" để đọc tự động.'
    return None, f'Lỗi Shopee: {err_str or "Không lấy được dữ liệu"}'


def _fetch_tiktok_cloud(url):
    """Lấy thông tin sản phẩm TikTok Shop trên cloud (không dùng Playwright).
    Follow redirect từ vt.tiktok.com rồi extract og_info từ redirect URL + __NEXT_DATA__ / meta tags + CDN scan.
    """
    import urllib.request as _req
    import json as _json
    import re
    from html.parser import HTMLParser
    from urllib.parse import urlparse, parse_qs

    UA_DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    headers = {
        'User-Agent': UA_DESKTOP,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com/',
    }

    UA_MOBILE = 'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36'
    UA_GBOT   = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

    def _is_blocked(h):
        low = h.lower()[:4000]
        return (len(h) < 2000
                or 'security check' in low
                or 'just a moment' in low
                or 'enable javascript' in low
                or 'cf-browser-verification' in low)

    # shop.tiktok.com/vn/pdp/ — thử nhiều UA theo thứ tự ưu tiên
    _is_shop_pdp = 'shop.tiktok.com' in url and '/pdp/' in url
    if _is_shop_pdp:
        _shop_headers_base = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        html = ''; final_url = url
        for _ua in [UA_MOBILE, UA_GBOT, UA_DESKTOP]:
            try:
                _req_shop = _req.Request(url, headers={**_shop_headers_base, 'User-Agent': _ua})
                with _req.urlopen(_req_shop, timeout=20) as _r:
                    _h = _r.read().decode('utf-8', errors='ignore')
                if not _is_blocked(_h):
                    html = _h; break
                html = _h  # giữ lại dù bị block để thử parse sau
            except Exception:
                pass
        if not html:
            return None, 'Không thể tải trang shop.tiktok.com'
    else:
        try:
            req = _req.Request(url, headers=headers)
            with _req.urlopen(req, timeout=20) as resp:
                final_url = resp.url  # URL sau khi follow redirect
                html = resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return None, f'Không thể tải trang: {str(e)}'

    html_shop_original = html  # giữ lại để fallback nếu re-fetch kém hơn

    # ── Re-fetch clean canonical URL khi cần ────────────────────────────────────────
    # vt.tiktok.com → redirect → view/product/{ID}?og_info=...  (TikTok trả về share-optimized page,
    #   thiếu full __NEXT_DATA__ chứa mô tả sản phẩm)
    # shop.tiktok.com/pdp/{ID}?...  (domain khác, HTML structure khác)
    # Giải pháp: luôn re-fetch URL sạch khi final_url có params hoặc sai domain
    import re as _re_prod
    _orig_final_url = final_url  # Lưu URL gốc (có og_info params) để dùng ở bước parse og_info
    _prod_id_m = _re_prod.search(r'/(?:pdp|view/product)/(\d{10,})', final_url)
    if _prod_id_m:
        _canonical = f'https://www.tiktok.com/view/product/{_prod_id_m.group(1)}'
        _needs_refetch = ('?' in final_url          # có query params → share-optimized page
                          or 'shop.tiktok.com' in final_url    # sai domain
                          or 'view/product' not in final_url)  # /pdp/ path
        if _needs_refetch:
            try:
                _req2 = _req.Request(_canonical, headers=headers)
                with _req.urlopen(_req2, timeout=20) as _r2:
                    _html2 = _r2.read().decode('utf-8', errors='ignore')
                # Chỉ dùng html2 nếu thật sự có nội dung sản phẩm (không phải security check)
                if len(_html2) > 1000 and 'security check' not in _html2.lower()[:3000]:
                    html = _html2
                    final_url = _canonical
            except Exception:
                pass  # Giữ nguyên html gốc nếu re-fetch thất bại

    # ── KEY FIX: TikTok nhúng og_info (title=mô tả thật, image=ảnh) vào redirect URL ──
    # vt.tiktok.com → tiktok.com/view/product/...?og_info={"title":"...","image":"..."}
    # Dùng _orig_final_url để parse og_info vì final_url có thể đã được cập nhật thành canonical (không có params)
    og_info_desc = ''
    og_info_img  = ''
    try:
        qs = parse_qs(urlparse(_orig_final_url).query)
        og_raw = qs.get('og_info', [''])[0]
        if og_raw:
            og = _json.loads(og_raw)
            og_info_desc = og.get('title', '').strip()
            og_info_img  = og.get('image', '').strip()
    except Exception:
        pass

    # Track image keys đã download — normalize URL để tránh duplicate cùng ảnh khác size/params
    _seen_img_keys = set()

    def _img_key(u):
        """Normalize TikTok CDN URL: bỏ query params và ~tplv transform suffix."""
        base = u.split('?')[0]   # bỏ ?x-expires=...
        base = base.split('~')[0]  # bỏ ~tplv-resize-jpeg:720:720...
        return base

    def _cdn_scan(html_text, existing_count=0):
        """Scan HTML source tìm ảnh TikTok/ByteDance CDN, bỏ qua URL cùng ảnh đã download."""
        cdn_re = re.compile(
            r'https://[a-z0-9\-]+\.(?:ibyteimg|tiktokcdn|ibytedtos|tiktokstaticb)\.com'
            r'/[^\s"\'<>\]\\]+\.(?:jpeg|jpg|png|webp)(?:[?~][^\s"\'<>\]]*)?'
        )
        SKIP = ('avatar', 'logo', 'icon', '100x100', '50x50', '30x30', 'header', 'banner/bg')
        seen_local, result = set(), []
        for u in cdn_re.findall(html_text):
            u = u.replace('\\u002F', '/').replace('%2F', '/')
            key = _img_key(u)
            if key not in _seen_img_keys and key not in seen_local and not any(x in u.lower() for x in SKIP):
                seen_local.add(key)
                result.append(u)
        images = []
        for i, img_url in enumerate(result[:max(0, 4 - existing_count)]):
            try:
                images.append({'id': f'tt-cdn-{i}', 'dataUrl': _download_image_b64(img_url, UA_DESKTOP)})
                _seen_img_keys.add(_img_key(img_url))
            except Exception:
                pass
        return images

    def _download_img_list(img_list, prefix='tt'):
        images = []
        for i, img in enumerate(img_list[:4]):
            img_url = img if isinstance(img, str) else img.get('url', img.get('src', img.get('urlList', [''])[0] if isinstance(img.get('urlList'), list) else ''))
            if img_url and img_url.startswith('http'):
                key = _img_key(img_url)
                if key not in _seen_img_keys:
                    try:
                        images.append({'id': f'{prefix}-{i}', 'dataUrl': _download_image_b64(img_url, UA_DESKTOP)})
                        _seen_img_keys.add(key)
                    except Exception:
                        pass
        return images

    def _parse_shop_tiktok_html(html_text):
        """Extract product info từ HTML của shop.tiktok.com — dùng class CSS đặc trưng."""
        # Tên sản phẩm: <span class="H2-Semibold ...">Tên SP</span>
        name = ''
        m_h2 = re.search(r'<span[^>]+class="[^"]*H2-Semibold[^"]*"[^>]*>(.*?)</span>', html_text, re.DOTALL)
        if m_h2:
            name = re.sub(r'<[^>]+>', '', m_h2.group(1)).strip()
        # Fallback: lấy từ <h1> tag
        if not name:
            m_h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.DOTALL)
            if m_h1:
                name = re.sub(r'<[^>]+>', '', m_h1.group(1)).strip()
        # Fallback: lấy từ img alt attribute (nhiều ảnh đều dùng tên SP làm alt)
        if not name:
            m_alt = re.search(r'<img[^>]+alt="([^"]{10,})"', html_text)
            if m_alt and 'tiktok' not in m_alt.group(1).lower():
                name = m_alt.group(1).strip()

        # Mô tả: các div.font-sans.font-normal.text-color-UIText1.mb-8
        desc_parts = re.findall(
            r'<div[^>]+class="[^"]*font-sans font-normal text-color-UIText1 mb-8[^"]*"[^>]*>(.*?)</div>',
            html_text, re.DOTALL
        )
        desc = '\n'.join(re.sub(r'<[^>]+>', '', p).replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<').strip()
                         for p in desc_parts if re.sub(r'<[^>]+>', '', p).strip()).strip()

        # Ảnh: img src từ CDN
        img_urls = re.findall(
            r'src="(https://[^"]+?\.(?:ibyteimg|tiktokcdn|ibytedtos)\.com/[^"]+?\.(?:jpeg|jpg|png|webp)[^"]*)"',
            html_text
        )
        SKIP = ('avatar', 'logo', 'icon', '100x100', '50x50', 'header', 'banner')
        seen_keys = set()
        images = []
        for img_url in img_urls:
            key = img_url.split('?')[0].split('~')[0]
            if key in seen_keys or any(s in img_url.lower() for s in SKIP):
                continue
            seen_keys.add(key)
            try:
                images.append({'id': f'sh-{len(images)}', 'dataUrl': _download_image_b64(img_url, UA_MOBILE)})
                if len(images) >= 4:
                    break
            except Exception:
                pass

        if name and len(name) > 3:
            return {'productName': name, 'productDescription': desc, 'images': images}
        return None

    def _is_generic_tiktok_desc(text):
        """TikTok luôn dùng og:description = text marketing chung, không phải mô tả sản phẩm thật."""
        markers = ('săn giá siêu hời', 'freeship mặt hàng', 'ưu đãi độc quyền',
                   'mua ngay để nhận', 'trên tiktok shop', 'make your day')
        tl = text.lower()
        return sum(1 for m in markers if m in tl) >= 2

    def _deep_find_product(obj, depth=0):
        """Recursive search trong JSON để tìm object chứa tên + mô tả sản phẩm thật."""
        if depth > 8 or not isinstance(obj, (dict, list)):
            return None
        if isinstance(obj, list):
            for item in obj:
                r = _deep_find_product(item, depth + 1)
                if r: return r
            return None
        # Kiểm tra nếu dict này trông như product object
        name = (obj.get('title') or obj.get('name') or obj.get('itemName') or
                obj.get('productName') or '').strip()
        desc = (obj.get('description') or obj.get('content') or obj.get('detail') or
                obj.get('itemDescription') or obj.get('productDesc') or '').strip()
        if name and 5 < len(name) < 300 and desc and len(desc) > 30 and not _is_generic_tiktok_desc(desc):
            imgs = (obj.get('images') or obj.get('imageUrls') or obj.get('imgUrlList') or [])
            return {'name': name, 'desc': desc, 'imgs': imgs}
        # Đệ quy xuống các key con có tên liên quan đến sản phẩm
        PRODUCT_KEYS = ('product', 'item', 'productInfo', 'itemInfo', 'itemStruct',
                        'productDetail', 'data', 'initialData', 'serverSideProps',
                        'pageProps', 'props', 'detail', 'info', 'pdp', 'goods')
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                if key in PRODUCT_KEYS or any(k in key.lower() for k in ('product', 'item', 'goods')):
                    r = _deep_find_product(val, depth + 1)
                    if r: return r
        return None

    # ── 0. shop.tiktok.com: parse trực tiếp từ CSS classes đặc trưng ────────────
    if _is_shop_pdp:
        _shop_result = _parse_shop_tiktok_html(html)
        if _shop_result:
            return _shop_result, None

    # ── 1. Tìm trong __NEXT_DATA__ (recursive) ───────────────────────────────
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            nd = _json.loads(m.group(1))
            found = _deep_find_product(nd)
            if found:
                images = _download_img_list(found['imgs'], 'tt-nd')
                if len(images) < 2:
                    images += _cdn_scan(html, len(images))
                return {'productName': found['name'], 'productDescription': found['desc'], 'images': images}, None
        except Exception:
            pass

    # ── 2. Tìm trong tất cả script tags khác (window.__xxx__, JSON blobs) ─────
    for script_text in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        if len(script_text) < 100 or 'function' in script_text[:50]:
            continue
        # Tìm JSON object lớn trong script tag
        for json_match in re.finditer(r'\{["\'](?:product|item|goods|pdp)["\']', script_text):
            start = json_match.start()
            # Lấy từ vị trí bắt đầu đến hết, thử parse
            chunk = script_text[start:start+50000]
            # Tìm balanced JSON
            depth_c, end = 0, -1
            for ci, ch in enumerate(chunk):
                if ch == '{': depth_c += 1
                elif ch == '}':
                    depth_c -= 1
                    if depth_c == 0: end = ci + 1; break
            if end > 0:
                try:
                    obj = _json.loads(chunk[:end])
                    found = _deep_find_product(obj)
                    if found:
                        images = _download_img_list(found['imgs'], 'tt-sc')
                        if len(images) < 2:
                            images += _cdn_scan(html, len(images))
                        return {'productName': found['name'], 'productDescription': found['desc'], 'images': images}, None
                except Exception:
                    pass

    # ── 3. JSON-LD structured data ───────────────────────────────────────────
    for ld_text in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            ld = _json.loads(ld_text)
            if isinstance(ld, list):
                ld = ld[0] if ld else {}
            if ld.get('@type') in ('Product', 'ItemPage', 'Offer'):
                name = ld.get('name', '').strip()
                desc = ld.get('description', '').strip()
                if _is_generic_tiktok_desc(desc): desc = ''
                if name and len(name) > 3:
                    raw_imgs = ld.get('image', [])
                    if isinstance(raw_imgs, str): raw_imgs = [raw_imgs]
                    images = _download_img_list(raw_imgs, 'tt-ld')
                    if len(images) < 2:
                        images += _cdn_scan(html, len(images))
                    return {'productName': name, 'productDescription': desc, 'images': images}, None
        except Exception:
            pass

    # ── 4. og:title + lọc bỏ mô tả chung chung ──────────────────────────────
    class _MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.d = {}; self.og_images = []; self._in_title = False; self._title = ''
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == 'title': self._in_title = True
            elif tag == 'meta':
                prop = a.get('property') or a.get('name') or ''
                c = a.get('content', '')
                if prop == 'og:image' and c:
                    self.og_images.append(c)
                elif prop in ('og:title', 'og:description',
                              'twitter:title', 'twitter:description', 'description'):
                    self.d[prop] = c
        def handle_data(self, d):
            if self._in_title: self._title += d
        def handle_endtag(self, tag):
            if tag == 'title': self._in_title = False; self.d.setdefault('title', self._title.strip())

    p = _MetaParser(); p.feed(html[:200000])
    d = p.d
    name = (d.get('og:title') or d.get('twitter:title') or d.get('title') or '').strip()
    raw_desc = (d.get('og:description') or d.get('twitter:description') or d.get('description') or '').strip()
    desc = '' if _is_generic_tiktok_desc(raw_desc) else raw_desc

    # og_info.title thường là TÊN sản phẩm. Chỉ dùng làm mô tả nếu rất dài (>120 chars) — tức seller viết desc vào title
    if not desc and og_info_desc and len(og_info_desc) > 120 and not _is_generic_tiktok_desc(og_info_desc):
        desc = og_info_desc

    INVALID_TITLES = ('tiktok', 'shop', 'trang chủ', 'home', 'make your day', 'security check', 'just a moment')
    name_ok = name and not any(t in name.lower() for t in INVALID_TITLES) and len(name) > 3
    if not name_ok and og_info_desc:
        # Lấy câu đầu tiên của og_info_desc làm tên sản phẩm
        name = og_info_desc[:120].rsplit(' ', 1)[0] if len(og_info_desc) > 120 else og_info_desc
        name_ok = bool(name)

    if name_ok:
        images = _download_img_list(p.og_images, 'tt-og')
        if og_info_img:
            key = _img_key(og_info_img)
            if key not in _seen_img_keys:
                try:
                    images.insert(0, {'id': 'tt-oginfo', 'dataUrl': _download_image_b64(og_info_img, UA_DESKTOP)})
                    _seen_img_keys.add(key)
                except Exception:
                    pass
        if len(images) < 3:
            images += _cdn_scan(html, len(images))
        note = '' if desc else '[Copy nội dung từ tab "Mô tả" trên TikTok Shop và dán vào đây]'
        return {'productName': name, 'productDescription': desc + note, 'images': images}, None

    # ── Fallback: nếu html hiện tại là kết quả re-fetch www.tiktok.com mà không có data,
    # thử lại với html gốc của shop.tiktok.com (có thể có meta tags khác)
    if _is_shop_pdp and html != html_shop_original and len(html_shop_original) > 2000:
        html = html_shop_original
        p2 = _MetaParser(); p2.feed(html[:200000])
        d2 = p2.d
        name2 = (d2.get('og:title') or d2.get('twitter:title') or d2.get('title') or '').strip()
        raw_desc2 = (d2.get('og:description') or d2.get('twitter:description') or d2.get('description') or '').strip()
        desc2 = '' if _is_generic_tiktok_desc(raw_desc2) else raw_desc2
        INVALID_TITLES2 = ('tiktok', 'shop', 'trang chủ', 'home', 'make your day', 'security check', 'just a moment')
        name_ok2 = name2 and not any(t in name2.lower() for t in INVALID_TITLES2) and len(name2) > 3
        if name_ok2:
            images2 = _download_img_list(p2.og_images, 'tt-sh')
            if len(images2) < 3:
                images2 += _cdn_scan(html, len(images2))
            note2 = '' if desc2 else '[Copy nội dung từ tab "Mô tả" trên TikTok Shop và dán vào đây]'
            return {'productName': name2, 'productDescription': desc2 + note2, 'images': images2}, None

    return None, None

def _download_image_b64(url, ua):
    import urllib.request as _req
    r = _req.Request(url, headers={'User-Agent': ua})
    with _req.urlopen(r, timeout=10) as resp:
        data = resp.read()
        mime = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"

@app.route('/api/open-browser', methods=['POST'])
def open_browser():
    url = (request.get_json() or {}).get('url', '')
    if url.startswith('http'):
        import webbrowser
        webbrowser.open(url)
    return jsonify({'success': True})

@app.route('/api/fetch-url', methods=['POST'])
def fetch_url():
    import re, urllib.request as _req
    from html.parser import HTMLParser

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'Chưa nhập URL'}), 400
    if not url.startswith('http'):
        url = 'https://' + url

    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

    # ── Shopee: gọi API nội bộ (hoạt động cả trên cloud) ─────────────────────
    if 'shopee.vn' in url:
        try:
            import http.cookiejar as _cj
            cj = _cj.CookieJar()
            shopee_opener = _req.build_opener(_req.HTTPCookieProcessor(cj))

            html_s = ''
            # Resolve short link s.shopee.vn
            if 's.shopee.vn' in url or (re.search(r'shopee\.vn/[A-Za-z0-9_-]{6,20}$', url) and not re.search(r'-i\.\d+\.\d+', url)):
                try:
                    req = _req.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
                    with shopee_opener.open(req, timeout=10) as resp:
                        resolved = resp.url
                        html_s = resp.read().decode('utf-8', errors='ignore')
                    if re.search(r'-i\.(\d+)\.(\d+)', resolved) or re.search(r'shopee\.vn/[^/?#]+/(\d+)/(\d+)', resolved):
                        url = resolved
                    else:
                        for pat in [
                            r'location\.href\s*=\s*["\']([^"\']+shopee[^"\']*i\.\d+\.\d+[^"\']*)["\']',
                            r'window\.location\s*=\s*["\']([^"\']+shopee[^"\']*i\.\d+\.\d+[^"\']*)["\']',
                            r'"(https://shopee\.vn/[^"]+i\.\d+\.\d+[^"]*)"',
                        ]:
                            m2 = re.search(pat, html_s)
                            if m2:
                                url = m2.group(1)
                                break
                except Exception:
                    pass

            # Thử parse og: tags từ HTML đã fetch (không cần gọi API)
            def _parse_shopee_html(html):
                if not html:
                    return None, None, []
                # og:title — thử cả 2 thứ tự attribute
                for pat in [
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']{3,300})["\']',
                    r'<meta[^>]+content=["\']([^"\']{3,300})["\'][^>]*property=["\']og:title["\']',
                ]:
                    mt = re.search(pat, html)
                    if mt:
                        name = re.sub(r'\s*[\|\-–]\s*(Shopee|Shop).*$', '', mt.group(1), flags=re.IGNORECASE).strip()
                        if name and len(name) > 3:
                            break
                else:
                    name = ''
                # og:description
                desc = ''
                for pat in [
                    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{5,})["\']',
                    r'<meta[^>]+content=["\']([^"\']{5,})["\'][^>]*property=["\']og:description["\']',
                ]:
                    md = re.search(pat, html)
                    if md:
                        desc = md.group(1).strip()
                        break
                # og:image
                imgs = []
                mi = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                if mi:
                    imgs = [{'id': 'sp-0', 'dataUrl': None, '_url': mi.group(1)}]
                return name or None, desc, imgs

            og_name, og_desc, og_imgs = _parse_shopee_html(html_s)
            if og_name:
                # Tải ảnh từ og:image URL nếu có
                images = []
                for ig in og_imgs:
                    try:
                        images.append({'id': ig['id'], 'dataUrl': _download_image_b64(ig['_url'], UA)})
                    except Exception:
                        pass
                return jsonify({'success': True, 'productName': og_name, 'productDescription': og_desc or '', 'images': images})

            # Fallback: gọi Shopee API (thường bị 403 từ cloud)
            item, err = _fetch_shopee_data(url, opener=shopee_opener)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            name = item.get('name', '')
            desc = item.get('description', '')
            image_hashes = item.get('images', [])[:4]
            images = []
            for i, h in enumerate(image_hashes):
                for img_url in [
                    f'https://down-vn.img.susercontent.com/file/{h}',
                    f'https://cf.shopee.vn/file/{h}',
                ]:
                    try:
                        images.append({'id': f'sp-{i}', 'dataUrl': _download_image_b64(img_url, UA)})
                        break
                    except Exception:
                        continue
            return jsonify({'success': True, 'productName': name, 'productDescription': desc, 'images': images})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Lỗi Shopee API: {str(e)}'}), 500

    # ── TikTok Shop ──────────────────────────────────────────────────────────
    if 'tiktok.com' in url or 'tiktokshop' in url:
        if IS_CLOUD:
            # Cloud: thử urllib trước, nếu thất bại thì thử headless Playwright (cho shop.tiktok.com)
            result, err2 = _fetch_tiktok_cloud(url)
            if result and result.get('productName'):
                return jsonify({'success': True, **result})
            # Fallback: headless Playwright cho shop.tiktok.com/pdp/
            _is_pdp = 'shop.tiktok.com' in url and '/pdp/' in url
            if _is_pdp:
                try:
                    result2, err3 = _fetch_with_playwright_headless(url)
                    if result2 and result2.get('productName'):
                        return jsonify({'success': True, **result2})
                except Exception:
                    pass
            return jsonify({'success': False,
                            'error': err2 or 'Không lấy được thông tin. Vui lòng nhập tên và mô tả thủ công.'})
        else:
            # Local (exe): dùng Playwright persistent profile với session
            chrome_cookies = _get_chrome_cookies('tiktok.com')
            try:
                result, err = _fetch_with_playwright(url, injected_cookies=chrome_cookies, cookie_domain='.tiktok.com')
                if result and result.get('productName'):
                    return jsonify({'success': True, **result})
                return jsonify({'success': False, 'needsAuth': True,
                                'error': err or 'Không lấy được thông tin. Thử lại — nếu cần đăng nhập thì hoàn tất trong cửa sổ vừa mở.'})
            except Exception as e:
                return jsonify({'success': False, 'needsAuth': True,
                                'error': f'Lỗi mở trình duyệt: {e}. Thử lại lần nữa.'})

    # ── Trang khác: parse HTML meta tags ────────────────────────────────────
    try:
        req = _req.Request(url, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Referer': 'https://www.google.com/',
        })
        with _req.urlopen(req, timeout=15) as resp:
            status = resp.status
            if status in (401, 403):
                needs_auth_msg = 'Trang yêu cầu đăng nhập. Hãy mở trong trình duyệt, đăng nhập, rồi nhập thông tin thủ công.' if IS_CLOUD else 'Trang yêu cầu đăng nhập. Hãy mở trong trình duyệt, đăng nhập, rồi chụp màn hình sản phẩm.'
                return jsonify({'success': False, 'needsAuth': not IS_CLOUD, 'error': needs_auth_msg})
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        msg = str(e)
        needs = '403' in msg or 'forbidden' in msg.lower() or '401' in msg
        if IS_CLOUD:
            return jsonify({'success': False,
                            'error': 'Trang chặn truy cập tự động. Vui lòng nhập thông tin sản phẩm thủ công.' if needs else f'Không thể tải trang: {msg}'})
        return jsonify({'success': False, 'needsAuth': needs,
                        'error': 'Trang chặn truy cập tự động. Hãy mở trong trình duyệt và dùng tính năng chụp màn hình.' if needs else f'Không thể tải trang: {msg}'})

    class _MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.d = {}; self._in_title = False; self._title = ''
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == 'title': self._in_title = True
            elif tag == 'meta':
                prop = a.get('property') or a.get('name') or ''
                c = a.get('content', '')
                if prop in ('og:title','og:description','og:image','twitter:title','twitter:description','description'):
                    self.d[prop] = c
        def handle_data(self, d):
            if self._in_title: self._title += d
        def handle_endtag(self, tag):
            if tag == 'title': self._in_title = False; self.d.setdefault('title', self._title.strip())

    p = _MetaParser(); p.feed(html[:200000])
    d = p.d
    name = (d.get('og:title') or d.get('twitter:title') or d.get('title') or '').strip()
    desc = (d.get('og:description') or d.get('twitter:description') or d.get('description') or '').strip()
    img_url = d.get('og:image', '')

    images = []
    if img_url:
        try:
            images.append({'id': 'url-img-0', 'dataUrl': _download_image_b64(img_url, UA)})
        except Exception:
            pass

    if not name and not desc:
        if IS_CLOUD:
            return jsonify({'success': False, 'error': 'Không đọc được nội dung trang. Vui lòng nhập thông tin sản phẩm thủ công.'})
        # Local: Fallback sang Playwright
        try:
            result, err = _fetch_with_playwright(url)
            if result and result.get('productName'):
                return jsonify({'success': True, **result})
        except Exception:
            pass
        return jsonify({'success': False, 'needsAuth': True,
                        'error': 'Không đọc được nội dung trang. Trình duyệt sẽ mở để bạn có thể đăng nhập nếu cần.'})

    return jsonify({'success': True, 'productName': name, 'productDescription': desc, 'images': images})


@app.route('/api/save-file', methods=['POST'])
def save_file():
    """Mở native Windows save dialog để lưu file — dùng cho export trong pywebview EXE."""
    try:
        data = request.get_json() or {}
        content  = data.get('content', '')
        filename = data.get('filename', 'export.json')
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        file_path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            initialfile=filename,
            title='Lưu thư viện mẫu',
        )
        root.destroy()
        if not file_path:
            return jsonify({'success': False, 'cancelled': True})
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'path': file_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/regenerate-section', methods=['POST'])
def regenerate_section():
    try:
        data = request.get_json() or {}
        section      = data.get('section', '')
        product_name = data.get('productName', '').strip()
        product_desc = data.get('productDescription', '').strip()
        settings     = dict(data.get('settings', {}))
        input_data   = data.get('input', {})
        current_script = data.get('currentScript', {})
        selected_hook  = data.get('selectedHook', '').strip()
        reference_candidates = data.get('referenceLibraryCandidates', [])

        if not product_name:
            return jsonify({'success': False, 'error': 'Thiếu tên sản phẩm'}), 400

        provider = settings.get('provider', 'openai')
        api_key  = settings.get('apiKey', '')
        if not api_key and provider != 'custom':
            return jsonify({'success': False, 'error': 'Chưa nhập API key'}), 400

        # Section nhỏ không cần nhiều token
        settings['maxTokens'] = max(int(settings.get('maxTokens', 2000) or 2000), 2000)

        # Reference Library cho hooks và script — cùng flow như /api/generate
        _regen_referenced = []
        if reference_candidates and section in ('script', 'hooks'):
            from ai_providers import select_relevant_examples
            _ref_r = select_relevant_examples(
                settings, product_name, product_desc, input_data.get('industry', 'auto'), reference_candidates
            )
            input_data['referenceExamples'] = _ref_r['contents']
            _regen_referenced = _ref_r['used']

        # V9: Variation rule — trích hook hiện tại để tránh lặp khi regenerate
        _avoid_hooks = []
        if section in ('script', 'hooks'):
            _s3 = current_script.get('section3') or {}
            _avoid_hooks = [h.get('text', '') for h in (_s3.get('hooks') or []) if h.get('text', '').strip()]
            # Cũng tránh hook đang dùng trong section4
            _s4_hook = (current_script.get('section4') or {}).get('hook', '').strip()
            if _s4_hook and _s4_hook not in _avoid_hooks:
                _avoid_hooks.insert(0, _s4_hook)

        from prompt_builder import build_section_prompt, _try_parse_json
        system_prompt, user_prompt = build_section_prompt(
            section, product_name, product_desc, input_data, current_script, selected_hook,
            avoid_hooks=_avoid_hooks
        )

        from ai_providers import call_ai
        raw = call_ai(settings, system_prompt, user_prompt, [])

        # Parse JSON từ response
        import re as _re
        text = raw.strip()
        m = _re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            text = m.group(1).strip()
        else:
            s, e = text.find('{'), text.rfind('}')
            if s != -1 and e != -1:
                text = text[s:e+1]

        try:
            result = _try_parse_json(text)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'AI trả về định dạng không hợp lệ. Thử lại.',
                'rawResponse': raw[:2000]
            }), 422

        # Auto-repair format cho hooks (string→dict) và lines (string→dict)
        if 'section3' in result and isinstance(result.get('section3'), dict):
            hooks = result['section3'].get('hooks', [])
            if isinstance(hooks, list):
                result['section3']['hooks'] = [
                    h if (isinstance(h, dict) and 'text' in h)
                    else {'text': h, 'isRecommended': i == 0} if isinstance(h, str)
                    else None
                    for i, h in enumerate(hooks)
                ]
                result['section3']['hooks'] = [h for h in result['section3']['hooks'] if h]

        if 'section4' in result and isinstance(result.get('section4'), dict):
            lines_data = result['section4'].get('lines', [])
            if isinstance(lines_data, list):
                result['section4']['lines'] = [
                    ln if (isinstance(ln, dict) and 'type' in ln and 'text' in ln)
                    else {'type': 'dialogue', 'text': ln} if isinstance(ln, str)
                    else None
                    for ln in lines_data
                ]
                result['section4']['lines'] = [ln for ln in result['section4']['lines'] if ln]

        return jsonify({'success': True, 'data': result, 'referencedSamples': _regen_referenced})

    except Exception as e:
        msg = str(e)
        if 'api key' in msg.lower() or '401' in msg:
            msg = 'API key không hợp lệ'
        elif '404' in msg or 'model_not_found' in msg or 'not found' in msg.lower():
            msg = 'Model không tồn tại. Kiểm tra tên model trong Cài đặt'
        elif '429' in msg or 'rate limit' in msg.lower():
            msg = 'Rate limit. Thử lại sau vài giây'
        elif 'connection' in msg.lower() or 'timeout' in msg.lower():
            msg = 'Không thể kết nối API'
        return jsonify({'success': False, 'error': msg}), 500


@app.route('/api/scan-product', methods=['POST'])
def scan_product():
    try:
        data = request.get_json() or {}
        images = data.get('images') or ([data['image']] if data.get('image') else [])
        if not images:
            return jsonify({'success': False, 'error': 'Không nhận được ảnh'}), 400
        from ai_providers import scan_product_from_screenshot
        main_settings = data.get('settings', {})
        vision_provider = main_settings.get('visionProvider', 'gemini')
        if vision_provider == 'gemini':
            raw = main_settings.get('visionGeminiKeys', '') or (main_settings.get('apiKeys') or {}).get('gemini', '')
            gemini_keys = [k.strip() for k in raw.replace(',', '\n').split('\n') if k.strip()]
            result = scan_product_from_screenshot(gemini_keys, images, main_settings=main_settings)
        elif vision_provider == 'openai':
            vision_key = main_settings.get('visionOpenaiKey', '').strip()
            vision_base_url = (main_settings.get('visionOpenaiBaseUrl', '') or 'https://api.openai.com/v1').strip()
            vision_model = (main_settings.get('visionOpenaiModel', '') or 'gpt-4o-mini').strip()
            openai_vision_ms = {
                'provider': 'openai',
                'apiKey': vision_key,
                'baseUrl': vision_base_url,
                'modelName': vision_model,
                'apiKeys': {'openai': vision_key},
            } if vision_key else None
            result = scan_product_from_screenshot([], images, main_settings=openai_vision_ms or main_settings)
        else:
            result = scan_product_from_screenshot([], images, main_settings=main_settings)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/transcribe-url', methods=['POST'])
def transcribe_url():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        groq_key = data.get('groqApiKey', '').strip()
        language = data.get('language', 'vi')
        if not url:
            return jsonify({'success': False, 'error': 'Chưa nhập URL'}), 400
        if not groq_key:
            return jsonify({'success': False, 'error': 'Chưa nhập Groq API key. Vào Cài đặt → mục 3.'}), 400
        import yt_dlp, tempfile, os as _os
        MAX = 25 * 1024 * 1024
        with tempfile.TemporaryDirectory() as tmp:
            ydl_opts = {
                'format': 'bestaudio[filesize<25M]/bestaudio/best[filesize<25M]/best',
                'outtmpl': _os.path.join(tmp, '%(id)s.%(ext)s'),
                'quiet': True, 'no_warnings': True,
                'noplaylist': True, 'max_filesize': MAX,
                'socket_timeout': 30,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except yt_dlp.utils.DownloadError as e:
                msg = str(e)
                if any(k in msg.lower() for k in ('private', 'login', 'cookie', 'sign in')):
                    return jsonify({'success': False, 'error': 'Video riêng tư hoặc yêu cầu đăng nhập — thử video public khác'}), 400
                if 'unsupported url' in msg.lower():
                    return jsonify({'success': False, 'error': 'URL không được hỗ trợ. Dùng link TikTok hoặc YouTube.'}), 400
                return jsonify({'success': False, 'error': f'Không thể tải: {msg[:200]}'}), 400
            files = [_os.path.join(tmp, f) for f in _os.listdir(tmp) if _os.path.isfile(_os.path.join(tmp, f))]
            if not files:
                return jsonify({'success': False, 'error': 'Không tìm thấy file sau khi tải. Thử URL khác.'}), 400
            filepath = files[0]
            sz = _os.path.getsize(filepath)
            if sz > MAX:
                return jsonify({'success': False, 'error': f'File quá lớn ({sz//1024//1024}MB). Groq giới hạn 25MB — thử video ngắn hơn.'}), 400
            fname = _os.path.basename(filepath)
            with open(filepath, 'rb') as f:
                file_bytes = f.read()
        from ai_providers import transcribe_with_groq
        text = transcribe_with_groq(groq_key, file_bytes, fname, language)
        return jsonify({'success': True, 'transcript': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detect-industry', methods=['POST'])
def detect_industry():
    try:
        data = request.get_json() or {}
        text = (data.get('text') or '').strip()
        groq_key = (data.get('groqApiKey') or '').strip()
        if not text or not groq_key:
            return jsonify({'success': True, 'industry': 'auto'})
        from ai_providers import detect_industry_with_groq
        industry = detect_industry_with_groq(groq_key, text)
        return jsonify({'success': True, 'industry': industry})
    except Exception:
        return jsonify({'success': True, 'industry': 'auto'})


@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        f = request.files.get('file')
        if not f:
            return jsonify({'success': False, 'error': 'Không có file được gửi lên'}), 400
        groq_key = request.form.get('groqApiKey', '').strip()
        if not groq_key:
            return jsonify({'success': False, 'error': 'Chưa nhập Groq API key. Vào Cài đặt → Transcript để nhập.'}), 400
        language = request.form.get('language', 'vi')
        file_bytes = f.read()
        max_size = 25 * 1024 * 1024  # 25MB
        if len(file_bytes) > max_size:
            mb = len(file_bytes) // 1024 // 1024
            return jsonify({'success': False, 'error': f'File quá lớn ({mb}MB). Groq giới hạn 25MB — hãy nén video hoặc cắt ngắn trước.'}), 400
        from ai_providers import transcribe_with_groq
        text = transcribe_with_groq(groq_key, file_bytes, f.filename or 'audio.mp4', language)
        return jsonify({'success': True, 'transcript': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-visual-prompt', methods=['POST'])
def generate_visual_prompt():
    try:
        data = request.get_json() or {}
        script = data.get('script', {})
        product_name = data.get('productName', '').strip()
        product_desc = data.get('productDescription', '').strip()
        image_analysis = data.get('imageAnalysis', '')
        input_data = data.get('input', {})
        visual_settings = data.get('visualSettings', {})
        settings = dict(data.get('settings', {}))

        if not product_name:
            return jsonify({'success': False, 'error': 'Thiếu tên sản phẩm'}), 400
        if not script:
            return jsonify({'success': False, 'error': 'Chưa có kịch bản. Tạo kịch bản trước.'}), 400

        provider = settings.get('provider', 'openai')
        api_key = settings.get('apiKey', '')
        if not api_key and provider != 'custom':
            return jsonify({'success': False, 'error': 'Chưa nhập API key'}), 400

        settings['maxTokens'] = 0

        from prompt_builder import build_visual_prompt, assemble_visual_section10
        from ai_providers import call_ai

        system_prompt, user_prompt = build_visual_prompt(
            script, product_name, product_desc, image_analysis, input_data, visual_settings
        )

        raw = call_ai(settings, system_prompt, user_prompt, [])

        import re as _re
        text = raw.strip()
        m = _re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            text = m.group(1).strip()
        else:
            s, e = text.find('{'), text.rfind('}')
            if s != -1 and e != -1:
                text = text[s:e+1]

        try:
            import json as _json
            ai_draft = _json.loads(text)
        except Exception:
            return jsonify({
                'success': False,
                'error': 'AI trả về định dạng không hợp lệ. Thử lại.',
                'rawResponse': raw[:2000]
            }), 422

        # AI có thể trả wrap dưới key 'section10' hoặc 'draft' — bóc ra nếu có
        if isinstance(ai_draft, dict):
            if 'section10' in ai_draft and isinstance(ai_draft['section10'], dict):
                ai_draft = ai_draft['section10']
            elif 'draft' in ai_draft and isinstance(ai_draft['draft'], dict):
                ai_draft = ai_draft['draft']

        # Lắp ráp section10 đầy đủ: Python tự gắn PRODUCT LOCK / negative prompt cố định,
        # AI draft chỉ cung cấp phần bối cảnh/camera/chuyển động (xem prompt_builder.py)
        section10 = assemble_visual_section10(ai_draft, product_name, input_data, visual_settings, script)

        return jsonify({'success': True, 'section10': section10})

    except Exception as e:
        msg = str(e)
        if 'api key' in msg.lower() or '401' in msg:
            msg = 'API key không hợp lệ hoặc đã hết hạn'
        elif '429' in msg or 'rate limit' in msg.lower():
            msg = 'Rate limit. Thử lại sau vài giây'
        elif 'connection' in msg.lower() or 'timeout' in msg.lower():
            msg = 'Không thể kết nối API'
        return jsonify({'success': False, 'error': msg}), 500


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    try:
        data = request.get_json() or {}
        settings = data.get('settings', {})
        from ai_providers import test_ai_connection
        result = test_ai_connection(settings)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/icon-<int:size>.png')
def app_icon(size):
    icon_path = os.path.join(BASE_DIR, 'bella_icon_512.png')
    if os.path.exists(icon_path):
        from PIL import Image
        import io
        target = min(max(size, 16), 512)
        with Image.open(icon_path) as im:
            im = im.resize((target, target), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format='PNG')
            buf.seek(0)
        return Response(buf.read(), mimetype='image/png',
                        headers={'Cache-Control': 'public, max-age=86400'})
    # Fallback: solid purple square
    def _chunk(t, d):
        crc = zlib.crc32(t + d) & 0xffffffff
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', crc)
    s = min(max(size, 16), 512)
    raw = b''.join(b'\x00' + bytes([147, 51, 234] * s) for _ in range(s))
    data = (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', s, s, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 9))
            + _chunk(b'IEND', b''))
    return Response(data, mimetype='image/png',
                    headers={'Cache-Control': 'public, max-age=86400'})

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "BELLA AI Script Generator",
        "short_name": "BELLA AI",
        "description": "Tạo kịch bản TikTok Shop AI cho mọi ngành hàng",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f9fafb",
        "theme_color": "#9333ea",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ]
    })

@app.route('/api/debug-urllib')
def debug_urllib():
    if IS_CLOUD:
        return jsonify({'error': 'Not available in production'}), 404
    import urllib.request as _req, re, json as _json, traceback
    from urllib.parse import urlparse, parse_qs
    test_url = request.args.get('url', 'https://vt.tiktok.com/ZS96rCQF3pPxt-uEtA5/')
    result = {'url': test_url}
    try:
        UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        req = _req.Request(test_url, headers={'User-Agent': UA, 'Accept': 'text/html', 'Accept-Language': 'vi-VN,vi;q=0.9'})
        with _req.urlopen(req, timeout=20) as resp:
            final_url = resp.url
            html = resp.read().decode('utf-8', errors='ignore')
        result['final_url'] = final_url[:200]
        result['html_len'] = len(html)
        # og_info
        qs = parse_qs(urlparse(final_url).query)
        og_raw = qs.get('og_info', [''])[0]
        if og_raw:
            try: result['og_info'] = _json.loads(og_raw)
            except: result['og_info_raw'] = og_raw[:300]
        # __NEXT_DATA__
        nd = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if nd:
            nd_text = nd.group(1)
            result['next_data_len'] = len(nd_text)
            try:
                nd_json = _json.loads(nd_text)
                # Tìm keys liên quan đến product
                def find_keys(obj, depth=0, path=''):
                    if depth > 5: return []
                    found = []
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if any(x in k.lower() for x in ('desc','detail','product','item','name','title')):
                                val_str = str(v)[:200] if not isinstance(v, (dict,list)) else f'[{type(v).__name__}]'
                                found.append(f'{path}.{k}={val_str}')
                            found += find_keys(v, depth+1, f'{path}.{k}')
                    elif isinstance(obj, list) and obj:
                        found += find_keys(obj[0], depth+1, f'{path}[0]')
                    return found[:20]
                result['next_data_keys'] = find_keys(nd_json)
            except Exception as e:
                result['next_data_parse_err'] = str(e)
        else:
            result['next_data'] = 'NOT FOUND'
            # og:title và og:description
            og_t = re.search(r'og:title[^>]+content=["\']([^"\']{5,300})["\']', html)
            og_d = re.search(r'og:description[^>]+content=["\']([^"\']{5,500})["\']', html)
            result['og_title'] = og_t.group(1) if og_t else None
            result['og_desc'] = og_d.group(1)[:300] if og_d else None
            result['html_sample'] = html[:500]
    except Exception as e:
        result['error'] = traceback.format_exc()[-800:]
    return jsonify(result)


@app.route('/api/debug-shopee')
def debug_shopee():
    if IS_CLOUD:
        return jsonify({'error': 'Not available in production'}), 404
    import urllib.request as _req, re, traceback
    test_url = request.args.get('url', 'https://s.shopee.vn/8KnQUMkqDK')
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    result = {'input_url': test_url}
    try:
        req = _req.Request(test_url, headers={'User-Agent': UA, 'Accept': 'text/html'})
        with _req.urlopen(req, timeout=15) as resp:
            result['final_url'] = resp.url
            result['status'] = resp.status
            html = resp.read().decode('utf-8', errors='ignore')
        result['html_len'] = len(html)
        result['html_sample'] = html[:1000]
        result['has_item_id'] = bool(re.search(r'-i\.(\d+)\.(\d+)', resp.url))
        # Tìm URL thật trong JS/meta
        for pat in [r'location\.href\s*=\s*["\']([^"\']+shopee[^"\']+)["\']',
                    r'window\.location\s*=\s*["\']([^"\']+shopee[^"\']+)["\']',
                    r'content=["\']0;\s*url=([^"\']+shopee[^"\']+)["\']',
                    r'href=["\']([^"\']+shopee\.vn/[^"\']+i\.\d+\.\d+[^"\']*)["\']']:
            m = re.search(pat, html)
            if m:
                result['js_redirect_url'] = m.group(1)
                result['js_has_item_id'] = bool(re.search(r'-i\.(\d+)\.(\d+)', m.group(1)))
                break
    except Exception as e:
        result['error'] = traceback.format_exc()[-600:]
    return jsonify(result)


def run_flask():
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    if IS_CLOUD:
        port = int(os.environ.get('PORT', 5001))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()
        import time
        time.sleep(1.5)
        import webview
        webview.create_window(
            title='BELLA AI Script Generator',
            url='http://localhost:5001',
            width=1200, height=800,
            min_size=(800, 600),
            resizable=True,
        )
        icon_path = os.path.join(EXE_DIR, 'bella_icon.ico') if getattr(sys, 'frozen', False) else os.path.join(BASE_DIR, 'bella_icon.ico')
        _webview_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'BELLA AI', 'webview_data')
        os.makedirs(_webview_data, exist_ok=True)
        webview.start(gui='edgechromium', icon=icon_path if os.path.exists(icon_path) else None, storage_path=_webview_data, private_mode=False)
