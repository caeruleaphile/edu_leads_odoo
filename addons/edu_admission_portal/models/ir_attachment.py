from odoo import models, api, _
from odoo.exceptions import UserError

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def action_preview_attachment(self):
        """Open the attachment in a preview window."""
        self.ensure_one()
        
        if not self.url and not self.datas:
            raise UserError(_("Aucun contenu à prévisualiser."))
            
        # For files stored in database or local filesystem
        if self.datas:
            action = {
                'type': 'ir.actions.act_url',
                'name': 'Preview',
                'target': 'new',
                'url': f'/web/content/{self.id}?download=false'
            }
            return action
            
        # For external URLs
        if self.url:
            action = {
                'type': 'ir.actions.act_url',
                'name': 'Preview',
                'target': 'new',
                'url': self.url
            }
            return action
            
        return {'type': 'ir.actions.act_window_close'} 