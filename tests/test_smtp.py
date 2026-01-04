import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()  # Carrega .env

# Configs do .env
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL')
SMTP_TO_EMAIL = 'eduardo.junnior@gmail.com'  # Troque pelo destinatário
SUBJECT = 'Teste SMTP Zoho OK!'
BODY = 'E-mail enviado com sucesso via Zoho SMTP! Data: 2026.'


def send_test_email():
    msg = MIMEMultipart()
    msg['From'] = SMTP_FROM_EMAIL
    msg['To'] = SMTP_TO_EMAIL
    msg['Subject'] = SUBJECT
    msg.attach(MIMEText(BODY, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()  # Para porta 587 (TLS)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print('✅ E-mail enviado com sucesso!')
    except Exception as e:
        print(f'❌ Erro: {e}')

if __name__ == '__main__':
    send_test_email()
