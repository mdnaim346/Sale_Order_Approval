from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleOrderApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_order_approval.threshold", "1000"
        )

        cls.sales_group = cls.env.ref("sales_team.group_sale_salesman")
        cls.manager_group = cls.env.ref(
            "Sale_Order_Approval.group_sale_order_manager"
        )
        cls.director_group = cls.env.ref(
            "Sale_Order_Approval.group_sale_order_director"
        )

        cls.salesperson = cls._create_user(
            "approval_salesperson",
            [cls.sales_group],
        )
        cls.manager = cls._create_user(
            "approval_manager",
            [cls.manager_group],
        )
        cls.director = cls._create_user(
            "approval_director",
            [cls.director_group],
        )

        cls.partner = cls.env["res.partner"].create({
            "name": "Approval Test Customer",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Approval Test Service",
            "type": "service",
            "list_price": 2000,
        })

    @classmethod
    def _create_user(cls, login, groups):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": login.replace("_", " ").title(),
            "login": f"{login}@example.com",
            "email": f"{login}@example.com",
            "groups_id": [(6, 0, [group.id for group in groups])],
        })

    def _create_order(self, price_unit=2000):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "user_id": self.salesperson.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": price_unit,
            })],
        })

    def test_high_value_order_requires_two_step_approval(self):
        order = self._create_order()

        self.assertTrue(order.approval_required)
        with self.assertRaises(UserError):
            order.action_confirm()

        order.with_user(self.salesperson).action_submit_approval()
        self.assertEqual(order.approval_state, "manager")

        order.with_user(self.manager).action_manager_approve()
        self.assertEqual(order.approval_state, "director")
        self.assertEqual(order.manager_id, self.manager)
        self.assertTrue(order.manager_approval_date)

        order.with_user(self.director).action_director_approve()
        self.assertEqual(order.approval_state, "approved")
        self.assertEqual(order.director_id, self.director)
        self.assertTrue(order.director_approval_date)

        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_reject_reason_and_reset_to_draft(self):
        order = self._create_order()
        order.with_user(self.salesperson).action_submit_approval()

        wizard_action = order.with_user(self.manager).action_open_reject_wizard()
        self.assertEqual(wizard_action["res_model"], "sale.order.reject.wizard")

        wizard = self.env["sale.order.reject.wizard"].with_user(self.manager).create({
            "order_id": order.id,
            "reason": "Budget <not> approved",
        })
        wizard.action_confirm_rejection()

        self.assertEqual(order.approval_state, "rejected")
        self.assertEqual(order.rejected_by_id, self.manager)
        self.assertTrue(order.rejection_date)
        self.assertEqual(order.rejection_reason, "Budget <not> approved")

        with self.assertRaises(UserError):
            order.action_confirm()

        order.action_reset_to_draft()
        self.assertEqual(order.approval_state, "draft")
        self.assertFalse(order.manager_id)
        self.assertFalse(order.director_id)
        self.assertFalse(order.rejected_by_id)
        self.assertFalse(order.rejection_reason)

    def test_salesperson_cannot_approve_or_reject(self):
        order = self._create_order()
        order.with_user(self.salesperson).action_submit_approval()

        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_manager_approve()

        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_open_reject_wizard()

    def test_below_threshold_order_can_confirm_without_approval(self):
        order = self._create_order(price_unit=500)

        self.assertFalse(order.approval_required)
        order.with_user(self.salesperson).action_submit_approval()
        self.assertEqual(order.approval_state, "approved")

        order.action_confirm()
        self.assertEqual(order.state, "sale")
