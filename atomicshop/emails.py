# v1.0.0 - 26.03.2023 23:10
import smtplib
import ssl
from email.message import EmailMessage


class SendGmail:
    """
    SendGmail class is responsible for sending emails from gmail account.
    """
    
    def __init__(self, sender_email, sender_api_key):
        # The mail account address and password
        self.sender_email: str = sender_email
        self.sender_api_key: str = sender_api_key

        self.port: int = 465  # For SSL
        self.smtp_server: str = "smtp.gmail.com"

    def send(self, receiver_address: str, email_content: str, subject: str) -> None:
        """
        Function will send an email.

        :param receiver_address: Email address of the receiver.
        :param email_content: The content that will be sent inside the email message.
        :param subject: The subject of the email message.
        :return:
        """

        msg = EmailMessage()
        msg.set_content(email_content)
        msg['Subject'] = subject
        msg['From'] = self.sender_email
        msg['To'] = receiver_address

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context) as server:
            server.login(self.sender_email, self.sender_api_key)
            server.send_message(msg, from_addr=self.sender_email, to_addrs=receiver_address)

        print('Email Sent')
