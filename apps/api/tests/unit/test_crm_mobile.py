from app.schemas.crm import coerce_mobile_raw, validate_lead_mobile_value


def test_coerce_excel_mobile_formats():
    assert coerce_mobile_raw(13434000000.0) == "13434000000"
    assert coerce_mobile_raw("13434000000.0") == "13434000000"
    assert coerce_mobile_raw("1.3434E+10") == "13434000000"
    assert coerce_mobile_raw("+8613434000000") == "13434000000"


def test_validate_lead_mobile_import_values():
    mobile, err = validate_lead_mobile_value("13434000000.0")
    assert err is None
    assert mobile == "13434000000"

    mobile, err = validate_lead_mobile_value(13434000000.0)
    assert err is None
    assert mobile == "13434000000"
