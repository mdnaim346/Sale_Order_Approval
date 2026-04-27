{
    "name": "Sale Approval Workflow",
    "version": "1.0",
    "summary": "Multi level approval for Sale Orders",
    "depends": ["sale_management"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/sale_order.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
