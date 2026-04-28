from odoo import fields, models
from odoo.exceptions import UserError


class SaleOrderRejectWizard(models.TransientModel):
    _name = "sale.order.reject.wizard"
    _description = "Sale Order Rejection Wizard"

    order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Rejection Reason",
        required=True,
    )

    def action_confirm_rejection(self):
        self.ensure_one()
        if not self.order_id:
            raise UserError("No sale order selected for rejection.")
        self.order_id._action_reject_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}
