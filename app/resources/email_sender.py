import base64
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, ContentId
from app.resources.constants import SENDGRID_EMAIL


class EmailSender:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.client = SendGridAPIClient(self.api_key)
        self.client = SendGridAPIClient(api_key=self.api_key)

    def load_template(self, template_name: str) -> str:
        template_path = f'templates/{template_name}.html'
        with open(template_path, 'r', encoding='utf-8') as file:
            return file.read()

    def replace_placeholders(self, html_content: str, placeholders: dict) -> str:
        for key, value in placeholders.items():
            html_content = html_content.replace('{{'+key+'}}', value)
        return html_content

    def attach_image(self, message: Mail, name: str):
        with open(f'templates/{name}', 'rb') as f:
            data = f.read()
            encoded_image = base64.b64encode(data).decode()
            attachment = Attachment(
                FileContent(encoded_image),
                FileName(name),
                FileType('image/png'),
                Disposition('inline'),
                ContentId(name)
            )
            message.add_attachment(attachment)

    def create_message(self, to_emails: list, subject: str, html_content: str) -> None:
        return Mail(
            from_email=SENDGRID_EMAIL,
            to_emails=to_emails,
            subject=subject,
            html_content=html_content
        )

    def send_message(self, message: Mail) -> None:
        try:
            response = self.client.send(message)
            print(f'Status Code: {response.status_code}')
            print(f'Response Body: {response.body}')
            print(f'Response Headers: {response.headers}')
        except Exception as e:
            print(f'Error: {str(e)}')
