from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape


class SaleOrder(models.Model):
    _inherit = "sale.order"

    approval_state = fields.Selection([
        ("draft", "Draft"),
        ("manager", "Awaiting Manager"),
        ("director", "Awaiting Director"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="draft", tracking=True, string="Approval Status", copy=False)

    manager_id = fields.Many2one(
        "res.users", string="Approved by Manager", readonly=True, copy=False)
    director_id = fields.Many2one(
        "res.users", string="Approved by Director", readonly=True, copy=False)
    manager_approval_date = fields.Datetime(
        string="Manager Approval Date", readonly=True, copy=False)
    director_approval_date = fields.Datetime(
        string="Director Approval Date", readonly=True, copy=False)
    rejected_by_id = fields.Many2one(
        "res.users", string="Rejected By", readonly=True, copy=False)
    rejection_date = fields.Datetime(
        string="Rejection Date", readonly=True, copy=False)
    rejection_reason = fields.Text(
        string="Rejection Reason", readonly=True, copy=False)

    approval_required = fields.Boolean(
        compute="_compute_approval_required",
        search="_search_approval_required",
    )

    def _get_threshold(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "sale_order_approval.threshold",
            default="5000.0",
        )
        try:
            return float(value)
        except (TypeError, ValueError):
            return 5000.0

    @api.depends("amount_total")
    def _compute_approval_required(self):
        threshold = self._get_threshold()
        for rec in self:
            rec.approval_required = rec.amount_total > threshold

    def _search_approval_required(self, operator, value):
        threshold = self._get_threshold()
        if operator not in ("=", "!=", "==", "<>"):
            raise UserError("Unsupported search operator for approval required.")

        approval_required = bool(value)
        if operator in ("!=", "<>"):
            approval_required = not approval_required

        if approval_required:
            return [("amount_total", ">", threshold)]
        return [("amount_total", "<=", threshold)]

    def _ensure_group(self, group_xmlid, error_message):
        if not self.env.user.has_group(group_xmlid):
            raise UserError(error_message)

    def action_submit_approval(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft quotations can be submitted for approval.")
            if rec.approval_required:
                rec.approval_state = "manager"
                rec.message_post(
                    body=f"Approval requested by {self.env.user.name}.",
                    subtype_xmlid="mail.mt_note",
                )
                rec._notify_approvers("manager")
            else:
                rec.approval_state = "approved"

    def action_confirm(self):
        for rec in self:
            if rec.approval_required and rec.approval_state != "approved":
                raise UserError(
                    "This order requires approval before it can be confirmed.\n"
                    "Please submit it for approval first."
                )
        return super().action_confirm()

    def action_manager_approve(self):
        self._ensure_group(
            "Sale_Order_Approval.group_sale_order_manager",
            "Only Sale Approval Managers can approve this step.",
        )
        for rec in self:
            if rec.approval_state != "manager":
                raise UserError("This order is not waiting for Manager approval.")
            rec.approval_state = "director"
            rec.manager_id = self.env.user
            rec.manager_approval_date = fields.Datetime.now()
            rec.message_post(
                body=f"Manager approved by {self.env.user.name}. Awaiting Director approval.",
                subtype_xmlid="mail.mt_note",
            )
            rec._notify_approvers("director")

    def action_director_approve(self):
        self._ensure_group(
            "Sale_Order_Approval.group_sale_order_director",
            "Only Sale Approval Directors can approve this step.",
        )
        for rec in self:
            if rec.approval_state != "director":
                raise UserError("This order is not waiting for Director approval.")
            rec.approval_state = "approved"
            rec.director_id = self.env.user
            rec.director_approval_date = fields.Datetime.now()
            rec.message_post(
                body=f"Director approved by {self.env.user.name}. Order is ready for confirmation.",
                subtype_xmlid="mail.mt_note",
            )
            rec._notify_salesperson_approved()

    def action_open_reject_wizard(self):
        self._ensure_group(
            "Sale_Order_Approval.group_sale_order_manager",
            "Only Sale Approval Managers or Directors can reject this order.",
        )
        self.ensure_one()
        if self.approval_state not in ("manager", "director"):
            raise UserError("Only orders waiting for approval can be rejected.")
        return {
            "name": "Reject Sale Order",
            "type": "ir.actions.act_window",
            "res_model": "sale.order.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
            },
        }

    def _action_reject_with_reason(self, reason):
        self._ensure_group(
            "Sale_Order_Approval.group_sale_order_manager",
            "Only Sale Approval Managers or Directors can reject this order.",
        )
        for rec in self:
            if rec.approval_state not in ("manager", "director"):
                raise UserError("Only orders waiting for approval can be rejected.")
            clean_reason = (reason or "").strip()
            if not clean_reason:
                raise UserError("Please provide a rejection reason.")
            escaped_reason = html_escape(clean_reason)
            if rec.approval_state == "manager":
                rec.manager_id = self.env.user
            elif rec.approval_state == "director":
                rec.director_id = self.env.user
            rec.approval_state = "rejected"
            rec.rejected_by_id = self.env.user
            rec.rejection_date = fields.Datetime.now()
            rec.rejection_reason = clean_reason
            rec.message_post(
                body=(
                    f"Order rejected by {self.env.user.name}.<br/>"
                    f"<b>Reason:</b> {escaped_reason}"
                ),
                subtype_xmlid="mail.mt_note",
            )
            rec._notify_salesperson_rejected()

    def action_reset_to_draft(self):
        for rec in self:
            if rec.approval_state != "rejected":
                raise UserError("Only rejected orders can be reset to draft.")
            rec.approval_state = "draft"
            rec.manager_id = False
            rec.director_id = False
            rec.manager_approval_date = False
            rec.director_approval_date = False
            rec.rejected_by_id = False
            rec.rejection_date = False
            rec.rejection_reason = False
            rec.message_post(
                body="Approval reset to draft.",
                subtype_xmlid="mail.mt_note",
            )

    def _notify_approvers(self, level):
        group_map = {
            "manager": "Sale_Order_Approval.group_sale_order_manager",
            "director": "Sale_Order_Approval.group_sale_order_director",
        }
        group = self.env.ref(group_map[level], raise_if_not_found=False)
        if not group:
            return

        users = group.users.filtered(lambda user: user.active and user.partner_id)
        for rec in self:
            if users:
                rec.message_subscribe(partner_ids=users.mapped("partner_id").ids)
            for user in users:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary="Sale Order Approval Required",
                    note=f"Please review sale order {rec.name}.",
                )

    def _notify_salesperson_approved(self):
        for rec in self:
            if rec.user_id and rec.user_id.partner_id:
                rec.message_notify(
                    partner_ids=[rec.user_id.partner_id.id],
                    subject="Sale Order Approved",
                    body=f"Sale order {rec.name} has been fully approved.",
                )

    def _notify_salesperson_rejected(self):
        for rec in self:
            if rec.user_id and rec.user_id.partner_id:
                rec.message_notify(
                    partner_ids=[rec.user_id.partner_id.id],
                    subject="Sale Order Rejected",
                    body=(
                        f"Sale order {rec.name} was rejected."
                        f"<br/><b>Reason:</b> {html_escape(rec.rejection_reason or '')}"
                    ),
                )
