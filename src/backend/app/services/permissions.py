"""Permissions discovery (اكتشاف الصلاحيات) — show a logged-in user exactly
what they can and can't do.

eStock hides features behind the EMP_CONTROL permission matrix, so staff often
don't know a capability exists. This surfaces, for the current user:

  * the per-employee permission flags (eStock EMP_CONTROL parity) as ON/OFF with
    plain bilingual descriptions,
  * the numeric limits (max discount %),
  * and what their ProCare login role unlocks (which screens/actions), derived
    from the same role gates the API enforces.

Read-only — it never changes a permission, only explains the current state.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import models as m

# Boolean permission flags on the employee row (EMP_CONTROL parity). Order is
# the display order; each carries a bilingual label + a one-line explanation.
PERMISSION_FLAGS = [
    {"code": "can_see_buy_price", "ar": "رؤية سعر الشراء", "en": "See buy price",
     "desc_ar": "الاطلاع على تكلفة الأصناف وأرباح الفاتورة", "desc_en": "View item cost and invoice profit"},
    {"code": "can_edit_sell_price", "ar": "تعديل سعر البيع", "en": "Edit sell price",
     "desc_ar": "تغيير سعر بيع الصنف أثناء الفاتورة", "desc_en": "Change an item's sell price during a sale"},
    {"code": "can_sale_credit", "ar": "البيع الآجل", "en": "Credit sales",
     "desc_ar": "البيع على حساب العميل (آجل)", "desc_en": "Sell on the customer's account (on credit)"},
    {"code": "can_return", "ar": "عمل مرتجعات", "en": "Process returns",
     "desc_ar": "إنشاء فواتير مرتجع", "desc_en": "Create return invoices"},
    {"code": "can_void", "ar": "إلغاء الفواتير", "en": "Void invoices",
     "desc_ar": "إلغاء أو حذف فاتورة", "desc_en": "Cancel or void an invoice"},
    {"code": "can_change_shift", "ar": "إدارة الوردية", "en": "Manage shift",
     "desc_ar": "فتح وتقفيل درج الكاشير", "desc_en": "Open and close the cash-desk shift"},
]

# What each ProCare login role unlocks (screen/action access), mirroring the
# auth_guard gates in api/routes.py. CEO is a superset of manager, which is a
# superset of assistant.
_ASSISTANT_ACCESS = [
    {"ar": "نقطة البيع والمرتجعات", "en": "POS & returns"},
    {"ar": "المخزون والجرد (عرض)", "en": "Inventory & stocktaking (view)"},
    {"ar": "الوصفات الطبية", "en": "Prescriptions"},
    {"ar": "المهام اليومية", "en": "Daily tasks"},
    {"ar": "كشكول النواقص", "en": "Shortage sheet"},
    {"ar": "مركز الإشعارات", "en": "Notification center"},
]
_MANAGER_ACCESS = _ASSISTANT_ACCESS + [
    {"ar": "اعتماد التحويلات وأوامر الشراء", "en": "Approve transfers & purchase orders"},
    {"ar": "التقارير والتحليلات", "en": "Reports & analytics"},
    {"ar": "الخزينة وأرصدة الفروع", "en": "Treasury & branch balances"},
    {"ar": "عمولات المندوبين", "en": "Rep commissions"},
    {"ar": "التسويق والحملات", "en": "Marketing & campaigns"},
    {"ar": "المراجعة والرقابة", "en": "Audit & oversight"},
]
_CEO_ACCESS = _MANAGER_ACCESS + [
    {"ar": "الحسابات وشجرة الحسابات", "en": "Accounting & chart of accounts"},
    {"ar": "إدارة الموظفين والرواتب", "en": "Employees & salaries"},
    {"ar": "الإعدادات والنسخ الاحتياطي", "en": "Settings & backups"},
]
ROLE_ACCESS = {"assistant": _ASSISTANT_ACCESS, "manager": _MANAGER_ACCESS, "ceo": _CEO_ACCESS}
ROLE_LABELS = {
    "assistant": {"ar": "مساعد", "en": "Assistant"},
    "manager": {"ar": "مدير فرع", "en": "Manager"},
    "ceo": {"ar": "المدير العام", "en": "CEO"},
}


def my_permissions(session: Session, employee_id: int) -> dict | None:
    """The full permission picture for one employee: role + role access, the
    ON/OFF flag matrix, and numeric limits. ``None`` if the employee is gone."""
    emp = session.get(m.Employee, employee_id)
    if emp is None:
        return None

    flags = [
        {**f, "enabled": bool(getattr(emp, f["code"], False))}
        for f in PERMISSION_FLAGS
    ]
    role = emp.role or "assistant"
    return {
        "employee_id": emp.employee_id,
        "name_ar": emp.name_ar,
        "name_en": emp.name_en,
        "role": role,
        "role_label_ar": ROLE_LABELS.get(role, {}).get("ar", role),
        "role_label_en": ROLE_LABELS.get(role, {}).get("en", role),
        "is_active": bool(emp.is_active),
        "max_disc_per": float(emp.max_disc_per or 0),
        "flags": flags,
        "granted_count": sum(1 for f in flags if f["enabled"]),
        "total_flags": len(flags),
        "role_access": ROLE_ACCESS.get(role, _ASSISTANT_ACCESS),
    }
