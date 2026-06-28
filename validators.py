"""V9: Schema validator cho AI response — kiểm tra và auto-repair kịch bản."""

REQUIRED_SECTIONS = ['section1', 'section2', 'section3', 'section4', 'section5', 'section7', 'section8', 'section9']

SECTION_DEFAULTS = {
    'section1': {'productName': '', 'targetAudience': '', 'shootingStyle': '', 'duration': '',
                 'tone': '', 'videoGoal': '', 'subjectMode': '', 'subjectModeResolved': '', 'productionMode': ''},
    'section2': {'targetCustomer': '', 'painPoints': '', 'insight': '', 'highlights': '',
                 'mainBenefits': '', 'usageSituations': '', 'heroBenefit': ''},
    'section3': {'hooks': []},
    'section4': {'duration': '', 'hook': '', 'lines': [], 'rawScript': '', 'voScript': ''},
    'section5': {'timeline': []},
    'section7': {'captions': []},
    'section8': {'hashtags': []},
    'section9': {'tips': []},
}

# Trường bắt buộc phải có giá trị (không được rỗng)
REQUIRED_FIELDS = {
    'section3': {'hooks': list},  # phải là list không rỗng
    'section4': {'lines': list, 'hook': str},
    'section7': {'captions': list},
    'section8': {'hashtags': list},
}


def validate_script_schema(parsed: dict) -> tuple[dict, list[str]]:
    """Kiểm tra và auto-repair schema AI response.

    Returns:
        (repaired_dict, issues) — issues là list mô tả vấn đề đã phát hiện.
        Nếu issues rỗng → schema hợp lệ hoàn toàn.
    """
    if not isinstance(parsed, dict):
        return {}, ['Response không phải dict']

    issues = []
    result = dict(parsed)

    # 1. Auto-repair sections bị thiếu
    for sec in REQUIRED_SECTIONS:
        if sec not in result:
            result[sec] = dict(SECTION_DEFAULTS[sec])
            issues.append(f'Thiếu {sec} — đã thêm default')
        elif not isinstance(result[sec], dict):
            result[sec] = dict(SECTION_DEFAULTS[sec])
            issues.append(f'{sec} không phải dict — đã reset về default')

    # 2. Merge fields còn thiếu trong từng section
    for sec, defaults in SECTION_DEFAULTS.items():
        if sec in result and isinstance(result[sec], dict):
            for field, default_val in defaults.items():
                if field not in result[sec]:
                    result[sec][field] = default_val
                    issues.append(f'{sec}.{field} bị thiếu — đã thêm default')

    # 3. Kiểm tra fields bắt buộc có nội dung
    for sec, fields in REQUIRED_FIELDS.items():
        for field, expected_type in fields.items():
            val = result.get(sec, {}).get(field)
            if expected_type is list and not isinstance(val, list):
                result[sec][field] = []
                issues.append(f'{sec}.{field} phải là list — đã reset')
            elif expected_type is list and len(val) == 0:
                issues.append(f'{sec}.{field} là list rỗng — AI không tạo nội dung')
            elif expected_type is str and not isinstance(val, str):
                result[sec][field] = str(val) if val is not None else ''
                issues.append(f'{sec}.{field} phải là string — đã convert')

    # 4. Kiểm tra section3.hooks có đúng format không
    hooks = result.get('section3', {}).get('hooks', [])
    if isinstance(hooks, list):
        repaired_hooks = []
        for i, h in enumerate(hooks):
            if isinstance(h, dict) and 'text' in h:
                repaired_hooks.append(h)
            elif isinstance(h, str):
                repaired_hooks.append({'text': h, 'isRecommended': i == 0})
                issues.append(f'section3.hooks[{i}] là string — đã wrap thành dict')
            else:
                issues.append(f'section3.hooks[{i}] format không hợp lệ — đã bỏ qua')
        result['section3']['hooks'] = repaired_hooks

    # 5. Kiểm tra section4.lines có đúng format không
    lines_data = result.get('section4', {}).get('lines', [])
    if isinstance(lines_data, list):
        repaired_lines = []
        for i, ln in enumerate(lines_data):
            if isinstance(ln, dict) and 'type' in ln and 'text' in ln:
                repaired_lines.append(ln)
            elif isinstance(ln, str):
                repaired_lines.append({'type': 'dialogue', 'text': ln})
                issues.append(f'section4.lines[{i}] là string — đã wrap thành dict')
            else:
                issues.append(f'section4.lines[{i}] format không hợp lệ — đã bỏ qua')
        result['section4']['lines'] = repaired_lines

    return result, issues


def is_major_issue(issues: list[str]) -> bool:
    """Trả về True nếu có vấn đề nghiêm trọng cần AI repair (không chỉ auto-repair được)."""
    critical = [i for i in issues if 'list rỗng' in i or 'không tạo nội dung' in i]
    return len(critical) >= 2
