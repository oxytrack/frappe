# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
<<<<<<< HEAD
from frappe.email.queue import send_one
from frappe.utils import now_datetime
=======
from frappe.email.queue import get_unsubcribed_url, get_unsubscribe_message
from frappe.email.email_body import add_attachment, get_formatted_html, get_email
from frappe.utils import cint, split_emails, add_days, nowdate, cstr, get_hook_method
from frappe.email.doctype.email_account.email_account import EmailAccount
>>>>>>> 1ec54c87c8 (feat: patched frappe email to work with frappecloud mail app (#15248))


class EmailQueue(Document):
	def set_recipients(self, recipients):
		self.set("recipients", [])
		for r in recipients:
			self.append("recipients", {"recipient":r, "status":"Not Sent"})

	def on_trash(self):
		self.prevent_email_queue_delete()

	def prevent_email_queue_delete(self):
		if frappe.session.user != 'Administrator':
			frappe.throw(_('Only Administrator can delete Email Queue'))

	def get_duplicate(self, recipients):
		values = self.as_dict()
		del values['name']
		duplicate = frappe.get_doc(values)
		duplicate.set_recipients(recipients)
		return duplicate

<<<<<<< HEAD
=======
	@classmethod
	def new(cls, doc_data, ignore_permissions=False):
		data = doc_data.copy()
		if not data.get('recipients'):
			return

		recipients = data.pop('recipients')
		doc = frappe.new_doc(cls.DOCTYPE)
		doc.update(data)
		doc.set_recipients(recipients)
		doc.insert(ignore_permissions=ignore_permissions)
		return doc

	@classmethod
	def find(cls, name):
		return frappe.get_doc(cls.DOCTYPE, name)

	@classmethod
	def find_one_by_filters(cls, **kwargs):
		name = frappe.db.get_value(cls.DOCTYPE, kwargs)
		return cls.find(name) if name else None

	def update_db(self, commit=False, **kwargs):
		frappe.db.set_value(self.DOCTYPE, self.name, kwargs)
		if commit:
			frappe.db.commit()

	def update_status(self, status, commit=False, **kwargs):
		self.update_db(status = status, commit = commit, **kwargs)
		if self.communication:
			communication_doc = frappe.get_doc('Communication', self.communication)
			communication_doc.set_delivery_status(commit=commit)

	@property
	def cc(self):
		return (self.show_as_cc and self.show_as_cc.split(",")) or []

	@property
	def to(self):
		return [r.recipient for r in self.recipients if r.recipient not in self.cc]

	@property
	def attachments_list(self):
		return json.loads(self.attachments) if self.attachments else []

	def get_email_account(self):
		if self.email_account:
			return frappe.get_doc('Email Account', self.email_account)

		return EmailAccount.find_outgoing(
			match_by_email = self.sender, match_by_doctype = self.reference_doctype)

	def is_to_be_sent(self):
		return self.status in ['Not Sent','Partially Sent']

	def can_send_now(self):
		hold_queue = (cint(frappe.defaults.get_defaults().get("hold_queue"))==1)
		if frappe.are_emails_muted() or not self.is_to_be_sent() or hold_queue:
			return False

		return True

	def send(self, is_background_task=False):
		""" Send emails to recipients.
		"""
		if not self.can_send_now():
			frappe.db.rollback()
			return

		with SendMailContext(self, is_background_task) as ctx:
			message = None
			for recipient in self.recipients:
				if not recipient.is_mail_to_be_sent():
					continue

				message = ctx.build_message(recipient.recipient)
				method = get_hook_method('override_email_send')
				if method:
					method(self, self.sender, recipient.recipient, message)
				else:
					if not frappe.flags.in_test:
						ctx.smtp_session.sendmail(from_addr=self.sender, to_addrs=recipient.recipient, msg=message)
					ctx.add_to_sent_list(recipient)

			if frappe.flags.in_test:
				frappe.flags.sent_mail = message
				return

			if ctx.email_account_doc.append_emails_to_sent_folder and ctx.sent_to:
				ctx.email_account_doc.append_email_to_sent_folder(message)


@task(queue = 'short')
def send_mail(email_queue_name, is_background_task=False):
	"""This is equalent to EmqilQueue.send.

	This provides a way to make sending mail as a background job.
	"""
	record = EmailQueue.find(email_queue_name)
	record.send(is_background_task=is_background_task)

class SendMailContext:
	def __init__(self, queue_doc: Document, is_background_task: bool = False):
		self.queue_doc = queue_doc
		self.is_background_task = is_background_task
		self.email_account_doc = queue_doc.get_email_account()
		self.smtp_server = self.email_account_doc.get_smtp_server()
		self.sent_to = [rec.recipient for rec in self.queue_doc.recipients if rec.is_main_sent()]

	def __enter__(self):
		self.queue_doc.update_status(status='Sending', commit=True)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		exceptions = [
			smtplib.SMTPServerDisconnected,
			smtplib.SMTPAuthenticationError,
			smtplib.SMTPRecipientsRefused,
			smtplib.SMTPConnectError,
			smtplib.SMTPHeloError,
			JobTimeoutException
		]

		self.smtp_server.quit()
		self.log_exception(exc_type, exc_val, exc_tb)

		if exc_type in exceptions:
			email_status = (self.sent_to and 'Partially Sent') or 'Not Sent'
			self.queue_doc.update_status(status = email_status, commit = True)
		elif exc_type:
			if self.queue_doc.retry < MAX_RETRY_COUNT:
				update_fields = {'status': 'Not Sent', 'retry': self.queue_doc.retry + 1}
			else:
				update_fields = {'status': (self.sent_to and 'Partially Errored') or 'Error'}
			self.queue_doc.update_status(**update_fields, commit = True)
		else:
			email_status = self.is_mail_sent_to_all() and 'Sent'
			email_status = email_status or (self.sent_to and 'Partially Sent') or 'Not Sent'

			update_fields = {'status': email_status}
			if self.email_account_doc.is_exists_in_db():
				update_fields['email_account'] = self.email_account_doc.name
			else:
				update_fields['email_account'] = None

			self.queue_doc.update_status(**update_fields, commit = True)

	def log_exception(self, exc_type, exc_val, exc_tb):
		if exc_type:
			traceback_string = "".join(traceback.format_tb(exc_tb))
			traceback_string += f"\n Queue Name: {self.queue_doc.name}"

			if self.is_background_task:
				frappe.log_error(title = 'frappe.email.queue.flush', message = traceback_string)
			else:
				frappe.log_error(message = traceback_string)

	@property
	def smtp_session(self):
		if frappe.flags.in_test:
			return
		return self.smtp_server.session

	def add_to_sent_list(self, recipient):
		# Update recipient status
		recipient.update_db(status='Sent', commit=True)
		self.sent_to.append(recipient.recipient)

	def is_mail_sent_to_all(self):
		return sorted(self.sent_to) == sorted([rec.recipient for rec in self.queue_doc.recipients])

	def get_message_object(self, message):
		return Parser(policy=SMTPUTF8).parsestr(message)

	def message_placeholder(self, placeholder_key):
		map = {
			'tracker': '<!--email open check-->',
			'unsubscribe_url': '<!--unsubscribe url-->',
			'cc': '<!--cc message-->',
			'recipient': '<!--recipient-->',
		}
		return map.get(placeholder_key)

	def build_message(self, recipient_email):
		"""Build message specific to the recipient.
		"""
		message = self.queue_doc.message
		if not message:
			return ""

		message = message.replace(self.message_placeholder('tracker'), self.get_tracker_str())
		message = message.replace(self.message_placeholder('unsubscribe_url'),
			self.get_unsubscribe_str(recipient_email))
		message = message.replace(self.message_placeholder('cc'), self.get_receivers_str())
		message = message.replace(self.message_placeholder('recipient'),
			self.get_receipient_str(recipient_email))
		message = self.include_attachments(message)
		return message

	def get_tracker_str(self):
		tracker_url_html = \
			'<img src="https://{}/api/method/frappe.core.doctype.communication.email.mark_email_as_seen?name={}"/>'

		message = ''
		if frappe.conf.use_ssl and self.email_account_doc.track_email_status:
			message = quopri.encodestring(
				tracker_url_html.format(frappe.local.site, self.queue_doc.communication).encode()
			).decode()
		return message

	def get_unsubscribe_str(self, recipient_email):
		unsubscribe_url = ''
		if self.queue_doc.add_unsubscribe_link and self.queue_doc.reference_doctype:
			doctype, doc_name = self.queue_doc.reference_doctype, self.queue_doc.reference_name
			unsubscribe_url = get_unsubcribed_url(doctype, doc_name, recipient_email,
				self.queue_doc.unsubscribe_method, self.queue_doc.unsubscribe_param)

		return quopri.encodestring(unsubscribe_url.encode()).decode()

	def get_receivers_str(self):
		message = ''
		if self.queue_doc.expose_recipients == "footer":
			to_str = ', '.join(self.queue_doc.to)
			cc_str = ', '.join(self.queue_doc.cc)
			message = f"This email was sent to {to_str}"
			message = message + f" and copied to {cc_str}" if cc_str else message
		return message

	def get_receipient_str(self, recipient_email):
		message = ''
		if self.queue_doc.expose_recipients != "header":
			message = recipient_email
		return message

	def include_attachments(self, message):
		message_obj = self.get_message_object(message)
		attachments = self.queue_doc.attachments_list

		for attachment in attachments:
			if attachment.get('fcontent'):
				continue

			file_filters = {}
			if attachment.get('fid'):
				file_filters['name'] = attachment.get('fid')
			elif attachment.get('file_url'):
				file_filters['file_url'] = attachment.get('file_url')

			if file_filters:
				_file = frappe.get_doc("File", file_filters)
				fcontent = _file.get_content()
				attachment.update({
					'fname': _file.file_name,
					'fcontent': fcontent,
					'parent': message_obj
				})
				attachment.pop("fid", None)
				attachment.pop("file_url", None)
				add_attachment(**attachment)

			elif attachment.get("print_format_attachment") == 1:
				attachment.pop("print_format_attachment", None)
				print_format_file = frappe.attach_print(**attachment)
				print_format_file.update({"parent": message_obj})
				add_attachment(**print_format_file)

		return safe_encode(message_obj.as_string())

>>>>>>> 1ec54c87c8 (feat: patched frappe email to work with frappecloud mail app (#15248))
@frappe.whitelist()
def retry_sending(name):
	doc = frappe.get_doc("Email Queue", name)
	if doc and (doc.status == "Error" or doc.status == "Partially Errored"):
		doc.status = "Not Sent"
		for d in doc.recipients:
			if d.status != 'Sent':
				d.status = 'Not Sent'
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def send_now(name):
	send_one(name, now=True)

def on_doctype_update():
	"""Add index in `tabCommunication` for `(reference_doctype, reference_name)`"""
	frappe.db.add_index('Email Queue', ('status', 'send_after', 'priority', 'creation'), 'index_bulk_flush')
