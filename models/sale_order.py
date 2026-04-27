from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    approval_state = fields.Selection([
        ("draft", "Draft"),
        ("manager", "Manager Approval"),
        ("director", "Director Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="draft", tracking=True, string="Approval Status")

    manager_id = fields.Many2one("res.users", string="Approved by Manager")
    director_id = fields.Many2one("res.users", string="Approved by Director")

    approval_required = fields.Boolean(
        compute="_compute_approval_required",
        store=False,
    )

    @api.depends("amount_total")
    def _compute_approval_required(self):
        for rec in self:
            rec.approval_required = rec.amount_total > 5000

    def action_submit_approval(self):
        for rec in self:
            if rec.approval_required:
                rec.approval_state = "manager"
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
        for rec in self:
            if rec.approval_state == "manager":
                rec.approval_state = "director"
                rec.manager_id = self.env.user

    def action_director_approve(self):
        for rec in self:
            if rec.approval_state == "director":
                rec.approval_state = "approved"
                rec.director_id = self.env.user

    def action_reject(self):
        for rec in self:
            if rec.approval_state == "manager":
                rec.manager_id = self.env.user
            elif rec.approval_state == "director":
                rec.director_id = self.env.user
            rec.approval_state = "rejected"
