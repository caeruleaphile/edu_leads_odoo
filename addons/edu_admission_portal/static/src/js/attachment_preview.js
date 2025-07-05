/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

class AttachmentPreviewWidget extends Component {
    setup() {
        this.state = useState({
            previewData: null,
            error: null
        });
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        
        onWillStart(async () => {
            await this._loadPreviewData();
        });
    }

    async _loadPreviewData() {
        try {
            const result = await this.rpc(
                `/admission/attachment/preview/modal/${this.props.attachmentId}`,
                {}
            );
            if (result.error) {
                this.notification.add(_t(result.error), {
                    type: "danger",
                });
                this.state.error = result.error;
            } else {
                this.state.previewData = result;
            }
        } catch (error) {
            this.notification.add(_t("Failed to load preview"), {
                type: "danger",
            });
            this.state.error = error;
        }
    }

    _onDownloadClick() {
        window.location = `/web/content/${this.props.attachmentId}?download=true`;
    }

    _onPrintClick() {
        window.print();
    }
}

AttachmentPreviewWidget.template = "edu_admission_portal.AttachmentPreview";
AttachmentPreviewWidget.props = {
    attachmentId: { type: Number, required: true },
    attachment: { type: Object, required: true },
};

class AttachmentPreviewDialog extends Dialog {
    setup() {
        super.setup();
        this.title = _t("Document Preview");
    }
}

AttachmentPreviewDialog.components = { AttachmentPreviewWidget };
AttachmentPreviewDialog.template = "edu_admission_portal.AttachmentPreviewDialog";

// Register the preview action for form and list views
registry.category("view_widgets").add("attachment_preview", {
    component: AttachmentPreviewWidget,
    supportedTypes: ["binary"],
});

export {
    AttachmentPreviewWidget,
    AttachmentPreviewDialog,
}; 