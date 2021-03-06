##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from datetime import datetime
import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountPaymentReceiptbook(models.Model):

    _name = 'account.payment.receiptbook'
    _description = 'Account payment Receiptbook'
    # analogo a account.journal.document.type pero para pagos
    _order = 'sequence asc'

    report_partner_id = fields.Many2one(
        'res.partner',
    )
    mail_template_id = fields.Many2one(
        'mail.template',
        'Email Template',
        domain=[('model', '=', 'account.payment.group')],
        help="If set an email will be sent to the customer when the related"
        " account.payment.group has been posted.",
    )
    sequence = fields.Integer(
        'Sequence',
        help="Used to order the receiptbooks",
        default=10,
    )
    name = fields.Char(
        'Name',
        size=64,
        required=True,
        index=True,
    )
    partner_type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Vendor')],
        required=True,
        index=True,
    )
    next_number = fields.Integer(
        related='sequence_id.number_next_actual',
        readonly=False,
    )

    # payment_type = fields.Selection(
    #     [('inbound', 'Inbound'), ('outbound', 'Outbound')],
    #     # [('receipt', 'Receipt'), ('payment', 'Payment')],
    #     string='Type',
    #     required=True,
    # )
    # lo dejamos solo como ayuda para generar o no la secuencia pero lo que
    # termina definiendo si es manual o por secuencia es si tiene secuencia
    sequence_type = fields.Selection(
        [('automatic', 'Automatic'), ('manual', 'Manual')],
        string='Sequence Type',
        readonly=False,
        default='automatic',
    )
    sequence_id = fields.Many2one(
        'ir.sequence',
        'Entry Sequence',
        help="This field contains the information related to the numbering "
        "of the receipt entries of this receiptbook.",
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        default=lambda self: self.env[
            'res.company']._company_default_get('account.payment.receiptbook')
    )
    prefix = fields.Char(
        'Prefix',
        # required=True,
        # TODO rename field to prefix
    )
    padding = fields.Integer(
        'Number Padding',
        help="automatically adds some '0' on the left of the 'Number' to get "
        "the required padding size."
    )
    active = fields.Boolean(
        'Active',
        default=True,
    )
    document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        'Document Type',
        required=True,
    )

    def write(self, vals):
        """
        If user change prefix we change prefix of sequence.
        TODO: we can use related field but we need to implement manual
        receipbooks with sequences. We should also make padding
        related to sequence
        """
        prefix = vals.get('prefix')
        for rec in self:
            if prefix and rec.sequence_id:
                rec.sequence_id.prefix = prefix
        return super(AccountPaymentReceiptbook, self).write(vals)

    @api.model
    def create(self, vals):
        sequence_type = vals.get(
            'sequence_type',
            self._context.get('default_sequence_type', False))
        prefix = vals.get(
            'prefix',
            self._context.get('default_prefix', False))
        company_id = vals.get(
            'company_id',
            self._context.get('default_company_id', False))

        if (
                sequence_type == 'automatic' and
                not vals.get('sequence_id', False) and
                company_id):
            seq_vals = {
                'name': vals['name'],
                'implementation': 'no_gap',
                'prefix': prefix,
                'padding': 8,
                'number_increment': 1
            }
            sequence = self.env['ir.sequence'].sudo().create(seq_vals)
            vals.update({
                'sequence_id': sequence.id
            })
        return super(AccountPaymentReceiptbook, self).create(vals)

    def _get_manual_prefix(self, date=None):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            now = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            if date:
                effective_date = fields.Datetime.from_string(date)

            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, format in sequences.items():
                res[key] = effective_date.strftime(format)
                res['current_' + key] = now.strftime(format)

            return res

        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
        except ValueError:
            raise UserError(_('Invalid prefix for sequence \'%s\'') % (self.get('name')))
        return interpolated_prefix
