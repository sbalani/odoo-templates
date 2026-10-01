from lxml import html

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSelfBillingReport(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.self_billing_journal = cls.env['account.journal'].create({
            'name': 'Autofacturas - Revenue Share',
            'code': 'AFRS',
            'type': 'purchase',
            'company_id': cls.env.company.id,
        })

    def _render(self, invoice):
        content, _ = self.env['ir.actions.report'].with_context(lang='en_US')._render_qweb_html(
            'account.account_invoices', invoice.ids,
        )
        return html.fromstring(content)

    def test_self_billing_title_number_and_unchanged_amount_sections(self):
        bill = self.init_invoice(
            'in_invoice', journal=self.self_billing_journal,
            products=self.product_a, taxes=self.tax_purchase_a,
        )
        bill.name = 'AFRS/2019/00001'
        amounts_before = (bill.amount_untaxed, bill.amount_tax, bill.amount_total)
        customized = self._render(bill)
        text = customized.text_content()
        self.assertIn('FACTURA', text)
        self.assertNotIn('Vendor Bill', text)
        self.assertIn(bill.name, text)
        self.assertEqual(len(customized.xpath("//p[@name='afrs_self_billing_notice']")), 1)
        self.assertIn('Facturación por el destinatario', text)

        # Render the very same bill with the inherited view disabled. Compare
        # the full line/tax/total subtrees, not only numeric amounts.
        self.env.ref('afrs_self_billing_report.report_invoice_document').active = False
        original = self._render(bill)
        self.assertIn('Vendor Bill', original.text_content())
        for xpath in ("//table[@name='invoice_line_table']", "//div[@id='total']"):
            with self.subTest(section=xpath):
                self.assertEqual(len(original.xpath(xpath)), 1)
                self.assertEqual(
                    html.tostring(customized.xpath(xpath)[0]),
                    html.tostring(original.xpath(xpath)[0]),
                )
        self.assertEqual(bill.name, 'AFRS/2019/00001')
        self.assertEqual(amounts_before, (bill.amount_untaxed, bill.amount_tax, bill.amount_total))

    def test_other_documents_retain_original_report(self):
        for move_type, journal, heading in (
            ('in_invoice', self.company_data['default_journal_purchase'], 'Vendor Bill'),
            ('out_invoice', self.company_data['default_journal_sale'], 'Draft Invoice'),
            ('in_refund', self.self_billing_journal, 'Vendor Credit Note'),
        ):
            with self.subTest(move_type=move_type):
                invoice = self.init_invoice(move_type, journal=journal, products=self.product_a)
                rendered = self._render(invoice)
                self.assertIn(heading, rendered.text_content())
                self.assertNotIn('FACTURA', rendered.text_content())
                self.assertFalse(rendered.xpath("//p[@name='afrs_self_billing_notice']"))

    def test_similar_journal_name_is_not_matched(self):
        self.self_billing_journal.name = 'Autofacturas - Revenue Share Other'
        bill = self.init_invoice('in_invoice', journal=self.self_billing_journal, products=self.product_a)
        rendered = self._render(bill)
        self.assertIn('Vendor Bill', rendered.text_content())
        self.assertFalse(rendered.xpath("//p[@name='afrs_self_billing_notice']"))
