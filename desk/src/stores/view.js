import { createResource } from 'frappe-ui';
import { ref } from 'vue';

export const config_name = ref('');

export const config_settings = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.get_config',
    makeParams() {
        return {
            config_name: config_name.value,
        }
    }
});

export const default_config = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.get_default_config',
    makeParams() {
        return {
            doctype: config_name.value,
        }
    }
})