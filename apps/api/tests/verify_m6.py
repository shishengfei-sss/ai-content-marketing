"""M6 验收：Web/H5 用户端 API 与页面文件。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / 'web' / 'src'
MP_ROOT = API_ROOT.parent / 'mp' / 'src'
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, clear_sms_rate_limits, reset_test_client

WEB_FILES = [
    'views/SelectTenant.vue',
    'views/ForgotPassword.vue',
    'views/SettingsTenant.vue',
    'views/SettingsTeam.vue',
    'config/permissions.js',
]

MP_FILES = [
    'pages/select-tenant/select-tenant.vue',
    'pages/forgot/forgot.vue',
    'pages/settings/tenant.vue',
    'pages/settings/team.vue',
    'pages/settings/preference.vue',
    'utils/session.js',
]


def login(phone, password):
    code, data = req('POST', '/auth/login', body={'phone': phone, 'password': password})
    assert code == 200, data
    return data['access_token']


def main():
    results = []
    reset_test_client()
    clear_sms_rate_limits()
    m6_phone = f"139{uuid.uuid4().int % 10**8:08d}"

    for f in WEB_FILES:
        results.append(check(f'Web 文件 {f}', (WEB_ROOT / f).is_file()))

    for f in MP_FILES:
        results.append(check(f'H5 文件 {f}', (MP_ROOT / f).is_file()))

    admin_token = login('13900000099', 'test123456')
    code, me = req('GET', '/auth/me', token=admin_token)
    results.append(check('V6 /me permissions', code == 200 and len(me.get('permissions', [])) >= 6))

    code, prof = req('GET', '/tenant/profile', token=admin_token)
    results.append(check('V6 tenant.profile', code == 200))

    code, members = req('GET', '/team/members', token=admin_token)
    results.append(check('V6 team.members', code == 200))

    multi_token = login('13900008888', 'Test123456')
    code, me_m = req('GET', '/auth/me', token=multi_token)
    results.append(check('V6 多公司 tenants', code == 200 and len(me_m.get('tenants', [])) >= 2))

    clear_sms_rate_limits()
    reg_code, reg = req(
        'POST',
        '/auth/register',
        body={
            'phone': m6_phone,
            'password': 'Test123456',
            'tenant_name': f'M6测试公司-{m6_phone[-4:]}',
            'industry_code': 'finance',
            'display_name': 'M6',
        },
    )
    results.append(check('V6 register forgot-user', reg_code == 200, f'{reg_code} {reg}'))
    clear_sms_rate_limits()
    code, send = req('POST', '/auth/password/forgot/send-code', body={'phone': m6_phone})
    results.append(check('V6 forgot send-code', code == 200, f'{code} {send}'))

    editor_token = login('13900008888', 'Test123456')
    code, me_e = req('GET', '/auth/me', token=editor_token)
    if me_e.get('need_select_tenant'):
        tenant_b = me_e['tenants'][1]['id']
        code, sel = req('POST', '/auth/select-tenant', token=editor_token, body={'tenant_id': tenant_b})
        editor_token = sel['access_token']
    code, _ = req('PATCH', '/tenant/profile', token=editor_token, body={'name': 'x'})
    results.append(check('V6 editor 无 tenant.manage', code == 403))

    passed = all(results)
    print('\n=== M6', '全部通过' if passed else '存在失败', '===')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
