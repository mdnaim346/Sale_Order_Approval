from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sale_approval_threshold = fields.Float(
        string="Approval Threshold Amount",
        default=5000.0,
        config_parameter="sale_order_approval.threshold",
        help="Sale orders above this amount require Manager and Director approval.",
    )
