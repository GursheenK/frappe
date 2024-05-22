# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.core.doctype.doctype.doctype import get_fields_not_allowed_in_list_view
import json

class ViewConfig(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		columns: DF.JSON | None
		document_type: DF.Link | None
		label: DF.Data | None
	# end: auto-generated types

	pass

def get_default_config(doctype):
	meta = frappe.get_meta(doctype)
	columns = []
	for field in meta.fields:
		if field.in_list_view:
			columns.append({"label": field.label, "key": field.fieldname, "type": field.fieldtype, "width": "10rem"})
	return {
		"label": "List",
		"columns": columns,
		"doctype_fields": get_doctype_fields(doctype)
	}

@frappe.whitelist()
def get_config(config_name=None, is_default=True):
	if is_default:
		return get_default_config(config_name)
	config = frappe.get_doc("View Config", config_name)
	config_dict = config.as_dict()
	config_dict.update({
		"columns": frappe.parse_json(config.columns),
		"doctype_fields": get_doctype_fields(config.document_type),
	})
	return config_dict

def get_doctype_fields(doctype):
	meta = frappe.get_meta(doctype)
	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)
	doctype_fields = []
	for field in meta.fields:
		if field.fieldtype in not_allowed_in_list_view:
			continue
		doctype_fields.append({"label": field.label, "value": field.fieldname, "type": field.fieldtype})
	for field in frappe.model.default_fields:
		doctype_fields.append({"label": meta.get_label(field), "value": field, "type": "Data"})
	return doctype_fields

@frappe.whitelist()
def update_config(config_name, new_config):
	new_config = frappe._dict(new_config)
	config = frappe.get_doc("View Config", config_name)
	config.columns = json.dumps(frappe.parse_json(new_config.columns))
	config.save()


@frappe.whitelist()
def get_views_for_doctype(doctype):
	return frappe.get_all("View Config", filters={"document_type": doctype}, fields=["name", "label", "icon"])