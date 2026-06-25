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
        data = request.get_json()
        product_name = data.get('productName', '').strip()
        product_desc = data.get('productDescription', '').strip()
        images = data.get('images', [])
        settings = data.get('settings', {})
        prompt_settings = data.get('promptSettings', {})
        input_data = data.get('input', {})

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
        from ai_providers import call_ai, analyze_images_with_gemini

        system_prompt = build_system_prompt(prompt_settings)
        has_images = len(images) > 0

        # Phân tích ảnh: luôn dùng Gemini (rẻ), không bao giờ gửi ảnh thô cho OpenAI/DeepSeek
        image_analysis = ''
        images_to_send = []
        if has_images:
            if provider == 'gemini':
                # Provider chính là Gemini → gửi ảnh trực tiếp, không cần phân tích trước
                images_to_send = images
            else:
                # Dùng Gemini key riêng để phân tích ảnh, kết quả nhúng vào prompt text
                gemini_key = (settings.get('apiKeys') or {}).get('gemini', '')
                if gemini_key:
                    image_analysis = analyze_images_with_gemini(gemini_key, images)
                # Không gửi ảnh cho OpenAI/DeepSeek dù có hay không có phân tích

        user_prompt = build_user_prompt(input_data, has_images, image_analysis)
        raw_response = call_ai(settings, system_prompt, user_prompt, images_to_send)

        try:
            script = parse_ai_response(raw_response)
            return jsonify({'success': True, 'script': script, 'rawResponse': raw_response})
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


BROWSER_PROFILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'BELLA_AI', 'browser')

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

_READ_DOM_JS = """() => {
    const m = (s) => document.querySelector(s)?.content || '';
    const title = document.querySelector('h1')?.innerText?.trim()
        || m('meta[property="og:title"]') || m('meta[name="twitter:title"]')
        || document.title || '';
    let descEl = null;
    for (const el of document.querySelectorAll('div')) {
        const cls = el.className || '';
        if (cls.includes('grid-cols-2') && cls.includes('overflow-visible') && cls.includes('px-20')) {
            descEl = el; break;
        }
    }
    let desc = descEl?.innerText?.trim() || '';
    if (!desc) {
        const candidates = Array.from(document.querySelectorAll('p, li, [class*="desc"], [class*="detail"]'))
            .map(el => el.innerText?.trim() || '')
            .filter(t => t.length > 80 && t.length < 8000)
            .filter(t => !t.includes('TikTok Shop') || t.length > 300)
            .sort((a, b) => b.length - a.length);
        desc = candidates[0] || m('meta[property="og:description"]') || '';
    }
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

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=_PLAYWRIGHT_PROFILE,
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-first-run'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='vi-VN',
            viewport={'width': 1280, 'height': 800},
        )

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

            # Scroll để trigger lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
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


def _fetch_shopee_data(url):
    import re, urllib.request as _req, json as _json
    m = re.search(r'-i\.(\d+)\.(\d+)', url)
    if not m:
        return None, 'Không nhận dạng được URL Shopee. Hãy dùng link trực tiếp đến sản phẩm.'
    shopid, itemid = m.group(1), m.group(2)
    api = f'https://shopee.vn/api/v4/item/get?itemid={itemid}&shopid={shopid}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://shopee.vn/',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
    }
    r = _req.Request(api, headers=headers)
    with _req.urlopen(r, timeout=15) as resp:
        data = _json.loads(resp.read())
    item = (data.get('data') or data.get('item') or {})
    if not item:
        return None, 'Không lấy được dữ liệu. Sản phẩm có thể đã bị ẩn hoặc xóa.'
    return item, None


def _fetch_tiktok_cloud(url):
    """Lấy thông tin sản phẩm TikTok Shop trên cloud (không dùng Playwright).
    Follow redirect từ vt.tiktok.com rồi extract từ __NEXT_DATA__ / JSON-LD / meta tags + CDN scan.
    """
    import urllib.request as _req
    import json as _json
    import re
    from html.parser import HTMLParser

    UA_DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    headers = {
        'User-Agent': UA_DESKTOP,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com/',
    }

    try:
        req = _req.Request(url, headers=headers)
        with _req.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None, f'Không thể tải trang: {str(e)}'

    def _cdn_scan(html_text, existing_count=0):
        """Scan HTML source tìm ảnh TikTok/ByteDance CDN (kể cả trong JSON strings)."""
        cdn_re = re.compile(
            r'https://[a-z0-9\-]+\.(?:ibyteimg|tiktokcdn|ibytedtos|tiktokstaticb)\.com'
            r'/[^\s"\'<>\]\\]+\.(?:jpeg|jpg|png|webp)(?:[?~][^\s"\'<>\]]*)?'
        )
        SKIP = ('avatar', 'logo', 'icon', '100x100', '50x50', '30x30', 'header', 'banner/bg')
        seen, result = set(), []
        for u in cdn_re.findall(html_text):
            u = u.replace('\\u002F', '/').replace('%2F', '/')
            if u not in seen and not any(x in u.lower() for x in SKIP):
                seen.add(u)
                result.append(u)
        images = []
        for i, img_url in enumerate(result[:max(0, 4 - existing_count)]):
            try:
                images.append({'id': f'tt-cdn-{i}', 'dataUrl': _download_image_b64(img_url, UA_DESKTOP)})
            except Exception:
                pass
        return images

    def _download_img_list(img_list, prefix='tt'):
        images = []
        for i, img in enumerate(img_list[:4]):
            img_url = img if isinstance(img, str) else img.get('url', img.get('src', img.get('urlList', [''])[0] if isinstance(img.get('urlList'), list) else ''))
            if img_url and img_url.startswith('http'):
                try:
                    images.append({'id': f'{prefix}-{i}', 'dataUrl': _download_image_b64(img_url, UA_DESKTOP)})
                except Exception:
                    pass
        return images

    # ── 1. __NEXT_DATA__ JSON (TikTok Shop là Next.js app) ───────────────────
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            nd = _json.loads(m.group(1))
            props = nd.get('props', {}).get('pageProps', {})
            product = (
                props.get('product') or
                props.get('item') or
                props.get('productInfo') or
                props.get('itemInfo', {}).get('item') or
                props.get('data', {}).get('product') or
                props.get('initialData', {}).get('product') or
                {}
            )
            name = (product.get('title') or product.get('name') or
                    product.get('itemName') or '').strip()
            desc = (product.get('description') or product.get('content') or
                    product.get('itemDescription') or '').strip()
            if name and len(name) > 3:
                img_list = (product.get('images') or product.get('imageUrls') or
                            product.get('imgUrlList') or [])
                images = _download_img_list(img_list, 'tt-nd')
                if len(images) < 2:
                    images += _cdn_scan(html, len(images))
                return {'productName': name, 'productDescription': desc, 'images': images}, None
        except Exception:
            pass

    # ── 2. JSON-LD structured data ───────────────────────────────────────────
    for ld_text in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            ld = _json.loads(ld_text)
            if isinstance(ld, list):
                ld = ld[0] if ld else {}
            if ld.get('@type') in ('Product', 'ItemPage', 'Offer'):
                name = ld.get('name', '').strip()
                desc = ld.get('description', '').strip()
                if name and len(name) > 3:
                    # Lấy tất cả ảnh từ JSON-LD image array
                    raw_imgs = ld.get('image', [])
                    if isinstance(raw_imgs, str):
                        raw_imgs = [raw_imgs]
                    images = _download_img_list(raw_imgs, 'tt-ld')
                    if len(images) < 2:
                        images += _cdn_scan(html, len(images))
                    return {'productName': name, 'productDescription': desc, 'images': images}, None
        except Exception:
            pass

    # ── 3. og:title / og:description + thu thập TẤT CẢ og:image ─────────────
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
                    self.og_images.append(c)   # thu thập list, không override
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
    desc = (d.get('og:description') or d.get('twitter:description') or d.get('description') or '').strip()

    skip_titles = ('tiktok', 'shop', 'trang chủ', 'home', 'make your day')
    if name and not any(t in name.lower() for t in skip_titles) and len(name) > 3:
        # Tải tất cả og:image thu thập được
        images = _download_img_list(p.og_images, 'tt-og')
        # Bổ sung bằng CDN scan nếu chưa đủ 3 ảnh
        if len(images) < 3:
            images += _cdn_scan(html, len(images))
        return {'productName': name, 'productDescription': desc, 'images': images}, None

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
    url = request.get_json().get('url', '')
    if url.startswith('http'):
        import webbrowser
        webbrowser.open(url)
    return jsonify({'success': True})

@app.route('/api/fetch-url', methods=['POST'])
def fetch_url():
    import re, urllib.request as _req
    from html.parser import HTMLParser

    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'Chưa nhập URL'}), 400
    if not url.startswith('http'):
        url = 'https://' + url

    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

    # ── Shopee: gọi API nội bộ (hoạt động cả trên cloud) ─────────────────────
    if 'shopee.vn' in url:
        try:
            item, err = _fetch_shopee_data(url)
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
            # Cloud: dùng urllib + extract JSON/meta (không có Playwright)
            result, err = _fetch_tiktok_cloud(url)
            if result and result.get('productName'):
                return jsonify({'success': True, **result})
            return jsonify({'success': False,
                            'error': err or 'Không lấy được thông tin từ link này. Link TikTok Shop cần đăng nhập — vui lòng nhập tên và mô tả sản phẩm thủ công.'})
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


@app.route('/api/regenerate-section', methods=['POST'])
def regenerate_section():
    try:
        data = request.get_json()
        section      = data.get('section', '')
        product_name = data.get('productName', '').strip()
        product_desc = data.get('productDescription', '').strip()
        settings     = dict(data.get('settings', {}))
        input_data   = data.get('input', {})
        current_script = data.get('currentScript', {})

        if not product_name:
            return jsonify({'success': False, 'error': 'Thiếu tên sản phẩm'}), 400

        provider = settings.get('provider', 'openai')
        api_key  = settings.get('apiKey', '')
        if not api_key and provider != 'custom':
            return jsonify({'success': False, 'error': 'Chưa nhập API key'}), 400

        # Section nhỏ không cần nhiều token
        settings['maxTokens'] = max(int(settings.get('maxTokens', 2000)), 2000)

        from prompt_builder import build_section_prompt, _try_parse_json
        system_prompt, user_prompt = build_section_prompt(
            section, product_name, product_desc, input_data, current_script
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

        result = _try_parse_json(text)
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        msg = str(e)
        if 'api key' in msg.lower() or '401' in msg:
            msg = 'API key không hợp lệ'
        elif '429' in msg or 'rate limit' in msg.lower():
            msg = 'Rate limit. Thử lại sau vài giây'
        elif 'connection' in msg.lower() or 'timeout' in msg.lower():
            msg = 'Không thể kết nối API'
        return jsonify({'success': False, 'error': msg}), 500


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    try:
        data = request.get_json()
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
        "description": "Tạo kịch bản TikTok Shop OneShot cho BELLA",
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

def run_flask():
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)


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
        webview.start(icon=icon_path if os.path.exists(icon_path) else None)
