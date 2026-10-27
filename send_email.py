import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import os

def send_email(receiver_emails, subject, body_text, attachment_path=None):
    sender_email = "info@airwatergreen.com"
    logo_filename = "awg_logo.jpg"

    msg = MIMEMultipart('related')
    msg["From"] = sender_email
    msg["Subject"] = subject

    # --- HTML BODY ---
    html_body = f"""
    <html>
      <body>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
          <tr>
            <td style="vertical-align: top; padding-right: 20px;">
              <pre style="font-family: sans-serif; font-size: 14px; margin: 0;">{body_text}</pre>
            </td>
            <td style="vertical-align: top;">
              <img src="cid:logo" alt="Company Logo" width="150">
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    try:
        with open(logo_filename, "rb") as logo_file:
            msg_image = MIMEImage(logo_file.read())
            msg_image.add_header('Content-ID', '<logo>')
            msg.attach(msg_image)
    except FileNotFoundError:
        print(f"Warning: Logo file '{logo_filename}' not found. Sending email without logo.")

    if attachment_path:
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment_path)}")
        msg.attach(part)

    ses_client = boto3.client("ses", region_name="eu-north-1")
    for receiver_email in receiver_emails:
        msg["To"] = receiver_email
        response = ses_client.send_raw_email(
            Source=sender_email,
            Destinations=[receiver_email],
            RawMessage={"Data": msg.as_string()}
        )
        print(f"Email with subject '{subject}' sent to {receiver_email}! Message ID: {response['MessageId']}")