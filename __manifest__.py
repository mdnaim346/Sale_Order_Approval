{
    "name": "Sale Approval Workflow",
    "version": "17.0.1.0",
    "summary": "Multi level approval for Sale Orders",
    "depends": ["sale_management", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/approval_menu.xml",
        "views/sale_order_reject_wizard.xml",
        "views/sale_order.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
